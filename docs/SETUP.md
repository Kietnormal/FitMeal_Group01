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

## Các chức năng hiện có

- `/products/`: danh mục sản phẩm lấy từ database, có tìm kiếm, lọc và xem thông tin sản phẩm.
- `/cart/`, `/checkout/`: tạo đơn hàng COD và lưu vào database. Đơn đặt khi đã đăng nhập sẽ được liên kết với tài khoản khách hàng.
- `/orders/track/`: theo dõi trạng thái đơn hàng. Khách cũng xem đơn trong lịch sử tài khoản.
- `/account/`: đăng ký/đăng nhập, hồ sơ, địa chỉ, điểm thưởng và đánh giá đơn đã hoàn tất.
- `/management/orders/`: khu vực làm việc theo vai trò. NV bán hàng xử lý đơn và chỉ xem thực đơn;
  Quản lý có thêm quản lý món/giá, tồn kho thủ công, báo cáo doanh thu 7 ngày và nhật ký thay đổi.
  Dashboard quản trị đầy đủ và quản lý nhân viên chỉ dành cho superuser.
- Xác thực hai bước cho nhân viên: sau khi đăng nhập, từng quản trị viên/quản lý mở **Xác thực hai bước**
  ở thanh bên `/management/orders/`, quét mã bằng ứng dụng TOTP và lưu mã khôi phục. Superuser chỉ
  bật yêu cầu bắt buộc trong tab **Bảo mật** sau khi tất cả tài khoản thuộc vai trò đó đã đăng ký;
  chính sách mặc định tắt để tránh khóa nhân viên trước khi họ thiết lập thiết bị.
- Quy trình hủy đơn: khách có thể hủy đơn đang chờ xác nhận/đã xác nhận; đơn đang chuẩn bị hoặc
  sẵn sàng giao cần nhân viên gọi xác nhận; đơn đang giao không thể hủy. Nhân viên ghi nhận yêu cầu
  hủy do hết món hoặc kết quả gọi khách, không tự duyệt. Quản lý xử lý yêu cầu trong tab **Yêu cầu
  hủy**, và hủy trực tiếp bắt buộc có lý do.
- Quy trình xác nhận giao hàng: khi nhân viên báo đã giao, khách có 3 phút để xác nhận đã nhận hoặc
  báo chưa nhận. Khiếu nại xuất hiện trong tab **Khiếu nại giao hàng** để Quản lý xác minh và chọn
  xác nhận hoàn tất hoặc tiếp tục giao. Chạy tác vụ hoàn tất tự động một lần để kiểm tra:
  `python manage.py finalize_delivery_confirmations`. Để tự động chạy đúng hạn khi không có người
  truy cập website, tạo tác vụ trong Windows Task Scheduler chạy mỗi phút; dùng `python.exe` trong
  môi trường ảo ở **Program/script**, `manage.py finalize_delivery_confirmations` ở **Add arguments**,
  và thư mục dự án ở **Start in**.
- Sao lưu và hết hạn thanh toán: để tác vụ chạy kể cả khi không có người truy cập, tạo hai lịch riêng
  trong Windows Task Scheduler. Chạy `manage.py backup_database` mỗi ngày lúc 03:00 và
  `manage.py expire_pending_payments` mỗi phút; đặt `python.exe` trong môi trường ảo ở
  **Program/script**, các lệnh trên ở **Add arguments**, thư mục dự án ở **Start in**. Giữ
  `BACKUP_ENCRYPTION_KEY` ổn định và lưu bản sao của khóa an toàn; đổi khóa sẽ khiến backup cũ
  không giải mã được. Đặt `BACKUP_EXTERNAL_ROOT` trên ổ/đích lưu trữ khác để có bản off-site.
- `/admin/`: trang quản trị Django để quản lý dữ liệu hệ thống. Tài khoản tạo bằng `createsuperuser` có quyền quản trị đầy đủ.
- Sau khi áp dụng migration, tồn kho của sản phẩm cũ mặc định là chưa nhập; hệ thống chưa tự trừ kho khi khách đặt hàng.
- `/policies/`: chính sách và thông tin hỗ trợ; xác nhận nội dung chính sách trước khi mở bán.

Dashboard `/demo-admin/` đã được gỡ. Không dùng trang demo để xử lý dữ liệu. Checkout có ba phương thức: MoMo ATM sandbox, chuyển khoản ngân hàng và thanh toán khi nhận hàng (COD). Cấu hình `MOMO_PARTNER_CODE`, `MOMO_ACCESS_KEY`, `MOMO_SECRET_KEY` để bật MoMo; checkout tạo QR nội bộ từ `payUrl`, còn IPN đã xác thực mới đánh dấu đơn đã thanh toán. Để thử callback, mở checkout bằng hostname HTTPS công khai đã khai báo trong `ALLOWED_HOSTS`; MoMo dùng hostname đó cho `redirectUrl` và `ipnUrl`. Khi chạy sau reverse proxy HTTPS đáng tin cậy, đặt `DEBUG=False`, dùng `SECRET_KEY` riêng, bật `USE_PROXY_SSL_HEADER=True`, và chỉ đưa hostname của phiên demo vào `ALLOWED_HOSTS`. Không đưa máy chủ `DEBUG=True` hoặc dữ liệu khách hàng thật ra Internet; ưu tiên staging riêng. Đăng ký IPN URL công khai `/payments/momo/ipn/` trong MoMo. Để tự đối soát chuyển khoản, cấu hình `BANK_TRANSFER_BANK_CODE`, `BANK_TRANSFER_ACCOUNT_NUMBER`, `BANK_TRANSFER_ACCOUNT_NAME`, `SEPAY_API_KEY` và webhook SePay tại URL công khai `/payments/bank/sepay-webhook/` với xác thực API Key (`Authorization: Apikey ...`) và sự kiện tiền vào. Dùng sandbox credentials trước khi bật production. Chạy `manage.py expire_pending_payments` mỗi phút để hủy giao dịch quá hạn. Tích hợp hãng vận chuyển tự động chưa được cấu hình.

Các trang prototype đã có bố cục responsive và hộp thoại hỗ trợ bàn phím cơ bản (giữ tiêu điểm trong hộp thoại, đóng bằng Escape, trả tiêu điểm về nút đã mở). Cần kiểm thử lại trên thiết bị và trình đọc màn hình thực tế trước khi triển khai.

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
