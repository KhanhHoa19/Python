# S01 – Kệ sách của tôi

**Mục đích:** xem, tìm, lọc, mở và quản lý sách của mình theo tiến độ nghe.  **Màn hình:** *Kệ Sách Của Tôi* (sidebar).

## Bố cục
```
┌ Kệ sách của tôi ───────────────────────────────────── [ + Thêm tài liệu ] ┐
│ ( Đang nghe dở 2 | Chưa nghe 3 | Đã hoàn thành 1 | Yêu thích 1 )          │
│ 🔍 [ Tìm theo tên sách hoặc tác giả… ]  [ Tất cả ▼ ] [ Đọc gần đây ▼ ]      │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                                      │
│ │  bìa 3:4 │ │  bìa 3:4 │ │  bìa 3:4 │   ♥ góc trên phải, chip "Hệ thống"   │
│ │          │ │          │ │          │                                      │
│ ├──────────┤ ├──────────┤ ├──────────┤                                      │
│ │ CÔNG NGHỆ│ │ KHÁC     │ │          │                                      │
│ │ Python   │ │ Ghi chép │ │          │                                      │
│ │ ▓▓▓░░ 48%│ │ ░░░░ 0%  │ │          │                                      │
│ │[Nghe tiếp]│ │[Bắt đầu nghe]│        │                                      │
│ │ ✎ ❝ ⬇ ✔ 🗑│ │          │ │          │                                      │
│ └──────────┘ └──────────┘ └──────────┘                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```
Dưới tiêu đề (và dưới 4 tab) có **dãy tag chủ đề** gồm `Tất cả` + 15 thể loại mặc định (Tiểu thuyết, Trinh thám, Khoa học, Lịch sử, Kỹ năng sống, Tâm lý, Triết học, Công nghệ, Kinh tế, Tình cảm, Kinh dị, Phiêu lưu, Thiếu nhi, Truyện ngắn, Khác), tự xuống dòng khi hẹp. Bấm một tag để lọc; bấm lại để bỏ lọc. Cùng một dãy tag có ở Khám phá và lựa chọn dùng chung giữa hai màn. Admin thêm/sửa/xóa tag ở Quản Trị (S11); "Khác" luôn ở cuối và không xóa được.

## Kệ sách gồm những gì
- **Sách của tôi** (tự tải lên) luôn nằm trên kệ.
- **Sách hệ thống** (admin đăng) chỉ nằm trên kệ **sau khi bấm "Thêm vào kệ"** ở Khám phá (hoặc khi bắt đầu nghe/ yêu thích). `Gỡ khỏi kệ` bỏ nó đi và quên tiến độ.

## 4 tab theo trạng thái (số bên cạnh là số sách khớp bộ lọc hiện tại)
| Tab | Điều kiện |
|---|---|
| **Đang nghe dở** | đã phát ít nhất một câu, chưa tới cuối. Tự chuyển vào khi phát câu đầu. Có thanh tiến độ và nút `Nghe tiếp` |
| **Chưa nghe** | sách mới tải lên / mới thêm vào kệ, chưa phát |
| **Đã hoàn thành** | tiến độ 100% (nghe tới câu cuối) hoặc bấm `Đánh dấu đã nghe xong` |
| **Yêu thích** | gắn trái tim. Độc lập với trạng thái: một cuốn vừa *đang nghe dở* vừa *yêu thích* hiện ở cả hai tab |
Mở màn lần đầu: vào tab đầu tiên có sách (theo thứ tự trên). Nghe lại sách đã hoàn thành từ đầu thì nó trở về *Đang nghe dở*.

## Thành phần
| Thành phần | Mô tả |
|------------|-------|
| Ô tìm kiếm | Backend tìm theo tên + tác giả, **không phân biệt hoa thường và dấu**, nhiều từ thì sách phải chứa tất cả (thứ tự bất kỳ). Gõ xong ~0,3 giây mới gửi |
| Nguồn | `Tất cả` · `Sách hệ thống` · `Sách của tôi` |
| Sắp xếp | `Đọc gần đây` · `Tên A→Z` · `Ngày thêm` · `Tiến độ` |
| Ảnh bìa | PDF: trang đầu; sách khác: bìa tự tạo (màu theo thể loại, tên sách và tác giả); hoặc ảnh người dùng chọn (JPEG/PNG ≤ 2 MB). Không tải được ảnh thì hiện ô màu + chữ cái đầu |
| Trái tim | bật/tắt yêu thích |
| Nút chính | `Bắt đầu nghe` (chưa nghe) · `Nghe tiếp` (đang dở) · `Nghe lại` (đã xong) → mở S03 |
| Hành động phụ | `Sửa` (chỉ sách của tôi) · `Trích dẫn` (→ S06 đã lọc theo sách này) · `Xuất` (→ S07) · `Đánh dấu đã nghe xong` (khi đang dở) / `Nghe lại từ đầu` (khi đã xong) · `Xóa` (sách của tôi) hoặc `Gỡ khỏi kệ` (sách hệ thống) |
| `+ Thêm tài liệu` | Mở S02 |

## Sửa thông tin tài liệu
Hộp thoại: **Tên**, **Tác giả**, **Thể loại** (danh sách + `(Chưa phân loại)`), **Đổi ảnh bìa** (xem trước ngay). Hai nút `Hủy` / `Lưu`.
- Tên: cắt khoảng trắng đầu/cuối, gộp khoảng trắng liên tiếp, 1–255 ký tự. Rỗng → `Tên không được để trống.`; quá dài → `Tên tối đa 255 ký tự.` (không gọi API).
- Ảnh bìa không phải JPEG/PNG → `Ảnh bìa phải là JPEG hoặc PNG.`; quá 2 MB → `Ảnh bìa tối đa 2 MB.`
- Không đổi gì → đóng hộp thoại, không gọi API. Thành công: toast `Đã lưu "<tên>".`, thẻ cập nhật; nếu sách đang mở ở Phòng Đọc thì tiêu đề ở đó cũng đổi, không dừng phát. Lỗi từ máy chủ hiện trong hộp thoại.

## Trạng thái
- **loading:** vòng xoay `Đang tải…`.
- **trống có bộ lọc:** `Không tìm thấy sách phù hợp.` (gợi ý bỏ bớt bộ lọc).
- **tab Đang nghe dở trống nhưng kệ có sách:** `Bạn chưa nghe dở cuốn nào.` (gợi ý mở tab Chưa nghe).
- **kệ trống:** `Chưa có sách nào ở đây.` + nút `+ Thêm tài liệu` và gợi ý vào Khám phá.
- **error:** thanh đỏ + `Thử lại`.
- **xóa:** hộp xác nhận `Xóa "<tên>"? Trích dẫn (cả file âm thanh đã lưu), tiến độ và ảnh bìa của tài liệu cũng bị xóa. [Hủy] [Xóa]`.

## API
`GET /api/books?q&category&source&status&sort` (trả mỗi sách kèm `progress`, `category`, `cover_url`) · `GET /api/books/counts?q&category&source` · `PATCH /api/books/{id}` (`title` và/hoặc `category_id`) · `PUT /api/books/{id}/cover` · `PUT /api/books/{id}/favorite` · `PUT /api/books/{id}/status` (`completed` | `unread`) · `POST|DELETE /api/books/{id}/shelf` · `DELETE /api/books/{id}` · `GET /api/categories` · `GET /api/covers/{tên}.jpg` (công khai).

## Ghi chú theo client
- **Web:** lưới thẻ responsive (`minmax(190px, 1fr)`), ảnh bìa tải lười (`loading="lazy"`).
- **Desktop:** danh sách thẻ ngang (ảnh bìa 84×112 bên trái); ảnh bìa tải ở luồng nền, trong lúc chờ hiện ô màu + chữ cái đầu.

## Tiêu chí hoàn thành
- [ ] Bốn tab đếm đúng và đổi theo ô tìm kiếm, nguồn, thể loại.
- [ ] Tìm `dac nhan tam` ra "Đắc Nhân Tâm".
- [ ] Sách hệ thống chỉ hiện trên kệ sau khi thêm; gỡ đi thì tiến độ mất.
- [ ] PDF có bìa là trang đầu; sách khác có bìa tự tạo đủ dấu tiếng Việt.
