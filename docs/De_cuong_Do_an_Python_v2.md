## **KẾ HOẠCH TỔNG THỂ – ĐỒ ÁN AUDIOBOOK TTS (MONOREPO)**

### **A. Tổng quan**

**Mục tiêu:** Xây dựng ứng dụng đọc sách/tài liệu học tập bằng giọng nói AI qua Cloud TTS. Ứng dụng có hai client là **Desktop** (CustomTkinter) và **Web**, dùng chung một **Backend**.

**Phạm vi:**

* Chỉ một người dùng, không có đăng nhập.  
* Hỗ trợ file PDF có lớp chữ, DOCX, TXT. Không xử lý PDF scan (không OCR).  
* Cloud TTS: phát triển với provider giả hoặc miễn phí trước, chốt provider trả phí sau.

**Nguyên tắc thiết kế:**

1. **API Key chỉ nằm ở backend.** Client không bao giờ gọi trực tiếp Cloud TTS.  
2. **Mọi lời gọi TTS đi qua interface `TTSProvider`**, nên đổi provider chỉ cần đổi `.env`.  
3. **Audio được cache** theo `hash(provider + voice_id + text)`, không gọi API trùng.  
4. **Tốc độ đọc xử lý ở client.** Audio luôn sinh ở tốc độ 1.0x.  
5. **Thống kê tính ở backend** bằng Pandas/NumPy và trả JSON. Mỗi client tự vẽ biểu đồ.

---

### **B. Kiến trúc & công nghệ**

```
Cloud TTS (thật) / Mock / Offline TTS
              ▲
              │  TTSProvider interface
┌─────────────┴──────────────────────────────┐
│ BACKEND – FastAPI + SQLAlchemy + Alembic   │
│ documents · voices · tts · notes · logs    │
│ stats (Pandas/NumPy) · network (socket)    │
└──────▲───────────────────────────▲─────────┘
       │ REST/JSON + audio file     │
┌──────┴──────────┐         ┌──────┴──────────┐
│ DESKTOP         │         │ WEB             │
│ CustomTkinter   │         │ React+Vite+TS   │
│ threading+Queue │         │ HTML5 Audio     │
│ pygame.mixer    │         │ Chart.js        │
│ Matplotlib      │         │                 │
└─────────────────┘         └─────────────────┘
           MySQL 8 (chỉ backend truy cập)
```

| Thành phần | Công nghệ |
| ----- | ----- |
| Backend | Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2, Alembic, PyMySQL, Pydantic |
| Xử lý tài liệu | pypdf, python-docx, `re`, `unicodedata` |
| Mạng | `socket` (DNS, port, latency), `requests` hoặc `httpx` |
| Audio | `wave` (ghép WAV), pydub \+ ffmpeg (MP3, không bắt buộc) |
| Thống kê | Pandas, NumPy |
| Desktop | CustomTkinter, threading, `queue.Queue`, pygame.mixer, Matplotlib (FigureCanvasTkAgg) |
| Web | React \+ Vite \+ TypeScript, Chart.js. Phương án thay thế thuần Python: Jinja2 \+ HTMX |
| Hạ tầng | Docker Compose (MySQL \+ backend), uv (Python workspace), pnpm (web) |
| Kiểm thử | pytest, ruff |

---

### **C. Cấu trúc monorepo**

```
audiobook-tts/
├── backend/
│   ├── app/
│   │   ├── api/            # routers
│   │   ├── services/
│   │   │   ├── tts/        # base.py, mock.py, offline.py, <provider_thật>.py
│   │   │   ├── parser/     # pdf.py, docx.py, txt.py, cleaner.py, chunker.py
│   │   │   ├── audio/      # cache.py, export.py
│   │   │   ├── stats/      # analytics.py
│   │   │   └── network/    # diagnostics.py
│   │   ├── db/             # models.py, session.py
│   │   └── core/           # config.py, logging.py
│   ├── migrations/
│   ├── scripts/test_connection.py
│   └── tests/
├── apps/
│   ├── desktop/            # ui/, player/, api_client.py, main.py
│   └── web/                # src/pages, src/components, src/api
├── packages/py-shared/     # Pydantic schemas + API client (backend ↔ desktop)
├── storage/                # uploads/ audio_cache/ exports/ voice_samples/
├── db/schema.sql
├── docker-compose.yml
├── pyproject.toml          # uv workspace
├── pnpm-workspace.yaml
├── .env.example
└── README.md
```

---

### **D. Thiết kế CSDL (7 bảng)**

| Bảng | Các cột chính |
| ----- | ----- |
| `documents` | id, title, file\_path, file\_type, total\_chunks, current\_chunk\_index, last\_voice\_id, last\_speed, created\_at, updated\_at |
| `document_chunks` | id, doc\_id, chunk\_index, text, word\_count |
| `voice_profiles` | voice\_id, provider, display\_name, description, language, gender, style, is\_custom, sample\_path, consent\_at |
| `audio_cache` | hash (PK), provider, voice\_id, file\_path, duration\_ms, created\_at |
| `audio_notes` | id, doc\_id, chunk\_index, start\_offset, end\_offset, note\_text, audio\_file\_path, created\_at |
| `reading_logs` | id, doc\_id, voice\_id, chunk\_index, words\_count, duration\_seconds, api\_latency\_ms, status, error\_code, speed, read\_date |
| `app_settings` | key, value (provider đang dùng, giới hạn ký tự/ngày…) |

---

### **E. Danh sách API backend**

| Nhóm | Endpoint |
| ----- | ----- |
| Health | `GET /health`, `GET /health/network`, `POST /tts/verify` |
| Voices | `GET /voices`, `POST /voices/sync`, `POST /voices/clone`, `DELETE /voices/{id}` |
| Documents | `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/chunks`, `PATCH /documents/{id}/progress`, `DELETE /documents/{id}` |
| TTS | `GET /tts/{doc_id}/{chunk_index}?voice_id=` → trả file audio, có cache |
| Logs | `POST /logs` |
| Notes | `POST /notes`, `GET /notes`, `GET /notes/{id}/audio`, `DELETE /notes/{id}` |
| Export | `POST /documents/{id}/export`, `GET /exports/{job_id}` |
| Stats | `GET /stats/daily?days=7`, `GET /stats/voices`, `GET /stats/metrics` |

---

### **F. Chiến lược TTS khi chưa thuê API**

| Provider | Vai trò | Thời điểm dùng |
| ----- | ----- | ----- |
| `MockProvider` | Sinh WAV im lặng hoặc bíp, dài theo số từ; giả lập độ trễ và tỷ lệ lỗi; clone giả | Từ giai đoạn 1, cho unit test và phát triển UI |
| `OfflineProvider` (Piper hoặc MMS-TTS tiếng Việt) | Nghe thử giọng Việt thật, miễn phí, chạy offline | Từ giai đoạn 1–2, để kiểm tra highlight và tốc độ |
| Provider thật (trả phí) | Sản phẩm cuối, clone giọng, số liệu thống kê thật | Sau mốc ★ |

**Tiêu chí chọn provider thật,** xếp theo mức ưu tiên:

1. Có clone giọng tiếng Việt.  
2. Số lượng và độ tự nhiên của giọng Việt có sẵn.  
3. Giá, có trial hay free tier không.  
4. Latency đo từ Việt Nam.  
5. Giới hạn ký tự mỗi request và rate limit.  
6. Chất lượng tài liệu API.

Nếu không có provider nào đáp ứng được cả tiêu chí 1 và 2, có thể dùng hai provider song song: một cho giọng có sẵn, một cho clone.

---

### **G. Lộ trình chi tiết**

Mã công việc (ví dụ 2.3) dùng để hai bên tham chiếu khi trao đổi.

#### **Giai đoạn 0 – Khởi tạo monorepo *(tuần 1, nửa đầu)***

* \[ \] 0.1 Tạo cấu trúc thư mục, uv workspace, pnpm workspace, `.gitignore`, `.env.example`  
* \[ \] 0.2 Docker Compose chạy MySQL 8 và backend  
* \[ \] 0.3 FastAPI skeleton, `core/config.py` đọc `.env`, endpoint `GET /health`  
* \[ \] 0.4 Cấu hình ruff và pytest, viết một test mẫu

**Kiểm tra:** `docker compose up` chạy được và `/health` trả `ok`.

#### **Giai đoạn 1 – Interface TTS & kiểm thử mạng *(tuần 1, nửa sau → tuần 2\)***

* \[ \] 1.1 Định nghĩa `TTSProvider` (`synthesize`, `list_voices`, `clone_voice`, `verify`, `capabilities`)  
* \[ \] 1.2 Viết `MockProvider`, có cấu hình độ trễ và tỷ lệ lỗi  
* \[ \] 1.3 Viết `OfflineProvider` dùng giọng Việt offline  
* \[ \] 1.4 `network/diagnostics.py` dùng socket: phân giải DNS, kiểm tra port 443, đo latency tới domain các provider ứng viên  
* \[ \] 1.5 `scripts/test_connection.py`: chạy diagnostics, gọi `synthesize`, lưu `output.wav`  
* \[ \] 1.6 Endpoint `/health/network` và `/tts/verify`  
* \[ \] 1.7 *(Song song)* Lập bảng so sánh provider theo tiêu chí ở mục F

**Kiểm tra:** `test_connection.py` tạo ra `output.wav` nghe được bằng giọng offline, và có số liệu latency tới các provider ứng viên.

#### **Giai đoạn 2 – CSDL & xử lý tài liệu *(tuần 2–3)***

* \[ \] 2.1 SQLAlchemy models cho 7 bảng, Alembic migration, xuất `db/schema.sql`  
* \[ \] 2.2 Parser cho PDF, DOCX, TXT  
* \[ \] 2.3 Cleaner: chuẩn hóa Unicode NFC, nối dòng bị ngắt, bỏ header/footer lặp, gộp khoảng trắng  
* \[ \] 2.4 Chunker regex, xử lý các trường hợp: "3.14", "TP.", "PGS.TS.", "…", câu dài vượt giới hạn ký tự (cắt tiếp theo dấu phẩy)  
* \[ \] 2.5 Bộ test cho chunker, gồm ít nhất 20 trường hợp tiếng Việt khó  
* \[ \] 2.6 API documents và chunks  
* \[ \] 2.7 Audio cache cùng endpoint `GET /tts/{doc}/{idx}`  
* \[ \] 2.8 API voices: sync từ provider, lưu vào `voice_profiles`

**Kiểm tra:** upload một PDF giáo trình thật, xem được danh sách câu sạch; gọi TTS lần hai thì lấy từ cache.

#### **Giai đoạn 3 – Desktop client *(tuần 3–5)***

* \[ \] 3.1 `api_client.py` dùng schema từ `py-shared`  
* \[ \] 3.2 Khung 3 tab: Phòng Đọc, Thư Viện & Ghi Chú, Thống Kê (tạm để trống)  
* \[ \] 3.3 Phòng Đọc: chọn tài liệu, dropdown giọng, khung văn bản, thanh điều khiển  
* \[ \] 3.4 Producer thread: tải trước N câu (mặc định 2\) vào `Queue(maxsize=N)`  
* \[ \] 3.5 Consumer thread: phát bằng pygame.mixer, ghi log; cập nhật UI qua `after()`  
* \[ \] 3.6 Play/Pause, Next/Prev, bấm chọn câu bất kỳ (dùng `threading.Event` để hủy và xả queue)  
* \[ \] 3.7 Thanh trượt tốc độ 0.75x–1.5x, xử lý phía client  
* \[ \] 3.8 Karaoke highlight câu đang đọc, tự cuộn theo  
* \[ \] 3.9 Auto-Bookmark và nút "Tiếp tục đọc" (khôi phục tài liệu, câu, giọng)  
* \[ \] 3.10 Kiểm tra kết nối: nhập API Key (gửi về backend lưu), gọi verify  
* \[ \] 3.11 Thêm giọng mới: chọn file mẫu 5–15 giây, đặt tên, tick đồng thuận, gọi `/voices/clone`  
* \[ \] 3.12 Thư viện: danh sách tài liệu, mở lại, xóa  
* \[ \] 3.13 Thử producer–consumer với độ trễ mock 200 ms, 1 s, 3 s và tỷ lệ lỗi 10%

**Kiểm tra:** đọc liền một chương; khi nhảy câu UI không bị đơ; tắt mở lại app thì đọc tiếp đúng vị trí.

#### **★ Mốc chốt provider *(cuối tuần 5\)***

* \[ \] ★.1 Chốt provider dựa vào bảng so sánh 1.7  
* \[ \] ★.2 Đăng ký, lấy API Key, viết adapter mới  
* \[ \] ★.3 Chạy lại `test_connection.py` với API thật  
* \[ \] ★.4 Đo latency thật và chỉnh kích thước queue N  
* \[ \] ★.5 Đặt giới hạn ký tự mỗi ngày trong `app_settings` để kiểm soát chi phí

#### **Giai đoạn 4 – Web client *(tuần 6–7)***

* \[ \] 4.1 Vite \+ React \+ TS, generate type từ OpenAPI  
* \[ \] 4.2 Trang Phòng Đọc: hiển thị câu, highlight, điều khiển phát  
* \[ \] 4.3 Prefetch N câu dạng Blob URL; `playbackRate` cho tốc độ; giải phóng URL sau khi phát  
* \[ \] 4.4 Thư viện, upload tài liệu, danh sách giọng, clone giọng  
* \[ \] 4.5 Đồng bộ tiến độ: đọc dở trên desktop thì mở web đọc tiếp được, và ngược lại

**Kiểm tra:** web làm được đủ chức năng như desktop; đồng bộ bookmark hoạt động.

#### **Giai đoạn 5 – Ghi chú, Export & Thống kê *(tuần 7–8)***

* \[ \] 5.1 Audio Note: bôi đen đoạn văn → lưu text, offset và audio tương ứng (cả hai client)  
* \[ \] 5.2 Kho ôn tập: liệt kê và phát lại ghi chú  
* \[ \] 5.3 Export: job chạy nền ghép audio của các câu thành WAV (và MP3 nếu có ffmpeg), tải về  
* \[ \] 5.4 `stats/analytics.py`: Pandas đọc `reading_logs`; NumPy tính tốc độ đọc trung bình (từ/phút), latency trung bình và p95, tỷ lệ thành công  
* \[ \] 5.5 Desktop: biểu đồ cột (phút và số từ theo ngày), biểu đồ tròn (tỷ lệ giọng), bảng chỉ số, vẽ bằng Matplotlib  
* \[ \] 5.6 Web: các biểu đồ tương tự bằng Chart.js  
* \[ \] 5.7 Test cho hàm thống kê, dùng dữ liệu mẫu cố định

**Kiểm tra:** sau vài phiên đọc thật, số liệu trên hai client khớp nhau.

#### **Giai đoạn 6 – Đóng gói & báo cáo *(tuần 9\)***

* \[ \] 6.1 README: cài đặt, cấu hình `.env`, chạy từng phần  
* \[ \] 6.2 `requirements.txt` (xuất từ uv), `schema.sql`, script seed dữ liệu demo  
* \[ \] 6.3 Đóng gói desktop bằng PyInstaller; build web ra static, cho backend serve  
* \[ \] 6.4 Rà soát: xử lý lỗi mạng, mất kết nối, hết quota API  
* \[ \] 6.5 Quay video demo toàn bộ luồng  
* \[ \] 6.6 Viết báo cáo: kiến trúc, CSDL, cơ chế đa luồng, kết quả đo đạc  
* 