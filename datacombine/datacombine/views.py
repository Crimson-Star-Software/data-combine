from django.views.generic import View
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.contrib import messages

from datacombine import models
from datacombine.forms import HarvestForm
from django.views.generic.edit import FormView


class CombineView(View):
    def get(self, request):
        return render(request, 'combine.html')
    def post(self, request):
        return render(request, 'combine.html')


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
