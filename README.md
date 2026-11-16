# 🥗 FitMeal – Website Thương Mại Điện Tử

**FitMeal – Protein tiện lợi mỗi ngày**

## 📌 Giới thiệu dự án

FitMeal là dự án website thương mại điện tử theo mô hình B2C, chuyên kinh doanh thực phẩm giàu Protein, hướng đến người tập Gym, Fitness, Yoga, Pilates và những người quan tâm đến chế độ ăn uống lành mạnh.

Dự án tập trung cung cấp các sản phẩm dinh dưỡng tiện lợi, giúp khách hàng tiết kiệm thời gian chuẩn bị bữa ăn, dễ dàng kiểm soát lượng Calo và Protein trong chế độ ăn hằng ngày.

## 🛒 Danh mục sản phẩm

- **Ức gà Sous-vide:** Ức gà nấu chậm với nhiều hương vị như tiêu đen thảo mộc, chanh sả ớt và cà ri xanh.
- **Thức uống Protein:** Clear Whey, Cold Brew Protein Coffee và trà sữa Protein.
- **Bánh Protein:** Brownie, Muffin Whey, Biscotti nguyên cám.
- **Thanh năng lượng:** Granola Bar, Energy Bar.
- **Thực phẩm Eat Clean:** Khô ức gà, ngũ cốc, các loại sốt ăn kiêng và bơ hạt.

## 🎯 Mục tiêu dự án

- Xây dựng nền tảng trực tuyến giới thiệu và kinh doanh sản phẩm FitMeal.
- Cung cấp thông tin sản phẩm, thành phần dinh dưỡng và chỉ số Macro minh bạch.
- Hỗ trợ khách hàng tìm hiểu, lựa chọn sản phẩm phù hợp với nhu cầu dinh dưỡng.
- Phát triển các chương trình combo, ưu đãi và chăm sóc khách hàng.
- Tăng độ nhận diện thương hiệu FitMeal trên nền tảng số.

## 👥 Khách hàng mục tiêu

- Người tập Gym, Fitness và các môn thể thao.
- Người muốn tăng cơ, giảm mỡ hoặc kiểm soát cân nặng.
- Sinh viên và nhân viên văn phòng bận rộn.
- Người quan tâm đến thực phẩm Eat Clean và lối sống lành mạnh.

## 🌟 Giá trị nổi bật

- Thực phẩm giàu Protein, tiện lợi và đa dạng hương vị.
- Ứng dụng phương pháp nấu chậm Sous-vide cho sản phẩm ức gà.
- Minh bạch thông tin dinh dưỡng như Protein, Carb, Fat và Calories.
- Đa dạng sản phẩm và combo theo nhu cầu khách hàng.
- Kết hợp website với các kênh bán hàng trực tuyến và mạng xã hội.

## 📚 Thông tin dự án

**Tên dự án:** FitMeal

**Loại dự án:** Website thương mại điện tử (E-commerce)

**Mô hình kinh doanh:** B2C (Business to Consumer)

**Lĩnh vực:** Thực phẩm dinh dưỡng, Eat Clean, Healthy Food

**Nhóm thực hiện:** Nhóm 1 – Thương mại điện tử

**Mục đích:** Dự án học tập và phát triển website thương mại điện tử cho thương hiệu FitMeal.

## Chạy backend với MySQL (Windows)

Django dùng ORM và migrations để tạo bảng MySQL. SQLite hiện tại không tự chuyển dữ liệu
sang MySQL; sau khi chuyển database, hãy tạo lại tài khoản quản trị và nhập lại các sản phẩm
cần giữ.

1. Cài và khởi động MySQL Server. Mở PowerShell tại thư mục dự án, sau đó đăng nhập bằng
   tài khoản quản trị MySQL:

   ```powershell
   & 'C:\Program Files\MySQL\MySQL Server 26.10\bin\mysql.exe' -u root -p
   ```

2. Tạo database và tài khoản riêng cho ứng dụng trong MySQL:

   ```sql
   CREATE DATABASE fitmeal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'fitmeal_app'@'127.0.0.1' IDENTIFIED BY 'replace-with-a-strong-password';
   GRANT ALL PRIVILEGES ON fitmeal.* TO 'fitmeal_app'@'127.0.0.1';
   ```

   Thay mật khẩu ví dụ bằng mật khẩu riêng của bạn. Không dùng tài khoản `root` trong ứng dụng.

3. Sao chép `.env.example` thành `.env`, giữ các thiết lập khác và cập nhật `DATABASE_URL`:

   ```text
   DATABASE_URL=mysql://fitmeal_app:your-password@127.0.0.1:3306/fitmeal
   ```

   Nếu mật khẩu chứa ký tự đặc biệt trong URL (ví dụ `@`, `:` hoặc `/`), hãy URL-encode
   phần mật khẩu. Không commit file `.env`.

4. Cài dependencies, tạo bảng, tạo tài khoản Django Admin và chạy website:

   ```powershell
   & 'C:\Users\admin\fitmeal\.venv-1\Scripts\python.exe' -m pip install -r requirements.txt
   & 'C:\Users\admin\fitmeal\.venv-1\Scripts\python.exe' manage.py migrate
   & 'C:\Users\admin\fitmeal\.venv-1\Scripts\python.exe' manage.py createsuperuser
   & 'C:\Users\admin\fitmeal\.venv-1\Scripts\python.exe' manage.py runserver
   ```

   Mở `http://127.0.0.1:8000/admin/` để thêm sản phẩm. Nếu đang dùng một virtual
   environment khác, thay đường dẫn Python bằng đường dẫn môi trường đó.

## Tài khoản khách hàng và quyền quản trị

- Khách hàng đăng ký tại trang **Tài khoản**; họ có thể đăng nhập bằng email hoặc số điện
  thoại, cập nhật hồ sơ, lưu nhiều địa chỉ giao hàng, xem lịch sử đơn hàng và điểm thưởng.
- Trong mục **Đánh giá đơn hàng**, khách có thể chấm 1–5 sao và nhận xét cho đơn đã hoàn tất,
  sau đó sửa lại đánh giá. Mục **Email liên hệ** mở ứng dụng email đến `hello@fitmeal.vn`.
- Điểm được cộng sau khi đơn hoàn tất: 1 điểm cho mỗi 10.000đ tiền món (không tính phí giao
  hàng). Nếu đơn đã nhận điểm bị hủy, hệ thống ghi giao dịch hoàn điểm.
- Khi đổi email, địa chỉ mới chỉ được áp dụng sau khi xác nhận liên kết. Ở môi trường phát
  triển, liên kết được in trong terminal nhờ email backend console; để gửi email thật, cấu
  hình máy chủ SMTP trong `.env` theo các biến ở `.env.example`. Số điện thoại mới chưa được
  xác minh vì dự án chưa tích hợp SMS.
- Đăng ký công khai chỉ tạo tài khoản khách hàng. Không cấp quyền nhân viên/quản trị từ biểu mẫu đăng ký.
- Tạo quản trị viên ban đầu bằng `manage.py createsuperuser`. Sau khi đăng nhập dashboard,
  quản trị viên mở **Nhân viên** để cấp tài khoản với một trong ba vai trò **Quản trị viên**,
  **Quản lý** hoặc **NV bán hàng**. Mật khẩu được tạo ngẫu nhiên, chỉ hiển thị một lần và nhân viên
  bắt buộc đổi khi đăng nhập lần đầu. CCCD là trường tùy chọn, danh sách nhân viên
  chỉ hiển thị 4 số cuối. Chỉ cấp **Superuser status** cho tài khoản quản trị viên cần toàn quyền.
- Đơn đặt khi khách đăng nhập sẽ gắn với tài khoản đó. `/management/orders/` là khu vực làm việc
  chung theo vai trò: **NV bán hàng** xử lý đơn và chỉ xem thực đơn; **Quản lý** có thêm quản lý
  món/giá, tồn kho thủ công, báo cáo doanh thu 7 ngày và nhật ký thay đổi sản phẩm. Dashboard quản
  trị đầy đủ và quản lý nhân viên chỉ dành cho superuser.
- Khách có thể hủy đơn đang chờ xác nhận/đã xác nhận; đơn đang chuẩn bị hoặc sẵn sàng giao sẽ tạo
  yêu cầu để nhân viên gọi xác nhận, còn đơn đang giao không thể hủy. Nhân viên có thể ghi nhận
  yêu cầu hủy do hết món nhưng không tự duyệt; sau hai lần gọi không liên lạc được, yêu cầu được
  chuyển cho Quản lý. Quản lý duyệt/từ chối trong tab **Yêu cầu hủy**; hủy trực tiếp luôn yêu cầu
  nhập lý do. Checkout hiện chỉ hỗ trợ COD, chưa tích hợp thanh toán hoặc hoàn tiền trực tuyến.
- Số tồn kho cũ để trống cho đến khi được nhập; hệ thống chưa tự trừ kho khi khách đặt hàng.
  Thay đổi giá và tồn kho trong trang quản lý hoặc Django Admin được ghi lại. Báo cáo doanh thu
  chỉ tính đơn hoàn tất, theo ngày đặt; chưa có dữ liệu chi phí để tính lợi nhuận.
  `/admin/` vẫn là trang quản trị Django để quản lý dữ liệu hệ thống.
- Chức năng gửi email đặt lại mật khẩu chưa được cấu hình; hiện tại quản trị viên có thể
  đặt lại mật khẩu người dùng từ trang quản trị.

## Đăng ký và đăng nhập bằng Google

1. Tạo một OAuth Client ID kiểu **Web application** trong Google Cloud Console và cấu hình
   màn hình đồng ý OAuth.
2. Thêm origin `http://127.0.0.1:8000` và redirect URI
   `http://127.0.0.1:8000/accounts/google/login/callback/` vào OAuth client.
3. Điền Client ID và Client Secret vào `.env`:

   ```text
   GOOGLE_OAUTH_CLIENT_ID=your-client-id
   GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
   ```

4. Cài dependencies, chạy `manage.py migrate`, rồi khởi động lại Django.

Nút Google chỉ hiện khi cả hai giá trị đã được cấu hình. Người dùng mới qua Google được
tạo với quyền khách hàng thường; quyền quản trị vẫn phải được cấp riêng. Không gửi Client
Secret lên chat hoặc commit vào repository. Khi triển khai thật, thêm domain HTTPS của
website vào danh sách origin và redirect URI trong Google Cloud.
