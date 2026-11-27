# S06 – Trích dẫn yêu thích

**Mục đích:** lưu những đoạn hay khi đang nghe (một chạm), gắn nhãn cảm xúc, nghe lại từng đoạn hoặc **phát liên tục** cả bộ sưu tập.  **Màn hình:** *Trích Dẫn Yêu Thích* (sidebar). Thay cho mục *Ghi chú* cũ: ghi chú theo đoạn bôi đen và đánh dấu một chạm là **cùng một loại bản ghi**.

## Bố cục
```
┌ Trích dẫn yêu thích ─────────────────────────── [ ▶ Phát liên tục (7) ] ┐
│ 🔍 [ Tìm trong trích dẫn… ]                          [ Tất cả sách ▼ ]    │
│ ( Tất cả cảm xúc | Truyền cảm hứng | Chạm cảm xúc | Triết lý hay | Hài hước ) │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ [TRIẾT LÝ HAY]  Giáo trình Python · câu 120 · 25/11/2026 21:12        │ │
│ │ …Biến là tên gọi của một vùng nhớ.                  ← câu trước (mờ)   │ │
│ │ “Kiểu dữ liệu được xác định khi gán giá trị.”       ← đoạn trích (serif)│ │
│ │ Ví dụ, x = 5 là kiểu số nguyên…                     ← câu sau (mờ)     │ │
│ │ 📝 Nhớ: Python là ngôn ngữ kiểu động.                                  │ │
│ │ [ ▶ Nghe lại ] [ Đến câu này ] [ Sửa ] [ Xóa ]                          │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

## Lưu một chạm (trong Phòng Đọc, S03)
- Nút **`⭐ Đánh dấu đoạn này`** hoặc phím **`B`** lưu **cả câu đang đọc**. Không hộp thoại nào chắn đường, nghe vẫn tiếp tục.
- Hệ thống tự lưu: câu đó, **câu liền trước và liền sau** (ngữ cảnh), giọng đang dùng, và **một bản sao file âm thanh** vào thư mục lưu vĩnh viễn riêng của bạn, nên dọn bộ nhớ đệm không làm mất.
- Ngay sau đó hiện thanh `Đã lưu đoạn này. Gắn nhãn: [Truyền cảm hứng] [Chạm cảm xúc] [Triết lý hay] [Hài hước] [Xem]` trong **8 giây** rồi tự ẩn. Gắn nhãn là **tùy chọn**; bấm nhãn khác thì đổi nhãn; không bấm gì vẫn lưu.
- Bấm lần hai trên cùng một câu **không tạo bản trùng**, chỉ có thể thêm nhãn.
- Bôi đen một phần câu rồi bấm `Trích đoạn đã chọn` (phím `N`) vẫn mở hộp **Lưu trích dẫn** (đoạn trích + ghi chú chữ + nhãn).

## Thành phần
| Thành phần | Mô tả |
|------------|-------|
| Bộ lọc | Theo **sách**, theo **nhãn cảm xúc** (4 nhãn), và tìm chữ trong đoạn trích/ghi chú/tên sách (không phân biệt dấu) |
| Thẻ trích dẫn | Nhãn (nếu có), sách, số câu, thời gian, câu trước (mờ), **đoạn trích cỡ lớn chữ có chân**, câu sau (mờ), ghi chú chữ |
| `▶ Nghe lại` | Phát file âm thanh đã lưu của đoạn đó (bấm lại để dừng) |
| **`▶ Phát liên tục`** | **Playlist**: phát lần lượt các trích dẫn đang hiển thị (theo bộ lọc). Trong lúc phát: `Đang phát 2 / 7`, `⏮` `⏹ Dừng` `⏭`; thẻ đang phát được tô nổi bật. Hết danh sách thì tự dừng. Một trích dẫn lỗi âm thanh bị báo và bỏ qua, không dừng cả danh sách |
| `Đến câu này` | Mở S03 tại đúng câu, không tự phát |
| `Sửa` | Sửa ghi chú chữ và nhãn (bấm lại nhãn đang chọn để bỏ) |
| `Xóa` | Có xác nhận; xóa cả file âm thanh đã lưu |

## Luật
- Bốn nhãn cố định: `Truyền cảm hứng` · `Chạm cảm xúc` · `Triết lý hay` · `Hài hước`.
- Chỉ của riêng bạn: người dùng khác (kể cả admin) không thấy trích dẫn, không nghe được âm thanh của bạn.
- Nghe phát liên tục sẽ **tạm dừng Phòng Đọc** để hai âm thanh không chồng nhau.
- File âm thanh nằm ở `.studylab/quotes/<id người dùng>/`; xóa trích dẫn hoặc xóa sách thì file bị xóa theo. Trích dẫn cũ chưa có file thì được tạo ở lần nghe đầu tiên.
- Nếu lúc đánh dấu hết hạn mức ký tự/ngày hoặc TTS lỗi, trích dẫn **vẫn được lưu**; âm thanh tạo lúc nghe lại.

## Trạng thái
- **empty:** `Chưa có trích dẫn nào.` + gợi ý bấm `Đánh dấu đoạn này` (phím B) trong Phòng Đọc; có bộ lọc thì `Không có trích dẫn phù hợp.`
- **loading / error** như README.

## API
`GET /api/notes?book_id&emotion_tag` · `POST /api/notes` (`book_id`, `sentence_index`, **tùy chọn** `start_offset` + `end_offset` — bỏ cả hai là cả câu —, `note_text`, `emotion_tag`, `voice`) → `201` mới, `200` nếu đã có · `PATCH /api/notes/{id}` (`note_text` và/hoặc `emotion_tag`, `null` để bỏ nhãn) · `DELETE /api/notes/{id}` · `GET /api/notes/{id}/audio`.
Trả về mỗi trích dẫn: `excerpt`, `emotion_tag`, `context_before`, `context_after`, `has_audio`, `voice`.

## Tiêu chí hoàn thành
- [ ] Bấm `B` khi đang nghe: đoạn hiện ở S06 với câu trước/sau và nghe lại được, kể cả sau khi dọn bộ nhớ đệm.
- [ ] Gắn/đổi/bỏ nhãn; lọc theo nhãn và theo sách; hai client giống nhau.
- [ ] `Phát liên tục` phát đúng thứ tự đang hiển thị, `⏭ ⏮ ⏹` hoạt động, hết thì dừng.
- [ ] Người dùng B không thấy trích dẫn của A.
