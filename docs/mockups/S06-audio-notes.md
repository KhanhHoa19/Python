# S06 – Ghi chú âm thanh

**Mục đích:** xem lại, nghe lại và quản lý các đoạn văn đã đánh dấu khi đọc.  **Tab:** Thư Viện & Ghi Chú → mục *Ghi chú*.

## Bố cục
```
┌ Thư Viện & Ghi Chú ───────────────────────────────────────────┐
│ [ Tài liệu ]  [ Ghi chú ]                                      │
│ Tài liệu: [ Tất cả ▼ ]   🔍 [ Tìm trong ghi chú… ]             │
│ ─────────────────────────────────────────────────────────────  │
│ ┌────────────────────────────────────────────────────────┐    │
│ │ 📄 Giáo trình Python · câu 120 · 25/11/2026 21:12       │    │
│ │ “Kiểu dữ liệu được xác định khi gán giá trị.”           │    │
│ │ 📝 Nhớ: Python là ngôn ngữ kiểu động.                   │    │
│ │ [ ▶ Nghe lại ]  [ Đến câu này ]  [ Sửa ]  [ Xóa ]       │    │
│ └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘

┌ Ghi chú mới (từ S03) ──────────────────────────── ✕ ┐
│ Đoạn đã chọn: “Kiểu dữ liệu được xác định khi gán…”    │
│ Ghi chú của bạn: [                                  ]  │
│                                   [ Hủy ] [ Lưu ghi chú ] │
└────────────────────────────────────────────────────────┘
```

## Thành phần
| Thành phần | Mô tả |
|------------|-------|
| Bộ lọc | Theo tài liệu; tìm trong đoạn trích và nội dung ghi chú |
| Thẻ ghi chú | Tên tài liệu, số câu, thời gian tạo, đoạn trích, nội dung ghi chú |
| `Nghe lại` | Phát audio của đoạn đã chọn (lấy từ cache, không gọi lại API nếu đã có) |
| `Đến câu này` | Mở S03 tại đúng câu, không tự phát |
| `Sửa` / `Xóa` | Sửa nội dung ghi chú; xóa có xác nhận |

## Trạng thái
- **empty:** `Chưa có ghi chú. Hãy bôi đen một đoạn trong Phòng Đọc để tạo.`
- **loading / error** như README.
- Hộp tạo ghi chú: nút `Lưu ghi chú` khóa khi chưa chọn đoạn; ghi chú trống vẫn lưu được (chỉ đánh dấu).

## API *(đều mới)*
`GET /api/notes?book_id=` · `POST /api/notes` (`book_id`, `sentence_index`, `start_offset`, `end_offset`, `note_text`) · `PATCH /api/notes/{id}` · `DELETE /api/notes/{id}` · `GET /api/notes/{id}/audio`.

## Ghi chú theo client
- **Web:** lấy đoạn chọn bằng `window.getSelection()`, tính `start/end_offset` trong câu.
- **Desktop:** lấy bằng `textbox.tag_ranges("sel")`.

## Tiêu chí hoàn thành
- [ ] Tạo ghi chú từ S03 và thấy ngay ở S06.
- [ ] `Nghe lại` phát đúng đoạn đã chọn, `Đến câu này` đúng vị trí.
- [ ] Hai client hiển thị cùng danh sách ghi chú.
