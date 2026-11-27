# S09 – Đăng nhập & Đăng ký

**Mục đích:** mỗi người có tài khoản riêng: thư viện, tiến độ, ghi chú, giọng nhân bản và thống kê của riêng mình.  **Hiện ra khi:** chưa đăng nhập, hoặc phiên đã hết hạn.  Không nằm trong sidebar.

## Bố cục
```
┌──────────────────────────────────────┐
│ ▣ Audiobook TTS                      │
│ Chào mừng trở lại                    │      (đăng ký: "Tạo tài khoản")
│ Đăng nhập để nghe tiếp từ chỗ bạn dừng.│
│ ( Đăng nhập | Đăng ký )              │
│ Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.   ← chỉ khi bị đăng xuất vì hết hạn
│ Tên đăng nhập  [                   ] │
│ Tên hiển thị (không bắt buộc) [    ] │      ← chỉ ở tab Đăng ký
│ Mật khẩu       [                   ] │
│ Nhập lại mật khẩu [                ] │      ← chỉ ở tab Đăng ký
│ <thông báo lỗi>                      │
│ [          Đăng nhập            ]    │
└──────────────────────────────────────┘
```

## Luật
- **Đăng ký mở:** ai cũng tạo được tài khoản thường (`Member`). **Quản trị viên không đăng ký được**: tài khoản `admin` tạo tự động ở lần chạy đầu từ `ADMIN_USERNAME` / `ADMIN_PASSWORD` (để trống mật khẩu thì sinh ngẫu nhiên và in **một lần** trong log backend). Đổi mật khẩu bằng `python -m src.core.auth.admin_cli reset-password <tên>`.
- **Tên đăng nhập:** 3–32 ký tự `A–Z a–z 0–9 . _ -`, không phân biệt hoa thường. **Mật khẩu:** ≥ 8 ký tự. Kiểm tra ngay trên form; backend vẫn kiểm tra lại.
- **Sai mật khẩu và không có tài khoản cho cùng một thông báo** (`Wrong username or password.`). Sai 5 lần trong 5 phút → tạm khóa (HTTP 429, `Retry-After`).
- **Phiên:** token JWT 12 giờ, không có refresh. Hết hạn (hoặc tài khoản bị xóa) → quay về màn này với dòng `Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.`
- **Lưu token:** web ở `localStorage`; desktop ở `~/.config/audiobook-tts/session.json` (quyền 600). `Đăng xuất` xóa nó.
- Sau khi đăng nhập, sidebar hiện **khối tài khoản** (chữ cái đầu, tên hiển thị, huy hiệu `ADMIN` / `MEMBER`) và nút `Đăng xuất` ở khu Công cụ.

## Tài khoản thử (chỉ khi phát triển)
Khi backend chạy với `DEV_QUICK_LOGIN=true`, dưới form (web) hoặc bên phải cửa sổ (desktop) hiện **3 ô**: `admin`, `khanhhoa36`, `xuanhai18`, mỗi ô ghi sẵn tên, vai trò, tên đăng nhập và mật khẩu; **bấm vào ô là đăng nhập ngay**. Ba tài khoản được tạo khi backend khởi động; `python -m src.core.auth.admin_cli seed-demo` đặt lại mật khẩu cả ba. Mặc định **tắt** và không bao giờ bật trên máy chủ người khác truy cập được, vì mật khẩu nằm ngay trên trang. API: `GET /api/auth/demo-accounts` (rỗng khi tắt).

## Quyền (tóm tắt)
- Sách và giọng tự tải lên là **riêng tư**; không ai khác thấy, kể cả admin. Sách do admin đăng *công khai* mọi người đều thấy, nhưng tiến độ, ghi chú, thống kê vẫn riêng từng người.
- Giới hạn ký tự/ngày dùng chung cho cả hệ thống, chỉ admin đổi được (ô này bị khóa với Member trong S05).
- Mỗi Member giữ tối đa `MAX_VOICES_PER_USER` giọng nhân bản (mặc định 3) vì tài khoản HeyGen và hạn mức tạo giọng mỗi ngày dùng chung.

## API
`POST /api/auth/register` · `POST /api/auth/login` → `{access_token, token_type, expires_in, user}` · `GET /api/auth/me`. Mọi API khác cần header `Authorization: Bearer <token>` (trừ `GET /api/health`).

## Tiêu chí hoàn thành
- [ ] Đăng ký → vào thẳng app; đăng xuất → về màn này; đăng nhập lại thấy đúng dữ liệu của mình.
- [ ] Người dùng B không thấy sách, ghi chú, giọng, thống kê của người dùng A.
- [ ] Token hỏng/hết hạn đưa về màn này kèm thông báo; không lộ mật khẩu trong log hay URL.
