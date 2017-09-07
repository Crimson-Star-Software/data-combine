"""datacombine URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from datacombine import views


urlpatterns = [
    url(r'^check_task_id/(?P<tid>[a-zA-Z0-9-]+)/$',
        login_required(views.CheckTaskProgressAJAX.as_view()),
        name='checktid'),
    url(r'^dash/', login_required(views.DashView.as_view())),
    url(r'^harvest/combining/', login_required(views.CombineView.as_view()),
        name='combining'),
    url(r'^harvest/', login_required(views.HarvestInitializationView.as_view()),
        name='harvest_init'),
    url(r'^admin/', admin.site.urls),
    url(r'^login/$', auth_views.login,
        kwargs={'template_name': 'login.html',
                'redirect_authenticated_user': True},
        name='login'),
    url(r'^logout/$', auth_views.logout, {'next_page': '/'}, name='logout'),
    url(r'^$', login_required(views.DashView.as_view(), login_url='/login')),
]
