from django.http import JsonResponse
from django.shortcuts import render


def home(request):
    return render(request, "core/home.html")


def healthz(request):
    """Endpoint kiểm tra sống cho giám sát (UptimeRobot, Docker healthcheck...)."""
    return JsonResponse({"status": "ok"})
