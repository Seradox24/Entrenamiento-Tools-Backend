from django.urls import path

from .views import receive_event


app_name = "moodle_integration"

urlpatterns = [
    path("events/", receive_event, name="events"),
]
