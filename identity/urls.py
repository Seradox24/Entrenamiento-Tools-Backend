from django.urls import path

from .views import (
    close_experience_launch,
    create_experience_launch,
    exchange_experience_launch,
    experience_heartbeat,
    logout_launcher,
    moodle_login,
    refresh_launcher_token,
)


app_name = "identity"

urlpatterns = [
    path("moodle/login/", moodle_login, name="moodle-login"),
    path("token/refresh/", refresh_launcher_token, name="token-refresh"),
    path("logout/", logout_launcher, name="logout"),
    path("launches/", create_experience_launch, name="launch-create"),
    path("launches/exchange/", exchange_experience_launch, name="launch-exchange"),
    path(
        "launches/<uuid:launch_id>/heartbeat/",
        experience_heartbeat,
        name="launch-heartbeat",
    ),
    path(
        "launches/<uuid:launch_id>/close/",
        close_experience_launch,
        name="launch-close",
    ),
]
