# S07 – Xuất audio

**Mục đích:** ghép các câu thành một file audio để nghe offline.  **Mở từ:** S01 (menu `⋯` → `Xuất audio`).

## Bố cục
```
┌ Xuất audio – Giáo trình Python ───────────────── ✕ ┐
│ Phạm vi : (•) Cả tài liệu                            │
│           ( ) Từ câu [ 1 ] đến câu [ 1240 ]          │
│ Giọng   : [ Hoài My ▼ ]                              │
│ Định dạng : theo audio của nhà cung cấp (WAV hoặc MP3); chọn sai định dạng → `failed`          │
│ Ước tính : ~ 1.240 câu · ~ 48 phút · ~ 62.000 ký tự cần gọi API (còn lại lấy từ cache) │
│                                                      │
│ Tiến trình: ▓▓▓▓▓░░░░░ 612 / 1240 câu                │
│                                    [ Bắt đầu xuất ] │
└──────────────────────────────────────────────────────┘
        ↓ khi xong
│ ✔ Hoàn tất. giao-trinh-python.wav (92 MB)   [ Tải về / Lưu file ] │
```

## Luật
- Ước tính ký tự cần gọi API = tổng ký tự các câu **chưa có trong cache**. Nếu vượt hạn mức ngày (S05) hiện cảnh báo, vẫn cho xuất phần đã cache.
- Xuất chạy **nền** trên backend; đóng hộp không hủy công việc, có thể mở lại xem tiến trình.
- Backend ghép trực tiếp: WAV bằng module `wave`, MP3 bằng nối byte. Không chuyển đổi định dạng (không cần ffmpeg).

## Trạng thái
`idle` → `running` → `done` (có nút tải), `failed` (`Xuất thất bại: <lý do>. [Thử lại]`) hoặc `cancelled`.

Trong lúc `running` có nút **Hủy xuất** (cạnh `Bắt đầu xuất`). Backend dừng sau câu đang tổng hợp; không tạo file; phần audio đã tổng hợp vẫn nằm trong cache. Thông báo: `Đã hủy xuất. Phần đã tổng hợp vẫn nằm trong cache.`

## API
`GET /api/books/{id}/export/estimate?from_index=&to_index=&voice=` · `POST /api/books/{id}/export` → `{job_id}` · `GET /api/exports/{job_id}` (tiến trình) · `DELETE /api/exports/{job_id}` (hủy, trả trạng thái hiện tại) · `GET /api/exports/{job_id}/file`.

## Ghi chú theo client
- **Web:** tải bằng thẻ `<a download>`.
- **Desktop:** `filedialog.asksaveasfilename` rồi tải file về đường dẫn đã chọn.

## Tiêu chí hoàn thành
- [ ] Ước tính, tiến trình và kết quả hiển thị giống nhau ở hai client.
- [ ] File xuất phát được liền mạch, đúng thứ tự câu.
- [ ] Lỗi giữa chừng (hết hạn mức, provider lỗi) báo `failed` và không để lại file dở.

> Chưa có chức năng `Hủy` giữa chừng (backend chưa hỗ trợ).
