from figs_common import *
import numpy as np

# H1.1 Mô hình dịch vụ
fig, ax = canvas(10, 6.4)
layers = ["Ứng dụng", "Dữ liệu", "Môi trường chạy", "Phần mềm trung gian", "Hệ điều hành", "Ảo hóa", "Máy chủ", "Lưu trữ", "Mạng"]
cols = [("Tại chỗ\n(On-premises)", 9), ("IaaS", 5), ("PaaS", 2), ("SaaS", 0)]
for ci, (name, user_n) in enumerate(cols):
    x = 4 + ci * 24
    ax.text(x + 10, 61, name, ha="center", va="center", fontsize=12.5, fontweight="bold")
    for li, lay in enumerate(layers):
        y = 52 - li * 5.6
        c = "blue" if li < user_n else "orange"
        box(ax, x, y, 20, 4.6, lay, c=c, fs=10.5, r=0.6)
box(ax, 18, 0.2, 3, 2.4, "", c="blue", r=0.4); ax.text(22, 1.4, "Người dùng tự quản lý", va="center", fontsize=11)
box(ax, 52, 0.2, 3, 2.4, "", c="orange", r=0.4); ax.text(56, 1.4, "Nhà cung cấp đám mây quản lý", va="center", fontsize=11)
save(fig, "f1_service_models")

# H1.2 Co giãn dọc và ngang
fig, ax = canvas(10, 4.2)
zone(ax, 1, 1, 44, 40, "(a) Co giãn dọc (scale up)", c="blue")
box(ax, 6, 10, 10, 9, "Máy chủ\n2 vCPU\n1 GiB", c="gray", fs=10)
arrow(ax, 17.5, 14.5, 25, 14.5, "nâng cấp", c=BLUE)
box(ax, 26.5, 6, 15, 17, "Máy chủ\n8 vCPU\n32 GiB", c="blue", fs=11)
ax.text(23, 30, "Thêm CPU/RAM cho một máy.\nGiới hạn bởi cỡ máy lớn nhất,\nthường phải khởi động lại.", ha="center", va="center", fontsize=10.5, color=INK2)
zone(ax, 55, 1, 44, 40, "(b) Co giãn ngang (scale out)", c="aqua")
box(ax, 67, 29, 20, 5.5, "Bộ cân bằng tải", c="yellow", fs=10.5)
for i, (x, c) in enumerate([(58, "gray"), (68.5, "gray"), (79, "aqua"), (89.5, "aqua")]):
    box(ax, x, 8, 8.5, 9, f"Máy\n#{i+1}", c=c, fs=10, ls="-" if i < 2 else "--")
    arrow(ax, 77, 29, x + 4.25, 17.3, c=INK2, lw=1.1)
ax.text(77, 4.2, "Thêm/bớt máy giống nhau; không cần dừng hệ thống", ha="center", fontsize=10.5, color=INK2)
save(fig, "f1_scaling_types")

# H1.3 Dung lượng cố định và co giãn (minh họa)
t = np.linspace(0, 24, 400)
demand = 18 + 10*np.exp(-((t-11.5)/2.2)**2) + 26*np.exp(-((t-20.5)/1.3)**2) + 4*np.sin(t/3.8)
cap_unit = 8
auto = np.ceil(demand*1.08/cap_unit)*cap_unit
fig, ax = plt.subplots(figsize=(8.6, 3.9))
ax.plot(t, demand, color=INK, lw=2, label="Nhu cầu thực tế (minh họa)")
ax.axhline(demand.max()*1.05, color=ORANGE, lw=2, ls="--", label="Cấu hình cố định theo đỉnh")
ax.axhline(demand.mean(), color=VIOLET, lw=2, ls=":", label="Cấu hình cố định theo trung bình")
ax.step(t, auto, where="post", color=AQUA, lw=2, label="Auto Scaling (bậc theo số máy)")
ax.fill_between(t, demand, demand.mean(), where=demand > demand.mean(), color=RED, alpha=0.12, lw=0)
ax.annotate("thiếu tài nguyên (quá tải)\nnếu cấu hình theo trung bình", xy=(19.7, 30), xytext=(14.5, 56), color=RED, fontsize=10, ha="center", arrowprops=dict(arrowstyle="-", color=RED, lw=0.8))
ax.text(0.4, demand.max()*1.05-4.2, "lãng phí lúc vắng khách nếu cấu hình theo đỉnh", color=ORANGE, fontsize=10)
ax.set_xlim(0, 24); ax.set_ylim(0, 64); ax.set_xlabel("Giờ trong ngày"); ax.set_ylabel("Tài nguyên (đơn vị tương đối)")
ax.set_xticks(range(0, 25, 3)); ax.grid(axis="y", color=GRID, lw=0.8)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), fontsize=10, frameon=False, ncol=2)
save(fig, "f1_capacity")

# H1.4 Vòng điều khiển Target Tracking
fig, ax = canvas(10, 4.6)
box(ax, 2, 25, 22, 12, "Auto Scaling Group\nEC2 #1 … EC2 #N", c="aqua", fs=11)
box(ax, 39, 33, 22, 10, "CloudWatch\nCPUUtilization\n(trung bình nhóm, 1 phút)", c="blue", fs=10.5)
box(ax, 76, 25, 22, 12, "Cảnh báo\nAlarmHigh / AlarmLow", c="red", fs=11)
box(ax, 39, 4, 22, 12, "Chính sách Target Tracking\nmục tiêu CPU = 50 %", c="yellow", fs=10.5)
arrow(ax, 24, 34, 39, 38, "gửi số liệu", rad=-0.1)
arrow(ax, 61, 38, 76, 34, "so với mục tiêu", rad=-0.1)
arrow(ax, 87, 25, 61, 11, "kích hoạt", rad=-0.15)
arrow(ax, 39, 10, 13, 25, "đổi Desired capacity\n(thêm / bớt máy)", rad=-0.15, off=(-4, -2))
ax.text(50, 24.5, "vòng phản hồi\nkhép kín", ha="center", va="center", fontsize=10.5, color=MUTED, style="italic")
save(fig, "f1_target_tracking")

# H1.5 Cân bằng tải + health check
fig, ax = canvas(10, 4.2)
box(ax, 2, 16, 14, 10, "Người dùng\n(trình duyệt)", c="gray", fs=10.5)
box(ax, 32, 14, 20, 14, "Bộ cân bằng tải\n(round robin)\nkiểm tra /health\nmỗi 15 giây", c="yellow", fs=10.5)
arrow(ax, 16, 21, 32, 21, "HTTP :80")
ys = [33, 19, 5]
for i, y in enumerate(ys):
    bad = i == 2
    box(ax, 70, y, 20, 8, f"Máy chủ #{i+1}\n" + ("không khỏe" if bad else "khỏe (200 OK)"), c="red" if bad else "aqua", fs=10.5, ls="--" if bad else "-")
    arrow(ax, 52, 21, 70, y + 4, c=RED if bad else INK2, ls="--" if bad else "-", lw=1.2)
ax.text(61, 6.5, "X", color=RED, fontsize=16, ha="center", va="center", fontweight="bold")
ax.text(80, 1.5, "bị loại khỏi vòng phục vụ", ha="center", fontsize=10, color=RED)
save(fig, "f1_load_balancer")

# H1.6 Có trạng thái vs phi trạng thái
fig, ax = canvas(10, 4.4)
zone(ax, 1, 1, 46, 45, "(a) Có trạng thái: giỏ hàng trong RAM từng máy", c="red")
box(ax, 4, 25, 18, 9, "Máy A\nRAM: giỏ = 2 món", c="gray", fs=10)
box(ax, 26, 25, 18, 9, "Máy B\nRAM: giỏ trống", c="gray", fs=10)
box(ax, 15, 6, 16, 7, "Khách", c="gray", fs=10.5)
arrow(ax, 19, 13, 13, 25, "request 1", off=(-5, -2))
arrow(ax, 27, 13, 35, 25, "request 2", off=(5, -2))
ax.text(24, 38, "đổi máy → mất giỏ hàng", color=RED, fontsize=10.5, ha="center")
zone(ax, 53, 1, 46, 45, "(b) Phi trạng thái: cookie ký + CSDL dùng chung", c="aqua")
box(ax, 56, 25, 18, 9, "Máy A", c="aqua", fs=10.5)
box(ax, 78, 25, 18, 9, "Máy B", c="aqua", fs=10.5)
box(ax, 56, 6, 18, 8, "Khách\ncookie phiên đã ký", c="gray", fs=10)
box(ax, 78, 6, 18, 8, "CSDL dùng chung\n(RDS)", c="blue", fs=10)
arrow(ax, 65, 14, 65, 25, both=False)
arrow(ax, 70, 14, 84, 25)
arrow(ax, 87, 25, 87, 14, both=True, c=BLUE)
ax.text(76, 38, "máy nào cũng phục vụ được", color=GREEN, fontsize=10.5, ha="center")
save(fig, "f1_stateless")
