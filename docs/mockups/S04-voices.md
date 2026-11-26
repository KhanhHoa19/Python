# S04 – Chọn giọng & Thêm giọng mới

**Mục đích:** xem danh sách giọng, nghe thử, và tạo giọng mới từ file mẫu.  **Mở từ:** S03 (dropdown giọng → `+ Thêm giọng mới…`) hoặc S05.

## Bố cục
```
┌ Giọng đọc ────────────────────────────────── ✕ ┐
│ [ Có sẵn ]  [ Giọng của tôi ]                    │
│ Lọc: Giới tính [ Tất cả ▼ ]  Phong cách [ Tất cả ▼ ] │
│ ────────────────────────────────────────────────  │
│ ( ) Hoài My   · Nữ · Bắc   · Kể chuyện   [ ▶ Nghe thử ] │
│ (•) Nam Minh  · Nam · Nam   · Tin tức    [ ▶ Nghe thử ] │
│ ( ) Giọng của tôi · Tùy chỉnh ·🗑        [ ▶ Nghe thử ] │
│                                  [ + Thêm giọng mới ] │
│                                       [ Hủy ] [ Dùng giọng này ] │
└───────────────────────────────────────────────────┘

┌ Thêm giọng mới ─────────────────────────────── ✕ ┐
│ Tên giọng     : [ Giọng của tôi           ]       │
│ File mẫu      : [ mau.wav ] [ Chọn file ]  (5–15 giây, WAV/MP3) │
│ Ngôn ngữ      : [ Tiếng Việt ▼ ]   Giới tính: [ Nữ ▼ ] │
│ [ ] Tôi xác nhận đây là giọng của tôi hoặc tôi được chủ giọng đồng ý.│
│                                   [ Hủy ] [ Tạo giọng ] │
└────────────────────────────────────────────────────┘
```

## Thành phần & luật
- Tab *Có sẵn*: giọng do nhà cung cấp TTS trả về. Tab *Giọng của tôi*: giọng đã clone, có nút xóa.
- `Nghe thử`: đọc câu mẫu cố định `Xin chào, đây là giọng đọc thử.`; nhấn lần nữa để dừng.
- Nút `Tạo giọng` **chỉ bật khi** đã chọn file hợp lệ **và** đã tick đồng thuận. Thời điểm đồng thuận (`consent_at`) được lưu cùng file mẫu.
- File mẫu: 5–15 giây, ≤ 10 MB; ngoài khoảng này hiện `Mẫu phải dài 5–15 giây.`

## Trạng thái
- **loading** danh sách · **empty** (tab Giọng của tôi): `Bạn chưa có giọng riêng nào.`
- **đang tạo:** `Đang tạo giọng… (có thể mất vài chục giây)`, khóa form.
- **provider không hỗ trợ clone:** nút `+ Thêm giọng mới` bị khóa kèm chú thích `Nhà cung cấp hiện tại không hỗ trợ tạo giọng.` (lấy từ `capabilities`).
- **thành công:** toast `Đã tạo giọng "<tên>"`, tự chọn giọng đó ở S03.

## API *(đều mới)*
`GET /api/voices` · `POST /api/voices/sync` · `POST /api/voices/clone` (multipart: `sample`, `name`, `language`, `gender`, `consent=true`) · `DELETE /api/voices/{id}` · `GET /api/voices/{id}/preview`.

## Ghi chú theo client
- **Web:** modal; `<input type=file accept="audio/*">`.
- **Desktop:** `CTkToplevel`; `filedialog`; nghe thử phát qua `pygame`.

## Tiêu chí hoàn thành
- [ ] Chặn tạo giọng khi thiếu file hoặc chưa tick đồng thuận.
- [ ] Giọng vừa tạo xuất hiện ngay trong dropdown ở S03.
- [ ] Hiển thị đúng trạng thái khi provider không hỗ trợ clone (kiểm bằng MockProvider).
