"""Reproduce the two time-horizon figures from METR TH1.1 data.

  1. t80/t50 ratio of each model as a function of release date.
  2. Success probability as a function of task length in units of t80
     (Weibull survival curves: constant hazard rate, current models, humans).

Usage:  python make_figures.py      (writes PDF, SVG and PNG to figures/)
"""
import yaml
from datetime import date
from math import log
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "benchmark_results_1_1.yaml"
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)

CHR = log(0.8) / log(0.5)  # 0.3219: t80/t50 under a constant hazard rate

LAB_COLOR = {
    "anthropic": "#D97757",
    "openai":    "#10A37F",
    "google":    "#4285F4",
}

def lab_of(key):
    if "claude" in key: return "anthropic"
    if "gemini" in key: return "google"
    return "openai"

with open(DATA) as f:
    d = yaml.safe_load(f)

rows = []
for k, v in d["results"].items():
    m = v["metrics"]
    rows.append({
        "key": k,
        "date": v["release_date"] if isinstance(v["release_date"], date) else date.fromisoformat(str(v["release_date"])),
        "t50": m["p50_horizon_length"]["estimate"],
        "t80": m["p80_horizon_length"]["estimate"],
        "lab": lab_of(k),
    })
rows.sort(key=lambda r: r["date"])
for r in rows:
    r["ratio"] = r["t80"] / r["t50"]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 13,
    "axes.titlesize": 16,
    "axes.labelsize": 14,
    "legend.fontsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    # 240 = 120 x 2: the published figures were laid out on a 2x (Retina) macOS
    # canvas. With the Agg backend this reproduces that layout on any platform.
    "figure.dpi": 240,
    "svg.hashsalt": "cdm",  # reproducible SVG ids
})

def save(fig, stem):
    # Timestamps are stripped so that re-running gives byte-identical files.
    fig.savefig(OUT / f"{stem}.pdf", metadata={"CreationDate": None})
    fig.savefig(OUT / f"{stem}.svg", metadata={"Date": None})
    fig.savefig(OUT / f"{stem}.png", dpi=400)

def lab_legend(ax):
    handles = [plt.Line2D([0],[0], marker='o', linestyle='', color=c,
                          label=l.capitalize(), markersize=9)
               for l,c in LAB_COLOR.items()]
    ax.legend(handles=handles, loc="best", frameon=False)

# ---------- Figure 1: t80/t50 ratio over time ----------
fig, ax = plt.subplots(figsize=(10, 6))
rows_p1 = [r for r in rows if r["key"] != "gpt2"]
dates = [r["date"] for r in rows_p1]
ratios = [r["ratio"] for r in rows_p1]
colors = [LAB_COLOR[r["lab"]] for r in rows_p1]

# Era background shading
era_split = date(2023, 1, 1)
x_left, x_right = date(2019, 6, 1), date(2026, 6, 1)
PRE_BG, POST_BG = "#DCE9D5", "#F5D9C8"
PRE_FG, POST_FG = "#3F6B33", "#9C4A1F"
ax.axvspan(x_left, era_split, facecolor=PRE_BG, alpha=0.55, zorder=0)
ax.axvspan(era_split, x_right, facecolor=POST_BG, alpha=0.55, zorder=0)

ax.axhline(CHR, linestyle="--", color="#444", linewidth=1.3, zorder=1)
ax.text(date(2020, 6, 1), CHR+0.012,
        f"Constant hazard rate (memoryless): {CHR:.3f}",
        color="#444", fontsize=11, style="italic")

ax.scatter(dates, ratios, c=colors, s=70, zorder=3, edgecolor="white", linewidth=0.8)

# Era labels on either side of the 2023 split
ax.text(date(2022, 10, 1), 0.55, "Completion models",
        color=PRE_FG, fontsize=12, fontweight="bold",
        ha="right", va="top")
ax.text(date(2023, 3, 1), 0.55, "Chat & agent models",
        color=POST_FG, fontsize=12, fontweight="bold",
        ha="left", va="top")

# Point labels for GPT-3, GPT-3.5, GPT-4 and Mythos
label_map = {
    "davinci_002": ("GPT-3", (6, -12)),
    "gpt_3_5_turbo_instruct": ("GPT-3.5", (6, -12)),
    "gpt_4": ("GPT-4", (6, -12)),
    "claude_mythos_preview_early_inspect": ("Mythos", (10, 10), "center"),
}
for r in rows_p1:
    if r["key"] in label_map:
        entry = label_map[r["key"]]
        text, offset = entry[0], entry[1]
        ha = entry[2] if len(entry) > 2 else ("right" if offset[0] < 0 else "left")
        ax.annotate(text,
                    xy=(r["date"], r["ratio"]),
                    xytext=offset, textcoords="offset points",
                    ha=ha, fontsize=10, color="#333")

ax.set_ylabel(r"$t_{80}\, /\, t_{50}$")
ax.set_title("Post-training changed the shape of failure. Scaling hasn't")
ax.set_ylim(0.05, 0.58)
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
lab_legend(ax)
fig.tight_layout()
save(fig, "ratio_over_time")
plt.close(fig)

# ---------- Figure 2: Weibull survival curves anchored at t_80 ----------
# S(x; k) = 0.8 ^ (10 ^ (k x)) where x = log10(t / t_80).
# All three curves cross at (0, 0.8).
#
# Human shape calibrated from Kwa et al. (2025) human data:
#   t_50(human) = 1.5 hr = 90 min;  S_human(16 hr) = 0.20
#   -> Weibull shape k_human = log(-ln 0.20 / -ln 0.5) / log(16*60/90) ~ 0.36
# AI shape calibrated from post-GPT4 mean ratio ~0.19:
#   ratio = 0.322^(1/k) -> k_ai = ln(0.322)/ln(0.19) ~ 0.68
# CHR is Weibull with k = 1 (memoryless).

k_hum_w, k_ai_w, k_chr_w = 0.36, 0.68, 1.0

def weibull_S_t80(x_log10, k):
    return 0.8 ** (10.0 ** (k * x_log10))

x5 = np.linspace(-2.0, 2.5, 600)
S_hum_5 = weibull_S_t80(x5, k_hum_w)
S_ai_5 = weibull_S_t80(x5, k_ai_w)
S_chr_5 = weibull_S_t80(x5, k_chr_w)

fig, ax = plt.subplots(figsize=(10, 6))

ax.plot(x5, S_chr_5, color="#555", linewidth=2.0, linestyle="--",
        label="Constant hazard rate models")
ax.plot(x5, S_ai_5, color="#c44536", linewidth=2.6,
        label="Current models\n"
              r"(unchanged for 2 yrs despite 240× improvement in $t_{50}$)")
ax.plot(x5, S_hum_5, color="#4a7c59", linewidth=2.6,
        label="Humans")

# Post-training gain: current models > memoryless past t_80
ax.fill_between(x5, S_chr_5, S_ai_5, where=(S_ai_5 > S_chr_5),
                color="#6a9dcf", alpha=0.22)
ax.text(1.0, 0.14, "Post-training gain", fontsize=13, style="italic",
        color="#2b5d87", ha="center",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7,
                  edgecolor="none"))

# Residual gap: humans vs current models past t_80
ax.fill_between(x5, S_ai_5, S_hum_5, where=(S_hum_5 > S_ai_5),
                color="#ffb703", alpha=0.22)
ax.text(1.55, 0.28, "Residual cognitive gap", fontsize=13, style="italic",
        color="#8a5a00", ha="center",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7,
                  edgecolor="none"))

ax.axvline(0, color="#888", linewidth=0.8, linestyle=":")
ax.axhline(0.5, color="#888", linewidth=0.8, linestyle=":")
ax.axhline(0.8, color="#888", linewidth=0.8, linestyle=":")

xticks5 = [-2, -1, 0, 1, 2]
xticklabels5 = [r"$0.01 \times t_{80}$", r"$0.1 \times t_{80}$", r"$t_{80}$",
                r"$10 \times t_{80}$", r"$100 \times t_{80}$"]
ax.set_xticks(xticks5)
ax.set_xticklabels(xticklabels5)

ax.set_xlim(-0.2, 2.5)
ax.set_ylim(0, 1)
ax.set_xlabel("Task length (log scale)")
ax.set_ylabel("Success probability")
ax.legend(loc="upper right", frameon=False)
fig.tight_layout()
save(fig, "success_vs_task_length")
plt.close(fig)

post = [r["ratio"] for r in rows if r["date"] >= era_split]
print(f"{len(rows)} models; mean t80/t50 since 2023 = {sum(post)/len(post):.3f} "
      f"(constant hazard rate: {CHR:.3f})")
print(f"Wrote 2 figures (PDF, SVG, PNG) to {OUT}")
