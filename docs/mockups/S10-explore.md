# S10 – Khám phá

**Mục đích:** duyệt kho **sách hệ thống** (do admin đăng) và thêm vào kệ của mình.  **Màn hình:** *Khám Phá* (sidebar).

## Bố cục
```
┌ Khám phá ─────────────────────────────────── [ + Thêm sách hệ thống ]* ┐
│ Kho sách chung của hệ thống. Thêm vào kệ để lưu tiến độ nghe riêng...   │
│ 🔍 [ Tìm theo tên sách hoặc tác giả… ]                [ Mới nhất ▼ ]    │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                                  │
│ │  bìa 3:4 │ │  bìa 3:4 │ │  bìa 3:4 │                                  │
│ │ KINH TẾ  │ │ CÔNG NGHỆ│ │          │                                  │
│ │ Tên sách │ │ Tên sách │ │          │                                  │
│ │ Tác giả  │ │          │ │          │                                  │
│ │ 3 chương · 8.200 từ     │          │                                  │
│ │[Nghe ngay] ✓ Trong kệ  │[Nghe ngay][+ Thêm vào kệ]                    │
│ └──────────┘ └──────────┘ └──────────┘                                  │
└──────────────────────────────────────────────────────────────────────────┘
* chỉ admin
```

## Luật
- Chỉ liệt kê **sách công khai**; không bao giờ có sách riêng của ai (kể cả của admin).
- `+ Thêm vào kệ` đưa sách lên kệ (tab *Chưa nghe*), toast `Đã thêm "<tên>" vào kệ.` Sách đã có trên kệ hiện `✓ Trong kệ`.
- `Nghe ngay` tự thêm vào kệ (nếu chưa có) rồi mở Phòng Đọc ở câu đầu (hoặc đúng câu đã lưu nếu từng nghe).
- Tìm kiếm không phân biệt hoa thường/dấu, nhiều từ phải chứa tất cả. Sắp xếp: `Mới nhất` · `Tên A→Z`. Lọc theo dãy tag chủ đề ngay dưới tiêu đề (xem S01).
- **Admin** có thêm `+ Thêm sách hệ thống`: mở S02 với ô `Công khai cho mọi người` đã tích sẵn. Member không thấy nút này và không đăng được sách công khai (backend trả 403).
- Sách hệ thống chỉ admin được sửa/xóa; Member chỉ `Gỡ khỏi kệ`.

## Trạng thái
- **loading:** `Đang tải…`. **error:** `Thử lại`.
- **trống:** `Chưa có sách hệ thống nào.` kèm gợi ý theo vai trò; có bộ lọc thì `Không tìm thấy sách phù hợp.`

## API
`GET /api/books/explore?q&category&sort` (mỗi sách có `on_shelf`) · `POST /api/books/{id}/shelf` · `POST /api/books/ingest` với `is_public=true` (admin).
