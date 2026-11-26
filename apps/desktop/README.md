# Desktop app (CustomTkinter)

Cùng chức năng và 8 màn hình (S01–S08) với web, xem `docs/mockups/`. Không chứa logic nghiệp vụ: mọi thứ
đi qua backend REST (`api_client.py`).

## Chạy

```bash
# 1. Tkinter (Ubuntu/Debian): sudo apt install python3-tk
# 2. Backend đang chạy ở http://127.0.0.1:5000 (xem start_dev.sh)
cd apps/desktop
pip install -r requirements.txt
python main.py            # API_BASE_URL có thể đặt trong .env
```

Chưa có API TTS trả phí: chạy backend với `TTS_PROVIDER=mock` (WAV im lặng, có clone giả).

## Cấu trúc

| Đường dẫn | Vai trò |
|-----------|---------|
| `api_client.py` | Client httpx duy nhất, lỗi → `ApiError` |
| `player/engine.py` | Producer–Consumer (`threading` + `queue.Queue`), không chứa code Tk |
| `player/controller.py` | Sách đang mở, bookmark, ghi phiên đọc |
| `player/audio_output.py` | `pygame.mixer` sau interface để test không cần loa |
| `ui/dispatcher.py` | Cầu nối luồng nền → luồng Tk (hàng đợi, không gọi widget từ thread) |
| `ui/*_tab.py`, `ui/dialogs.py` | Các màn hình |

## Kiểm thử

```bash
cd apps/desktop && pytest -q     # logic, API client, view-model: không cần Tk hay âm thanh
```

## Khác với mockup

- Tốc độ đọc gửi lên backend (`speed=`) thay vì xử lý ở client, để giữ cao độ giọng; audio được cache theo từng mức tốc độ.
- Chưa có biểu đồ tròn "theo giọng" (backend chưa ghi giọng của phiên đọc).
