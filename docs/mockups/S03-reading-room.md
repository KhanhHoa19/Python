# S03 – Phòng Đọc (player)

**Mục đích:** nghe và đọc theo tài liệu, từng câu một, có highlight, bookmark và ghi chú.  **Tab:** Phòng Đọc.

## Bố cục
```
┌ Phòng Đọc ─────────────────────────────────────────────────────────────┐
│ 📄 Giáo trình Python  ▼ [đổi]        Giọng: [ Hoài My (nữ, Bắc) ▼ ]     │
│ ─────────────────────────────────────────────────────────────────────  │
│  …câu 118: Biến là tên gọi của một vùng nhớ.                            │
│  …câu 119: Python không cần khai báo kiểu.                              │
│ ▶▓ câu 120: Kiểu dữ liệu được xác định khi gán giá trị. ◀ (đang đọc)     │
│  …câu 121: Ví dụ, x = 5 là kiểu số nguyên.                              │
│  …câu 122: Còn x = "an" là kiểu chuỗi.                                  │
│                                                                         │
│                                  [ 📝 Ghi chú đoạn đã chọn ]            │
│ ─────────────────────────────────────────────────────────────────────  │
│ Câu 120 / 1.240   ▓▓▓▓▓░░░░░░░░░░ 9,7%                                  │
│  [ ⏮ ]  [ ⏪ Câu trước ]  [ ▶ / ⏸ ]  [ Câu sau ⏩ ]  [ ⏭ ]               │
│  Tốc độ: (•)0.75x ( )1.0x ( )1.25x ( )1.5x      Nhảy tới câu: [ 120 ] [Đi]│
│  Trạng thái: ● Đang phát · bộ đệm 2/2 · độ trễ 640 ms                   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Thành phần
| Thành phần | Mô tả |
|------------|-------|
| Chọn tài liệu | Mở danh sách rút gọn của S01 |
| Chọn giọng | Dropdown giọng; mục cuối `+ Thêm giọng mới…` mở S04 |
| Khung văn bản | Hiển thị ±N câu quanh câu hiện tại, tự cuộn; bấm vào câu bất kỳ để nhảy tới |
| Highlight | Câu đang đọc nền vàng nhạt, chữ đậm; câu đã đọc làm mờ |
| Thanh tiến độ | `Câu x / tổng` và `%` |
| Điều khiển | `⏮` về đầu · `⏪` câu trước · `▶/⏸` · `⏩` câu sau · `⏭` về cuối |
| Tốc độ | 4 mức, đổi tức thì, không tải lại audio |
| Nhảy câu | Nhập số câu rồi `Đi` |
| Ghi chú | Bôi đen chữ → nút `📝 Ghi chú` bật lên → mở hộp nhập (xem S06) |
| Dòng trạng thái | Đang phát/Tạm dừng/Đang tải · bộ đệm · độ trễ API gần nhất |

## Trạng thái
- **chưa chọn tài liệu:** `Chưa chọn tài liệu. [Mở Thư viện]`.
- **đang tải câu:** nút phát hiện vòng xoay, trạng thái `Đang tải…`.
- **hết tài liệu:** dừng, toast `Đã đọc xong. [Đọc lại từ đầu]`.
- **lỗi một câu:** thử lại 1 lần; vẫn lỗi thì ghi log `fail` và tự sang câu sau, hiện cảnh báo nhỏ `Bỏ qua câu 120 (lỗi TTS)`.
- **mất mạng / hết quota:** dừng phát, thanh đỏ + `Thử lại`, mở S05.

## Hành vi
1. Mở màn: nếu có bookmark thì nhảy đúng câu, giọng và tốc độ lần trước; **không tự phát**.
2. `Phát`: tải câu hiện tại, đồng thời **tải trước 2 câu kế tiếp** (cấu hình ở S05).
3. Hết một câu: ghi log, lưu bookmark (tối đa mỗi 5 giây một lần), sang câu sau.
4. Đổi giọng giữa chừng: hủy bộ đệm, đọc lại từ câu hiện tại với giọng mới.
5. Nhảy câu/câu trước/câu sau: hủy yêu cầu đang chờ, xả bộ đệm, phát từ vị trí mới.
6. Đóng app/chuyển tab: lưu bookmark ngay.

## API
`GET /api/books/{id}/sentences` · `GET /api/audio/{book}/{idx}?voice=&speed=1.0` · `GET/POST /api/bookmarks` · `POST /api/sessions` · `GET /api/voices` *(mới)* · `POST /api/notes` *(mới)*.

## Ghi chú theo client
- **Web:** `<audio>` + prefetch bằng `fetch` → Blob URL, thu hồi URL sau khi phát; `audio.playbackRate`; highlight bằng class CSS.
- **Desktop:** Producer thread đẩy vào `queue.Queue(maxsize=2)`, Consumer thread phát bằng `pygame.mixer`; chỉ cập nhật UI qua `widget.after()`; dùng `threading.Event` để hủy; highlight bằng tag của `CTkTextbox`.

## Tiêu chí hoàn thành
- [ ] Đọc liền mạch cả một chương, không ngắt quãng giữa các câu (mock độ trễ 1 s).
- [ ] Nhảy câu/đổi giọng không làm đơ giao diện.
- [ ] Tắt và mở lại, đọc tiếp đúng câu, giọng, tốc độ.
- [ ] Bookmark đồng bộ giữa web và desktop.
- [ ] Đủ 4 phím tắt nêu ở README.
