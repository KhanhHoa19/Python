# S02 – Thêm tài liệu

**Mục đích:** tải file lên để backend phân tích và tách câu.  **Mở từ:** S01 (`+ Thêm tài liệu`).

## Bố cục
```
┌ Thêm tài liệu ──────────────────────────────── ✕ ┐
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │   ⬆  Kéo thả file vào đây hoặc [ Chọn file ] │  │
│  │      Hỗ trợ: PDF (có lớp chữ), DOCX, TXT, MD  │  │
│  │      Tối đa 10 MB                             │  │
│  └──────────────────────────────────────────────┘  │
│  Tên tài liệu : [ Giáo trình Python            ]   │
│  Tác giả      : [ (không bắt buộc)             ]   │
│                                                    │
│  Tiến trình: ▓▓▓▓▓▓░░░░ Đang tách câu… 60%        │
│                                  [ Hủy ] [ Tải lên ] │
└────────────────────────────────────────────────────┘
```

## Thành phần & luật
| Thành phần | Luật |
|------------|------|
| Vùng chọn file | Chỉ nhận `.pdf .docx .txt .md`, ≤ 10 MB |
| Tên tài liệu | Tự điền từ tên file/nội dung, người dùng sửa được |
| Tác giả | Tùy chọn, mặc định `Không rõ` |
| Tiến trình | 3 bước: `Đang tải lên` → `Đang đọc nội dung` → `Đang tách câu` |

## Trạng thái
- **idle:** nút `Tải lên` bị khóa đến khi chọn file hợp lệ.
- **uploading:** khóa form, hiện tiến trình, `Hủy` dừng yêu cầu.
- **success:** đóng hộp, quay S01, thẻ mới nổi bật 3 giây, toast `Đã thêm "<tên>" (1.240 câu)`.
- **error:** thông báo ngay trong hộp, giữ nguyên file đã chọn:
  - `Định dạng không được hỗ trợ.`
  - `File vượt quá 10 MB.`
  - `Không đọc được chữ. Có thể đây là PDF scan (chưa hỗ trợ OCR).`

## API
`POST /api/books/ingest` (multipart: `file`, `title`, `author`) → `201 {book_id, total_sentences,…}`.
> Backend nhận `.txt .md .pdf .docx` (≤ 10 MB). PDF scan không có chữ trả `400` với thông điệp nhắc OCR.

## Ghi chú theo client
- **Web:** kéo thả HTML5 + `<input type=file>`.
- **Desktop:** `filedialog.askopenfilename` (tkinterdnd2 là tùy chọn); tiến trình chạy trong thread, cập nhật bằng `after()`.

## Tiêu chí hoàn thành
- [ ] Ba thông báo lỗi trên hiển thị đúng chuỗi.
- [ ] Thành công thì S01 tự làm mới.
- [ ] Không treo giao diện khi file lớn.
