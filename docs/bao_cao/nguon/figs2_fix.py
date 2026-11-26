from figs_common import *
import sys
which = sys.argv[1:] or ["all"]
def want(n): return "all" in which or n in which
WB = dict(fc="white", ec="none", pad=0.5)

if want("arch"):
    fig, ax = canvas(10.5, 8.4)  # 105 x 84
    zone(ax, 15, 1, 89, 74, "AWS Cloud · Region Asia Pacific (Sydney) ap-southeast-2", c="orange", ls="-")
    zone(ax, 17, 3, 63, 67, "VPC 10.20.0.0/16", c="violet")
    zone(ax, 24, 5, 26, 52, "Vùng sẵn sàng A", c="gray")
    zone(ax, 52, 5, 26, 52, "Vùng sẵn sàng B", c="gray")
    zone(ax, 25.5, 28, 23, 25, "Subnet công khai 10.20.1.0/24", c="aqua", fs=9)
    zone(ax, 53.5, 28, 23, 25, "Subnet công khai 10.20.2.0/24", c="aqua", fs=9)
    zone(ax, 25.5, 6.5, 23, 19, "Subnet riêng 10.20.11.0/24", c="blue", fs=9)
    zone(ax, 53.5, 6.5, 23, 19, "Subnet riêng 10.20.12.0/24", c="blue", fs=9)
    box(ax, 26, 60, 50, 5.5, "Application Load Balancer · HTTP :80 · health check /health", c="yellow", fs=10.5, bold=True)
    ax.add_patch(FancyBboxPatch((27, 30), 48.5, 18.5, boxstyle="round,pad=0,rounding_size=1.2", fc="none", ec=ORANGE, lw=1.6, ls="-."))
    ax.text(51.2, 32.3, "Auto Scaling Group (1–4 máy, Target Tracking CPU 50 %)", ha="center", fontsize=9.5, color=ORANGE, fontweight="bold", bbox=WB)
    box(ax, 29, 36, 17, 9, "EC2 t3.micro #1\nGunicorn :8000", c="aqua", fs=9.5)
    box(ax, 57, 36, 17, 9, "EC2 t3.micro #2…#4\n(thêm khi tải cao)", c="aqua", fs=9.5, ls="--")
    box(ax, 29, 9, 17, 9, "Amazon RDS\nMySQL 8.4\ndb.t3.micro", c="blue", fs=9.5)
    ax.text(65, 15, "(subnet thứ hai của\nDB Subnet Group)", ha="center", va="center", fontsize=9, color=MUTED, style="italic")
    box(ax, 17.6, 60, 5.6, 5.5, "IGW", c="violet", fs=9)
    box(ax, 1, 58.5, 12, 8.5, "Người dùng\n(trình duyệt)", c="gray", fs=10)
    arrow(ax, 13, 62.7, 17.6, 62.7, c=INK2)
    arrow(ax, 23.2, 62.7, 26, 62.7, c=INK2)
    arrow(ax, 37.5, 60, 37.5, 45, c=INK2); arrow(ax, 65.5, 60, 65.5, 45, c=INK2)
    ax.text(41.5, 55.5, ":8000", fontsize=9, color=INK2, ha="center", bbox=WB)
    arrow(ax, 33, 36, 33, 18, c=BLUE); ax.text(36.5, 22.5, ":3306", fontsize=9, color=BLUE, ha="center", bbox=WB)
    ax.text(40.5, 27.4, "mọi EC2 → RDS", fontsize=8.5, color=BLUE, ha="center", bbox=WB)
    sx = 83
    box(ax, sx, 62, 19, 7.5, "CloudFront (CDN)\nảnh sản phẩm", c="violet", fs=9.5)
    box(ax, sx, 50, 19, 8.5, "Amazon S3\ncatalog.json + images/", c="red", fs=9.5)
    box(ax, sx, 37.5, 19, 9, "CloudWatch\nsố liệu · cảnh báo\ndashboard", c="blue", fs=9.5)
    box(ax, sx, 26, 19, 8, "Amazon SNS\nemail co giãn", c="yellow", fs=9.5)
    box(ax, sx, 14.5, 19, 7.5, "IAM Role\n(EC2 → S3)", c="gray", fs=9.5)
    box(ax, sx, 3, 19, 7.5, "CloudFormation\n(stack cloudshop)", c="orange", fs=9.5)
    arrow(ax, 74, 43, sx, 54, "đọc/ghi", c=RED, fs=8.5, off=(0, 1.0))
    arrow(ax, sx + 9.5, 62, sx + 9.5, 58.5, c=VIOLET)
    arrow(ax, 74, 39, sx, 41.5, "số liệu", c=BLUE, fs=8.5, off=(0, -2.2))
    arrow(ax, sx + 9.5, 37.5, sx + 9.5, 34, c=INK2)
    ax.plot([7, 7, sx + 9.5], [67, 79.5, 79.5], color=VIOLET, lw=1.4, ls="--")
    arrow(ax, sx + 9.5, 79.5, sx + 9.5, 69.5, c=VIOLET, ls="--")
    ax.text(50, 80.6, "trình duyệt tải ảnh sản phẩm trực tiếp từ CloudFront", fontsize=9, color=VIOLET, ha="center")
    save(fig, "f2_architecture")

if want("erd"):
    fig, ax = canvas(10.5, 6.6)
    def ent(x, y, name, fields, c="blue", w=24):
        h = 4.2 + 2.9 * len(fields)
        ax.add_patch(FancyBboxPatch((x, y - h), w, h, boxstyle="round,pad=0,rounding_size=0.8", fc="white", ec=EDGE[c], lw=1.4))
        ax.add_patch(FancyBboxPatch((x, y - 4.2), w, 4.2, boxstyle="round,pad=0,rounding_size=0.8", fc=TINT[c], ec=EDGE[c], lw=1.4))
        ax.text(x + w / 2, y - 2.1, name, ha="center", va="center", fontweight="bold", fontsize=11)
        for i, f in enumerate(fields):
            ax.text(x + 1.2, y - 6 - i * 2.9, f, va="center", fontsize=9.5)
    ent(2, 64, "users", ["PK id", "email (duy nhất)", "full_name", "password_hash", "is_admin", "created_at"], c="gray")
    ent(40, 64, "categories", ["PK id", "name", "slug (duy nhất)"], c="aqua")
    ent(40, 46, "products", ["PK id", "sku (duy nhất)", "name, price, stock", "FK category_id", "description, hue", "is_active", "uid (đồng bộ)", "updated_at, deleted_at"], c="blue", w=26)
    ent(79, 46, "product_photos", ["PK id", "FK product_id", "position", "key (tên file ảnh)"], c="violet")
    ent(2, 38, "orders", ["PK id", "code (mã đơn)", "FK user_id (có thể rỗng)", "customer_name, phone", "address, total", "status", "served_by (instance)", "created_at"], c="orange", w=26)
    ent(40, 13, "order_items", ["PK id", "FK order_id · FK product_id", "product_name, price, quantity"], c="yellow", w=30)
    def rel(x1, y1, x2, y2, tx, ty):
        arrow(ax, x1, y1, x2, y2, c=INK2, lw=1.2)
        ax.text(tx, ty, "1 – n", fontsize=9.5, color=INK2, ha="center", va="center", bbox=dict(fc="white", ec="none", pad=0.3))
    rel(52, 51.1, 52, 46, 56, 48.6)
    rel(66, 34, 79, 34, 72.5, 36)
    rel(14, 42.4, 14, 38, 18, 40.2)
    rel(28, 20, 40, 7, 30, 12)
    rel(55, 18.6, 55, 13, 59, 15.8)
    save(fig, "f2_erd")

if want("deploy"):
    fig, ax = canvas(10.5, 3.2)
    steps = [("deploy.py\nđọc deploy.env", "gray"), ("CloudFormation\ntạo hoặc cập\nnhật stack", "orange"), ("Tạo VPC, SG,\nRDS, S3,\nCloudFront, ALB", "violet"),
             ("ASG khởi chạy\nEC2 theo Launch\nTemplate", "aqua"), ("User data: cài\nPython, git clone,\npip, systemd", "blue"), ("/health = ok\n→ InService,\nnhận tải", "yellow")]
    for i, (t, c) in enumerate(steps):
        box(ax, 1 + i * 17.3, 8, 15.3, 16, t, c=c, fs=9.6)
        if i: arrow(ax, i * 17.3 - 1.0, 16, 1 + i * 17.3, 16, c=INK2)
    ax.text(52, 3.2, "Khoảng 10–15 phút (RDS lâu nhất), thêm 2–4 phút để EC2 cài xong ứng dụng", ha="center", fontsize=10, color=INK2, style="italic")
    save(fig, "f2_deploy_flow")

if want("local"):
    fig, ax = canvas(10, 4.4)
    box(ax, 1, 18, 15, 9, "Trình duyệt\n/system/live", c="gray", fs=10)
    box(ax, 25, 15, 22, 15, "local_cluster.py\nbộ cân bằng tải :8000\nround robin + /health\nmỗi 2 giây", c="yellow", fs=10)
    arrow(ax, 16, 22.5, 25, 22.5, c=INK2)
    for i, (n, ls) in enumerate([("local-node-1 :8001", "-"), ("local-node-2 :8002", "-"), ("local-node-3 :8003\n(gõ + để thêm)", "--")]):
        y = 33 - i * 13
        box(ax, 55, y, 20, 9, n, c="aqua", fs=10, ls=ls)
        arrow(ax, 47, 22.5, 55, y + 4.5, c=INK2, lw=1.1)
        arrow(ax, 75, y + 4.5, 82, 22.5, c=BLUE, lw=1.1)
    box(ax, 82, 12, 17.5, 21, "Dùng chung:\ninstance/shop.db\nthư mục catalog/\nSECRET_KEY", c="blue", fs=9.5)
    save(fig, "f2_local_cluster")

if want("roadmap"):
    fig, ax = canvas(10.5, 3.0)
    cols = [("Bảo mật", "red", ["HTTPS và tên miền riêng", "AWS Secrets Manager", "EC2 trong subnet riêng"]),
            ("Sẵn sàng cao", "blue", ["RDS Multi-AZ", "Sao lưu tự động", "Tối thiểu 2 máy trên 2 AZ"]),
            ("Hiệu năng", "aqua", ["Bộ nhớ đệm dữ liệu", "Co giãn theo lịch", "Co giãn theo số request"]),
            ("Vận hành", "violet", ["Tự động kiểm thử, triển khai", "Chuyển sang container", "Cảnh báo chi phí"])]
    for i, (h, c, its) in enumerate(cols):
        x = 1 + i * 26
        box(ax, x, 22, 25, 6.5, h, c=c, fs=11.5, bold=True)
        for j, t in enumerate(its):
            box(ax, x, 15 - j * 6.2, 25, 5.2, t, c="gray", fs=10.5, fill="white")
    save(fig, "f3_roadmap")
