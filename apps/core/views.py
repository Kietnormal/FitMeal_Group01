from django.http import JsonResponse
from django.shortcuts import render


def home(request):
    return render(request, "core/home.html")


def shop(request):
    return render(request, "core/shop.html", {"active_page": "shop"})


def cart(request):
    return render(request, "core/cart.html", {"active_page": "cart"})


def checkout(request):
    return render(request, "core/checkout.html", {"active_page": "checkout"})


def order_tracking(request):
    return render(request, "core/tracking.html", {"active_page": "tracking"})


def account(request):
    return render(request, "core/account.html", {"active_page": "account"})


def demo_admin(request):
    return render(request, "core/admin_dashboard.html", {"active_page": "admin"})


def healthz(request):
    """Endpoint kiểm tra sống cho giám sát (UptimeRobot, Docker healthcheck...)."""
    return JsonResponse({"status": "ok"})
