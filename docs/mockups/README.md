# Mockup màn hình – Audiobook TTS

Bộ mockup này là **hợp đồng giao diện chung** cho Web (React) và Desktop (CustomTkinter).
Công nghệ khác nhau, nhưng **số màn hình, tên màn, chức năng, trạng thái và API phải khớp nhau**.

## Danh sách màn hình (11 màn – cả hai client đều phải có đủ)

| Mã | Màn hình | File | Loại | Nhóm tab |
|----|----------|------|------|----------|
| S01 | Kệ sách của tôi | [S01-library.md](S01-library.md) | Trang | Kệ Sách Của Tôi |
| S02 | Thêm tài liệu | [S02-upload-document.md](S02-upload-document.md) | Hộp thoại | Thư Viện & Ghi Chú |
| S03 | Phòng Đọc (player) | [S03-reading-room.md](S03-reading-room.md) | Trang | Phòng Đọc |
| S04 | Kho Giọng Đọc (+ hộp thoại Thêm giọng mới) | [S04-voices.md](S04-voices.md) | Trang | Kho Giọng Đọc |
| S05 | Kiểm tra kết nối & Cài đặt | [S05-connection-settings.md](S05-connection-settings.md) | Hộp thoại | (menu ⚙) |
| S06 | Trích dẫn yêu thích | [S06-audio-notes.md](S06-audio-notes.md) | Trang | Trích Dẫn Yêu Thích |
| S07 | Xuất audio | [S07-export.md](S07-export.md) | Hộp thoại | Thư Viện & Ghi Chú |
| S08 | Thống kê | [S08-statistics.md](S08-statistics.md) | Trang | Thống Kê |
| S10 | Khám phá | [S10-explore.md](S10-explore.md) | Trang | Khám Phá |
| S11 | Quản Trị (chỉ admin) | [S11-admin.md](S11-admin.md) | Trang | Quản Trị |
| S09 | Đăng nhập & Đăng ký | [S09-login.md](S09-login.md) | Trang (ngoài sidebar) | – |

## Điều hướng chung

Thanh điều hướng là **sidebar dọc bên trái** (web ở màn hẹp ≤ 860 px: thanh dưới đáy). Tên, thứ tự, biểu tượng giống nhau ở hai client. Màu, chữ và thành phần theo [design system](../conventions/design.md).

```
┌───────────────┬──────────────────────────────────────────┐
│ ▣ Audiobook TTS│  Tiêu đề màn hình                  [hành động] │
│ 🎧 Phòng Đọc   │                                          │
│ 🧭 Khám Phá    │                                          │
│ 📚 Kệ Sách Của Tôi │  Nội dung                          │
│ ⭐ Trích Dẫn Yêu Thích │                                  │
│ 📊 Thống Kê    │                                          │
│ 🎙 Kho Giọng Đọc│                                         │
│ 🛡 Quản Trị (admin)│                                      │
│ CÔNG CỤ       │                                          │
│ ⚙ Kết nối & Cài đặt │                                    │
│ 🖥 Giao diện: Tự động │                                   │
└───────────────┴──────────────────────────────────────────┘
```

| Tab | Màn chính | Màn phụ |
|-----|-----------|---------|
| Phòng Đọc | S03 | S04 (ô chọn giọng › `+ Thêm giọng mới…` chuyển sang màn Kho Giọng Đọc) |
| Khám Phá | S10 | S02 (admin đăng sách hệ thống) |
| Kệ Sách Của Tôi | S01 (4 tab theo trạng thái) | S02, S07 |
| Trích Dẫn Yêu Thích | S06 | S03 (nút ⭐ / phím B lưu trích dẫn) |
| Thống Kê | S08 | – |
| Công cụ › Kết nối & Cài đặt | S05 | – |
| Kho Giọng Đọc | S04 (giọng hệ thống + giọng của tôi) | hộp thoại Thêm giọng mới, Đổi tên |
| Quản Trị (chỉ `role=admin`) | S11 (sách hệ thống, thể loại, giọng hệ thống, người dùng) | – |
| Công cụ › Giao diện | đổi Tự động / Sáng / Tối (lưu lại) | – |

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
| Danh sách / tìm / đổi tên / xóa tài liệu | S01 | `GET/PATCH/DELETE /api/books` | Lưới thẻ | Danh sách bảng |
| Tải tài liệu lên | S02 | `POST /api/books/ingest` | Kéo thả / chọn file | Hộp thoại chọn file |
| Phát / dừng / câu trước / sau / nhảy câu | S03 | `GET /api/audio/{book}/{idx}` | `<audio>` + prefetch | pygame + Producer/Consumer |
| Đổi tốc độ | S03 | `GET /api/audio/...?speed=` | `playbackRate` hoặc `speed=` | gửi `speed=` |
| Karaoke highlight | S03 | `GET /api/books/{id}/sentences` | CSS class | tag trong textbox |
| Auto-Bookmark / Tiếp tục đọc | S03 | `GET/POST /api/bookmarks` | ✔ | ✔ |
| Ghi log phiên đọc | S03 | `POST /api/sessions` | `onended` | consumer |
| Chọn giọng | S03, S04 | `GET /api/voices` *(mới)* | Dropdown | Dropdown |
| Thêm giọng (clone) | S04 | `POST /api/voices/clone` *(mới)* | Form | Form |
| Kiểm tra kết nối | S05 | `GET /api/health/network`, `POST /api/tts/verify` *(mới)* | ✔ | ✔ |
| Trích dẫn yêu thích | S03, S06 | `/api/notes` | `getSelection()` | bôi đen textbox |
| Xuất audio | S07 | `POST /api/books/{id}/export` *(mới)* | Tải về | Lưu file |
| Thống kê | S08 | `GET /api/analytics/...` | Chart.js | Matplotlib |

> Trạng thái endpoint: tất cả endpoint trong bảng đã có trong backend FastAPI (`/docs` liệt kê đầy đủ), **trừ** thống kê theo giọng `GET /api/analytics/voices` (S08) vì phiên đọc chưa ghi lại giọng. Dấu *(mới)* chỉ để đánh dấu endpoint thêm sau hợp đồng cũ `docs/specs/002-fullstack-web-player/contracts/rest-api-endpoints.md`.

## Cách dùng bộ mockup

1. Dựng màn theo thứ tự S01 → S03 → S02 → S04 → S05 → S06 → S07 → S08.
2. Mỗi file có: **mục đích · bố cục · thành phần · trạng thái · hành vi · API · ghi chú riêng Web/Desktop · tiêu chí hoàn thành**.
3. Khi làm xong một màn ở client này, đối chiếu mục *Tiêu chí hoàn thành* ở client kia để giữ khớp.
