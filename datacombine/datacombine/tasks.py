from celery import shared_task,current_task

import json
import logging
import time

from datacombine.data_combine import DataCombine
from datacombine import settings


def make_channel_uri(tid):
    return f'task:{tid}:progress'

@shared_task
def harvest():
    if settings.DEBUG:
        dc = DataCombine(loglvl=logging.DEBUG)
    else:
        dc = DataCombine()
    context = {
        'harvest_done': 0,
        'process_percent': 0
    }
    current_task.update_state(state='PROGRESS', meta=context)

    for i in range(10):
        time.sleep(1)
    context['harvest_done'] = 1
    current_task.update_state(state='PROGRESS', meta=context)
    #dc.harvest_lists()
    #dc.harvest_contacts()

    #for prg in dc.combine_contacts_into_db(update_web_interface=True):
    #    current_task.update_state(state='PROGRESS',
    #                             meta={'process_percent': prg})
    for i in range(100):
        time.sleep(1)
        context['process_percent'] = i
        current_task.update_state(state='PROGRESS', meta=context)
    return

@shared_task
def combine_contacts(self):
    channel = self.make_channel_uri(self.combine_task_id)
    self.pubsub.subscribe(channel)
    for prg in self.dc.combine_contacts_into_db(update_web_interface=True):
        self.redis_pub.publish(channel, json.dumps(prg))
