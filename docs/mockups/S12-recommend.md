# S12 – Gợi Ý (Recommendation)

**Mục đích:** đề xuất sách hệ thống chưa có trên kệ, dựa trên **lịch sử nghe**, **thể loại yêu thích**, **thời lượng mong muốn** và **tâm trạng**. **Là một tab** trong sidebar (*Gợi Ý*, sau *Khám Phá*).

## Bố cục
```
┌ Gợi Ý ───────────────────────────────────────────────────────────────┐
│ Sách hợp với bạn hôm nay, kèm lý do vì sao.                            │
│ ┌ Lần đầu: Bạn thích thể loại nào? (chọn vài thể loại) ──────────────┐ │
│ │ [Trinh thám] [Khoa học] [Lịch sử] …            [ Lưu ] [ Bỏ qua ]   │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│ Thể loại yêu thích: Trinh thám · Khoa học · Kinh dị     [ ✎ Sửa ]       │
│ Tâm trạng:  [Tất cả] [Thư giãn] [Hồi hộp] [Suy ngẫm] [Học hỏi] [Lãng mạn] [Vui vẻ] │
│ Thời lượng: [Bất kỳ] [≤ 15 phút] [≤ 30 phút] [≤ 1 giờ] [≤ 3 giờ]       │
│ ┌ bìa ┐ Tên sách · Tác giả · ~25 phút                                  │
│ │     │ ✦ Bạn hay nghe Trinh thám · Hợp tâm trạng Hồi hộp             │
│ └─────┘ [ Nghe ngay ] [ + Thêm vào kệ ]                                │
└────────────────────────────────────────────────────────────────────────┘
```

## Luật
- **Chỉ gợi ý sách công khai chưa có trên kệ** của người xem. Không bao giờ lộ sách riêng hoặc lịch sử của người khác; độ phổ biến chỉ là một **con số tổng hợp** (số người đang giữ sách).
- **Lần đầu** (chưa chọn thể loại và chưa bỏ qua): hiện khung chọn nhiều thể loại (tối đa 15) → `Lưu` hoặc `Bỏ qua`. Sau này đổi bất cứ lúc nào bằng `✎ Sửa` (thêm hoặc bỏ thể loại yêu thích); lưu `PUT /api/recommendations/preferences`.
- **Chấm điểm** (xem `core/recommend/engine.py`): độ hợp thể loại (từ lịch sử nghe: thời gian nghe, sách đã xong, yêu thích, trừ điểm sách bỏ dở; giảm dần theo thời gian; cộng thể loại đã chọn) · độ hợp tâm trạng · độ vừa thời lượng · độ phổ biến · độ mới. Người **chưa có lịch sử** dựa vào thể loại đã chọn; khi **đã có lịch sử** thì kết hợp thêm độ phổ biến.
- **Tâm trạng → thể loại** (bảng cố định, giống nhau ở hai client):
  | Tâm trạng | Thể loại |
  |-----------|----------|
  | Thư giãn | Truyện ngắn, Thiếu nhi, Tình cảm, Tiểu thuyết |
  | Hồi hộp | Trinh thám, Kinh dị, Phiêu lưu |
  | Suy ngẫm | Triết học, Tâm lý, Lịch sử |
  | Học hỏi | Khoa học, Công nghệ, Kinh tế, Kỹ năng sống |
  | Lãng mạn | Tình cảm, Tiểu thuyết |
  | Vui vẻ | Thiếu nhi, Phiêu lưu, Truyện ngắn |
  Chọn một tâm trạng thì **chỉ** hiện sách thuộc các thể loại đó.
- **Thời lượng** ước tính = số từ ÷ tốc độ nghe của chính người dùng (mặc định 150 từ/phút khi chưa có dữ liệu). Chọn `≤ N` thì loại sách dài hơn N.
- Mỗi gợi ý kèm **lý do** (`Bạn hay nghe …`, `Bạn đã chọn thích …`, `Hợp tâm trạng …`, `Vừa đủ ~N phút`, `N người đang giữ sách này`, `Sách mới`).

## Trạng thái
`loading` · `empty`: `Chưa có sách phù hợp. Thử đổi tâm trạng hoặc thời lượng.` (hoặc `Bạn đã có tất cả sách hệ thống trên kệ.`) · `error` + `Thử lại`.

## API
`GET /api/recommendations?mood=&max_minutes=&limit=` → `{items[{…sách, reasons[], estimated_minutes}], moods[], favorite_categories[], onboarded, has_history, top_categories[]}` · `PUT /api/recommendations/preferences` (`{favorite_categories: [slug], onboarded: true}`; slug lạ → 400).
