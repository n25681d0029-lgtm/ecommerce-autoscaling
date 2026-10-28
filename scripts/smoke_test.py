"""Kiểm tra nhanh website sau khi triển khai và xem Load Balancer chia request cho bao nhiêu instance.

    python scripts/smoke_test.py http://cloudshop-...elb.amazonaws.com
    python scripts/smoke_test.py http://127.0.0.1:8000 --requests 20     # thử với bản chạy cục bộ
    python scripts/smoke_test.py --stack cloudshop                      # tự lấy WebsiteURL từ stack (cần boto3)

Chỉ dùng thư viện chuẩn của Python (urllib) nên chạy được ở mọi nơi. Mã thoát khác 0 nếu có bước lỗi.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

CHECKS = [
    ("/health", "Health check của ALB", lambda b: json.loads(b)["status"] == "ok"),
    ("/", "Trang chủ", lambda b: "CloudShop" in b),
    ("/product/1", "Chi tiết sản phẩm", lambda b: "Thêm vào giỏ" in b or "Hết hàng" in b),
    ("/api/products", "API danh sách sản phẩm", lambda b: len(json.loads(b)) > 0),
    ("/system", "Trang thông tin máy chủ", lambda b: "Instance ID" in b),
    ("/system/live", "Trang demo cân bằng tải", lambda b: "whoami" in b),
]


def fetch(url: str, timeout: float = 10) -> tuple[int, str, float]:
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"User-Agent": "cloudshop-smoke-test"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), time.perf_counter() - t0


def url_from_stack(stack: str, region: str) -> str:
    import boto3
    outs = boto3.client("cloudformation", region_name=region).describe_stacks(StackName=stack)["Stacks"][0]["Outputs"]
    return next(o["OutputValue"] for o in outs if o["OutputKey"] == "WebsiteURL")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cho phép chuyển hướng output ra file trên Windows
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", help="địa chỉ website, vd. http://<ALB-DNS>")
    ap.add_argument("--stack", help="lấy URL từ output WebsiteURL của stack CloudFormation")
    ap.add_argument("--region", default="ap-southeast-1")
    ap.add_argument("--requests", type=int, default=40, help="số request /api/whoami để đếm phân bổ")
    a = ap.parse_args()
    if not a.url and not a.stack:
        ap.error("cần URL hoặc --stack")
    base = (a.url or url_from_stack(a.stack, a.region)).rstrip("/")
    print(f"Kiểm tra {base}\n")

    failed = 0
    for path, label, ok in CHECKS:
        try:
            status, body, dt = fetch(base + path)
            good = status == 200 and ok(body)
        except Exception as exc:  # noqa: BLE001 - in lỗi mạng/JSON thay vì dừng hẳn
            status, dt, good = f"lỗi: {exc}", 0, False
        failed += not good
        print(f"  [{'OK ' if good else 'LỖI'}] {label:<28} {path:<16} {status}  {dt * 1000:.0f} ms")

    print(f"\nGửi {a.requests} request tới /api/whoami để xem phân bổ tải:")
    seen, errors, times = Counter(), 0, []
    for _ in range(a.requests):
        try:
            status, body, dt = fetch(base + "/api/whoami")
            if status != 200:
                raise ValueError(status)
            d = json.loads(body)
            seen[f"{d['instance_id']} ({d['az']})"] += 1
            times.append(dt)
        except Exception:  # noqa: BLE001
            errors += 1
    for inst, n in seen.most_common():
        print(f"  {inst:<40} {n:>4} request  {'█' * round(n * 30 / a.requests)}")
    if times:
        print(f"  Độ trễ trung bình {sum(times) / len(times) * 1000:.0f} ms, lỗi {errors}/{a.requests}")
    if len(seen) == 1:
        print("  (Chỉ 1 instance trả lời: bình thường khi ASG đang ở mức tối thiểu 1 máy.)")
    failed += errors > 0

    print("\nKẾT QUẢ:", "TẤT CẢ ĐỀU ỔN" if not failed else f"{failed} mục lỗi")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
