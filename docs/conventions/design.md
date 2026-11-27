# Design System — "Giấy & Mực" (paper & ink)

> **Bắt buộc cho mọi màn hình và chức năng mới**, ở cả Web (`apps/web/`) và Desktop (`apps/desktop/`).
> Nguồn token: Web `apps/web/src/index.css` (khối `:root`) · Desktop `apps/desktop/ui/theme.py`. Hai nơi này **phải khớp nhau**; đổi một nơi thì đổi nơi kia.

## 1. Tinh thần

Ứng dụng đọc sách nói nên giao diện **ấm, tĩnh, dễ đọc lâu**: nền giấy (sáng) hoặc mực (tối), **một** màu nhấn hổ phách, chữ nội dung dùng font có chân, mọi thứ còn lại gọn và nhẹ. Không dùng nhiều màu nhấn, không gradient trang trí (trừ ảnh bìa sách sinh tự động).

## 2. Màu (token)

Mỗi màu có cặp **sáng / tối**; giao diện theo hệ thống và người dùng đổi được (Tự động → Sáng → Tối).

| Token | Dùng cho | Sáng | Tối |
|---|---|---|---|
| `bg` | nền trang | `#f5f1ea` | `#14120f` |
| `surface` | thẻ, sidebar, khung đọc | `#fffdf8` | `#1c1916` |
| `surface-2` | ô nhập, nút phụ, vùng lõm | `#f0ebe1` | `#25211d` |
| `surface-3` | hover, thanh tiến độ nền | `#e7e0d3` | `#2f2a25` |
| `border` / `border-strong` | viền thẻ / viền ô nhập | `#e2dacb` / `#cfc5b2` | `#34302a` / `#4a443c` |
| `text` / `text-2` / `muted` | chữ chính / phụ / chú thích | `#26221c` / `#51493d` / `#7b7264` | `#f1ece3` / `#c9c1b4` / `#928a7c` |
| `accent` (+ `-hover`, `-ink`, `-soft`) | nút chính, mục đang chọn, câu đang đọc | `#a95a05` | `#f0a93e` |
| `success` / `warning` / `danger` | trạng thái | `#1f7a4a` / `#8a6200` / `#c0392b` | `#6fcf97` / `#f2c94c` / `#ef6a5b` |
| `chart-1…6` | biểu đồ (theo thứ tự) | amber, xanh lá, xanh dương, tím, đỏ, ngọc | |

**Quy tắc màu**
- **Không viết mã màu thô** (`#xxxxxx`, `gray40`, `rgba(...)`) trong component. Chỉ dùng token (`var(--accent)` ở web, `theme.ACCENT` ở desktop). Ngoại lệ: chữ trắng trên ảnh bìa và trên nút danger đặc.
- Chữ trên nền `accent` dùng `accent-ink`. Chữ nhấn màu trên nền `surface` dùng `accent` (đạt tương phản AA ở cả hai chế độ).
- Ý nghĩa màu cố định: `success` = xong/ổn, `warning` = cần chú ý (gần hết hạn mức), `danger` = lỗi và hành động xóa. Không dùng `accent` để báo lỗi.
- Biểu đồ: web đọc màu bằng `cssVar('--chart-1')` (đã làm trong `BarChart`/`PieChart`), desktop dùng `theme.CHARTS[i]` qua `theme.mode_color`. Vẽ lại khi đổi giao diện.

## 3. Chữ

| Vai trò | Web | Desktop | Cỡ |
|---|---|---|---|
| Giao diện (nút, nhãn, tiêu đề trang) | **Be Vietnam Pro** (thiết kế cho tiếng Việt) | font cài sẵn đầu tiên trong: Be Vietnam Pro, Inter, Segoe UI, Noto Sans, DejaVu Sans | 12–14 |
| Nội dung sách, tên sách, câu trích | **Source Serif 4** (có chân) | Source Serif 4, Literata, Georgia, Noto Serif, DejaVu Serif | 17–19 (nội dung), 22–28 (tên sách) |
| Tiêu đề trang (`PageHeader`) | 700 | 700 | 26–30 |

- Tiêu đề nhóm nhỏ (ví dụ "CÔNG CỤ", "ĐANG ĐỌC"): chữ hoa, đậm, cỡ 10–12, giãn chữ, màu `muted` hoặc `accent`.
- Số liệu dùng chữ số đều bề rộng (`font-variant-numeric: tabular-nums`) ở web.
- Desktop không đóng gói font; nếu máy không có Be Vietnam Pro/Source Serif 4 thì rơi về font hệ thống (đã xử lý trong `theme.apply()`).

## 4. Hình khối và khoảng cách

- Bo góc: **8** (chip nhỏ), **12** (nút, ô nhập, thẻ nhỏ), **18** (thẻ lớn, khung đọc, hộp thoại). Nút tròn hoàn toàn cho nút Phát và nhóm phân đoạn.
- Khoảng cách theo bội của 4: 4 · 8 · 12 · 16 · 24 · 32. Lề trang: 24–44 px (web `clamp(1rem, 3.5vw, 2.75rem)`).
- Thẻ: nền `surface`, viền 1 px `border`, **không bóng** ở trạng thái thường; khi hover chỉ đổi viền sang `accent` (web) và nhấc nhẹ 2 px. Bóng (`shadow`) chỉ dành cho thanh phát nổi, hộp thoại và toast.
- Nút Phát: tròn 60 px, màu `accent`, có quầng sáng nhẹ.

## 5. Khung ứng dụng (App shell)

```
┌───────────────┬──────────────────────────────────────────────┐
│ ▣ Audiobook TTS│  [banner lỗi, nếu có]                         │
│               │  PageHeader: Tiêu đề + mô tả        [hành động]│
│ ▸ Phòng Đọc   │                                              │
│ ▸ Thư Viện…   │  Nội dung trang (tối đa ~1120 px, căn giữa ở web)│
│ ▸ Thống Kê    │                                              │
│ ▸ Kho Giọng Đọc│                                             │
│ ▸ Quản Trị *  │   (* chỉ admin)                              │
│ CÔNG CỤ       │                                  [toast]      │
│ ▸ Cài đặt     │                                              │
│ ▸ Giao diện   │                                              │
└───────────────┴──────────────────────────────────────────────┘
```

- **Sidebar trái** rộng 232–256 px. Trên web, màn hẹp (≤ 860 px) tự thành **thanh điều hướng dưới đáy**.
- **Thêm một màn hình mới:** (1) thêm một dòng vào `TABS` của `components/Sidebar/Sidebar.tsx` và `TabId` trong `AppContext.tsx` (web); (2) gọi `tabs.add(TÊN, icon)` trong `ui/app.py` (desktop, lớp `SidebarTabs` có sẵn). Tên màn và thứ tự phải giống nhau ở hai client và có mockup trong `docs/mockups/`.
- **Màn chỉ dành cho admin** (ví dụ *Quản Trị*) không được dựng với người khác: web chỉ thêm vào `TABS` khi `user.role === 'admin'`; desktop chỉ gọi `tabs.add(...)` cho admin. Mọi endpoint của màn đó vẫn tự kiểm tra `require_admin`.
- **Sidebar dài:** desktop dùng nút cao 36 px để 7 mục + công cụ vẫn vừa màn 800 px. Thể loại **không** nằm ở sidebar mà là dãy tag (chip) trên Khám phá và Kệ sách.
- **Công cụ phụ** (không phải màn hình) đặt ở khu "Công cụ" cuối sidebar (`add_tool` / mục trong `nav-footer`).
- Mọi màn hình bắt đầu bằng **`PageHeader`** (web: `components/common/PageHeader.tsx`; desktop: nhãn tiêu đề 26 + mô tả `muted`). Hành động chính của màn nằm bên phải tiêu đề.

## 6. Thành phần dùng chung

| Thành phần | Web | Desktop |
|---|---|---|
| Nút chính | `.btn-primary` | `CTkButton` mặc định (đã theo theme) |
| Nút phụ | `.btn-secondary` | `**theme.SECONDARY` |
| Nút nhẹ (hành động phụ trong thẻ) | `.btn-ghost` (`.danger` cho xóa) | `**theme.GHOST` |
| Nút nguy hiểm đặc | `.btn-danger` | `**theme.DANGER_BUTTON` |
| Nhóm phân đoạn (tab con, tốc độ, khoảng thời gian) | `.segmented` | `CTkSegmentedButton` (theme) |
| Thẻ | `.book-card`, `.chart-card`, `.metric-card` | `CTkFrame(border_width=1, border_color=theme.BORDER, corner_radius=16)` |
| Ảnh bìa sách | `<BookCover title>` | khung màu + chữ cái đầu (`cover_color`, `cover_initials` trong `ui/viewmodels.py`) |
| Trạng thái rỗng / đang tải / lỗi | `EmptyState`, `LoadingState`, `ErrorState` | nhãn `muted` / `danger` trong khung của màn |
| Hộp thoại | `<Modal>` | `ModalDialog` |
| Thông báo ngắn | `.toast` (đáy giữa) | `toast_label` (đáy khung nội dung) |

Ảnh bìa sinh tự động: màu lấy từ **cùng một thuật toán** ở hai nơi (`apps/web/src/lib/cover.ts`, `apps/desktop/ui/viewmodels.py`), bảo đảm cùng một sách có cùng màu trên web và desktop. Khi có ảnh bìa thật (kế hoạch trong `Additional_function.md`), ảnh thay phần màu, giữ nguyên khung và tỷ lệ.

## 7. Trạng thái và khả năng truy cập

- Mọi phần tử bấm được có trạng thái **hover**, **focus** (web: vòng `accent`), **disabled** (mờ 50%).
- Chỉ dùng màu để phân biệt thôi là chưa đủ: kèm biểu tượng hoặc chữ (ví dụ "Đã đọc xong" kèm dấu ✔).
- Tương phản chữ/nền tối thiểu AA (4.5:1). Token đã chọn để đạt mức này; đừng làm sáng `muted` hơn.
- Web tôn trọng `prefers-reduced-motion` (đã tắt animation toàn cục). Không đưa animation dài hơn 200 ms vào thao tác thường dùng.
- Biểu đồ phải có chú thích văn bản (`aria-label` ở web, tiêu đề + tiêu đề trục ở desktop).

## 8. Kiểm tra khi thêm giao diện

1. Xem ở **cả Sáng và Tối** (nút "Giao diện" ở cuối sidebar).
2. Web: xem ở độ rộng điện thoại (375 px) và máy tính (≥ 1280 px). Desktop: kích thước nhỏ nhất `1000×660`.
3. Không có mã màu thô trong code mới: `grep -nE "#[0-9a-fA-F]{6}|gray[0-9]" <file>` phải trống (trừ ngoại lệ ở mục 2).
4. Chuỗi hiển thị giống mockup; web và desktop giống nhau.
5. Chạy `npm run build && npm test` (web) và `pytest tests` (desktop).
