from django.urls import path

from .views import lrs_home


urlpatterns = [
    path("", lrs_home, name="lrs-home"),
]
