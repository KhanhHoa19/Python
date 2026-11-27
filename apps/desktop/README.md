# Desktop app (CustomTkinter)

Cùng chức năng và 11 màn hình (S01–S11) với web, xem `docs/mockups/`. Không chứa logic nghiệp vụ: mọi thứ
đi qua backend REST (`api_client.py`).

## Chạy

```bash
# 1. Tkinter (Ubuntu/Debian): sudo apt install python3-tk
# 2. Backend đang chạy ở http://127.0.0.1:5000 (xem start_dev.sh)
cd apps/desktop
pip install -r requirements.txt
python main.py            # API_BASE_URL có thể đặt trong .env; mở ra là cửa sổ đăng nhập
```

Chưa có API TTS trả phí: chạy backend với `TTS_PROVIDER=mock` (WAV im lặng, có clone giả).

## Đóng gói thành file chạy (PyInstaller)

```bash
cd apps/desktop
pip install pyinstaller
pyinstaller audiobook_tts.spec --noconfirm      # kết quả: dist/AudiobookTTS/ (khoảng 140 MB)
printf 'API_BASE_URL=http://127.0.0.1:5000\n' > dist/AudiobookTTS/.env   # địa chỉ backend
dist/AudiobookTTS/AudiobookTTS
```
Chạy được trên **đúng hệ điều hành đã build** (build trên Linux thì chạy trên Linux; muốn bản Windows phải build trên Windows).
Vẫn cần backend đang chạy: app desktop chỉ là giao diện. Không cần cài Python hay thư viện trên máy chạy.

## Cấu trúc

| Đường dẫn | Vai trò |
|-----------|---------|
| `api_client.py` | Client httpx duy nhất, lỗi → `ApiError` |
| `player/engine.py` | Producer–Consumer (`threading` + `queue.Queue`), không chứa code Tk |
| `player/controller.py` | Sách đang mở, bookmark, ghi phiên đọc |
| `player/audio_output.py` | `pygame.mixer` sau interface để test không cần loa (kênh giọng + một kênh riêng cho nhạc nền) |
| `player/ambient.py`, `player/chime.py` | Nhạc nền lặp và tiếng chuông chuyển chương |
| `ui/dispatcher.py` | Cầu nối luồng nền → luồng Tk (hàng đợi, không gọi widget từ thread) |
| `ui/*_tab.py`, `ui/dialogs.py` | Các màn hình |

## Kiểm thử

```bash
cd apps/desktop && pytest -q     # logic, API client, view-model: không cần Tk hay âm thanh
```

## Khác với mockup

- Tốc độ đọc gửi lên backend (`speed=`) thay vì xử lý ở client, để giữ cao độ giọng; audio được cache theo từng mức tốc độ.
- Mọi ô chọn bằng stub trong test; hộp thoại mới nên được xem bằng Tk thật khi thay đổi giao diện.
