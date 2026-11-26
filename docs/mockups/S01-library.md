# S01 – Thư viện tài liệu

**Mục đích:** xem, tìm, mở và xóa các tài liệu đã thêm.  **Tab:** Thư Viện & Ghi Chú → mục *Tài liệu*.

## Bố cục
```
┌ Thư Viện & Ghi Chú ───────────────────────────────────────────┐
│ [ Tài liệu ]  [ Ghi chú ]                                      │
│                                                                │
│ 🔍 [ Tìm theo tên…          ]  Sắp xếp: [ Đọc gần đây ▼ ]  [ + Thêm tài liệu ] │
│ ─────────────────────────────────────────────────────────────  │
│ ┌────────────────────────┐ ┌────────────────────────┐          │
│ │ 📄 Giáo trình Python   │ │ 📘 Cấu trúc dữ liệu    │          │
│ │ PDF · 1.240 câu        │ │ DOCX · 860 câu         │          │
│ │ ▓▓▓▓▓░░░░░ 48%         │ │ ░░░░░░░░░░ 0%          │          │
│ │ Đọc: 25/11/2026 21:10  │ │ Chưa đọc               │          │
│ │ [ Tiếp tục đọc ] [ ⋯ ] │ │ [ Bắt đầu đọc ] [ ⋯ ]  │          │
│ └────────────────────────┘ └────────────────────────┘          │
└────────────────────────────────────────────────────────────────┘
```

## Thành phần
| Thành phần | Mô tả |
|------------|-------|
| Ô tìm kiếm | Lọc theo tiêu đề, không phân biệt hoa thường/dấu |
| Sắp xếp | Đọc gần đây · Tên A→Z · Ngày thêm · Tiến độ |
| Thẻ tài liệu | Biểu tượng loại file, tiêu đề, loại file, số câu, thanh tiến độ %, lần đọc cuối |
| Nút chính | `Tiếp tục đọc` nếu tiến độ > 0, ngược lại `Bắt đầu đọc` → mở S03 đúng câu đã lưu |
| Menu `⋯` | `Ghi chú của tài liệu` (→ S06 đã lọc) · `Xuất audio` (→ S07) · `Xóa` |
| `+ Thêm tài liệu` | Mở S02 |

## Trạng thái
- **loading:** 6 thẻ khung xám.
- **empty:** `Chưa có tài liệu nào.` + nút `+ Thêm tài liệu`.
- **error:** thanh đỏ + `Thử lại`.
- **xóa:** hộp xác nhận `Xóa "<tên>"? Ghi chú và lịch sử đọc của tài liệu cũng bị xóa. [Hủy] [Xóa]`.

## API
`GET /api/books?limit&offset` · `DELETE /api/books/{id}` *(mới)* · `GET /api/bookmarks/{id}` (tiến độ).

## Ghi chú theo client
- **Web:** lưới thẻ responsive (3 cột ≥1100px, 2 cột ≥700px, 1 cột còn lại).
- **Desktop:** có thể dùng bảng (CTkScrollableFrame) mỗi dòng là một thẻ rút gọn; cột và nút giữ nguyên nội dung.

## Tiêu chí hoàn thành
- [ ] Hiển thị đúng 3 trạng thái loading/empty/error.
- [ ] Tìm kiếm và sắp xếp hoạt động cùng kết quả ở web và desktop.
- [ ] `Tiếp tục đọc` mở đúng câu bookmark.
- [ ] Xóa có xác nhận.
