import os as _os; _os.chdir(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # chạy từ thư mục docs/bao_cao
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 12, "axes.edgecolor": "#8a8984",
                     "axes.labelcolor": "#0b0b0b", "xtick.color": "#52514e", "ytick.color": "#52514e",
                     "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 200})
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e2dc"
TINT = {"blue": "#e6f0fb", "orange": "#fdece4", "aqua": "#e2f5ee", "yellow": "#fdf3dc", "gray": "#f1f0ec", "violet": "#ecebfb", "red": "#fbe7e7"}
EDGE = {"blue": BLUE, "orange": ORANGE, "aqua": AQUA, "yellow": YELLOW, "gray": MUTED, "violet": VIOLET, "red": RED}
def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h)); ax.set_xlim(0, w * 10); ax.set_ylim(0, h * 10); ax.axis("off")
    return fig, ax
def box(ax, x, y, w, h, text, c="blue", fs=11, bold=False, r=1.2, lw=1.4, tc=INK, fill=None, ls="-", va="center", ha="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fill or TINT[c], ec=EDGE[c], lw=lw, ls=ls))
    if text:
        tx = x + w / 2 if ha == "center" else x + 1
        ty = y + h / 2 if va == "center" else y + h - 1.2
        ax.text(tx, ty, text, ha=ha, va=va if va == "center" else "top", fontsize=fs, color=tc, fontweight="bold" if bold else "normal", linespacing=1.25)
def zone(ax, x, y, w, h, label, c="gray", fs=10.5, ls="--"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.5", fc="none", ec=EDGE[c], lw=1.2, ls=ls))
    ax.text(x + 1.2, y + h - 1.0, label, ha="left", va="top", fontsize=fs, color=EDGE[c] if c != "gray" else INK2, fontweight="bold")
def arrow(ax, x1, y1, x2, y2, text=None, c=INK2, lw=1.4, both=False, fs=9.5, off=(0, 1.2), rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="<|-|>" if both else "-|>", mutation_scale=13, color=c, lw=lw,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls, shrinkA=0, shrinkB=0))
    if text:
        ax.text((x1 + x2) / 2 + off[0], (y1 + y2) / 2 + off[1], text, ha="center", va="center", fontsize=fs, color=INK2,
                bbox=dict(fc="white", ec="none", pad=0.6))
def save(fig, name):
    fig.savefig(f"hinh_minh_hoa/{name}.png", bbox_inches="tight", pad_inches=0.08, facecolor="white"); plt.close(fig); print("fig", name)
