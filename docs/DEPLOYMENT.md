# Triển khai FitMeal lên VPS Ubuntu

Tài liệu này chuẩn bị phương án VPS chạy **Ubuntu 24.04 LTS + MySQL + Gunicorn + Nginx + HTTPS**.
Chưa có thông tin VPS/domain nên các bước dưới đây là cấu hình và quy trình, không có máy chủ production
nào được tạo hay thay đổi trong phiên này. Nên triển khai staging trước, kiểm tra dữ liệu/luồng thanh
toán, rồi mới chuyển production.

## Điều kiện trước khi mở dịch vụ

- VPS Ubuntu có SSH; bản ghi DNS `A` (và `AAAA` nếu có IPv6) của domain trỏ đến IP VPS.
- Chỉ mở cổng công khai **22/80/443** (giới hạn SSH theo IP nếu có thể). **Không mở cổng MySQL 3306 ra Internet**.
- Có bản sao lưu đã kiểm tra khôi phục; không sao chép `db.sqlite3`, `.locust-test.sqlite3` hoặc database thử nghiệm Locust sang production.
- Quyết định rõ bắt đầu database production trống hay có kế hoạch chuyển dữ liệu đã kiểm tra riêng; không đưa tài khoản, đơn hàng, media hoặc thông tin cá nhân thật lên VPS nếu chưa có kế hoạch bảo vệ/chuyển dữ liệu.
- Chuẩn bị tài khoản email SMTP thật và xác nhận chính sách giao hàng/đổi trả. Ban đầu để trống credentials thanh toán hoặc dùng sandbox; chỉ bật MoMo/SePay production sau khi kiểm thử callback HTTPS và đối soát.
- Tạo `SECRET_KEY`, mật khẩu database, SMTP, OAuth và payment credentials riêng cho máy chủ. Không gửi hoặc commit các giá trị này.

## 1. Chuẩn bị MySQL

Ưu tiên cài MySQL trên cùng VPS hoặc dùng dịch vụ database có mạng riêng/TLS. Nếu MySQL chạy cùng VPS, chỉ bind vào `127.0.0.1`. Trong MySQL, tạo database và tài khoản ứng dụng giới hạn trong database FitMeal (thay mật khẩu ngay trong MySQL, không dùng mật khẩu ví dụ):

```sql
CREATE DATABASE fitmeal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'fitmeal_app'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_A_LONG_RANDOM_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE
ON fitmeal.* TO 'fitmeal_app'@'127.0.0.1';
CREATE USER 'fitmeal_migrator'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_ANOTHER_LONG_RANDOM_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES
ON fitmeal.* TO 'fitmeal_migrator'@'127.0.0.1';
```

Tài khoản runtime `fitmeal_app` chỉ có quyền đọc/ghi dữ liệu. Chỉ dùng `fitmeal_migrator` cho lệnh `migrate`; không cấp quyền quản trị toàn máy chủ cho hai tài khoản. Database Locust `fitmeal_locust` là dữ liệu thử, không phải database triển khai.

## 2. Cài ứng dụng và dependency trên VPS

SSH vào Ubuntu:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-dev build-essential pkg-config default-libmysqlclient-dev nginx certbot
sudo useradd --system --user-group --create-home --home-dir /srv/fitmeal --shell /usr/sbin/nologin fitmeal
sudo mkdir -p /srv/fitmeal/app /srv/fitmeal/backups /etc/fitmeal
sudo git clone --branch main --single-branch https://github.com/Kietnormal/FitMeal_Group01.git /srv/fitmeal/app
sudo chown -R root:fitmeal /srv/fitmeal/app
sudo chmod -R g+rX,o-rwx /srv/fitmeal/app
sudo chmod 751 /srv/fitmeal /srv/fitmeal/app
sudo -u fitmeal python3 -m venv /srv/fitmeal/venv
sudo -u fitmeal /srv/fitmeal/venv/bin/pip install --upgrade pip
sudo -u fitmeal /srv/fitmeal/venv/bin/pip install -r /srv/fitmeal/app/requirements.txt
sudo install -d -o fitmeal -g www-data -m 2750 /srv/fitmeal/app/media
sudo install -d -o fitmeal -g www-data -m 2750 /srv/fitmeal/app/staticfiles
sudo install -d -o fitmeal -g fitmeal -m 0750 /srv/fitmeal/backups
```

Thay `main` bằng nhánh/tag release đã được kiểm thử nếu nhóm phát hành từ nhánh khác. Khi có deploy mới, dùng commit/tag cụ thể và ghi lại mã phiên bản; không deploy trực tiếp thay đổi chưa được review.

## 3. Tạo file môi trường production

Tạo `/etc/fitmeal/fitmeal.env` bằng editor trên VPS. Tối thiểu cần các biến dưới đây; thay domain và secrets. Mật khẩu trong `DATABASE_URL` phải URL-encode nếu có ký tự đặc biệt như `@`, `:`, `/`, `#` hoặc `%`.

```dotenv
DEBUG=False
SECRET_KEY=REPLACE_WITH_A_UNIQUE_RANDOM_SECRET
ALLOWED_HOSTS=example.com,www.example.com
CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
DATABASE_URL=mysql://fitmeal_app:URL_ENCODED_PASSWORD@127.0.0.1:3306/fitmeal
USE_PROXY_SSL_HEADER=True
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=15552000
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
APP_VERSION=REPLACE_WITH_RELEASE_TAG_OR_COMMIT
BACKUP_ROOT=/srv/fitmeal/backups
```

Sinh khóa riêng bằng Python trên VPS:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Giữ file chỉ đọc được bởi root và service group:

```bash
sudo chown root:fitmeal /etc/fitmeal/fitmeal.env
sudo chmod 640 /etc/fitmeal/fitmeal.env
```

`SECURE_SSL_REDIRECT` và `USE_PROXY_SSL_HEADER` chỉ bật như trên khi Nginx đã proxy HTTPS. Chỉ đưa domain thật vào `ALLOWED_HOSTS` và `CSRF_TRUSTED_ORIGINS`. Chỉ đặt `SECURE_HSTS_INCLUDE_SUBDOMAINS=True` nếu mọi subdomain đều luôn dùng HTTPS; chỉ bật `SECURE_HSTS_PRELOAD=True` khi đã chủ ý đáp ứng yêu cầu preload của trình duyệt. Cấu hình SMTP trước khi cần gửi email; không để credentials mặc định hoặc secrets của sandbox trong production.

Các cổng thanh toán vẫn tắt khi không có credentials. Chỉ bật MoMo sau khi cấu hình credentials và URL production riêng (`MOMO_CREATE_PAYMENT_URL`), đặt `MOMO_PUBLIC_BASE_URL=https://<domain>` và đăng ký callback HTTPS với nhà cung cấp. Chuyển khoản tự đối soát chỉ bật khi đủ cấu hình ngân hàng và `SEPAY_API_KEY`. Không sao chép secrets từ máy phát triển hoặc Locust.

Tạo thêm `/etc/fitmeal/fitmeal-migrate.env` với cùng cấu hình cần thiết nhưng dùng URL database của user `fitmeal_migrator`. Giữ cả hai file ở quyền `root:fitmeal`, mode `640`. Service Gunicorn chỉ đọc `fitmeal.env`; file migrate chỉ dùng cho lệnh migration và không được cấu hình vào service.

## 4. Kiểm tra cấu hình, migrate và static files

Chạy các lệnh trong khi file môi trường đã được tạo. File cần giữ định dạng biến môi trường `KEY=value`; không in nội dung secrets ra log/chat.

```bash
sudo systemd-run --wait --pipe --collect --property=User=fitmeal --property=WorkingDirectory=/srv/fitmeal/app --property=EnvironmentFile=/etc/fitmeal/fitmeal.env /srv/fitmeal/venv/bin/python manage.py check --deploy
sudo systemd-run --wait --pipe --collect --property=User=fitmeal --property=WorkingDirectory=/srv/fitmeal/app --property=EnvironmentFile=/etc/fitmeal/fitmeal-migrate.env /srv/fitmeal/venv/bin/python manage.py migrate --noinput
sudo systemd-run --wait --pipe --collect --property=User=fitmeal --property=WorkingDirectory=/srv/fitmeal/app --property=EnvironmentFile=/etc/fitmeal/fitmeal.env /srv/fitmeal/venv/bin/python manage.py collectstatic --noinput
sudo systemd-run --wait --pipe --collect --property=User=fitmeal --property=WorkingDirectory=/srv/fitmeal/app --property=EnvironmentFile=/etc/fitmeal/fitmeal.env /srv/fitmeal/venv/bin/python manage.py createsuperuser
```

Không tiếp tục nếu `check --deploy` có lỗi, database không kết nối được, hoặc migration/static files thất bại. Các cảnh báo `security.W005`/`security.W021` liên quan đến HSTS subdomain/preload cần được xem xét theo điều kiện nêu trên; không bật các tùy chọn đó chỉ để xóa cảnh báo. Kiểm tra quyền đọc cấu hình và quyền ghi `media`, `staticfiles`, `backups`. Không chạy `flush` trên production.

## 5. Cài Gunicorn bằng systemd

Từ thư mục gốc repo, cài service file:

```bash
sudo install -m 644 deploy/systemd/fitmeal.service /etc/systemd/system/fitmeal.service
sudo systemctl daemon-reload
sudo systemctl enable --now fitmeal
sudo systemctl status fitmeal --no-pager
sudo journalctl -u fitmeal -n 100 --no-pager
```

Gunicorn chỉ nghe trên `127.0.0.1:8000`; không mở cổng này ra Internet. `systemd` chạy dưới user `fitmeal`, dùng file secrets ở `/etc/fitmeal/fitmeal.env` và giới hạn quyền ghi vào thư mục dữ liệu cần thiết. Nginx chỉ có quyền traverse thư mục ứng dụng và đọc `staticfiles`/`media`; không có quyền ghi vào chúng.

## 6. Cấp HTTPS và bật Nginx

Trước tiên xác nhận DNS của domain trỏ đúng VPS và cổng 80/443 được phép qua firewall. Nếu bật UFW, cho phép SSH trước khi bật firewall để tránh tự khóa phiên quản trị. Tạo webroot xác thực Let's Encrypt và bật cấu hình HTTP tạm (thay domain; nếu không dùng `www`, bỏ `-d www.example.com` và bỏ hostname `www` khỏi cấu hình Nginx/Django):

```bash
sudo install -d -o root -g www-data -m 0755 /var/www/certbot
sudo ufw allow 'Nginx Full'
sudo install -m 644 deploy/nginx/fitmeal-acme.conf /etc/nginx/sites-available/fitmeal
sudo ln -s /etc/nginx/sites-available/fitmeal /etc/nginx/sites-enabled/fitmeal
sudo nginx -t
sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/certbot -d example.com -d www.example.com
```

Trong `deploy/nginx/fitmeal.conf`, thay mọi `example.com` bằng domain thật rồi cài và bật cấu hình:

```bash
sudo install -m 644 deploy/nginx/fitmeal.conf /etc/nginx/sites-available/fitmeal
sudo nginx -t
sudo systemctl reload nginx
```

Nếu file cấu hình mặc định Nginx chiếm domain/cổng, tắt symlink mặc định sau khi kiểm tra nó không phục vụ website khác. Cấu hình HTTPS vẫn phục vụ đường dẫn ACME ở cổng 80 để Certbot tự gia hạn bằng webroot; xác minh bằng `sudo certbot renew --dry-run`. Không bật HSTS trước khi HTTPS được kiểm tra hoạt động.

## 7. Xác minh sau deploy và cập nhật phiên bản

- Mở `https://example.com/` và `https://example.com/healthz/`; health check phải trả HTTP 200.
- Đăng nhập quản trị, kiểm tra static/media, đăng ký/đăng nhập và các luồng đơn hàng bằng dữ liệu staging.
- Kiểm tra log bằng `sudo journalctl -u fitmeal -f` và `sudo tail -f /var/log/nginx/error.log`.
- Trước mỗi cập nhật: chụp backup database/media, ghi phiên bản hiện tại, triển khai commit/tag mới, cài dependency nếu đổi, chạy `check --deploy` bằng `fitmeal.env`, chạy `migrate` bằng `fitmeal-migrate.env`, collectstatic, restart service và smoke test. Có quy trình rollback code; không rollback database bằng cách xóa dữ liệu.
- Các lịch `expire_pending_payments`, `finalize_delivery_confirmations`, `purge_expired_order_pii` và backup/giám sát cần được cấu hình ở mục vận hành; không coi việc service chạy là đã hoàn tất vận hành production.

Không chạy Locust trực tiếp trên production bằng kịch bản COD hiện tại. Chạy tải trên staging với database và dữ liệu riêng.
