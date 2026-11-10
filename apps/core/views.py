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
    """Endpoint kiểm tra sống cho giám sát."""
    return JsonResponse({"status": "ok"})


def employee(request):
    # Dữ liệu mẫu (Đã thêm email, sđt, ngày vào làm)
    employees = [
        {'id': 1, 'name': 'Nguyễn Văn A', 'email': 'nva@fitmeal.vn', 'phone': '0901234567', 'role': 'Quản lý', 'is_active': True, 'join_date': '15/01/2023'},
        {'id': 2, 'name': 'Trần Thị B', 'email': 'ttb@fitmeal.vn', 'phone': '0912345678', 'role': 'Giao hàng', 'is_active': True, 'join_date': '20/03/2023'},
        {'id': 3, 'name': 'Lê Văn C', 'email': 'lvc@fitmeal.vn', 'phone': '0923456789', 'role': 'Đầu bếp', 'is_active': False, 'join_date': '10/05/2022'},
        {'id': 4, 'name': 'Phạm Thị D', 'email': 'ptd@fitmeal.vn', 'phone': '0934567890', 'role': 'Chăm sóc KH', 'is_active': True, 'join_date': '05/11/2023'},
        {'id': 5, 'name': 'Hoàng Văn E', 'email': 'hve@fitmeal.vn', 'phone': '0945678901', 'role': 'Giao hàng', 'is_active': True, 'join_date': '12/12/2023'},
    ]

    
    search_query = request.GET.get('search', '').lower()
    role_filter = request.GET.get('role', '')

    # Xử lý Lọc & Tìm kiếm
    filtered_employees = employees
    if search_query:
        filtered_employees = [emp for emp in filtered_employees if search_query in emp['name'].lower() or search_query in emp['email'].lower()]
    if role_filter:
        filtered_employees = [emp for emp in filtered_employees if emp['role'] == role_filter]

    # Lấy danh sách các vai trò duy nhất để đưa vào Dropdown lọc
    roles = list(set([emp['role'] for emp in employees]))

    context = {
        'employees': filtered_employees,
        'search_query': search_query,
        'role_filter': role_filter,
        'roles': roles,
        'active_page': 'employees'
    }
    return render(request, 'core/employee.html', context)

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
