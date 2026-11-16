from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .operations import create_database_backup, get_database_backup


@login_required
@require_POST
def create_backup(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    backup = create_database_backup()
    messages.success(request, f"Đã tạo bản sao lưu được mã hóa: {backup.name}.")
    return redirect(f"{reverse('staff_orders:dashboard')}?section=operations")


@login_required
@require_GET
def download_backup(request, filename):
    if not request.user.is_superuser:
        raise PermissionDenied
    backup = get_database_backup(filename)
    if backup is None:
        raise Http404("Không tìm thấy bản sao lưu.")
    return FileResponse(
        backup.open("rb"),
        as_attachment=True,
        filename=backup.name,
        content_type="application/octet-stream",
    )
