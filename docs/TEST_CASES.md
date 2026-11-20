# Kế hoạch kiểm thử FitMeal

## Phạm vi và cách chạy

Chạy toàn bộ kiểm thử Django trước mỗi lần phát hành:

```powershell
python manage.py test
```

Nếu `.env` đang chọn MySQL nhưng máy chưa cài `mysqlclient`, có thể chạy test bằng SQLite tạm trong PowerShell:

```powershell
$previousDatabaseUrl = $env:DATABASE_URL
$env:DATABASE_URL = "sqlite:///:memory:"
python manage.py test
$testExitCode = $LASTEXITCODE
if ($null -eq $previousDatabaseUrl) {
    Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
} else {
    $env:DATABASE_URL = $previousDatabaseUrl
}
```

Kết quả chạy trên máy phát triển ngày 20/11/2026: **183 test Django đạt** bằng SQLite in-memory. Các test cổng thanh toán dùng mock; chưa thay cho UAT thủ công.

Các test cổng thanh toán tự động dùng dữ liệu giả lập/mock, không gửi giao dịch thật đến VNPay hoặc ngân hàng. Các dòng ghi “Chưa chạy” là kiểm thử thủ công, cần staging và tài khoản sandbox. Không dùng thẻ thật hoặc dữ liệu khách hàng thật. Mục kiểm thử đăng nhập ngoài giờ ca đang bị chặn vì ứng dụng chưa có chức năng/lịch ca.

### Kiểm thử giao diện bằng Playwright

Kích hoạt môi trường Python đã cài `requirements.txt`, rồi chạy tại thư mục gốc:

```powershell
npm ci
npx playwright install chromium
npm run test:e2e:slow
```

Lệnh trên mở Chromium và làm chậm khoảng 700 ms giữa các thao tác để dễ quan sát hai luồng: tìm món/quản lý giỏ hàng; đăng ký tài khoản khách mới, thêm món, đặt COD rồi xác nhận đơn xuất hiện trong lịch sử tài khoản. Dùng `npm run test:e2e:ui` để mở Playwright UI và xem/chạy lại từng bước; `npm run test:e2e:headed` chạy có cửa sổ nhưng ở tốc độ bình thường, còn `npm run test:e2e` chạy headless. Django tự khởi động cục bộ trên cổng 8765 bằng SQLite riêng, nạp một sản phẩm giả và tạo lại database mỗi lần chạy. Đơn COD chỉ được tạo trong database kiểm thử; không gọi cổng thanh toán thật.

| Mã | Chức năng | Các bước | Kết quả mong đợi | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|---|
| TC-001 | Tải danh sách món | Mở trang thực đơn khi có sản phẩm đang bán | Món, giá và trạng thái sẵn có hiển thị đúng | Có test API danh sách sản phẩm | Đạt tự động |
| TC-002 | Chi tiết món | Mở chi tiết một món đang bán | Tên, giá, thành phần và thông tin món chính xác | Có test API chi tiết sản phẩm | Đạt tự động |
| TC-003 | Tìm món trên giao diện | Tìm bằng tên, lọc danh mục, xóa từ khóa | Danh sách khớp tìm kiếm/lọc; trạng thái rỗng dễ hiểu | Playwright xác nhận tìm theo tên, trạng thái rỗng và xóa từ khóa; chưa kiểm tra lọc danh mục | Đạt tự động · lọc danh mục chưa bao phủ |
| TC-004 | Món tạm ngừng bán | Tạm dừng món rồi thử đặt qua checkout | Không thể tạo đơn chứa món không bán | Có test checkout từ chối món không khả dụng | Đạt tự động |
| TC-005 | Thêm món vào giỏ | Thêm một món từ thực đơn | Giỏ hiện đúng tên, đơn giá và số lượng | Playwright xác nhận món và số lượng hiển thị trong giỏ | Đạt tự động |
| TC-006 | Sửa/xóa giỏ hàng | Tăng giảm số lượng, xóa món, tải lại trang | Tổng tiền cập nhật; không còn món đã xóa | Playwright xác nhận tăng số lượng, cập nhật tạm tính và xóa món; chưa kiểm tra giảm số lượng/tải lại trang | Đạt tự động · giảm/tải lại chưa bao phủ |
| TC-007 | Đặt nhiều món | Gửi đơn có nhiều món và dòng trùng sản phẩm | Server gộp dòng trùng và lưu đúng số lượng từng món | Có test gộp dòng đơn trùng | Đạt tự động |
| TC-008 | Chống sửa giá phía trình duyệt | Gửi giá thấp hơn giá trong cơ sở dữ liệu | Server vẫn tính bằng giá chuẩn của sản phẩm | Có test bỏ qua giá client gửi lên | Đạt tự động |
| TC-009 | Tính tiền đơn | Đặt hai món giá 100.000₫, mỗi món số lượng 2 | Tạm tính, phí giao và tổng đơn khớp quy tắc | Có test tính giá và snapshot món | Đạt tự động |
| TC-010 | Ngưỡng miễn phí giao | Đặt đơn có tạm tính đạt ngưỡng miễn phí | Phí giao bằng 0; tổng bằng tạm tính | Có test ngưỡng miễn phí | Đạt tự động |
| TC-011 | Phí đồ khô nội thành | Đặt đồ khô với khối lượng/khu vực TP.HCM | Phí tính theo khối lượng và mức nội thành | Có test tính phí đồ khô TP.HCM | Đạt tự động |
| TC-012 | Phí đồ khô liên tỉnh | Đặt đồ khô giao tỉnh khác | Phí tính theo khối lượng và mức liên tỉnh | Có test tính phí toàn quốc | Đạt tự động |
| TC-013 | Giới hạn món tươi | Đặt món tươi đến ngoài TP.HCM | Checkout từ chối đơn và không lưu đơn | Có test từ chối khu vực ngoài phạm vi | Đạt tự động |
| TC-014 | Đơn gắn tài khoản | Khách đăng nhập rồi đặt hàng | Đơn được liên kết đúng tài khoản khách | Có test checkout đã đăng nhập | Đạt tự động |
| TC-015 | Thanh toán COD | Chọn COD và đặt đơn | Đơn được lưu; không tạo giao dịch online | Có test COD không tạo payment transaction | Đạt tự động |
| TC-016 | Mã QR chuyển khoản | Đặt đơn, chọn chuyển khoản | Hiện VietQR đúng ngân hàng, số tài khoản, số tiền; nội dung có tiền tố ngân hàng yêu cầu (`SEVQR FM...`) | Có test trang hướng dẫn và URL VietQR | Đạt tự động |
| TC-017 | Webhook có tiền tố ngân hàng | SePay gửi nội dung `SEVQR FM...` (có hoặc không có dấu cách) | Mã đơn vẫn được nhận ra; giao dịch chuyển sang đã thanh toán | Có test hai dạng nội dung | Đạt tự động |
| TC-018 | Trang thanh toán thành công | Thanh toán chuyển khoản được xác nhận | Trang chờ tự chuyển sang trang hoàn tất: mã đơn, số tiền, tóm tắt đơn, 4 bước tiếp theo | Có test trang chờ (vòng xoay) và trang hoàn tất | Đạt tự động |
| TC-019 | Tiến trình đơn sau thanh toán | Nhân viên chuyển đơn sang "Đang chuẩn bị" rồi mở lại trang hoàn tất | Bước 1–2 hoàn tất, bước 3 là bước hiện tại | Có test trạng thái từng bước | Đạt tự động |
| TC-020 | Chuyển khoản thật qua SePay | Quét VietQR bằng app ngân hàng trên bản deploy, chuyển đúng số tiền và nội dung | Đơn tự chuyển sang đã thanh toán, không cần thao tác tay | Đã chạy thủ công trên web ngày 20/11/2026 với VietinBank | Đạt thủ công |
| TC-021 | Phương thức thanh toán đã gỡ | Gửi đơn với phương thức `momo` | Bị từ chối; không tạo đơn hay giao dịch | Có test từ chối phương thức không hỗ trợ | Đạt tự động |
| TC-022 | Quên mật khẩu bằng OTP | Nhập email, nhận mã 6 số, nhập mã và mật khẩu mới | Đổi mật khẩu thành công; mã hết hạn sau 10 phút, dùng một lần, khoá sau 5 lần sai; email không đăng ký nhận cùng phản hồi | Có test Django và Playwright cho luồng đầy đủ | Đạt tự động |
| TC-023 | Miễn phí giao hàng | Tắt `SHIPPING_FEES_ENABLED` rồi đặt đơn đồ tươi và đồ khô | Phí giao bằng 0, tổng bằng tạm tính; giỏ hàng hiện "Miễn phí" | Có test API đặt hàng và giao diện | Đạt tự động |
| TC-024 | IPN VNPay lặp/sai dữ liệu | Gửi sai số tiền rồi gửi IPN hợp lệ hai lần | Sai dữ liệu bị từ chối; IPN hợp lệ lặp không nhân đôi thanh toán | Có test VNPay sai số tiền và lặp IPN | Đạt tự động |
| TC-025 | Webhook chuyển khoản | Gửi thiếu API key, sai số tiền, rồi sự kiện đúng | Thiếu/sai bị từ chối; sự kiện hợp lệ khớp mã, tài khoản và tiền | Có test SePay cả ba trường hợp | Đạt tự động |
| TC-026 | Thanh toán quá hạn | Cho giao dịch online hết hạn rồi chạy tác vụ | Giao dịch hết hạn, đơn hủy, kho được hoàn nếu đã trừ | Có test hết hạn và hoàn kho | Đạt tự động |
| TC-027 | Khách hủy đơn chờ | Khách yêu cầu hủy đơn pending | Đơn hủy theo chính sách và ghi nhận lý do | Có test khách hủy đơn pending | Đạt tự động |
| TC-028 | Khách hủy ngay sau khi NV xác nhận | NV xác nhận; khách gửi hủy ngay; thử cập nhật tiếp trạng thái | Đơn hủy hợp lệ; cập nhật đến sau không hồi sinh đơn | Có test tuần tự hai thao tác; chưa mô phỏng đồng thời nhiều kết nối | Đạt tự động · race thật chưa thử |
| TC-029 | NV bán hàng gọi URL hủy | Đăng nhập NV bán hàng, POST trực tiếp URL hủy quản lý | HTTP 403 và đơn không bị hủy | Có test POST URL trực tiếp trả 403 | Đạt tự động |
| TC-030 | Chuyển trạng thái đơn | NV chuyển đơn qua bước được phép; thử bước không hợp lệ | Bước hợp lệ được lưu; bước không hợp lệ giữ nguyên trạng thái | Có test luồng NV và chặn hủy qua cập nhật trạng thái | Đạt tự động |
| TC-031 | Duyệt hủy sau khi gọi | NV ghi nhận hai lần không liên lạc; quản lý từ chối/duyệt | Yêu cầu chuyển đúng hàng đợi; quyết định có lý do | Có test hai lần gọi và quyết định quản lý | Đạt tự động |
| TC-032 | Phân quyền workspace | Khách hoặc nhân viên không có vai trò mở workspace/endpoint nhân viên | Trả 403; dữ liệu đơn không đổi | Có test khách và nhân viên thiếu vai trò bị từ chối | Đạt tự động |
| TC-033 | Khách xác nhận đã nhận | Đơn chờ xác nhận; khách xác nhận trong hạn | Đơn chuyển hoàn tất, ghi thời điểm/phương thức | Có test xác nhận của khách | Đạt tự động |
| TC-034 | Giao thất bại/khiếu nại giao | Khách báo chưa nhận; quản lý chọn hướng xử lý | Yêu cầu vào hàng đợi; trạng thái đổi theo quyết định | Có test báo lỗi và xử lý quản lý | Đạt tự động |
| TC-035 | Khiếu nại/đổi trả trong 7 ngày | Chủ đơn gửi từng loại yêu cầu trong thời hạn; thử gửi lại khi Quản lý đã từ chối đổi/trả | Yêu cầu được tạo trong hạn; sau khi từ chối đổi/trả, đơn không nhận thêm khiếu nại/đổi trả qua giao diện hoặc endpoint | Có test từ chối qua luồng Quản lý, ẩn biểu mẫu và chặn POST gửi lại cả hai loại | Đạt tự động |
| TC-036 | Hết hạn xem PII | Sau 7 ngày, quản lý nhập lý do mở dữ liệu | Dữ liệu hiện có no-store; lần xem có audit log; NV bán hàng bị từ chối | Có test quyền, lý do, log và cache header | Đạt tự động |
| TC-037 | Xóa PII sau 12 tháng | Chạy purge với nhiều đơn hết hạn | Xóa định danh/nội dung; giữ khu vực; mã theo dõi cũ hết hiệu lực | Có test purge nhiều đơn và giữ quận/tỉnh | Đạt tự động |
| TC-038 | Không bán âm kho | Đặt vượt tồn kho đồ khô nhiều lần | Tồn không âm; phần thiếu thành yêu cầu bổ sung hàng | Có test tồn bằng 0 và tạo cảnh báo thiếu | Đạt tự động · hỗ trợ backorder |
| TC-039 | Hủy đơn hoàn kho một lần | Hủy đơn đã trừ kho rồi gửi lại yêu cầu hủy | Tồn được cộng lại đúng một lần | Có test hoàn kho idempotent | Đạt tự động |
| TC-040 | Đăng nhập sai liên tục | Gửi 5 mật khẩu sai từ cùng IP | IP tạm khóa và sự kiện đăng nhập được ghi | Có test khóa IP và nhật ký | Đạt tự động |
| TC-041 | MFA nhân viên | Đăng nhập nhân viên đã bật TOTP, thử trước/sau mã đúng | Chưa xác minh không vào workspace; mã đúng được vào | Có test luồng xác minh MFA | Đạt tự động |
| TC-042 | Đăng nhập ngoài giờ ca | Thử đăng nhập ngoài khung ca đã phân công | Mong đợi bị chặn và ghi log | Chưa có tính năng/lịch ca để thực hiện | Chưa hỗ trợ · cần chốt nghiệp vụ |
| TC-043 | CSV chống công thức | Xuất báo cáo có chuỗi bắt đầu bằng `=`, `+`, `-`, `@` | Giá trị được escape, không chạy công thức trong spreadsheet | Có test escape dữ liệu CSV | Đạt tự động |
| TC-044 | Đăng ký và đặt đơn COD trên giao diện | Tạo tài khoản mới, thêm món, nhập địa chỉ, đồng ý chính sách và đặt COD | Tài khoản được đăng nhập; đơn pending gắn đúng tài khoản và hiện trong lịch sử | Playwright tạo đơn trả HTTP 201, phương thức COD và xác nhận mã đơn trong lịch sử tài khoản | Đạt tự động |
| UAT-001 | Người dùng thử 1 | Tự tìm món, thêm giỏ, sửa số lượng, đặt COD trên staging | Hoàn tất không cần hỗ trợ; ghi lại điểm vướng | Chưa có người thử | Chưa chạy · cần người thử |
| UAT-002 | Người dùng thử 2 | Đặt đơn chuyển khoản bằng mã VietQR và quay lại trang đơn hàng | Thanh toán/điều hướng dễ hiểu; trạng thái nhất quán | Chưa có người thử | Chưa chạy · cần người thử |
| UAT-003 | Người dùng thử 3 | Xem lịch sử, gửi khiếu nại hoặc yêu cầu đổi/trả | Tìm được chức năng; hiểu rõ hạn 7 ngày và trạng thái | Chưa có người thử | Chưa chạy · cần người thử |
| UAT-004 | Người dùng thử 4 | Dùng điện thoại đặt hàng và theo dõi đơn | Không lỗi bố cục/điều khiển trên màn hình nhỏ | Chưa có người thử | Chưa chạy · cần người thử |
| UAT-005 | Người dùng thử 5 | Tự hoàn tất các tác vụ trên; không được hướng dẫn | Ghi thời gian, lỗi gặp và đề xuất cải thiện | Chưa có người thử | Chưa chạy · cần người thử |

### Ghi nhận kiểm thử người dùng

Thực hiện các dòng UAT trên staging với 3–5 người, không dùng thanh toán thật. Mỗi người ghi lại thiết bị/trình duyệt, tác vụ hoàn thành, thời gian, lỗi hoặc điểm gây nhầm lẫn. Không đánh dấu UAT đạt cho đến khi đã có kết quả thực tế; nếu phát hiện lỗi, tạo issue và chạy lại test liên quan sau khi sửa.
