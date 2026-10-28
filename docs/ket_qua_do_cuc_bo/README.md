# Số liệu đo cục bộ (dùng trong Mục 6.3 của báo cáo)

- Máy đo: Linux 2 vCPU Intel Xeon 2,1 GHz. Gunicorn (2 worker, 2 luồng, keep-alive 75 s) ghim vào 1 vCPU bằng `taskset`; Locust chạy trên vCPU còn lại.
- Mỗi mức tải 60 giây. CPU máy chủ = tổng thời gian CPU của các tiến trình Gunicorn / thời gian đo.
- `shopper_summary.json`, `heavy_summary.json`: bảng tổng hợp; `*_u<N>_stats.csv`: thống kê gốc của Locust cho từng mức N người dùng.
- Đo lại: `python scripts/bench_local.py results/bench Shopper 50,100,200,400,600` (Linux hoặc Kaggle).
