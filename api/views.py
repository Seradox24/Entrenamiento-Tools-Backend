from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .forms import NormalUserCreationForm, NormalUserUpdateForm, ProjectForm
from .models import Project


User = get_user_model()


def require_superuser(user):
    if not user.is_superuser:
        raise PermissionDenied


@login_required
def home(request):
    return render(request, "home.html")


@login_required
def normal_user_list(request):
    require_superuser(request.user)
    users = User.objects.filter(is_superuser=False).order_by("username")
    return render(request, "users/list.html", {"users": users})


@login_required
def normal_user_create(request):
    require_superuser(request.user)
    if request.method == "POST":
        form = NormalUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("normal-user-list")
    else:
        form = NormalUserCreationForm()

    return render(
        request,
        "users/form.html",
        {
            "form": form,
            "title": "Crear usuario",
            "submit_label": "Crear",
        },
    )


@login_required
def normal_user_update(request, pk):
    require_superuser(request.user)
    user = get_object_or_404(User, pk=pk, is_superuser=False)

    if request.method == "POST":
        form = NormalUserUpdateForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect("normal-user-list")
    else:
        form = NormalUserUpdateForm(instance=user)

    return render(
        request,
        "users/form.html",
        {
            "form": form,
            "title": "Modificar usuario",
            "submit_label": "Guardar",
            "managed_user": user,
        },
    )


@login_required
def project_admin(request, pk=None):
    require_superuser(request.user)
    project = get_object_or_404(Project, pk=pk) if pk else None

    if request.method == "POST":
        action = request.POST.get("action", "save")

        if action == "delete":
            project_to_delete = get_object_or_404(Project, pk=request.POST.get("project_id"))
            project_to_delete.delete()
            return redirect("project-admin")

        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            return redirect("project-admin")
    else:
        form = ProjectForm(instance=project)

    projects = Project.objects.all()
    return render(
        request,
        "projects/admin.html",
        {
            "form": form,
            "projects": projects,
            "editing_project": project,
        },
    )


@api_view(["GET"])
def health_check(request):
    return Response(
        {
            "status": "ok",
            "service": "django-rest-framework",
        }
    )
