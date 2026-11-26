# Mockup màn hình – Audiobook TTS

Bộ mockup này là **hợp đồng giao diện chung** cho Web (React) và Desktop (CustomTkinter).
Công nghệ khác nhau, nhưng **số màn hình, tên màn, chức năng, trạng thái và API phải khớp nhau**.

## Danh sách màn hình (8 màn – cả hai client đều phải có đủ)

| Mã | Màn hình | File | Loại | Nhóm tab |
|----|----------|------|------|----------|
| S01 | Thư viện tài liệu | [S01-library.md](S01-library.md) | Trang | Thư Viện & Ghi Chú |
| S02 | Thêm tài liệu | [S02-upload-document.md](S02-upload-document.md) | Hộp thoại | Thư Viện & Ghi Chú |
| S03 | Phòng Đọc (player) | [S03-reading-room.md](S03-reading-room.md) | Trang | Phòng Đọc |
| S04 | Chọn giọng & Thêm giọng mới | [S04-voices.md](S04-voices.md) | Hộp thoại | Phòng Đọc |
| S05 | Kiểm tra kết nối & Cài đặt | [S05-connection-settings.md](S05-connection-settings.md) | Hộp thoại | (menu ⚙) |
| S06 | Ghi chú âm thanh | [S06-audio-notes.md](S06-audio-notes.md) | Trang | Thư Viện & Ghi Chú |
| S07 | Xuất audio | [S07-export.md](S07-export.md) | Hộp thoại | Thư Viện & Ghi Chú |
| S08 | Thống kê | [S08-statistics.md](S08-statistics.md) | Trang | Thống Kê |

## Điều hướng chung

Thanh điều hướng có **3 tab** + nút ⚙. Tên, thứ tự, biểu tượng giống nhau ở hai client.

```
┌──────────────────────────────────────────────────────────────┐
│ 🎧 Audiobook TTS   [ Phòng Đọc ] [ Thư Viện & Ghi Chú ] [ Thống Kê ]      ⚙ │
└──────────────────────────────────────────────────────────────┘
```

| Tab | Màn chính | Màn phụ |
|-----|-----------|---------|
| Phòng Đọc | S03 | S04 (mở từ ô chọn giọng) |
| Thư Viện & Ghi Chú | S01 (có 2 mục con: *Tài liệu* / *Ghi chú*) | S02, S06, S07 |
| Thống Kê | S08 | – |
| ⚙ | S05 | – |

Mở app lần đầu: vào **Thư Viện** nếu chưa có tài liệu; nếu có tài liệu đọc dở thì vào **Phòng Đọc** và hiện nút *Tiếp tục đọc*.

## Quy ước chung

- **Ngôn ngữ giao diện:** tiếng Việt. Dùng đúng chuỗi trong mockup để hai client giống nhau.
- **Trạng thái bắt buộc ở mọi màn:** `loading` (đang tải), `empty` (chưa có dữ liệu), `error` (lỗi, có nút *Thử lại*), `ready`.
- **Lỗi mạng/backend:** thanh cảnh báo đỏ trên cùng: `Không kết nối được máy chủ. [Thử lại]`.
- **Tốc độ đọc:** 0.75x / 1.0x / 1.25x / 1.5x. Desktop gửi `speed=` lên backend (giữ cao độ giọng với edge-tts; audio cache riêng từng mức tốc độ). Web có thể dùng `audio.playbackRate`; hành vi nhìn thấy phải giống nhau.
- **Phím tắt (S03):** `Space` phát/dừng, `←` `→` câu trước/sau, `↑` `↓` đổi tốc độ, `N` ghi chú nhanh.
- **Mốc thời gian:** hiển thị `dd/mm/yyyy HH:MM`; thời lượng `mm:ss`.
- Ký hiệu trong khung ASCII: `[ Nút ]`, `( ) / (•)` radio, `[ ] / [x]` checkbox, `▼` dropdown, `░▓` thanh tiến độ.

## Ma trận chức năng (đối chiếu hai client)

| Chức năng | Màn | API backend | Web | Desktop |
|-----------|-----|-------------|-----|---------|
| Danh sách / tìm / xóa tài liệu | S01 | `GET/DELETE /api/books` | Lưới thẻ | Danh sách bảng |
| Tải tài liệu lên | S02 | `POST /api/books/ingest` | Kéo thả / chọn file | Hộp thoại chọn file |
| Phát / dừng / câu trước / sau / nhảy câu | S03 | `GET /api/audio/{book}/{idx}` | `<audio>` + prefetch | pygame + Producer/Consumer |
| Đổi tốc độ | S03 | `GET /api/audio/...?speed=` | `playbackRate` hoặc `speed=` | gửi `speed=` |
| Karaoke highlight | S03 | `GET /api/books/{id}/sentences` | CSS class | tag trong textbox |
| Auto-Bookmark / Tiếp tục đọc | S03 | `GET/POST /api/bookmarks` | ✔ | ✔ |
| Ghi log phiên đọc | S03 | `POST /api/sessions` | `onended` | consumer |
| Chọn giọng | S03, S04 | `GET /api/voices` *(mới)* | Dropdown | Dropdown |
| Thêm giọng (clone) | S04 | `POST /api/voices/clone` *(mới)* | Form | Form |
| Kiểm tra kết nối | S05 | `GET /api/health/network`, `POST /api/tts/verify` *(mới)* | ✔ | ✔ |
| Ghi chú âm thanh | S03, S06 | `/api/notes` *(mới)* | `getSelection()` | bôi đen textbox |
| Xuất audio | S07 | `POST /api/books/{id}/export` *(mới)* | Tải về | Lưu file |
| Thống kê | S08 | `GET /api/analytics/...` | Chart.js | Matplotlib |

> Trạng thái endpoint: tất cả endpoint trong bảng đã có trong backend FastAPI (`/docs` liệt kê đầy đủ), **trừ** thống kê theo giọng `GET /api/analytics/voices` (S08) vì phiên đọc chưa ghi lại giọng. Dấu *(mới)* chỉ để đánh dấu endpoint thêm sau hợp đồng cũ `docs/specs/002-fullstack-web-player/contracts/rest-api-endpoints.md`.

## Cách dùng bộ mockup

1. Dựng màn theo thứ tự S01 → S03 → S02 → S04 → S05 → S06 → S07 → S08.
2. Mỗi file có: **mục đích · bố cục · thành phần · trạng thái · hành vi · API · ghi chú riêng Web/Desktop · tiêu chí hoàn thành**.
3. Khi làm xong một màn ở client này, đối chiếu mục *Tiêu chí hoàn thành* ở client kia để giữ khớp.
