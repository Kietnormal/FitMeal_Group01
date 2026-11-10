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

## Giao diện prototype

Các trang dưới đây là prototype frontend dùng dữ liệu minh họa, chưa kết nối nghiệp vụ backend:

- `/products/`: danh mục cơm, salad, món ăn nhẹ, thức uống và combo; tìm kiếm, lọc theo giá/protein/calo, sắp xếp, xem thành phần và thông tin dinh dưỡng.
- `/cart/`, `/checkout/`: luồng giỏ hàng và đặt hàng mô phỏng; chỉnh số lượng, chọn địa chỉ/ngày/khung giờ, xem phí giao, thử COD hoặc kết quả thanh toán online thành công/thất bại.
- `/orders/track/`: lịch sử đơn demo, chi tiết trạng thái giao hàng và yêu cầu hủy khi đơn còn ở trạng thái cho phép.
- `/account/`: đăng ký/đăng nhập demo, khôi phục mật khẩu minh họa, chỉnh hồ sơ và xem lịch sử đơn; mật khẩu không được lưu.
- `/demo-admin/`: dashboard minh họa sản phẩm, khách hàng, đơn hàng, thanh toán, vận chuyển, bảo mật và vận hành. Mục Sản phẩm có thể thêm/xóa món, đổi giá và đánh dấu hết món; mục Bảo mật có biểu mẫu đăng ký admin demo.

Hồ sơ demo, giỏ hàng, lịch sử đơn và danh sách món prototype được lưu trong `localStorage` của trình duyệt hiện tại; không đồng bộ giữa thiết bị hoặc người dùng. Dữ liệu dinh dưỡng là số liệu minh họa. Mọi bước thanh toán, đăng nhập, đặt hàng và hủy đơn đều là giả lập, không gọi dịch vụ thật. Biểu mẫu admin chỉ kiểm tra giao diện, không tạo tài khoản và không lưu mật khẩu. Không nhập dữ liệu thật hoặc thông tin thanh toán. `/demo-admin/` chưa có đăng nhập hay phân quyền và không dùng như trang quản trị triển khai thật. Database, xác thực, thanh toán, bảo mật, vận chuyển, backup và giám sát sẽ làm ở giai đoạn backend sau.

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
