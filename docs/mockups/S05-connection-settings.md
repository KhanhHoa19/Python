# S05 – Kiểm tra kết nối & Cài đặt

**Mục đích:** kiểm tra mạng/nhà cung cấp TTS, đổi cấu hình đọc và giới hạn chi phí.  **Mở từ:** nút ⚙ trên thanh điều hướng, hoặc khi gặp lỗi mạng ở S03.

## Bố cục
```
┌ Kết nối & Cài đặt ───────────────────────────── ✕ ┐
│ KẾT NỐI                                              │
│  Nhà cung cấp : [ Mock ▼ ]    API Key: [ ••••••••• ] [ Lưu ] │
│  [ Kiểm tra kết nối ]                                │
│   ✔ DNS            tts.example.com → 203.0.113.5     │
│   ✔ Cổng 443       mở                                │
│   ✔ Độ trễ mạng    86 ms                             │
│   ✔ API Key        hợp lệ                            │
│   ✖ Thử đọc 1 câu  lỗi 429 (hết hạn mức)             │
│ ──────────────────────────────────────────────────  │
│ CÀI ĐẶT ĐỌC                                          │
│  Số câu tải trước : [ 2 ▼ ]   (1–5)                  │
│  Tốc độ mặc định  : [ 1.0x ▼ ]                       │
│  Giọng mặc định   : [ Hoài My ▼ ]                    │
│  Giới hạn ký tự/ngày : [ 50.000 ]   Đã dùng hôm nay: 12.430 (25%) │
│                                  [ Đóng ] [ Lưu cài đặt ] │
└──────────────────────────────────────────────────────┘
```

## Thành phần & luật
- Mỗi dòng kiểm tra có 3 trạng thái: `⏳ đang chạy` · `✔ đạt` · `✖ lỗi + lý do`; chạy tuần tự DNS → cổng 443 → độ trễ → API Key → đọc thử.
- API Key hiển thị dạng che; chỉ gửi **lên backend** để lưu, client không giữ lại. Không ghi vào log.
- Khi gần chạm giới hạn ký tự/ngày (≥ 80%) thanh dùng đổi sang màu cam; đạt 100% thì S03 từ chối tạo audio mới (vẫn phát được câu đã cache) và báo `Đã đạt giới hạn ký tự hôm nay.`
- Số câu tải trước, tốc độ mặc định, giọng mặc định áp dụng cho S03 ở lần mở sau.

## API
`GET /api/health` · `GET /api/health/network` *(mới)* · `POST /api/tts/verify` *(mới)* · `GET/PUT /api/settings` *(mới)*.

## Ghi chú theo client
- **Web:** modal hoặc trang `/settings`.
- **Desktop:** `CTkToplevel`; chạy kiểm tra trong thread, cập nhật từng dòng bằng `after()`.

## Tiêu chí hoàn thành
- [ ] Năm dòng kiểm tra hiện đúng thứ tự và trạng thái.
- [ ] API Key không lộ ở giao diện, log hay phản hồi.
- [ ] Giới hạn ký tự có hiệu lực thật ở backend.
