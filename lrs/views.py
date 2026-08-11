from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@login_required
def lrs_home(request):
    return JsonResponse({"service": "som-lrs", "status": "ready"})
