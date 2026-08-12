from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

from api.views import (
    home,
    normal_user_create,
    normal_user_list,
    normal_user_update,
    project_admin,
)

som_urlpatterns = [
    path(
        "",
        LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("home/", home, name="home"),
    path("home/projects/", project_admin, name="project-admin"),
    path("home/projects/<int:pk>/edit/", project_admin, name="project-admin-edit"),
    path("home/users/", normal_user_list, name="normal-user-list"),
    path("home/users/new/", normal_user_create, name="normal-user-create"),
    path("home/users/<int:pk>/edit/", normal_user_update, name="normal-user-update"),
    path("lrs/", include("lrs.urls")),
    path("identity/", include("identity.urls")),
    path("moodle_integration/", include("moodle_integration.urls")),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
]

urlpatterns = [
    path("som/", include(som_urlpatterns)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
