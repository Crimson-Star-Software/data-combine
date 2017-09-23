from django.views.generic import View, CreateView
from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect

import json
from celery.result import AsyncResult


from datacombine import models
from datacombine import forms
from datacombine import tasks

class CombineView(View):
    def get(self, request):
        # harvest_task_id = tasks.harvest.apply_async()
        # self.combine_task_id = self.combine_contacts()
        if 'job' in request.GET:
            job_id = request.GET.get('job')
            job = AsyncResult(job_id)
            data = job.result or job.state
            context = {
                'data': data,
                'task_id': job_id,
            }
            return render(request, 'combine.html', context)
        else:
            job = tasks.harvest.delay()
            return HttpResponseRedirect(
                reverse('combining') + '?job=' + job.id
            )

    def post(self, request):
        data = 'FAIL'
        if request.is_ajax():
            if 'task_id' in request.POST.keys() and request.POST['task_id']:
                task_id = request.POST['task_id']
                task = AsyncResult(task_id)
                data = task.result or task.state
            else:
                data = 'No task_id in the request'
        else:
            data = 'This is not an ajax request'
        json_data = json.dumps(data)
        return HttpResponse(json_data, content_type='application/json')


class HarvestInitializationView(CreateView):
    form_class = forms.HarvestForm
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
        # success_message = "You did it! Yeaaaah!"
        # messages.success(self.request, success_message)
        super().form_valid(form)
        return redirect('combining')


class CreateNewContactView(View):
    def get(self, request):
        addresses_form = forms.AddressForm
        email_form = forms.EmailAddressForm
        contact_form = forms.CreateContactForm

        context = {
            'addresses_form': addresses_form,
            'email_form': email_form,
            'contact_form': contact_form
        }

        return render(request, "add_new_contact.html", context)


class ManageView(View):
    def get(self, request):
        return render(request, 'manage.html')

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
