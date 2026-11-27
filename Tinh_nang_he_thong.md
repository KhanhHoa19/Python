# Audiobook TTS – Tính năng hiện có

Hệ thống nghe sách nói bằng giọng đọc AI, gồm **web** và **desktop** dùng chung một backend, cùng chức năng và cùng 12 màn hình.

## Tài khoản và bảo mật
- Đăng ký, đăng nhập (JWT), vai trò `admin` và `user`.
- Dữ liệu riêng từng người: sách, ghi chú, tiến độ, cài đặt. Admin cũng không đọc được dữ liệu riêng của người khác.
- Tự kiểm tra mọi endpoint đều cần đăng nhập; đăng nhập sai nhiều lần bị tạm khóa.
- Đăng nhập nhanh cho phát triển (tùy chọn).

## Thư viện sách
- Nạp sách PDF, DOCX, TXT, MD; tự nhận chương (Phần/Chương), loại dòng mục lục.
- **Kệ sách của tôi:** các tab Đang nghe dở, Chưa nghe, Đã hoàn thành, Yêu thích.
- **Khám phá:** kho sách hệ thống dùng chung, thêm vào kệ để lưu tiến độ riêng.
- 15 tag thể loại để lọc, tìm kiếm không phân biệt dấu, ảnh bìa (trang đầu PDF, tự tạo hoặc tải lên).

## Phòng Đọc
- Nghe từng câu, tô sáng câu đang đọc, bấm câu để nhảy tới, nhớ vị trí đọc.
- Tốc độ 0,75x–1,5x, mục lục chương, hẹn giờ tắt có giảm dần âm lượng.
- **Đọc phân vai:** lời thoại trong ngoặc kép hoặc gạch đầu dòng đọc bằng giọng nhân vật, phần còn lại bằng giọng dẫn chuyện.
- **Nhạc nền** lặp dưới giọng đọc (âm lượng riêng) và **tiếng chuông** khi sang chương mới.
- Chữ IN HOA được chuẩn hóa để giọng đọc không đọc sai.

## Gợi ý
- Tab Gợi Ý đề xuất sách theo lịch sử nghe, thể loại yêu thích (hỏi chọn lần đầu, sửa sau), thời lượng mong muốn và 6 tâm trạng.
- Mỗi gợi ý kèm lý do; kết hợp độ phổ biến khi đã có lịch sử.

## Trích dẫn yêu thích
- Lưu cả câu bằng một chạm, gắn nhãn cảm xúc, có kèm âm thanh.
- Lọc theo sách hoặc cảm xúc, nghe lại liên tục (playlist).

## Giọng đọc
- **Kho Giọng Đọc:** giọng hệ thống và giọng clone của riêng bạn, nghe thử, đặt mặc định, đổi tên, xóa.
- Clone giọng từ file mẫu, có xác nhận đồng thuận và giới hạn số giọng mỗi người.
- Nhiều nhà cung cấp TTS: HeyGen, edge-tts, openai, mock (giả lập để thử).
- Âm thanh được lưu bộ nhớ đệm, không tính phí lặp lại.

## Quản trị (chỉ admin)
- **Sách hệ thống:** thêm, sửa, xóa, công khai hoặc gỡ công khai.
- **Thể loại:** thêm, sửa, xóa.
- **Giọng hệ thống:** công khai giọng, đặt giọng mặc định cho cả hệ thống.
- **Âm thanh nền:** quản lý thư viện nhạc nền.
- **Người dùng:** xem danh sách tài khoản (chỉ xem).
- Kiểm tra kết nối TTS và đặt giới hạn ký tự mỗi ngày.

## Thống kê và xuất file
- Thống kê thói quen nghe: thời gian, số từ, tốc độ, độ trễ, giọng dùng nhiều.
- Xuất audio cả cuốn hoặc một khoảng câu ra WAV/MP3 (có đọc phân vai).

## Giao diện
- Thiết kế "Giấy & Mực", chế độ sáng, tối hoặc theo hệ thống.
- Web và desktop giống nhau về màn hình, chữ và chức năng.
