"""Đo năng lực MỘT máy chủ trên Linux/Kaggle: gunicorn ghim 1 vCPU (taskset), Locust ghim vCPU khác.

    python scripts/bench_local.py results/bench Shopper 50,100,200,400,600
    python scripts/bench_local.py results/bench_heavy HeavyShopper 10,20,40,80
Chỉ chạy trên Linux (cần taskset, gunicorn). Biến môi trường DUR = số giây mỗi mức tải (mặc định 60).
"""
import csv, json, os, subprocess, sys, time, signal, shutil

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(sys.argv[1])
USER_CLASS = sys.argv[2] if len(sys.argv) > 2 else "Shopper"
STEPS = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "10,25,50,100,150,200").split(",")]
DUR = int(os.environ.get("DUR", 60))
os.makedirs(OUT, exist_ok=True)

db = os.path.join(OUT, "bench.db")
if os.path.exists(db):
    os.remove(db)
# CSDL riêng cho phép đo, không đụng tới instance/shop.db
env = dict(os.environ, DISABLE_IMDS="1", SECRET_KEY="bench-secret-key-123456", DATABASE_URL="sqlite:///" + db)
srv = subprocess.Popen(["taskset", "-c", "0", "gunicorn", "-w", "2", "--threads", "2", "--keep-alive", "75", "-b", "127.0.0.1:8100",
                        "--log-level", "warning", "wsgi:app"], cwd=APP, env=env, start_new_session=True)
time.sleep(5)

TCK = os.sysconf("SC_CLK_TCK")
def cpu_ticks():
    total = 0
    pids = subprocess.run(["pgrep", "-g", str(os.getpgid(srv.pid))], capture_output=True, text=True).stdout.split()
    for p in pids:
        try:
            f = open(f"/proc/{p}/stat").read().rsplit(")", 1)[1].split()
            total += int(f[11]) + int(f[12])
        except Exception:
            pass
    return total

rows = []
for u in STEPS:
    prefix = os.path.join(OUT, f"u{u}")
    c0, t0 = cpu_ticks(), time.time()
    subprocess.run(["taskset", "-c", "1", "locust", "-f", f"{APP}/loadtest/locustfile.py", "--host", "http://127.0.0.1:8100",
                    "--headless", "-u", str(u), "-r", str(max(1, u // 5)), "-t", f"{DUR}s", "--csv", prefix,
                    "--only-summary", "--loglevel", "ERROR", USER_CLASS], cwd=APP, capture_output=True)
    c1, t1 = cpu_ticks(), time.time()
    cpu = (c1 - c0) / TCK / (t1 - t0) * 100
    agg = next(r for r in csv.DictReader(open(prefix + "_stats.csv")) if r["Name"] == "Aggregated")
    row = {"users": u, "rps": round(float(agg["Requests/s"]), 1), "requests": int(agg["Request Count"]),
           "failures": int(agg["Failure Count"]), "p50_ms": int(float(agg["50%"])), "p95_ms": int(float(agg["95%"])),
           "p99_ms": int(float(agg["99%"])), "avg_ms": round(float(agg["Average Response Time"]), 1),
           "server_cpu_pct": round(cpu, 1)}
    rows.append(row)
    print(row, flush=True)

os.killpg(os.getpgid(srv.pid), signal.SIGTERM)
json.dump(rows, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
