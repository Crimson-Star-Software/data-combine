from celery.decorators import task
from celery.utils.log import get_task_logger

import redis
import json
import logging
import time

from datacombine import models
from datacombine.forms import HarvestForm
from datacombine.data_combine import DataCombine
from datacombine import settings


def make_channel_uri(tid):
    return f'task:{tid}:progress'

@task(name="harvest", bind=True)
def harvest(self):
    if settings.DEBUG:
        dc = DataCombine(loglvl=logging.DEBUG)
    else:
        dc = DataCombine()

    redis_pub = redis.StrictRedis()
    pubsub = redis_pub.pubsub()
    channel = make_channel_uri(self.request.id)
    pubsub.subscribe(channel)
    redis_pub.publish(channel, json.dumps({'harvest_done': False}))
    # self.dc.harvest_lists()
    # self.dc.harvest_contacts()
    time.sleep(10)
    redis_pub.publish(channel, json.dumps({'harvest_done': True}))

@task(name="combine")
def combine_contacts(self):
    channel = self.make_channel_uri(self.combine_task_id)
    self.pubsub.subscribe(channel)
    for prg in self.dc.combine_contacts_into_db(update_web_interface=True):
        self.redis_pub.publish(channel, json.dumps(prg))
