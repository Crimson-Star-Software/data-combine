from django.views.generic import View
from django.shortcuts import render
from datacombine import models


class HomeView(View):

    def get(self, request):
        return render(
            request,
            'home.html',
            {'contacts_count': models.Contact.objects.count()}
        )
