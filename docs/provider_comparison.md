# So sánh nhà cung cấp TTS (kế hoạch mục 1.7)

Tra cứu ngày 26/11/2026. Ký hiệu: ✅ đọc từ tài liệu chính thức · ⚠ mâu thuẫn hoặc chưa xác nhận (phải kiểm tra trên tài khoản thật) · ❌ không dùng được cho đồ án.

**Quyết định của chủ dự án:** dùng **HeyGen**, với giọng tiếng Việt **tự tạo (clone)** vì thư viện công khai chưa có giọng Việt. Adapter đã viết và đã chạy thử với API thật (xem mục kết quả xác minh bên dưới).

## Bảng theo 6 tiêu chí

| Nhà cung cấp | 1. Clone giọng tiếng Việt | 2. Giọng Việt | 3. Giá | 4. Độ trễ mạng từ máy bạn* | 5. Giới hạn | 6. Tài liệu |
|---|---|---|---|---|---|---|
| **HeyGen** | ⚠ có API clone (`instant`/`professional`), chưa thấy tài liệu nói rõ tiếng Việt; tính năng giọng đang ở dạng xem trước (private preview) theo một nguồn | ✅ `vi` có trong bảng ngôn ngữ TTS | ⚠ tính theo giây audio, prepaid, nạp từ $5; con số giữa các nguồn khác nhau (xem dưới); bản `turbo-free` miễn phí đến 30/11/2026 | **239 ms** (chậm nhất) | ✅ 10.000 ký tự/yêu cầu; ⚠ **30 yêu cầu/phút**/thành viên | ✅ tốt, nhưng có nhiều trang mâu thuẫn endpoint |
| ElevenLabs | ✅ clone tức thì, tự phục vụ; Flash v2.5, v3, v4 hỗ trợ tiếng Việt | ✅ | ✅ $0,04/1.000 ký tự (Flash/Turbo), $0,08 (v3/v4); Free 10.000 ký tự/tháng; Starter $6/tháng | 57 ms | ✅ 40.000 ký tự/yêu cầu (Flash) | ✅ |
| Azure Speech | ❌ giọng cá nhân là "Limited Access", chỉ khách do Microsoft quản lý | ✅ HoaiMy, NamMinh (cùng giọng edge-tts đang dùng) | ⚠ không lấy được số; gói miễn phí neural 0,5 triệu ký tự/tháng | 40 ms | chưa xác nhận | ✅ |
| Google Cloud | ❌ clone có vi-VN nhưng **phải được allowlist qua đội bán hàng** | ✅ Chirp 3 HD vi-VN | ⚠ $16 hoặc $30/triệu ký tự tùy bản trang | 51 ms | mẫu tham chiếu ≤10 giây | ✅ |
| OpenAI | ❌ giọng tùy chỉnh chỉ cho khách đủ điều kiện | ✅ gpt-4o-mini-tts hỗ trợ tiếng Việt | ≈ $12/triệu token audio ra (~1,5 cent/phút) | 30 ms | – | ✅ |
| FPT.AI | ❌ không thấy | ✅ giọng Việt (banmai, lannhi...) | ⚠ không công bố, phải liên hệ | 19 ms | 5.000 ký tự/yêu cầu | trung bình |
| Viettel AI, Zalo AI, Vbee | chưa xác nhận (Vbee có "Instant Voice Cloning" trong Studio) | giọng Việt bản địa | ⚠ không tìm được bảng giá API | chưa đo | chưa rõ | chưa đọc |
| Fish Audio | chưa xác nhận có tiếng Việt | – | ≈ $15/triệu byte UTF-8 (nguồn thứ ba); tiếng Việt có dấu tốn ~2 byte/ký tự | chưa đo | – | – |

\* Trung vị thời gian mở kết nối TCP tới cổng 443 (7 lần đo, `python -m scripts.test_connection`). Đây chỉ là độ trễ mạng, chưa gồm thời gian sinh audio.

## Những điều HeyGen đòi hỏi ở thiết kế của mình

1. **Giới hạn 30 yêu cầu/phút.** Đọc bình thường (khoảng 12 câu/phút kèm tải trước 2 câu) vẫn nằm trong giới hạn, nhưng **xuất audio** một cuốn sách 1.000 câu sẽ mất ít nhất ~33 phút. Adapter cần bộ giới hạn tốc độ và xử lý `429` (`Retry-After`), `500`, `503` (an toàn để thử lại theo tài liệu).
2. **Hai bước mỗi câu:** `POST` trả về `audio_url` rồi phải tải file. Kết hợp với độ trễ 239 ms, câu đầu tiên sẽ chậm hơn; tải trước vẫn che được phần lớn các câu sau.
3. **Định dạng:** mặc định WAV mono 44,1 kHz; có thể chọn mp3. Xuất WAV ghép trực tiếp được; chọn một định dạng cố định để không lẫn lộn trong cache.
4. **Chi phí tính theo giây audio, không theo ký tự.** Giới hạn "ký tự/ngày" hiện có chỉ là ước lượng gần đúng. Ước tính thô: một cuốn ~500.000 ký tự ≈ 10 giờ audio (giả định ~14 ký tự/giây), tức ~$12 nếu $0,000333/giây hoặc ~$24 nếu $0,000667/giây. Cần xác nhận đơn giá thật.
5. Khóa cache phải gồm `provider` (hiện chưa có) để audio của edge-tts không bị phát nhầm sau khi đổi sang HeyGen.

## Kết quả xác minh trên tài khoản HeyGen thật (26/11/2026)

Đã chạy bằng API Key của dự án (model `heygen-voice-1-turbo-free`, không tốn credit trả phí):

- [x] **Thư viện công khai không có giọng tiếng Việt:** duyệt hết 2.602 giọng, 0 giọng `vi` (2.529 giọng `en`). Giọng tiếng Việt phải là giọng **riêng** do bạn tạo (clone).
- [x] **Giọng riêng tiếng Việt đọc tốt qua API:** workspace đã có giọng `hayami` (`language: vi`, `ACTIVE`). `POST /v3/models/audio/tts` với `language: "vi"` trả `{"data": {"audio_url", "duration"}}`.
- [x] **Đường clone đúng là** `POST /v3/models/audio/voices` với `mode: "instant"` (tải file bằng `POST /v3/assets` lấy `asset_id`, rồi poll `GET .../voices/{id}` đến khi `ACTIVE`). Trang tài liệu cũ `/v3/voices/clone` không còn dùng. Giới hạn: tài khoản Free 20 lần clone/ngày, số giọng theo gói.
- [x] **Mẫu clone:** khoảng 1 phút giọng rõ cho kết quả tốt nhất, chỉ dùng 3 phút đầu, WAV hoặc MP3, tối đa 50 MB khi tải lên.
- [x] **Định dạng:** mp3 nhỏ hơn WAV ~5 lần (34 KB cho 2,1 giây so với 294 KB cho 3,3 giây), nên adapter dùng mp3 mặc định (`HEYGEN_AUDIO_FORMAT`).
- [x] **Độ trễ thật mỗi câu:** ~1,9 giây gọi API + 0,5–2 giây tải file, tổng 2–4 giây. Câu đọc lại lấy từ cache (12 ms). Tải trước 2 câu đủ che độ trễ khi đọc liền.
- [x] **Giới hạn 30 yêu cầu/phút:** adapter dùng bộ giới hạn dùng chung toàn tiến trình (28/phút) và thử lại khi gặp 429/500/503; xuất audio dài sẽ chậm hơn nhưng không lỗi.
- [ ] **Đơn giá của `heygen-voice-1` và `-turbo`:** vẫn chưa xác nhận (trang giá chính thức không đọc được). Xem số dư/lịch sử trong dashboard HeyGen sau vài lần đọc để biết chi phí thực tế.
- [ ] **`turbo-free` miễn phí đến 30/11/2026.** Sau ngày đó đổi `HEYGEN_MODEL` sang `heygen-voice-1` (hoặc `-turbo`) và kiểm tra chất lượng tiếng Việt.
- [ ] **Hạn của `audio_url`:** tài liệu không nêu; adapter tải ngay sau khi nhận và không lưu URL.
- [ ] **Clone qua giao diện của app:** chưa thử với file ghi âm thật (tránh dùng hạn mức clone của bạn); luồng đã được test bằng HTTP giả.

**Chuyển sang HeyGen:** đặt `TTS_PROVIDER=heygen` trong `.env` rồi chạy lại backend. Giọng mặc định lấy từ `HEYGEN_DEFAULT_VOICE`, nếu để trống thì dùng giọng đầu tiên trong workspace.

## Nguồn

- [HeyGen: tạo giọng nói (speech)](https://developers.heygen.com/docs/voices/speech), [tổng quan voices](https://developers.heygen.com/docs/voices/overview)
- [HeyGen: giá API (help center)](https://help.heygen.com/en/articles/10060327-heygen-api-pricing-subscriptions-explained)
- [HeyGen: Vietnamese Text to Speech](https://www.heygen.com/text-to-speech/vietnamese)
- [ElevenLabs: models](https://elevenlabs.io/docs/overview/models), [API pricing](https://elevenlabs.io/pricing/api)
- [Google: Chirp 3 Instant Custom Voice](https://docs.cloud.google.com/text-to-speech/docs/chirp3-instant-custom-voice), [Chirp 3 HD](https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd)
- [Azure: personal voice](https://learn.microsoft.com/azure/ai-services/speech-service/personal-voice-overview), [Limited Access](https://learn.microsoft.com/en-us/legal/cognitive-services/speech-service/text-to-speech/limited-access)
- [OpenAI: gpt-4o-mini-tts](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts)
- [FPT.AI: TTS pricing](https://docs.fpt.ai/docs/en/speech/documentation/tts-pricing)
