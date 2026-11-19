# Triển khai FitMeal lên PythonAnywhere (miễn phí)

Tài liệu này dùng để đưa FitMeal lên Internet với một địa chỉ HTTPS công khai dạng
`https://<username>.pythonanywhere.com`, để giảng viên và người dùng truy cập từ bất kỳ đâu.

Gói **Beginner (miễn phí)** của PythonAnywhere có sẵn:

- Web chạy 24/7, không "ngủ" như một số dịch vụ miễn phí khác.
- HTTPS do PythonAnywhere cấp sẵn.
- MySQL 8.0, đúng loại database dự án đang dùng, nên nạp thẳng được file `database/fitmeal.sql`.
- Không cần thẻ thanh toán.

Giới hạn của gói miễn phí (xem mục 10):

- Máy chủ chỉ gọi ra được một số website nằm trong danh sách cho phép, nên **MoMo sandbox không chạy được**.
- Web app phải được gia hạn 3 tháng một lần (bấm một nút).
- Dung lượng đĩa 512 MB.

Trong hướng dẫn, thay `USERNAME` bằng tên tài khoản PythonAnywhere của bạn.

---

## 1. Tạo tài khoản

1. Vào <https://www.pythonanywhere.com/registration/register/beginner/>.
2. Chọn `USERNAME` cẩn thận, vì tên miền sẽ là `USERNAME.pythonanywhere.com`. Ví dụ: `fitmealgroup01`.
3. Xác nhận email.

## 2. Tạo database MySQL

1. Mở tab **Databases**.
2. Ở mục **MySQL password**, đặt mật khẩu database và ghi lại.
3. Ở mục **Create a database**, gõ `fitmeal` rồi bấm **Create**. Database thật sẽ có tên `USERNAME$fitmeal`.
4. Ghi lại **Database host address**, dạng `USERNAME.mysql.pythonanywhere-services.com`.

## 3. Tải code và cài thư viện

Mở tab **Consoles**, chọn **Bash**, rồi chạy:

```bash
git clone --branch claude/admiring-meitner-vh92s0 https://github.com/Kietnormal/FitMeal_Group01.git
cd FitMeal_Group01
mkvirtualenv --python=python3.12 fitmeal
pip install -r requirements.txt
```

- Nếu repo đang để **private**, `git clone` sẽ hỏi tài khoản. Khi đó dùng GitHub username và một
  **Personal Access Token** (GitHub → Settings → Developer settings → Personal access tokens) thay cho mật khẩu.
- Nếu sau này nhóm gộp code vào nhánh khác (ví dụ `main`), đổi tên nhánh sau `--branch`.
- Lần sau mở console mới, gõ `workon fitmeal` để bật lại môi trường ảo.

## 4. Tạo file cấu hình `.env`

Tạo khoá bí mật cho Django:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Mở file `.env`:

```bash
nano .env
```

Dán nội dung dưới đây và thay các phần `USERNAME`, `<...>`:

```dotenv
DEBUG=False
SECRET_KEY=<chuỗi vừa tạo ở trên>
ALLOWED_HOSTS=USERNAME.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://USERNAME.pythonanywhere.com
DATABASE_URL=mysql://USERNAME:<mật-khẩu-mysql>@USERNAME.mysql.pythonanywhere-services.com/USERNAME$fitmeal
APP_VERSION=pythonanywhere-1

# Gửi email thật qua Gmail (mật khẩu ứng dụng 16 ký tự, viết liền)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<gmail-du-an>@gmail.com
EMAIL_HOST_PASSWORD=<mat-khau-ung-dung>
DEFAULT_FROM_EMAIL=FitMeal <<gmail-du-an>@gmail.com>
```

Lưu bằng `Ctrl + O`, Enter, rồi thoát bằng `Ctrl + X`.

- Nếu mật khẩu MySQL có ký tự đặc biệt (`@ : / # %`), phải viết chúng dưới dạng mã hoá URL, ví dụ `@` thành `%40`.
- **Không commit file `.env`.** File này đã nằm trong `.gitignore`.

## 5. Nạp dữ liệu và chuẩn bị static

```bash
mysql -u USERNAME -h USERNAME.mysql.pythonanywhere-services.com -p 'USERNAME$fitmeal' < database/fitmeal.sql
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

- Lệnh `mysql` sẽ hỏi mật khẩu MySQL đã đặt ở bước 2.
- `migrate` sẽ tạo thêm bảng `accounts_passwordresetcode` (chức năng quên mật khẩu).
- `check --deploy` có thể cảnh báo `security.W004` và `security.W008`. Hai cảnh báo này đã được xử lý
  bằng tuỳ chọn **Force HTTPS** ở bước 6.

Nếu muốn tạo thêm tài khoản quản trị:

```bash
python manage.py createsuperuser
```

## 6. Tạo web app

1. Mở tab **Web**, bấm **Add a new web app**, rồi **Next**.
2. Chọn **Manual configuration** (không chọn "Django"), sau đó chọn **Python 3.12**.
3. Ở trang cấu hình web app:
   - **Source code:** `/home/USERNAME/FitMeal_Group01`
   - **Working directory:** `/home/USERNAME/FitMeal_Group01`
   - **Virtualenv:** `/home/USERNAME/.virtualenvs/fitmeal`
4. Bấm vào link **WSGI configuration file** (dạng `/var/www/USERNAME_pythonanywhere_com_wsgi.py`),
   **xoá toàn bộ nội dung cũ**, dán đoạn dưới đây rồi bấm **Save**:

   ```python
   import os
   import sys

   project_path = "/home/USERNAME/FitMeal_Group01"
   if project_path not in sys.path:
       sys.path.insert(0, project_path)
   os.chdir(project_path)
   os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

   from django.core.wsgi import get_wsgi_application

   application = get_wsgi_application()
   ```

5. Ở mục **Static files**, thêm 2 dòng:

   | URL | Directory |
   |---|---|
   | `/static/` | `/home/USERNAME/FitMeal_Group01/staticfiles` |
   | `/media/` | `/home/USERNAME/FitMeal_Group01/media` |

6. Ở mục **Security**, bật **Force HTTPS**.
7. Kéo lên đầu trang và bấm nút xanh **Reload USERNAME.pythonanywhere.com**.

## 7. Tải ảnh sản phẩm lên (nếu có)

Ảnh sản phẩm do quản trị viên tải lên nằm trong thư mục `media/` trên máy phát triển. Thư mục này
không có trong git. Để server có đủ ảnh:

1. Trên máy của bạn, nén thư mục `media` thành `media.zip`.
2. Ở tab **Files**, vào `/home/USERNAME/FitMeal_Group01`, bấm **Upload a file** và chọn `media.zip`.
3. Trong Bash console, chạy:

   ```bash
   cd ~/FitMeal_Group01 && unzip -o media.zip && rm media.zip
   ```

## 8. Kiểm tra sau khi deploy

| Kiểm tra | Kết quả mong đợi |
|---|---|
| `https://USERNAME.pythonanywhere.com/healthz/` | Trả về trạng thái OK (HTTP 200) |
| Trang chủ, Thực đơn, Giỏ hàng | Hiển thị đủ giao diện và ảnh |
| Đăng nhập bằng tài khoản có sẵn trong database | Đăng nhập được |
| `https://USERNAME.pythonanywhere.com/admin/` | Vào được trang quản trị |
| Đặt một đơn COD | Đơn xuất hiện trong khu vực nhân viên |
| Quên mật khẩu → nhập email | Mã OTP về hộp thư Gmail |

Nếu trang báo lỗi, xem log ở tab **Web**: mục **Log files** có **Error log** và **Server log**.

## 9. Cập nhật phiên bản mới

Mỗi khi có code mới trên GitHub, mở Bash console và chạy:

```bash
cd ~/FitMeal_Group01
workon fitmeal
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Sau đó vào tab **Web** và bấm **Reload**. Nên tăng `APP_VERSION` trong `.env` để biết server đang chạy bản nào.

## 10. Giới hạn của gói miễn phí và thanh toán trực tuyến

- **Gia hạn:** tab **Web** có nút **Run until 3 months from today**. Bấm trước khi hết hạn, nếu không web sẽ tạm tắt.
- **Email:** gói miễn phí cho phép gửi mail qua Gmail SMTP như cấu hình ở bước 4.
- **MoMo:** server gói miễn phí chỉ được gọi ra các website trong danh sách cho phép của PythonAnywhere.
  `test-payment.momo.vn` không nằm trong danh sách, nên lựa chọn MoMo sẽ không tạo được giao dịch. Có hai hướng:
  - Gửi yêu cầu thêm `test-payment.momo.vn` vào danh sách cho phép qua nút **Send feedback** của PythonAnywhere,
    vì đây là API công khai có tài liệu.
  - Hoặc nâng cấp lên gói trả phí **Hacker** (khoảng 5 USD/tháng), gói này không giới hạn truy cập Internet.

  Khi MoMo dùng được, thêm vào `.env` các khoá sandbox MoMo và
  `MOMO_PUBLIC_BASE_URL=https://USERNAME.pythonanywhere.com`, rồi bấm **Reload**.
- **Chuyển khoản ngân hàng + VietQR:** ảnh QR do trình duyệt của khách tải từ VietQR, còn SePay chủ động gọi về
  web, nên cách này **vẫn chạy được trên gói miễn phí**. Cần một tài khoản ngân hàng thật và tài khoản SePay, rồi:
  1. Thêm vào `.env`:

     ```dotenv
     BANK_TRANSFER_BANK_CODE=<mã ngân hàng, ví dụ MB, VCB, TPB>
     BANK_TRANSFER_ACCOUNT_NUMBER=<số tài khoản>
     BANK_TRANSFER_ACCOUNT_NAME=<TÊN CHỦ TÀI KHOẢN, VIẾT HOA KHÔNG DẤU>
     SEPAY_API_KEY=<API key tự đặt, chuỗi ngẫu nhiên dài>
     ```

  2. Trong trang quản lý SePay, tạo **Webhook** với:
     - URL: `https://USERNAME.pythonanywhere.com/payments/bank/sepay-webhook/`
     - Kiểu xác thực: **API Key**, giá trị đúng bằng `SEPAY_API_KEY` ở trên.
  3. Bấm **Reload** web app. Ở trang thanh toán sẽ có thêm lựa chọn "Chuyển khoản" kèm mã QR. Khi tiền về,
     SePay báo cho web và đơn được tự động xác nhận.
- **Thanh toán khi nhận hàng (COD)** luôn hoạt động, không cần cấu hình thêm.
