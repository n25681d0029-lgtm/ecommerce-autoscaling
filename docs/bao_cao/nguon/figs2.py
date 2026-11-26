from figs_common import *
import numpy as np, json, sys
which = sys.argv[1:] or ["all"]
def want(n): return "all" in which or n in which

if want("arch"):
    fig, ax = canvas(10.5, 7.4)  # 105 x 74
    zone(ax, 15, 1, 89, 72, "AWS Cloud · Region Asia Pacific (Sydney) ap-southeast-2", c="orange", ls="-")
    zone(ax, 17, 3, 63, 63, "VPC 10.20.0.0/16", c="violet")
    zone(ax, 24, 5, 26, 52, "Vùng sẵn sàng A", c="gray")
    zone(ax, 52, 5, 26, 52, "Vùng sẵn sàng B", c="gray")
    zone(ax, 25.5, 28, 23, 24, "Subnet công khai 10.20.1.0/24", c="aqua", fs=9)
    zone(ax, 53.5, 28, 23, 24, "Subnet công khai 10.20.2.0/24", c="aqua", fs=9)
    zone(ax, 25.5, 6.5, 23, 19, "Subnet riêng 10.20.11.0/24", c="blue", fs=9)
    zone(ax, 53.5, 6.5, 23, 19, "Subnet riêng 10.20.12.0/24", c="blue", fs=9)
    box(ax, 26, 59, 50, 5.5, "Application Load Balancer · HTTP :80 · health check /health", c="yellow", fs=10.5, bold=True)
    ax.add_patch(FancyBboxPatch((27, 30), 48.5, 17.5, boxstyle="round,pad=0,rounding_size=1.2", fc="none", ec=ORANGE, lw=1.6, ls="-."))
    ax.text(51.2, 31.2, "Auto Scaling Group: min 1 · max 4 · Target Tracking CPU 50 %", ha="center", fontsize=9.5, color=ORANGE, fontweight="bold")
    box(ax, 29, 35, 17, 9, "EC2 t3.micro #1\nGunicorn :8000", c="aqua", fs=9.5)
    box(ax, 57, 35, 17, 9, "EC2 t3.micro #2…#4\n(thêm khi tải cao)", c="aqua", fs=9.5, ls="--")
    box(ax, 29, 9, 17, 9, "Amazon RDS\nMySQL 8.4\ndb.t3.micro", c="blue", fs=9.5)
    ax.text(65, 13.5, "(subnet thứ hai của\nDB Subnet Group)", ha="center", va="center", fontsize=9, color=MUTED, style="italic")
    box(ax, 17.5, 56, 5.5, 6, "IGW", c="violet", fs=9)
    box(ax, 1, 56, 12, 8, "Người dùng\n(trình duyệt)", c="gray", fs=10)
    arrow(ax, 13, 60, 17.5, 59, c=INK2)
    arrow(ax, 23, 60, 26, 61.7, c=INK2)
    arrow(ax, 41, 59, 37.5, 44, c=INK2); arrow(ax, 61, 59, 65.5, 44, c=INK2)
    ax.text(51, 52.5, ":8000", fontsize=9, color=INK2, ha="center")
    arrow(ax, 37.5, 35, 37.5, 18, c=BLUE); ax.text(39, 22.5, ":3306", fontsize=9, color=BLUE)
    arrow(ax, 65.5, 35, 46, 16, c=BLUE)
    sx = 83
    box(ax, sx, 62, 19, 7.5, "CloudFormation\n(stack cloudshop)", c="orange", fs=9.5)
    box(ax, sx, 50, 19, 8.5, "Amazon S3\ncatalog.json + images/", c="red", fs=9.5)
    box(ax, sx, 39, 19, 8, "CloudFront (CDN)\nảnh sản phẩm", c="violet", fs=9.5)
    box(ax, sx, 27, 19, 8.5, "CloudWatch\nsố liệu · cảnh báo\ndashboard", c="blue", fs=9.5)
    box(ax, sx, 15, 19, 8, "Amazon SNS\nemail co giãn", c="yellow", fs=9.5)
    box(ax, sx, 4, 19, 7.5, "IAM Role\n(EC2 → S3)", c="gray", fs=9.5)
    arrow(ax, 74, 40.5, sx, 53, "đọc/ghi", c=RED, fs=8.5, off=(0, 1.5))
    arrow(ax, sx + 9.5, 47, sx + 9.5, 50, c=VIOLET)
    arrow(ax, 7, 64, sx, 43, c=VIOLET, rad=-0.25, ls="--")
    ax.text(48, 71.5, "ảnh sản phẩm tải qua CloudFront", fontsize=8.5, color=VIOLET, ha="center")
    arrow(ax, 74, 37, sx, 31, "CPU, request", c=BLUE, fs=8.5, off=(0, -1.6))
    arrow(ax, sx + 9.5, 27, sx + 9.5, 23, c=INK2)
    save(fig, "f2_architecture")

if want("sg"):
    fig, ax = canvas(10, 2.0)
    items = [("Internet\n0.0.0.0/0", "gray"), ("SG-ALB\nnhận :80", "yellow"), ("SG-App (EC2)\nnhận :8000 từ SG-ALB", "aqua"), ("SG-DB (RDS)\nnhận :3306 từ SG-App", "blue")]
    for i, (t, c) in enumerate(items):
        box(ax, 1 + i * 25, 4, 21, 12, t, c=c, fs=10.5)
        if i: arrow(ax, i * 25 - 3, 10, 1 + i * 25, 10, c=INK2)
    save(fig, "f2_sg_chain")

if want("erd"):
    fig, ax = canvas(10.5, 6.2)
    def ent(x, y, name, fields, c="blue", w=24):
        h = 4.2 + 2.9 * len(fields)
        ax.add_patch(FancyBboxPatch((x, y - h), w, h, boxstyle="round,pad=0,rounding_size=0.8", fc="white", ec=EDGE[c], lw=1.4))
        ax.add_patch(FancyBboxPatch((x, y - 4.2), w, 4.2, boxstyle="round,pad=0,rounding_size=0.8", fc=TINT[c], ec=EDGE[c], lw=1.4))
        ax.text(x + w / 2, y - 2.1, name, ha="center", va="center", fontweight="bold", fontsize=11)
        for i, f in enumerate(fields):
            ax.text(x + 1.2, y - 6 - i * 2.9, f, va="center", fontsize=9.5)
    ent(2, 60, "users", ["PK id", "email (duy nhất)", "full_name", "password_hash", "is_admin", "created_at"], c="gray")
    ent(40, 60, "categories", ["PK id", "name", "slug (duy nhất)"], c="aqua")
    ent(40, 43, "products", ["PK id", "sku (duy nhất)", "name, price, stock", "FK category_id", "description, hue", "is_active", "uid (đồng bộ)", "updated_at, deleted_at"], c="blue", w=26)
    ent(79, 43, "product_photos", ["PK id", "FK product_id", "position", "key (tên file ảnh)"], c="violet")
    ent(2, 36, "orders", ["PK id", "code (mã đơn)", "FK user_id (có thể rỗng)", "customer_name, phone", "address, total", "status", "served_by (instance)", "created_at"], c="orange", w=26)
    ent(40, 14.5, "order_items", ["PK id", "FK order_id · FK product_id", "product_name, price, quantity"], c="yellow", w=30)
    def rel(x1, y1, x2, y2, t):
        arrow(ax, x1, y1, x2, y2, c=INK2, lw=1.2)
        ax.text((x1 + x2) / 2 + 2.2, (y1 + y2) / 2, t, fontsize=9, color=INK2, ha="center", bbox=dict(fc="white", ec="none", pad=0.4))
    rel(52, 51.1, 52, 43, "1 – n")
    rel(66, 34, 79, 34, "1 – n")
    rel(14, 39.6, 14, 36, "1 – n")
    rel(28, 22, 40, 10, "1 – n")
    rel(55, 19.8, 55, 14.5, "1 – n")
    save(fig, "f2_erd")

if want("seq"):
    fig, ax = canvas(10.5, 5.4)
    actors = [("Trình duyệt", 8, "gray"), ("ALB", 30, "yellow"), ("EC2 (Flask)", 53, "aqua"), ("RDS MySQL", 76, "blue"), ("CloudFront / S3", 97, "violet")]
    for n, x, c in actors:
        box(ax, x - 8, 48, 16, 5, n, c=c, fs=10.5, bold=True)
        ax.plot([x, x], [2, 48], color=MUTED, lw=1, ls="--")
    msgs = [(8, 30, 44, "GET /product/3 + cookie phiên"), (30, 53, 40, "chuyển tới máy khỏe (round robin)"),
            (53, 76, 36, "SELECT sản phẩm, ảnh"), (76, 53, 32, "dữ liệu"), (53, 30, 28, "HTML (chân trang ghi instance ID)"),
            (30, 8, 24, "200 OK"), (8, 97, 19.5, "GET ảnh /images/<mã băm>.jpg"), (97, 8, 15, "ảnh JPEG (lưu đệm ở CDN)"),
            (8, 30, 10.5, "POST /checkout (CSRF token)"), (30, 53, 7, "có thể là máy khác"), (53, 76, 3.5, "khóa dòng tồn kho, ghi đơn")]
    for x1, x2, y, t in msgs:
        arrow(ax, x1, y, x2, y, c=INK2 if x2 > x1 else BLUE, lw=1.2)
        ax.text((x1 + x2) / 2, y + 1.1, t, ha="center", fontsize=9, color=INK, bbox=dict(fc="white", ec="none", pad=0.3))
    save(fig, "f2_sequence")

if want("sync"):
    fig, ax = canvas(10, 4.6)
    box(ax, 36, 30, 28, 12, "Kho catalog dùng chung\nS3: catalog.json + images/\n(cục bộ: thư mục catalog/)", c="red", fs=10.5)
    for i, (n, c) in enumerate([("EC2 #1", "aqua"), ("EC2 #2", "aqua"), ("run_local.py\n(máy cá nhân)", "gray")]):
        x = 6 + i * 32
        box(ax, x, 3, 22, 11, n + "\nCSDL riêng của máy", c=c, fs=10)
        arrow(ax, x + 11, 14, 50, 30, both=True, c=INK2, lw=1.2)
    ax.text(50, 21.5, "gộp lúc khởi động, sau mỗi lần sửa và mỗi 30 giây;\nbản có updated_at mới hơn thắng", ha="center", fontsize=10, color=INK2,
            bbox=dict(fc="white", ec="none"))
    box(ax, 76, 32, 22, 8, "CloudFront\nphát ảnh tới khách", c="violet", fs=10)
    arrow(ax, 64, 36, 76, 36, c=VIOLET)
    save(fig, "f2_catalog_sync")

if want("deploy"):
    fig, ax = canvas(10.5, 3.2)
    steps = [("deploy.py\nđọc deploy.env", "gray"), ("CloudFormation\ntạo/cập nhật stack", "orange"), ("VPC, SG, RDS,\nS3, CloudFront, ALB", "violet"),
             ("ASG khởi chạy EC2\ntheo Launch Template", "aqua"), ("User data: cài Python,\ngit clone, pip, systemd", "blue"), ("/health = ok\n→ InService, nhận tải", "yellow")]
    for i, (t, c) in enumerate(steps):
        box(ax, 1 + i * 17.3, 9, 15, 14, t, c=c, fs=9.8)
        if i: arrow(ax, i * 17.3 - 1.3, 16, 1 + i * 17.3, 16, c=INK2)
    ax.text(52, 3.5, "Khoảng 10–15 phút (RDS lâu nhất), thêm 2–4 phút để EC2 cài xong ứng dụng", ha="center", fontsize=10, color=INK2, style="italic")
    save(fig, "f2_deploy_flow")

if want("local"):
    fig, ax = canvas(10, 4.4)
    box(ax, 2, 18, 15, 9, "Trình duyệt\n/system/live", c="gray", fs=10)
    box(ax, 27, 15, 22, 15, "local_cluster.py\nbộ cân bằng tải :8000\nround robin + /health\nmỗi 2 giây", c="yellow", fs=10)
    arrow(ax, 17, 22.5, 27, 22.5, c=INK2)
    for i, (n, ls) in enumerate([("local-node-1 :8001", "-"), ("local-node-2 :8002", "-"), ("local-node-3 :8003\n(gõ + để thêm)", "--")]):
        y = 33 - i * 13
        box(ax, 58, y, 20, 9, n, c="aqua", fs=10, ls=ls)
        arrow(ax, 49, 22.5, 58, y + 4.5, c=INK2, lw=1.1)
        arrow(ax, 78, y + 4.5, 85, 22.5, c=BLUE, lw=1.1)
    box(ax, 85, 13, 14, 19, "CSDL chung\ninstance/shop.db\n+ catalog/\n+ SECRET_KEY\nchung", c="blue", fs=9.5)
    save(fig, "f2_local_cluster")

if want("gantt"):
    tasks = [("Khảo sát yêu cầu, chọn dịch vụ", 1, 1, 0), ("Nghiên cứu cơ sở lý thuyết", 1, 2, 0), ("Phân tích, thiết kế hệ thống và CSDL", 2, 2, 1),
             ("Lập trình website và kiểm thử tự động", 2, 4, 1), ("Viết hạ tầng dạng mã (CloudFormation)", 4, 5, 2),
             ("Triển khai thử trên AWS, sửa lỗi", 5, 6, 2), ("Kiểm thử tải, đo Auto Scaling", 6, 7, 2), ("S3/CloudFront, đồng bộ ảnh, chi phí", 7, 7, 2),
             ("Tổng hợp kết quả, viết báo cáo", 7, 8, 3)]
    cols = [BLUE, AQUA, ORANGE, VIOLET]; names = ["Khảo sát", "Xây dựng ứng dụng", "Hạ tầng và thực nghiệm", "Tổng hợp"]
    fig, ax = plt.subplots(figsize=(8.8, 3.9))
    for i, (t, a, b, g) in enumerate(tasks):
        y = len(tasks) - 1 - i
        ax.barh(y, b - a + 1, left=a - 0.5, height=0.56, color=cols[g], edgecolor="white", lw=2)
        ax.text(0.35, y, f"{i+1}. {t}", ha="right", va="center", fontsize=10.5)
    ax.set_yticks([]); ax.set_xticks(range(1, 9)); ax.set_xticklabels([f"Tuần {k}" for k in range(1, 9)])
    ax.set_xlim(0.5, 8.5); ax.grid(axis="x", color=GRID, lw=0.8); ax.spines["left"].set_visible(False)
    from matplotlib.patches import Patch
    ax.legend([Patch(color=c) for c in cols], names, loc="upper center", bbox_to_anchor=(0.2, -0.12), ncol=4, frameon=False, fontsize=10)
    save(fig, "f2_gantt")

if want("tests"):
    data = [("test_shop.py", 17, "cửa hàng, giỏ, đặt hàng"), ("test_ui.py", 11, "giao diện"), ("test_admin.py", 8, "quản trị"),
            ("test_auth.py", 7, "tài khoản"), ("test_catalog_sync.py", 7, "đồng bộ S3"), ("test_images.py", 6, "xử lý ảnh"), ("test_system.py", 6, "/health, /system")]
    fig, ax = plt.subplots(figsize=(7.6, 3.2))
    ys = np.arange(len(data))[::-1]
    ax.barh(ys, [d[1] for d in data], color=BLUE, height=0.55, edgecolor="white")
    for y, (n, v, d) in zip(ys, data):
        ax.text(v + 0.25, y, f"{v}", va="center", fontsize=10.5, color=INK)
    ax.set_yticks(ys); ax.set_yticklabels([f"{n} ({d})" for n, _, d in data], fontsize=10.5)
    ax.set_xlabel("Số ca kiểm thử (tổng 62, tất cả đạt)"); ax.set_xlim(0, 19); ax.grid(axis="x", color=GRID, lw=0.8)
    save(fig, "f2_tests")

if want("timeline"):
    import datetime as dt
    import matplotlib.dates as md
    T = lambda h, m, s=0: dt.datetime(2026, 10, 28, h, m, s)
    fig, ax = plt.subplots(figsize=(8.6, 3.3))
    ax.step([T(21, 27), T(21, 33, 58), T(22, 23, 21), T(22, 54, 50), T(23, 10)], [0, 1, 2, 1, 1], where="post", color=AQUA, lw=2.4)
    ax.xaxis.set_major_formatter(md.DateFormatter("%H:%M")); ax.set_ylim(0, 4.6); ax.set_yticks(range(0, 5))
    ax.set_ylabel("Số EC2 mong muốn"); ax.set_xlabel("Thời gian ngày 28/10/2026 (UTC+7)")
    ax.axhline(4, color=MUTED, ls=":", lw=1); ax.text(T(21, 28), 4.08, "MaxSize = 4", fontsize=9.5, color=MUTED)
    for x, y, t, dy in [(T(21, 33, 58), 1, "21:33:58 máy đầu tiên\n(stack bắt đầu 21:27:35)", 1.1), (T(22, 23, 21), 2, "22:23:21 AlarmHigh\nscale out 1 → 2", 1.0),
                        (T(22, 54, 50), 1, "22:54:50 AlarmLow\nscale in 2 → 1", 1.6)]:
        ax.annotate(t, xy=(x, y), xytext=(x, y + dy), fontsize=9.5, ha="center", arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
        ax.plot([x], [y], "o", color=AQUA, ms=7, mec="white", mew=1.5)
    ax.axvspan(T(22, 23, 21), T(22, 54, 50), color=AQUA, alpha=0.08, lw=0)
    ax.grid(axis="y", color=GRID, lw=0.8)
    save(fig, "f2_aws_timeline")

if want("bench"):
    root = "../ket_qua_do_cuc_bo/"
    sh = json.load(open(root + "shopper_summary.json")); hv = json.load(open(root + "heavy_summary.json"))
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, d, name in [(axs[0], sh, "(a) Shopper: duyệt web, đặt hàng"), (axs[1], hv, "(b) HeavyShopper: thêm tác vụ nặng CPU")]:
        u = [r["users"] for r in d]; c = [r["server_cpu_pct"] for r in d]
        ax.plot(u, c, "-o", color=BLUE, lw=2, ms=7, mec="white", mew=1.5)
        for x, y in zip(u, c): ax.text(x, y + 4, f"{y:.0f} %", ha="center", fontsize=9.5)
        ax.axhline(50, color=ORANGE, ls="--", lw=1.5); ax.text(u[0], 52, "mục tiêu 50 %", color=ORANGE, fontsize=9.5)
        ax.set_title(name, fontsize=11); ax.set_xlabel("Số người dùng ảo"); ax.set_xticks(u); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_ylim(0, 108)
    axs[0].set_ylabel("CPU máy chủ (%)")
    save(fig, "f2_bench_cpu")
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, d, name in [(axs[0], sh, "(a) Shopper"), (axs[1], hv, "(b) HeavyShopper")]:
        u = [r["users"] for r in d]; p = [r["p95_ms"] for r in d]; m = [r["p50_ms"] for r in d]
        ax.plot(u, p, "-o", color=ORANGE, lw=2, ms=7, mec="white", mew=1.5, label="p95")
        ax.plot(u, m, "-s", color=BLUE, lw=2, ms=6, mec="white", mew=1.5, label="p50")
        for x, y in zip(u, p): ax.text(x, y + 14, f"{y}", ha="center", fontsize=9.5)
        ax.set_title(name, fontsize=11); ax.set_xlabel("Số người dùng ảo"); ax.set_xticks(u); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_ylim(0, 440)
    axs[0].set_ylabel("Độ trễ (ms)"); axs[1].legend(frameon=False, fontsize=10, loc="upper left")
    save(fig, "f2_bench_latency")

if want("roadmap"):
    fig, ax = canvas(10.5, 3.6)
    cols = [("Bảo mật", "red", ["HTTPS: ACM + Route 53", "Secrets Manager cho mật khẩu", "EC2 trong subnet riêng + NAT", "AWS WAF trước ALB"]),
            ("Sẵn sàng cao", "blue", ["RDS Multi-AZ, sao lưu tự động", "Tối thiểu 2 máy trên 2 AZ", "Snapshot RDS trước khi xóa stack"]),
            ("Hiệu năng", "aqua", ["ElastiCache cho dữ liệu nóng", "CDN cho tệp tĩnh CSS/JS", "Co giãn theo request và theo lịch"]),
            ("Vận hành", "violet", ["CI/CD: kiểm thử → Instance Refresh", "Container: Amazon ECS Fargate", "Cảnh báo chi phí, nhật ký tập trung"])]
    for i, (h, c, its) in enumerate(cols):
        x = 1 + i * 26
        box(ax, x, 27, 24, 6.5, h, c=c, fs=11.5, bold=True)
        for j, t in enumerate(its):
            box(ax, x, 20 - j * 6.2, 24, 5.2, t, c="gray", fs=9.8, fill="white")
    save(fig, "f3_roadmap")
