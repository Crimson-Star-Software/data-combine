from celery import shared_task,current_task

import json
import logging

from datacombine.data_combine import DataCombine
from datacombine import settings


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

    dc.harvest_lists()
    dc.harvest_contacts()

    context['harvest_done'] = 1
    current_task.update_state(state='PROGRESS', meta=context)

    for prg in dc.combine_contacts_into_db(update_web_interface=True):
        context['process_percent'] = round((prg['processed'] / prg['total']) * 100)
        current_task.update_state(state='PROGRESS', meta=context)
    return
