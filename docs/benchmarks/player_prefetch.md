# Kết luận đo khoảng lặng giữa các câu (mục 3.13 / ★.4)

Công cụ: `apps/desktop/benchmarks/benchmark_player.py` (PlaybackEngine thật, TTS và loa mô phỏng).
Số liệu đầy đủ: [player_prefetch_baseline.md](player_prefetch_baseline.md) (1 luồng tải, N=1..5)
và [player_prefetch_workers.md](player_prefetch_workers.md) (1–4 luồng tải).

## Phát hiện

1. **Số câu tải trước (N) gần như không ảnh hưởng**: kết quả giống hệt nhau với N=1…5 ở mọi kịch bản.
2. **Điểm nghẽn là số luồng tải.** Engine cũ chỉ có 1 luồng tải tuần tự. Khi độ trễ TTS (~3 s, giống
   HeyGen) lớn hơn thời lượng câu đọc (tốc độ 1.5x ≈ 2.5–3.5 s), **45% lần chuyển câu bị ngắt**, khoảng lặng
   p95 ≈ 1.6–2.5 s. Với tốc độ ≤ 1.0x hoặc độ trễ ≤ 1 s thì 0% ngắt.
3. **2 luồng tải song song đưa tỷ lệ ngắt về 0%** ở mọi kịch bản đã đo (kể cả HeyGen-like, giới hạn
   28 yêu cầu/phút, và lỗi 10%). 3–4 luồng không cải thiện thêm.

## Thay đổi

- `PlaybackEngine(fetch_workers=…)`: tải song song nhưng trả về đúng thứ tự câu (bộ đệm sắp xếp lại);
  lỗi bỏ qua / lỗi nghiêm trọng cũng đến đúng thứ tự. Cửa sổ tải trước vẫn giới hạn bởi `prefetch`.
- Mặc định desktop: `fetch_workers = 2`, `prefetch = 2` (giữ nguyên vì N không đổi kết quả).
- Bộ giới hạn 28 yêu cầu/phút của adapter HeyGen dùng chung toàn tiến trình nên song song không vượt
  hạn mức. Web đã tải song song sẵn (AudioPrefetcher).

## Hạn chế

Mô phỏng: không đo mạng/loa thật; tốc độ nói đặt 0.28 s/từ (giọng clone, trường hợp khó hơn hayami 0.40).
