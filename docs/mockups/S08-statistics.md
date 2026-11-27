# S08 – Thống kê

**Mục đích:** xem thói quen nghe và hiệu năng hệ thống.  **Tab:** Thống Kê.

## Bố cục
```
┌ Thống Kê ──────────────────────────────────────────────────────┐
│ Khoảng thời gian: ( ) 7 ngày  (•) 30 ngày  ( ) Tất cả           │
│ ┌ Tổng thời gian ┐ ┌ Tổng số từ ┐ ┌ Tốc độ TB ┐ ┌ Tỷ lệ thành công ┐ │
│ │   12 giờ 40    │ │   96.200   │ │ 152 từ/ph │ │      98,4%       │ │
│ └────────────────┘ └────────────┘ └───────────┘ └──────────────────┘ │
│ ┌ Độ trễ API (ms) ─────────────────────────────────────────────┐  │
│ │  Trung bình 640   ·   P95 1.420   ·   Lớn nhất 3.100         │  │
│ └──────────────────────────────────────────────────────────────┘  │
│ ┌ Phút nghe theo ngày (cột) ┐   ┌ Thời gian theo giọng (tròn) ┐   │
│ │ ▇ ▃ ▅ ▁ ▇ ▆ ▂             │   │   ◔  Hoài My 60%             │   │
│ │ T2 T3 T4 T5 T6 T7 CN      │   │      Nam Minh 40%            │   │
│ └───────────────────────────┘   └──────────────────────────────┘   │
│ ┌ Số từ theo ngày (cột) ─────────────────────────────────────┐    │
│ └────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

## Thành phần
| Thành phần | Nguồn số liệu |
|------------|---------------|
| 4 thẻ số | Tổng thời gian, tổng từ, tốc độ nghe TB (từ/phút), tỷ lệ gọi API thành công |
| Độ trễ API | Trung bình, P95, lớn nhất |
| Biểu đồ cột *Phút theo ngày* | Gộp `reading_logs` theo ngày trong tuần |
| Biểu đồ cột *Số từ theo ngày* | Như trên |
| Biểu đồ tròn *Theo giọng* | Tỷ lệ thời gian mỗi giọng |

Số liệu do **backend tính** (Pandas/NumPy) và trả JSON; hai client chỉ vẽ, nên số phải trùng nhau.

## Trạng thái
- **empty:** `Chưa có dữ liệu đọc. Hãy nghe một vài câu rồi quay lại.`
- **loading / error** như README. Đổi khoảng thời gian thì tải lại, giữ nguyên bố cục.

## API
`GET /api/analytics/summary?days=` · `GET /api/analytics/daily?days=` (đủ từng ngày, ngày không đọc = 0) · `GET /api/analytics/metrics?days=` (độ trễ TB/P95/lớn nhất, tỷ lệ thành công, từ/phút) · `GET /api/analytics/voices?days=` (phút/từ/phiên theo giọng, giọng nhiều nhất đứng đầu).

Mỗi phiên đọc lưu giọng đã dùng (cột `reading_sessions.voice`); đổi giọng giữa chừng kết thúc phiên cũ và mở phiên mới. Phiên ghi trước khi có cột này hiện là `Không rõ`. Biểu đồ tròn tên **Thời gian nghe theo giọng**, ẩn khi chưa có phút nào.

## Ghi chú theo client
- **Web:** Chart.js hoặc Recharts, vẽ từ JSON.
- **Desktop:** Matplotlib + `FigureCanvasTkAgg` (backend `Agg` ở phía server nếu dùng ảnh PNG, ở desktop vẽ trực tiếp từ JSON). Màu series giống web.

## Tiêu chí hoàn thành
- [ ] Cùng dữ liệu thì web và desktop hiển thị cùng con số.
- [ ] Đổi khoảng thời gian cập nhật đủ 4 thẻ và 3 biểu đồ.
- [ ] Trạng thái empty hiển thị đúng khi chưa có log.
