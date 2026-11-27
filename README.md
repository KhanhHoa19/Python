# Audiobook TTS

Ứng dụng nghe sách nói: nạp sách (PDF, DOCX, TXT, MD), nghe bằng giọng đọc nhân tạo (TTS), nhiều người dùng với kho sách chung.
Một backend dùng chung cho **web** (React) và **desktop** (CustomTkinter); hai client có cùng màn hình và chức năng.

## Chức năng
- **Tài khoản:** đăng ký / đăng nhập (JWT), vai trò `admin` và `user`. Sách, ghi chú, tiến độ, cài đặt là của riêng từng người; admin cũng không đọc được dữ liệu riêng của người khác.
- **Gợi ý:** tab *Gợi Ý* đề xuất sách hệ thống theo lịch sử nghe, thể loại yêu thích (hỏi chọn lần đầu, sửa được), thời lượng mong muốn và 6 tâm trạng (ánh xạ sang thể loại), kèm lý do từng gợi ý; kết hợp độ phổ biến khi đã có lịch sử.
- **Thư viện:** Kệ sách (tab Đang nghe dở / Chưa nghe / Đã hoàn thành / Yêu thích), Khám phá (kho sách hệ thống), 15 tag chủ đề để lọc, tìm kiếm không phân biệt dấu, ảnh bìa (trang đầu PDF, tự tạo hoặc tải lên).
- **Phòng Đọc:** nghe theo từng câu có tô sáng, mục lục chương (nhận cả "Phần/Chương", loại dòng mục lục), tốc độ 0,75–1,5x, hẹn giờ tắt có giảm dần âm lượng, chuyển giọng.
- **Đọc phân vai:** lời thoại trong ngoặc kép / gạch đầu dòng đọc bằng *giọng nhân vật*, phần còn lại bằng *giọng dẫn chuyện*.
- **Âm thanh nền & chuông chương:** nhạc/tiếng nền lặp dưới giọng đọc với âm lượng riêng; tiếng chuông khi tự sang chương mới.
- **Trích dẫn yêu thích:** lưu cả câu bằng một chạm, gắn nhãn cảm xúc, nghe lại liên tục (playlist).
- **Kho Giọng Đọc:** giọng hệ thống và giọng clone của riêng bạn (có đồng thuận, giới hạn số giọng/người), nghe thử, đặt mặc định.
- **Quản Trị (chỉ admin):** sách hệ thống (thêm, sửa, xóa, công khai), thể loại, giọng công khai và giọng mặc định, thư viện âm thanh nền, danh sách người dùng.
- **Thống kê** thói quen nghe và **xuất audio** (WAV/MP3).

## Cấu trúc
| Thư mục | Nội dung |
|---------|----------|
| `backend/` | FastAPI + SQLAlchemy (MySQL, hoặc SQLite khi thử nghiệm), tests, Dockerfile |
| `apps/web/` | Web React 18 + Vite + TypeScript (`npm test`, `npm run build`) |
| `apps/desktop/` | Desktop CustomTkinter + pygame (xem [apps/desktop/README.md](apps/desktop/README.md)) |
| `docs/mockups/` | **Hợp đồng giao diện** S01–S12 cho cả hai client ([README](docs/mockups/README.md)) |
| `docs/conventions/` | Quy ước code, giao diện ([design.md](docs/conventions/design.md)), bảo mật backend |
| `docs/benchmarks/` | Đo bộ đệm tải trước của trình phát |
| `storage/` | Sao lưu và dữ liệu cục bộ (không commit) |

## Chạy
```bash
cp .env.example .env            # điền ADMIN_PASSWORD, khóa TTS...; .env không bao giờ commit
docker compose up --build -d    # MySQL + backend (5000) + web (5173) + adminer (8081)
```
Web: <http://localhost:5173>. Lần đầu backend tự tạo tài khoản `admin` (mật khẩu `ADMIN_PASSWORD`; nếu để trống sẽ sinh ngẫu nhiên và ghi vào log **một lần**) và 15 thể loại mặc định.
Chưa có khóa TTS: đặt `TTS_PROVIDER=mock` (giọng im lặng, có clone giả).
Chạy không Docker: `./start_dev.sh` (migration, backend, web). Desktop: `cd apps/desktop && python main.py`.

**Đăng nhập nhanh khi phát triển:** `DEV_QUICK_LOGIN=true` thêm 3 ô tài khoản mẫu ở màn đăng nhập (mật khẩu đặt trong `.env`: `DEMO_PASSWORD_*`). **Không bật trên máy chủ dùng chung.**

### Dữ liệu mẫu để xem hệ thống vận hành
```bash
cd backend && python -m scripts.seed_demo_data --base http://localhost:5000 --admin-password ... \
    --demo khanhhoa36=... --demo xuanhai18=...
```
Nạp 28 sách mẫu công khai (nội dung gốc, mọi thể loại) và cho hai tài khoản demo hai gu nghe khác nhau (hồi hộp / học hỏi) để thấy gợi ý khác nhau. Chạy lại an toàn (bỏ qua sách đã có).

## Cấu hình chính (`.env`)
| Biến | Ý nghĩa |
|------|---------|
| `TTS_PROVIDER` | `heygen`, `edge-tts`, `openai` hoặc `mock` (+ khóa riêng của nhà cung cấp) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Tài khoản admin đầu tiên |
| `JWT_SECRET` / `JWT_EXPIRE_HOURS` | Khóa ký token (để trống: tự sinh và lưu trong DB) và thời hạn |
| `MAX_VOICES_PER_USER` | Số giọng clone tối đa mỗi thành viên (admin không giới hạn) |
| `DEV_QUICK_LOGIN`, `DEMO_PASSWORD_*` | Tài khoản mẫu cho phát triển |
| `COVER_DIR`, `QUOTES_DIR`, `AMBIENT_DIR`, `AUDIO_CACHE_DIR`, `EXPORT_DIR`, `VOICE_SAMPLES_DIR` | Nơi lưu file (Docker dùng volume `/app/.studylab`) |

Giới hạn ký tự TTS mỗi ngày do admin đặt ở *Kết nối & Cài đặt*.

## Kiểm thử và chất lượng
```bash
cd backend && pytest -q && ruff check . && mypy src     # ~500 test, gồm kiểm toán quyền cho mọi endpoint
cd apps/web && npm test && npm run build
cd apps/desktop && pytest -q && ruff check .
```
Test không gọi TTS trả phí (dùng nhà cung cấp giả). Quy tắc bắt buộc nằm trong [CLAUDE.md](CLAUDE.md) và `docs/conventions/`.

## Bảo mật (tóm tắt)
- Mọi endpoint cần đăng nhập, trừ danh sách công khai nhỏ (health, đăng nhập/đăng ký, ảnh bìa, file nhạc nền). `backend/tests/integration/test_route_audit.py` tự sinh từ OpenAPI và **fail nếu thêm route mà quên bảo vệ**.
- Dữ liệu của người khác trả `404` như dữ liệu không tồn tại; mật khẩu băm scrypt, đăng nhập sai nhiều lần bị tạm khóa; bí mật chỉ ở `.env`.
- Kiểm tra kết nối TTS chỉ admin (dùng tài khoản TTS dùng chung).

## Giới hạn đã biết
- Đăng ký đang **mở** cho mọi người; chưa có công tắc tắt đăng ký.
- Đọc phân vai chỉ có hai vai; lời thoại gạch đầu dòng nhiều câu chỉ nhận ra ở câu đầu (xem mockup S03).
- Sách nạp trước các bản sửa mục lục cần nạp lại để có mục lục mới.
