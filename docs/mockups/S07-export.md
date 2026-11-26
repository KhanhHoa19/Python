# S07 – Xuất audio

**Mục đích:** ghép các câu thành một file audio để nghe offline.  **Mở từ:** S01 (menu `⋯` → `Xuất audio`).

## Bố cục
```
┌ Xuất audio – Giáo trình Python ───────────────── ✕ ┐
│ Phạm vi : (•) Cả tài liệu                            │
│           ( ) Từ câu [ 1 ] đến câu [ 1240 ]          │
│ Giọng   : [ Hoài My ▼ ]                              │
│ Định dạng : (•) WAV   ( ) MP3  (cần ffmpeg)          │
│ Ước tính : ~ 1.240 câu · ~ 48 phút · ~ 62.000 ký tự cần gọi API (còn lại lấy từ cache) │
│                                                      │
│ Tiến trình: ▓▓▓▓▓░░░░░ 612 / 1240 câu                │
│                             [ Hủy ] [ Bắt đầu xuất ] │
└──────────────────────────────────────────────────────┘
        ↓ khi xong
│ ✔ Hoàn tất. giao-trinh-python.wav (92 MB)   [ Tải về / Lưu file ] │
```

## Luật
- Ước tính ký tự cần gọi API = tổng ký tự các câu **chưa có trong cache**. Nếu vượt hạn mức ngày (S05) hiện cảnh báo, vẫn cho xuất phần đã cache.
- Xuất chạy **nền** trên backend; đóng hộp không hủy công việc, có thể mở lại xem tiến trình.
- MP3 bị khóa kèm chú thích nếu backend không có ffmpeg.

## Trạng thái
`idle` → `running` (có `Hủy`) → `done` (có nút tải) hoặc `failed` (`Xuất thất bại: <lý do>. [Thử lại]`).

## API *(đều mới)*
`GET /api/books/{id}/export/estimate?from=&to=&voice=` · `POST /api/books/{id}/export` → `{job_id}` · `GET /api/exports/{job_id}` (tiến trình) · `GET /api/exports/{job_id}/file`.

## Ghi chú theo client
- **Web:** tải bằng thẻ `<a download>`.
- **Desktop:** `filedialog.asksaveasfilename` rồi tải file về đường dẫn đã chọn.

## Tiêu chí hoàn thành
- [ ] Ước tính, tiến trình và kết quả hiển thị giống nhau ở hai client.
- [ ] File xuất phát được liền mạch, đúng thứ tự câu.
- [ ] Hủy giữa chừng không để lại file dở.
