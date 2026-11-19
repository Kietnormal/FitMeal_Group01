# Giao diện FitMeal

Tài liệu ngắn cho cả nhóm khi sửa hoặc thêm giao diện.

## File chính

| File | Vai trò |
|---|---|
| `static/css/fitmeal.css` | Hệ thống thiết kế: màu, font, nút, form, header/footer, trang chủ, thực đơn, các trang khách hàng và khu vực nhân viên. Được nạp **sau cùng** trên mọi trang. |
| `static/css/storefront.css` | Bố cục cũ của từng trang. Vẫn được dùng; `fitmeal.css` ghi đè phần hình thức. |
| `templates/base.html` | Font Google, bộ icon SVG dùng chung (`#fm-leaf`, `#fm-bag`, `#fm-plus`…), nạp CSS/JS. |
| `templates/core/store_base.html` | Thanh thông báo, header, menu di động, footer, giỏ hàng trượt cho mọi trang khách hàng. |
| `apps/core/templatetags/fitmeal.py` | `food_image` (ảnh sản phẩm hoặc ảnh tạm theo danh mục), `vnd` (định dạng 129.000₫), `energy_share` (% năng lượng cho nhãn dinh dưỡng). |
| `static/img/food/` | Ảnh tạm từ Unsplash, xem `CREDITS.md`. |

## Màu

| Token | Mã | Dùng cho |
|---|---|---|
| `--fm-green-800` | `#173a2e` | Màu thương hiệu: nút chính, hero, thanh bên nhân viên |
| `--fm-green-900` | `#0f2a21` | Footer, tiêu đề |
| `--fm-rice` | `#f3f5ee` | Nền trang |
| `--fm-yolk` | `#f0b43c` | Chỉ để nhấn: số protein, nút chính trên nền xanh, focus trên nền tối |
| `--fm-chili` | `#c4442c` | Tạm hết món, giảm giá, lỗi |
| `--fm-muted` | `#56645b` | Chữ phụ (tương phản 5,7:1 trên nền trang) |

Không dùng mã màu trực tiếp trong template; thêm token vào `:root` nếu cần màu mới.

## Font

- Tiêu đề: **Fraunces** (class `fm-display`), có dấu tiếng Việt đầy đủ.
- Nội dung, nút, số liệu: **Be Vietnam Pro**. Số tiền và macro dùng `font-variant-numeric: tabular-nums`.

## Quy ước

- Nhãn và nút viết thường, viết hoa chữ đầu (không viết IN HOA toàn bộ).
- Icon là SVG từ sprite trong `base.html`: `<svg class="fm-i" aria-hidden="true"><use href="#fm-plus"/></svg>`. Không dùng emoji làm icon.
- Giá luôn qua filter `vnd`: `{{ product.price|vnd }}`.
- Ảnh sản phẩm luôn qua `food_image` để có ảnh tạm khi chưa tải ảnh thật.
- Kiểm tra trên 390px (điện thoại) và 1440px (máy tính); trang không được cuộn ngang.

## Ảnh

Ảnh trong `static/img/food/` là ảnh tạm. Khi có ảnh chụp sản phẩm thật, tải lên ở trang
"Thêm món mới" hoặc Django admin; thẻ sản phẩm sẽ tự dùng ảnh thật thay cho ảnh tạm.
