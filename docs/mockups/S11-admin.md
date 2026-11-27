# S11 – Quản Trị

**Mục đích:** nơi admin quản lý nội dung **dùng chung**: sách hệ thống, thể loại, giọng hệ thống và danh sách tài khoản.  **Chỉ có với `role=admin`:** mục *Quản Trị* chỉ hiện trong sidebar của admin (web không dựng màn, desktop không tạo tab); mọi endpoint `/api/admin/*` trả `403` cho người khác và `401` khi chưa đăng nhập.

## Bố cục
```
┌ Quản Trị ───────────────────────────────────────────────────────────┐
│ Quản lý nội dung dùng chung cho mọi người.                          │
│ [ Sách hệ thống ] [ Thể loại ] [ Giọng hệ thống ] [ Âm thanh nền ] [ Người dùng ]    │
│ ─ Sách hệ thống ───────────────────────  [ + Thêm sách hệ thống ]  │
│ [bìa] Đắc Nhân Tâm · Dale Carnegie · 2 chương · Kỹ năng sống        │
│       ● Công khai · 12 kệ              [ Gỡ công khai ] [✎] [🗑]  │
│ [bìa] Sách riêng của admin   ○ Riêng tư   [ Công khai ] [✎] [🗑]     │
│ ─ Thể loại ─────────────────────────────  [ + Thêm thể loại ]       │
│ ● Tiểu thuyết · 3 sách · tieu-thuyet                      [✎] [🗑]   │
│ ─ Giọng hệ thống ───────────────────────────────────────────────────│
│ Giọng Hoa  ● Công khai ✓ Mặc định hệ thống  [▶][★ Đặt mặc định][Gỡ]  │
│ ─ Người dùng (chỉ xem) ─────────────────────────────────────────────│
│ Tài khoản · Họ tên · Vai trò · Ngày tạo · Sách · Giọng              │
└─────────────────────────────────────────────────────────────────────┘
```

## Luật theo từng mục
- **Sách hệ thống (CRUD đầy đủ):** `+ Thêm sách hệ thống` mở S02 với ô *Công khai* đã tick sẵn (chọn thể loại, ảnh bìa như thường). `✎` sửa **tên, tác giả, thể loại, ảnh bìa** (`PATCH /api/books/{id}`, `PUT …/cover`). `🗑` xóa hẳn sách (hộp xác nhận nêu số người đang giữ sách; **tiến độ nghe và trích dẫn của họ cũng mất**). Admin chỉ sửa/xóa được sách công khai hoặc của chính mình; sách riêng của người khác trả `404`, thành viên thường trả `403`.
  Danh sách hiện các sách **công khai** (kèm số kệ đang giữ sách) và các sách **admin tự tải lên** (ứng viên để công khai). `Công khai` chỉ bật cho sách của chính admin; `Gỡ công khai` hỏi xác nhận (người đã để sách trên kệ sẽ không còn thấy). Sách riêng của người khác **không bao giờ** xuất hiện, `PUT` lên sách đó trả `404`. Sách công khai hiện ở S10 Khám phá. Tải sách mới: S02 như thường.
- **Thể loại:** thêm / sửa (tên, biểu tượng, màu `#rrggbb`) / xóa. Slug tự sinh từ tên (bỏ dấu, trùng thì thêm `-2`), giữ nguyên khi đổi tên. Xóa không xóa sách: sách trong thể loại đó thành chưa phân loại. **`Khác` không xóa được.** Thay đổi hiện ngay ở sidebar.
- **Giọng hệ thống:** liệt kê giọng công khai và giọng clone của chính admin. `Công khai` / `Gỡ công khai` chia sẻ hoặc thu hồi; `Đặt mặc định` chọn **giọng mặc định hệ thống** — giọng bắt đầu của người chưa tự chọn (người đã chọn rồi giữ lựa chọn của họ). Chỉ giọng công khai mới đặt được làm mặc định; giọng đang là mặc định không gỡ công khai được.
- **Âm thanh nền:** thư viện nhạc/tiếng nền mà mọi người chọn trong S03. `+ Thêm âm thanh` (file MP3/OGG/WAV/M4A ≤ 15 MB + tên hiển thị; server kiểm tra đuôi và nội dung, từ chối file không phải âm thanh), `▶ Nghe thử`/`Dừng`, `✎` đổi tên, `🗑` xóa (có xác nhận; ai đang dùng bản đó sẽ không nghe nhạc nền cho tới khi chọn bản khác). **Chỉ thêm nhạc không dính bản quyền.** File lưu ở `AMBIENT_DIR` (mặc định `.studylab/ambient`).
- **Người dùng (chỉ xem):** tài khoản, họ tên, vai trò, ngày tạo, số sách và số giọng sở hữu. **Không** có nội dung riêng, mật khẩu hay lịch sử nghe của họ.

## Trạng thái
`loading` · `empty` (mỗi mục có thông báo riêng) · `error` + `Thử lại` · toast sau mỗi thay đổi (`Đã công khai "<tên>"`, `Đã gỡ …`, `Đã xóa thể loại "<tên>"`).

## API (tất cả cần admin)
`GET /api/admin/books` · `PUT /api/admin/books/{id}/public` · `GET|POST /api/admin/categories` · `PUT|DELETE /api/admin/categories/{id}` · `GET /api/admin/voices` · `PUT /api/admin/voices/{id}/public` · `PUT /api/admin/default-voice` · `GET /api/admin/users` · `POST /api/admin/ambient` (multipart `name`, `file`) · `PATCH|DELETE /api/admin/ambient/{id}`. Người nghe: `GET /api/ambient` (danh sách, cần đăng nhập) và `GET /api/ambient/{id}/audio` (công khai như ảnh bìa, vì thẻ `<audio>` không gửi được token).
