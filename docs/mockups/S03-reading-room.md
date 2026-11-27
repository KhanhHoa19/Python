# S03 – Phòng Đọc (player)

**Mục đích:** nghe và đọc theo tài liệu, từng câu một, có highlight, bookmark và ghi chú.  **Tab:** Phòng Đọc.

## Bố cục
```
┌ Phòng Đọc ─────────────────────────────────────────────────────────────┐
│ 📄 Giáo trình Python  ▼ [đổi]  [☰ Mục lục]   Giọng: [ Hoài My (nữ, Bắc) ▼ ] │
│ ─────────────────────────────────────────────────────────────────────  │
│  …câu 118: Biến là tên gọi của một vùng nhớ.                            │
│  …câu 119: Python không cần khai báo kiểu.                              │
│ ▶▓ câu 120: Kiểu dữ liệu được xác định khi gán giá trị. ◀ (đang đọc)     │
│  …câu 121: Ví dụ, x = 5 là kiểu số nguyên.                              │
│  …câu 122: Còn x = "an" là kiểu chuỗi.                                  │
│                                                                         │
│       [ ⭐ Đánh dấu đoạn này (B) ]  [ 📝 Trích đoạn đã chọn (N) ]        │
│ ─────────────────────────────────────────────────────────────────────  │
│ Câu 120 / 1.240   ·  Chương 3: Biến và kiểu dữ liệu   ▓▓▓▓░░░░░ 9,7%    │
│  [ ⏮ ]  [ ⏪ Câu trước ]  [ ▶ / ⏸ ]  [ Câu sau ⏩ ]  [ ⏭ ]               │
│  Tốc độ: (•)0.75x ( )1.0x ( )1.25x ( )1.5x  [⏲ Hẹn giờ] [🎵 Nhạc nền]  Nhảy tới câu: [ 120 ] [Đi]│
│  Trạng thái: ● Đang phát · bộ đệm 2/2 · độ trễ 640 ms                   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Thành phần
| Thành phần | Mô tả |
|------------|-------|
| Chọn tài liệu | Mở danh sách rút gọn của S01 |
| Mục lục | Nút `☰ Mục lục` (chỉ hiện khi tài liệu có từ 2 chương) mở hộp **Mục lục**; xem mục "Mục lục chương" bên dưới |
| Chọn giọng | Dropdown **Giọng dẫn chuyện**; mục cuối `+ Thêm giọng mới…` mở S04 |
| Giọng nhân vật | Dropdown **Giọng nhân vật**: `Một giọng (không phân vai)` (mặc định) hoặc một giọng bất kỳ; xem mục "Đọc phân vai" bên dưới |
| Khung văn bản | Hiển thị ±N câu quanh câu hiện tại, tự cuộn; bấm vào câu bất kỳ để nhảy tới |
| Highlight | Câu đang đọc nền vàng nhạt, chữ đậm; câu đã đọc làm mờ |
| Thanh tiến độ | `Câu x / tổng` và `%` |
| Điều khiển | `⏮` về đầu · `⏪` câu trước · `▶/⏸` · `⏩` câu sau · `⏭` về cuối |
| Tốc độ | 4 mức, đổi tức thì, không tải lại audio |
| Nhảy câu | Nhập số câu rồi `Đi` |
| Nhạc nền | Nút `🎵 Nhạc nền` mở hộp **Âm thanh nền** (xem dưới); có màu nhấn khi đang chọn một bản |
| Hẹn giờ | Nút `⏲ Hẹn giờ` mở hộp **Hẹn giờ tắt** (xem dưới). Khi đang hẹn, nút đổi thành `⏲ 12:30` (còn lại) hoặc `⏲ Hết chương` và có màu nhấn |
| Đánh dấu đoạn này | Nút `⭐` hoặc phím **B**: lưu cả câu đang đọc thành **trích dẫn yêu thích** (một chạm, không chắn nghe); hiện thanh gắn nhãn cảm xúc 8 giây (xem S06) |
| Trích đoạn đã chọn | Bôi đen chữ → nút `📝` (phím N) bật lên → mở hộp **Lưu trích dẫn** (xem S06) |
| Dòng trạng thái | Đang phát/Tạm dừng/Đang tải · bộ đệm · độ trễ API gần nhất |

## Trạng thái
- **chưa chọn tài liệu:** `Chưa chọn tài liệu. [Mở Thư viện]`.
- **đang tải câu:** nút phát hiện vòng xoay, trạng thái `Đang tải…`.
- **hết tài liệu:** dừng, toast `Đã đọc xong. [Đọc lại từ đầu]`.
- **lỗi một câu:** thử lại 1 lần; vẫn lỗi thì ghi log `fail` và tự sang câu sau, hiện cảnh báo nhỏ `Bỏ qua câu 120 (lỗi TTS)`.
- **mất mạng / hết quota:** dừng phát, thanh đỏ + `Thử lại`, mở S05.

## Hành vi
1. Mở màn: nếu có bookmark thì nhảy đúng câu và dùng giọng đã đọc lần trước của tài liệu đó (lưu cùng bookmark: `bookmarks.voice`; bỏ qua nếu giọng đã bị xóa) và tốc độ lần trước; **không tự phát**.
2. `Phát`: tải câu hiện tại, đồng thời **tải trước 2 câu kế tiếp** (cấu hình ở S05).
3. Hết một câu: ghi log, lưu bookmark (tối đa mỗi 5 giây một lần), sang câu sau.
4. Đổi giọng giữa chừng: hủy bộ đệm, đọc lại từ câu hiện tại với giọng mới.
5. Nhảy câu/câu trước/câu sau: hủy yêu cầu đang chờ, xả bộ đệm, phát từ vị trí mới.
6. Đóng app/chuyển tab: lưu bookmark ngay.

## Mục lục chương
Hộp thoại **Mục lục** liệt kê mọi chương: tên chương và `N câu · M từ`; chương đang đọc tô màu nhấn và được cuộn tới. **Bấm một chương → hủy hàng đợi âm thanh cũ và phát từ câu đầu của chương đó ngay.** Thanh tiến độ hiện thêm tên chương đang đọc.
- **Nguồn tên chương:** (1) dấu trang (bookmark) của PDF hoặc `Heading 1` của DOCX, nếu có từ 2 mục trở lên; (2) tiêu đề dạng `Chương/Phần/Bài/Mục/Chapter/Part N` hoặc `# Tiêu đề` trong văn bản. Phần chữ trước tiêu đề đầu tiên tên `Mở đầu`; tài liệu không có tiêu đề nào là một chương `Toàn bộ tài liệu`.
- **Sách nạp từ trước khi có mục lục:** backend dựng lại từ số chương của từng câu, tên `Chương N` (lưu lại, chỉ làm một lần). Muốn có tên chương thật, xóa sách rồi tải lại file.
- Nếu không lấy được mục lục (lỗi mạng/404) thì vẫn đọc bình thường, chỉ không có nút và tên chương.

## Đọc phân vai (Multi-Voice Narration)
Chọn một giọng ở ô **Giọng nhân vật** thì **lời thoại** đọc bằng giọng đó, phần còn lại (lời dẫn) đọc bằng **Giọng dẫn chuyện**. Chọn `Một giọng (không phân vai)` để tắt. Lựa chọn **lưu riêng từng người** (`character_voice` trong `PUT /api/settings`), áp dụng cho mọi sách, đổi giữa chừng thì câu đang đọc phát lại bằng giọng mới; toast `Đã bật đọc phân vai: …` / `Đã tắt đọc phân vai.`
- **Nhận diện lời thoại** (tự động, ở máy chủ, **không cần nạp lại sách**): chữ nằm trong ngoặc kép `“…”`, `"…"`, `«…»`, hoặc câu mở đầu bằng gạch đầu dòng đối thoại (`-`, `–`, `—` kèm dấu cách). Ví dụ `Anh nói: "Đừng đi!" rồi quay đi.` → dẫn `Anh nói:` · nhân vật `Đừng đi!` · dẫn `rồi quay đi.`; `- Em đi đâu đấy? - Nam hỏi.` → nhân vật `Em đi đâu đấy?` · dẫn `Nam hỏi.`
- Một lời thoại **kéo dài nhiều câu** (mở ngoặc ở câu này, đóng ở câu sau) được nhận ra: các câu giữa vẫn là nhân vật. Ngoặc mở quá 12 câu không đóng bị coi là dấu thừa (không biến cả cuốn thành lời thoại).
- Máy chủ đọc từng đoạn bằng giọng tương ứng rồi **ghép thành một file cho câu đó**, nên web, desktop và **xuất audio** (S07) cho kết quả giống nhau (`GET /api/audio/{sách}/{câu}?voice=&dialogue_voice=`, `POST /api/books/{id}/export` nhận `dialogue_voice`). Câu không có lời thoại dùng đúng audio như khi một giọng, nên bộ nhớ đệm cũ vẫn dùng được.
- **Chi phí:** số ký tự không đổi (dấu ngoặc không được đọc) nhưng một câu thoại cần 2–3 lượt gọi TTS thay vì 1, nên lần nghe đầu chậm hơn một chút. Giọng nhân vật phải dùng được với người nghe (không thể chọn giọng riêng của người khác).
- **Giới hạn đã biết:** lời thoại bằng gạch đầu dòng kéo dài qua nhiều câu chỉ nhận ra ở câu đầu (hệ thống không giữ ranh giới đoạn văn); gạch đầu dòng của danh sách liệt kê bị đọc như lời thoại; PDF làm hỏng dấu ngoặc thì nhận diện kém. Chỉ có **hai vai** (dẫn chuyện và nhân vật), không phân biệt từng nhân vật.

## Âm thanh nền & chuông chuyển chương
Hộp thoại **Âm thanh nền**: danh sách `Tắt` + các bản trong thư viện (admin quản lý ở S11), thanh **âm lượng nền** 0–100% (độc lập với giọng đọc), ô `Phát tiếng chuông khi sang chương mới`, nút `Xong`. Mọi thay đổi **lưu ngay** và áp dụng ngay.
- Lựa chọn **riêng từng người** (`GET/PUT /api/settings`: `ambient_track` (0 = tắt), `ambient_volume` (mặc định 0.4), `chapter_chime` (mặc định bật)). Mặc định là **tắt** nhạc nền.
- Nhạc nền **lặp vô hạn** và chỉ phát khi đang đọc: tạm dừng/dừng/đọc xong/hết giờ hẹn thì nhạc cũng dừng; Phát lại thì nhạc tiếp tục. Hẹn giờ giảm dần âm lượng cả giọng lẫn nhạc nền. Admin xóa bản đang dùng thì người nghe không còn nghe nhạc nền cho tới khi chọn bản khác.
- **Tiếng chuông** (1,6 giây, hai nốt E5→A5, nhỏ, tự tổng hợp, không cần file) phát **trước câu đầu của chương mới** khi việc đọc tự chuyển chương. Không phát khi nhảy tay (tua, mục lục, đổi sách), khi bắt đầu đọc, hoặc khi đã tắt chuông.
- Lỗi tải nhạc nền không bao giờ làm dừng việc đọc.

## Hẹn giờ tắt (sleep timer)
Hộp thoại **Hẹn giờ tắt**: `15 phút` · `30 phút` · `45 phút` · `60 phút` · `Tùy chỉnh [ ] phút` (số nguyên 1–600) · `Dừng khi hết chương này` · `Tắt hẹn giờ` · `Đóng`. Mục đang dùng được tô màu nhấn.
- Chỉ làm ở client, **không gọi backend**. Đồng hồ **chỉ chạy khi đang phát** (tạm dừng thì đứng yên).
- **10 giây cuối** âm lượng giảm tuyến tính về 0%; chạm 0 thì tạm dừng, lưu vị trí đọc, **khôi phục âm lượng 100%** và tắt hẹn giờ; toast `Hết giờ hẹn: đã tạm dừng.`
- **Dừng khi hết chương này:** phát hết câu cuối của chương hiện tại (âm lượng giảm đều suốt câu cuối, tối đa 10 giây) rồi dừng ở **câu đầu của chương sau**, sẵn sàng đọc tiếp; toast `Đã dừng hết chương theo hẹn giờ.` Nếu chương cuối thì coi như đọc xong.
- Hẹn giờ bị hủy khi đổi tài liệu. Đổi tốc độ/giọng giữa chừng không làm mất hẹn giờ.
- Quy tắc dùng chung ở `apps/web/src/lib/sleepTimer.ts` và `apps/desktop/player/sleep_timer.py` (hai nơi phải khớp).

## API
`GET /api/books/{id}/sentences` · `GET /api/books/{id}/chapters` *(mới)* · `GET /api/audio/{book}/{idx}?voice=&speed=1.0` · `GET/POST /api/bookmarks` · `POST /api/sessions` · `GET /api/voices` *(mới)* · `POST /api/notes` (trích dẫn; không có `start/end_offset` là cả câu).

## Ghi chú theo client
- **Web:** `<audio>` + prefetch bằng `fetch` → Blob URL, thu hồi URL sau khi phát; `audio.playbackRate`; highlight bằng class CSS.
- **Desktop:** Producer thread đẩy vào `queue.Queue(maxsize=2)`, Consumer thread phát bằng `pygame.mixer`; chỉ cập nhật UI qua `widget.after()`; dùng `threading.Event` để hủy; highlight bằng tag của `CTkTextbox`.

## Tiêu chí hoàn thành
- [ ] Mục lục: chương đúng với tài liệu, bấm chương phát từ câu đầu, chương đang đọc được tô.
- [ ] Đọc phân vai: chọn giọng nhân vật thì lời trong ngoặc kép đổi giọng, lời dẫn giữ giọng dẫn chuyện; tắt thì về một giọng; câu không có lời thoại không bị chậm hơn.
- [ ] Nhạc nền: chọn/tắt/đổi âm lượng có hiệu lực ngay và được nhớ; chạy khi đọc, dừng khi tạm dừng. Chuông chỉ phát khi tự sang chương.
- [ ] Hẹn giờ: đếm đúng, giảm âm lượng 10 giây cuối, tự dừng và lưu vị trí, âm lượng trở về 100%; chế độ hết chương dừng đúng ranh giới chương; đồng hồ không chạy lúc tạm dừng.
- [ ] Đọc liền mạch cả một chương, không ngắt quãng giữa các câu (mock độ trễ 1 s).
- [ ] Nhảy câu/đổi giọng không làm đơ giao diện.
- [ ] Tắt và mở lại, đọc tiếp đúng câu, giọng, tốc độ.
- [ ] Bookmark đồng bộ giữa web và desktop.
- [ ] Đủ 4 phím tắt nêu ở README.
