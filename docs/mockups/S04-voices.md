# S04 – Kho Giọng Đọc

**Mục đích:** xem các giọng đọc, nghe thử, chọn giọng mặc định, và tạo/đổi tên/xóa giọng riêng của mình.  **Là một màn (tab) trong sidebar**, không còn là hộp thoại. **Mở từ:** sidebar › *Kho Giọng Đọc*, hoặc S03 (dropdown giọng → `+ Thêm giọng mới…`).

## Bố cục
```
┌ Kho Giọng Đọc ──────────────────── 2/3 giọng riêng  [ + Thêm giọng mới ] ┐
│ Nghe thử, chọn giọng mặc định và tạo giọng riêng của bạn.                 │
│ [ Giọng hệ thống (5) ]  [ Giọng của tôi (2) ]                              │
│ ┌────────────────────────────────────────────────────────────────────────┐│
│ │ Hoài My                         [▶ Nghe thử] [★ Đặt mặc định]           ││
│ │ Nữ · VI-VN · kể chuyện                                                  ││
│ ├────────────────────────────────────────────────────────────────────────┤│
│ │ Giọng Hoa  (✓ Mặc định)  Giọng chung  [▶ Nghe thử] [★ …] [✎] [🗑]       ││
│ └────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘

┌ Thêm giọng mới ─────────────────────────────── ✕ ┐   (hộp thoại, như cũ)
│ Tên giọng · File mẫu (a–b giây) · Ngôn ngữ · Giới tính │
│ [ ] Tôi xác nhận đây là giọng của tôi hoặc tôi được chủ giọng đồng ý.│
│                                   [ Hủy ] [ Tạo giọng ] │
└────────────────────────────────────────────────────┘
```

## Thành phần & luật
- **Giọng hệ thống:** giọng của nhà cung cấp TTS **và** giọng chung do admin công khai (nhãn `Giọng chung`). Ai cũng nghe thử và dùng được; không sửa/xóa được (trừ admin với giọng chung).
- **Giọng của tôi:** giọng bạn đã clone (nhãn `Riêng tư`, hoặc `Giọng chung` nếu admin đã công khai). Có `✎` đổi tên và `🗑` xóa (có hộp xác nhận). **Người khác không thấy** giọng riêng của bạn, kể cả admin.
- `▶ Nghe thử`: đọc câu mẫu cố định `Xin chào, đây là giọng đọc thử.`
- `★ Đặt mặc định`: lưu thành giọng mặc định **của riêng bạn** (`PUT /api/settings`), toast `Đã đặt "<tên>" làm giọng mặc định`; nút khóa trên giọng đang là mặc định. Người chưa chọn giọng nào dùng *giọng mặc định hệ thống* do admin đặt (S11).
- **Giới hạn:** mỗi thành viên tối đa `max_voices` giọng riêng (mặc định 3, `MAX_VOICES_PER_USER`); admin không giới hạn. Góc phải hiện `đã dùng/tối đa giọng riêng`; khi đầy nút `+ Thêm giọng mới` bị khóa kèm `Bạn đã dùng hết N giọng riêng. Hãy xóa một giọng để tạo giọng mới.`
- Nút `Tạo giọng` **chỉ bật khi** đã chọn file hợp lệ **và** đã tick đồng thuận. Thời điểm đồng thuận (`consent_at`) được lưu cùng file mẫu. File mẫu: khoảng độ dài do nhà cung cấp quy định (`clone_sample_seconds`; mặc định 5–15 giây, HeyGen 5–180 giây), ≤ 10 MB.

## Trạng thái
- **loading** · **empty** (Giọng của tôi): `Bạn chưa có giọng riêng nào.` kèm gợi ý tải mẫu · (Giọng hệ thống): `Chưa có giọng nào.`
- **đang tạo:** `Đang tạo giọng… (có thể mất vài chục giây)`, khóa form.
- **provider không hỗ trợ clone:** nút `+ Thêm giọng mới` khóa, chú thích `Nhà cung cấp hiện tại không hỗ trợ tạo giọng.`
- **thành công:** toast `Đã tạo giọng "<tên>"`, chuyển sang nhóm *Giọng của tôi*.

## API
`GET /api/voices` (mỗi giọng có `is_custom`, `is_public`, `is_mine`; kèm `my_voice_count`, `max_voices` (null = không giới hạn), `system_default_voice`, `supports_cloning`, `warning`) · `POST /api/voices/clone` (multipart: `sample`, `name`, `language`, `gender`, `consent=true`; `403` khi đủ giới hạn) · `PATCH /api/voices/{id}` (`display_name`; chủ giọng, hoặc admin với giọng chung; `404` nếu là giọng riêng của người khác) · `DELETE /api/voices/{id}` · `GET /api/voices/{id}/preview`. Clone trả `501` nếu provider không hỗ trợ, `400` nếu thiếu đồng thuận hoặc mẫu WAV ngoài khoảng cho phép.
