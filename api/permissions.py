from rest_framework.permissions import BasePermission


class IsSuperUser(BasePermission):
    message = "Solo los superusuarios pueden administrar proyectos."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )
