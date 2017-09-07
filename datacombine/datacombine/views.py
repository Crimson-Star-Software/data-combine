from django.views.generic import View
from django.shortcuts import render, redirect
from django.views.generic.edit import FormView
from django.contrib import messages
from django.http import JsonResponse

import redis
import json
import logging
import time

from datacombine import models
from datacombine.forms import HarvestForm
from datacombine.data_combine import DataCombine
from datacombine import settings
from datacombine import tasks

class CombineView(View):
    # def __init__(self):
    #     if settings.DEBUG:
    #         self.dc = DataCombine(loglvl=logging.DEBUG)
    #     else:
    #         self.dc = DataCombine()
    #     self.combine_task_id = None
    #     self.harvest_task_id = None
    #     self.redis_pub = redis.StrictRedis()
    #     self.pubsub = self.redis_pub.pubsub()
    #
    # def make_channel_uri(self, tid):
    #     return f'task:{tid}:progress'
    #
    # @task(name="harvest_initialize")
    # def harvest_initialize(self):
    #     channel = self.make_channel_uri(self.harvest_task_id)
    #     self.pubsub.subscribe(channel)
    #     self.redis_pub.publish(channel, json.dumps({'harvest_done': False}))
    #     #self.dc.harvest_lists()
    #     #self.dc.harvest_contacts()
    #     time.sleep(10)
    #     self.redis_pub.publish(channel, json.dumps({'harvest_done': True}))
    #     return
    #
    # @task(name="combine")
    # def combine_contacts(self):
    #     channel = self.make_channel_uri(self.combine_task_id)
    #     self.pubsub.subscribe(channel)
    #     for prg in self.dc.combine_contacts_into_db(update_web_interface=True):
    #         self.redis_pub.publish(channel, json.dumps(prg))

    def get(self, request):
        harvest_task_id = tasks.harvest.apply_async()
        # self.combine_task_id = self.combine_contacts()
        return render(request, 'combine.html', {'htid': harvest_task_id})

    def post(self, request):
        return render(request, 'combine.html')


class CheckTaskProgressAJAX(View):
    def get(self, request, tid):
        return JsonResponse(self.pubsub.get_message().get('data'))


class HarvestInitializationView(FormView):
    form_class = HarvestForm
    success_url = "/dash/"
    template_name = "harvest.html"

    def _get_secrets(self):
        try:
            from datacombine.secret_settings import (
                AUTH_KEY, API_KEY, POSTGRES_PASSWORD
            )
        except ImportError:
            AUTH_KEY, API_KEY, POSTGRES_PASSWORD = (None, None, None)
        return dict(
            api_key=API_KEY,
            auth_key=AUTH_KEY,
            postgres_password=POSTGRES_PASSWORD
        )

    def get_initial(self):
        self.initial = self._get_secrets()
        return self.initial.copy()

    def form_valid(self, form):
        success_message = "You did it! Yeaaaah!"
        messages.success(self.request, success_message)
        super().form_valid(form)
        return redirect('combining')


class DashView(View):
    def get(self, request):
        if models.Contact.objects.count() == 0:
            return redirect('/harvest/')
        else:
            return render(
                request,
                'dash.html',
                {}
            )
