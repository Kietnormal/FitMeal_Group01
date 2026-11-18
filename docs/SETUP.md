# Hướng dẫn chạy dự án FitMeal (cho cả nhóm)

Không cần Docker. Cần cài: **Python 3.12**, **Git**, VS Code; cài thêm **Node.js/npm** nếu muốn
chạy kiểm thử giao diện Playwright.

Hướng dẫn triển khai Ubuntu VPS (Gunicorn, Nginx, MySQL và HTTPS): [DEPLOYMENT.md](./DEPLOYMENT.md).

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
- Hậu mãi và quyền riêng tư: khách gửi khiếu nại hoặc yêu cầu đổi/trả từ lịch sử đơn trong vòng
  7 ngày kể từ khi nhận hàng; Quản lý xử lý tại tab **Khiếu nại / đổi trả**. Chấp thuận yêu cầu
  không tự hoàn tiền. Sau 7 ngày, chỉ Quản lý/Quản trị viên có thể xem dữ liệu định danh sau khi
  nhập lý do; lần truy cập được ghi nhật ký. Sau 12 tháng, thông tin định danh và nội dung hỗ trợ
  bị xóa, còn khu vực được giữ cho báo cáo. Chạy `python manage.py purge_expired_order_pii` để
  thực hiện đợt xóa; nên tạo tác vụ Windows Task Scheduler chạy hằng ngày, dùng `python.exe` trong
  môi trường ảo, lệnh trên ở **Add arguments**, và thư mục dự án ở **Start in**.
- Sao lưu và hết hạn thanh toán: để tác vụ chạy kể cả khi không có người truy cập, tạo hai lịch riêng
  trong Windows Task Scheduler. Chạy `manage.py backup_database` mỗi ngày lúc 03:00 và
  `manage.py expire_pending_payments` mỗi phút; đặt `python.exe` trong môi trường ảo ở
  **Program/script**, các lệnh trên ở **Add arguments**, thư mục dự án ở **Start in**. Giữ
  `BACKUP_ENCRYPTION_KEY` ổn định và lưu bản sao của khóa an toàn; đổi khóa sẽ khiến backup cũ
  không giải mã được. Đặt `BACKUP_EXTERNAL_ROOT` trên ổ/đích lưu trữ khác để có bản off-site.
- `/admin/`: trang quản trị Django để quản lý dữ liệu hệ thống. Tài khoản tạo bằng `createsuperuser` có quyền quản trị đầy đủ.
- Sau khi áp dụng migration, tồn kho của sản phẩm cũ mặc định là chưa nhập; hệ thống chưa tự trừ kho khi khách đặt hàng.
- `/policies/`: chính sách và thông tin hỗ trợ; xác nhận nội dung chính sách trước khi mở bán.
- Kế hoạch kiểm thử: xem [TEST_CASES.md](./TEST_CASES.md) để chạy toàn bộ test Django, kiểm thử
  trình duyệt và ghi kết quả UAT trên staging. Để xem trình duyệt tự thao tác, kích hoạt môi trường
  Python đã cài `requirements.txt`, sau đó chạy từ thư mục dự án:

  ```powershell
  npm ci
  npx playwright install chromium
  npm run test:e2e:slow
  ```

  Chromium sẽ tự mở và chạy luồng tìm món/giỏ hàng, sau đó tạo tài khoản khách và đặt một đơn COD thử;
  mỗi thao tác được làm chậm khoảng 700 ms để dễ quan sát. Chạy `npm run test:e2e:headed` nếu muốn
  chạy nhanh, hoặc `npm run test:e2e:ui` để mở giao diện Playwright và xem/chạy lại từng bước. E2E tự
  khởi động Django trên `127.0.0.1:8765`, dùng SQLite riêng `.playwright-e2e.sqlite3` (được tạo lại
  mỗi lần) và dữ liệu món giả lập. Đơn COD chỉ nằm trong SQLite kiểm thử, không ghi vào MySQL; không
  gửi giao dịch hoặc gọi cổng thanh toán thật. Các giao dịch MoMo/thẻ ATM cần dùng sandbox; không
  thực hiện kiểm thử tải hoặc thanh toán thử trên production.

### Kiểm thử tải đặt hàng cục bộ bằng Locust

Locust mô phỏng mỗi người dùng mở thực đơn, vào trang thanh toán và tạo đúng một đơn COD với email
giả lập riêng. Kịch bản chỉ cho phép host `127.0.0.1` hoặc `localhost` trên cổng `8766`; nó không gọi
cổng thanh toán. Đây là kiểm thử API/backend, không mở nhiều cửa sổ trình duyệt.

1. Cài Locust trong môi trường Python của dự án:

   ```powershell
   pip install -r requirements-loadtest.txt
   ```

2. Ở Terminal 1, chuẩn bị database Locust rồi chạy máy chủ. Mặc định là SQLite riêng để thử nhanh:

   ```powershell
   # Dành cho kiểm tra nhanh một người dùng; SQLite không phù hợp đo ghi đồng thời.
   python manage.py migrate --noinput --settings=config.locust_settings
   python manage.py flush --noinput --settings=config.locust_settings
   python manage.py loaddata playwright_catalog --settings=config.locust_settings
   python manage.py runserver 127.0.0.1:8766 --noreload --settings=config.locust_settings
   ```

   Để chạy 10–20 người dùng cùng lúc, hãy dùng một database MySQL/PostgreSQL thử nghiệm riêng (cùng
   loại với môi trường bạn muốn đo), không dùng SQLite. Đặt URL trước các lệnh trên, ví dụ:

   ```powershell
   $env:LOCUST_DATABASE_URL = 'mysql://USER:PASSWORD@127.0.0.1:3306/fitmeal_locust'
   ```

   Tạo database rỗng `fitmeal_locust` trước; thay `USER`/`PASSWORD` bằng tài khoản chỉ có quyền trên
   database thử nghiệm. Nếu dùng MySQL mà thiếu driver, cài `mysqlclient`. Lệnh `flush` xóa dữ liệu
   trong database Locust đã cấu hình; tuyệt đối không đặt URL tới database thật. Nếu bỏ qua biến môi
   trường, Locust dùng `.locust-test.sqlite3`, chỉ phù hợp kiểm tra nhanh và có thể báo khóa database
   khi nhiều đơn được ghi cùng lúc.

3. Ở Terminal 2, mở Locust:

   ```powershell
   python -m locust -f locustfile.py --host http://127.0.0.1:8766
   ```

   Mở `http://127.0.0.1:8089`, nhập **10** rồi **20** ở *Number of users*, đặt *Spawn rate* là
   **5 users/second** để mô phỏng nhóm người vào gần cùng lúc, sau đó chạy mỗi lượt khoảng **1 phút**.
   Mỗi user chỉ tạo một đơn và vẫn giữ phiên hoạt động đến khi dừng bài thử;
   kết quả `POST /api/orders/ (COD)` phải trả HTTP 201. Theo dõi số lỗi và thời gian phản hồi trong
   Locust. Chỉ dùng database thử nghiệm riêng với dữ liệu giả; hiệu năng sẽ khác production.

Dừng Locust rồi máy chủ bằng `Ctrl+C`. Không chạy bài thử này trên production hoặc trên hệ thống
thanh toán thật.

### Demo MoMo sandbox qua HTTPS tạm thời

Luồng này dành cho demo MoMo khi máy chủ đang chạy trên localhost. Nó dùng SQLite và thư mục media
riêng, `DEBUG=False`, chỉ cho phép endpoint MoMo sandbox; không dùng database MySQL chính. Cần có
`cloudflared` và credentials MoMo sandbox trong `.env`. Quick Tunnel là địa chỉ tạm, công khai trong
thời gian chạy; chỉ dùng dữ liệu giả và gửi link cho người cần xem.

1. Ở Terminal 1, tại thư mục dự án, mở tunnel đến cổng demo riêng:

   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8001
   ```

   Sao chép hostname HTTPS do lệnh in ra, ví dụ `https://random-name.trycloudflare.com`. Không nhập
   placeholder có dấu `<...>`.

2. Ở Terminal 2, đặt cấu hình bằng hostname vừa nhận rồi tạo database mới:

   ```powershell
   $publicUrl = 'https://random-name.trycloudflare.com'
   $publicHost = ([uri]$publicUrl).Host
   $env:MOMO_DEMO_DIR = Join-Path $env:LOCALAPPDATA ('FitMealMomoDemo-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
   New-Item -ItemType Directory -Path $env:MOMO_DEMO_DIR | Out-Null
   $dbPath = Join-Path $env:MOMO_DEMO_DIR 'db.sqlite3'
   $dbUrl = 'sqlite:///' + ($dbPath -replace '\\', '/')
   $env:DEBUG = 'False'
   $env:SECRET_KEY = (& python -c "import secrets; print(secrets.token_urlsafe(64))")
   $env:MOMO_DEMO_SECRET_KEY = (& python -c "import secrets; print(secrets.token_urlsafe(64))")
   $env:DATABASE_URL = $dbUrl
   $env:MOMO_DEMO_DATABASE_URL = $dbUrl
   $env:MOMO_DEMO_ALLOWED_HOSTS = $publicHost
   $env:MOMO_DEMO_CSRF_TRUSTED_ORIGINS = $publicUrl
   $env:MOMO_DEMO_PUBLIC_BASE_URL = $publicUrl
   python manage.py migrate --noinput --settings=config.momo_demo_settings
   python manage.py loaddata playwright_catalog --settings=config.momo_demo_settings
   python manage.py collectstatic --noinput --settings=config.momo_demo_settings
   python manage.py runserver 127.0.0.1:8001 --noreload --settings=config.momo_demo_settings
   ```

3. Mở đúng `https://random-name.trycloudflare.com` trong một trình duyệt, thêm món kiểm thử vào giỏ
   rồi đặt đơn MoMo. Giữ nguyên tunnel, server và cùng phiên trình duyệt đến khi hoàn tất; QR thanh
   toán gắn với phiên đã tạo đơn. Dừng cả hai tiến trình bằng `Ctrl+C` sau khi demo.

Settings từ chối khởi động nếu database không phải SQLite nằm trong thư mục demo riêng, hostname HTTPS
không khớp cấu hình host/CSRF, MoMo chưa bật hoặc endpoint không phải sandbox. Không dùng tunnel này
để public cổng 8000, database MySQL hoặc dữ liệu người dùng thật.

Dashboard `/demo-admin/` đã được gỡ. Không dùng trang demo để xử lý dữ liệu. Checkout có ba phương thức: MoMo ATM sandbox, chuyển khoản ngân hàng và thanh toán khi nhận hàng (COD). Cấu hình `MOMO_PARTNER_CODE`, `MOMO_ACCESS_KEY`, `MOMO_SECRET_KEY` để bật MoMo; checkout tạo QR nội bộ từ `payUrl`, IPN đã xác thực hoặc `redirectUrl` có chữ ký hợp lệ đều có thể xác nhận thanh toán. Để callback hoạt động khi mở checkout bằng `localhost`, cấu hình `MOMO_PUBLIC_BASE_URL` thành origin HTTPS công khai của staging/tunnel; hostname đó phải được khai báo trong `ALLOWED_HOSTS` và đăng ký IPN URL `/payments/momo/ipn/` trong MoMo. Khi chạy sau reverse proxy HTTPS đáng tin cậy, đặt `DEBUG=False`, dùng `SECRET_KEY` riêng, bật `USE_PROXY_SSL_HEADER=True`, và chỉ đưa hostname của phiên demo vào `ALLOWED_HOSTS`. Không đưa máy chủ `DEBUG=True` hoặc dữ liệu khách hàng thật ra Internet; ưu tiên staging riêng. Để tự đối soát chuyển khoản, cấu hình `BANK_TRANSFER_BANK_CODE`, `BANK_TRANSFER_ACCOUNT_NUMBER`, `BANK_TRANSFER_ACCOUNT_NAME`, `SEPAY_API_KEY` và webhook SePay tại URL công khai `/payments/bank/sepay-webhook/` với xác thực API Key (`Authorization: Apikey ...`) và sự kiện tiền vào. Dùng sandbox credentials trước khi bật production. Chạy `manage.py expire_pending_payments` mỗi phút để hủy giao dịch quá hạn. Tích hợp hãng vận chuyển tự động chưa được cấu hình.

Với MoMo, `redirectUrl` chỉ cập nhật đơn khi chữ ký, đối tác, mã đơn, số tiền và mã giao dịch hợp lệ; IPN vẫn được xử lý idempotent nếu đến sau. Giữ trang QR mở trên máy tính để trang tự kiểm tra trạng thái và hiển thị dấu tích xanh sau khi điện thoại tự quay về trang FitMeal.

Các trang prototype đã có bố cục responsive và hộp thoại hỗ trợ bàn phím cơ bản (giữ tiêu điểm trong hộp thoại, đóng bằng Escape, trả tiêu điểm về nút đã mở). Cần kiểm thử lại trên thiết bị và trình đọc màn hình thực tế trước khi triển khai.

Khi chạy demo cô lập với `DEBUG=False` mà chưa có web server phục vụ media, có thể đặt `SERVE_PRODUCT_MEDIA=True` để Django phục vụ ảnh trong `MEDIA_ROOT/products/`. Tùy chọn này không phục vụ ảnh đại diện; không bật cho production.

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
