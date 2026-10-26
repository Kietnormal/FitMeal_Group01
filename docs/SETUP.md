# Hướng dẫn chạy dự án FitMeal (cho cả nhóm)

Không cần Docker. Cần cài: **Python 3.12**, **Git**, VS Code.

## Chạy lần đầu

```bash
git clone https://github.com/Kietnormal/FitMeal_Group01.git
cd FitMeal_Group01
git checkout develop

python -m venv venv
source venv/Scripts/activate        # Git Bash trên Windows
# PowerShell:  venv\Scripts\Activate.ps1
# Linux/Mac:   source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser    # tạo tài khoản quản trị để vào /admin
python manage.py runserver
```

Mở http://127.0.0.1:8000 (trang chủ) và http://127.0.0.1:8000/admin (quản trị).

## Mỗi ngày trước khi code

```bash
git checkout develop
git pull origin develop
pip install -r requirements.txt     # nếu có thư viện mới
python manage.py migrate            # nếu có migration mới
```

## Cấu trúc dự án

| Thư mục | Nội dung |
|---|---|
| `config/` | Cấu hình Django (settings, urls) |
| `apps/core/` | Trang chủ, trang dùng chung, endpoint `/healthz/` |
| `apps/accounts/` | Tài khoản, phân quyền (model `User` tùy biến) |
| `apps/products/` | Danh mục, sản phẩm (calo, protein...) |
| `apps/cart/` | Giỏ hàng |
| `apps/orders/` | Đơn hàng, trạng thái đơn |
| `apps/payments/` | Thanh toán |
| `apps/shipping/` | Vận chuyển |
| `templates/`, `static/` | Giao diện dùng chung |
| `docs/` | Tài liệu phân tích, thiết kế, ERD, báo cáo |

## Quy trình làm việc với Git

1. Không push trực tiếp vào `main` và `develop`.
2. Tạo nhánh từ `develop`: `git checkout -b feature/ten-chuc-nang` (sửa lỗi: `fix/ten-loi`).
3. Commit thường xuyên, tiền tố: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
4. Trước khi push: `git pull origin develop`, chạy `python manage.py test`.
5. Mở Pull Request vào **`develop`** (kiểm tra ô base), nhờ một bạn duyệt rồi merge.

## Quy tắc quan trọng

- **Migration:** luôn `git pull` trước khi chạy `makemigrations`. Mỗi app chỉ một người sửa model tại một thời điểm. Nếu trùng số migration: `python manage.py makemigrations --merge`.
- **Thư viện mới:** thêm vào `requirements.txt` và báo cả nhóm.
- **Bí mật:** không commit `.env`, mật khẩu, khóa API. Chỉ commit `.env.example`.
- **Model người dùng** là `apps.accounts.User`. Trong code dùng `get_user_model()` hoặc `settings.AUTH_USER_MODEL`, không import trực tiếp `django.contrib.auth.models.User`.
