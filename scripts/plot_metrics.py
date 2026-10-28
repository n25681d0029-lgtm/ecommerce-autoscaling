"""Vẽ biểu đồ số instance + CPU + request từ file CSV của collect_metrics.py.

    python scripts/plot_metrics.py results/metrics_20261022_2000.csv
Ảnh PNG được lưu cạnh file CSV để chèn vào báo cáo (Hình 6.x).
"""
import csv
import sys
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


def f(v):
    return float(v) if v not in ("", "None", None) else float("nan")


def main(path: str):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    t = [datetime.strptime(r["time_utc"], "%Y-%m-%d %H:%M:%S") for r in rows]
    fig, (ax1, ax3) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True, dpi=150)
    ax1.step(t, [int(r["in_service"]) for r in rows], where="post", color="#0b6bcb", lw=2.2, label="Instance InService")
    ax1.step(t, [int(r["desired"]) for r in rows], where="post", color="#0b6bcb", lw=1, ls="--", label="Desired capacity")
    ax1.set_ylabel("Số instance")
    ax1.set_ylim(0, max(int(r["desired"]) for r in rows) + 1)
    ax2 = ax1.twinx()
    ax2.plot(t, [f(r["cpu_avg"]) for r in rows], color="#d9480f", lw=1.8, label="CPU trung bình (%)")
    ax2.set_ylabel("CPU (%)")
    ax2.set_ylim(0, 100)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=9)
    ax1.set_title("Auto Scaling Group: số instance và CPU theo thời gian")
    ax3.plot(t, [f(r["requests_per_min"]) for r in rows], color="#2b8a3e", lw=1.8, label="Request/phút (ALB)")
    ax3.set_ylabel("Request/phút")
    ax4 = ax3.twinx()
    ax4.plot(t, [f(r["resp_time_ms"]) for r in rows], color="#7048e8", lw=1.4, label="Thời gian phản hồi TB (ms)")
    ax4.set_ylabel("ms")
    h3, l3 = ax3.get_legend_handles_labels()
    h4, l4 = ax4.get_legend_handles_labels()
    ax3.legend(h3 + h4, l3 + l4, loc="upper left", fontsize=9)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax3.set_xlabel("Thời gian (UTC)")
    for ax in (ax1, ax3):
        ax.grid(alpha=.3)
    fig.tight_layout()
    out = path.rsplit(".", 1)[0] + ".png"
    fig.savefig(out)
    print("Đã lưu", out)


if __name__ == "__main__":
    main(sys.argv[1])
