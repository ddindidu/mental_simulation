#!/usr/bin/env python3
"""
Turn-level scatter: expert per-turn rating (mean of Expert 2 & 3) vs. automated
per-turn metric (Jaccard rigid; QTS). Points beyond IQR_K×IQR of the residuals from
the pooled linear fit are drawn hollow and excluded from the fit and r.

Usage:
  MS_RUN=run_batch_20260912 python human_validation/judge/plot_turn_level_scatter.py
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent
for p in (_REPO_ROOT, _THIS_DIR):
    if str(p) not in _sys.path:
        _sys.path.insert(0, str(p))

from plot_expert_vs_llm_correlation import (  # noqa: E402
    doctor_from_kor_path,
    find_kor_file,
    pearson,
    spearman,
    turn_ias,
    turn_jaccard_rigid,
)
from correlate_expert_3 import EXPERT_FILES, expert_turn_ratings  # noqa: E402

IQR_K = 0.75
PANELS = [
    ("hyp", turn_jaccard_rigid, "Jaccard (rigid), per turn", "진단 가설 품질 (expert, per turn)"),
    ("qst", turn_ias, "QTS (IAS), per turn", "질문 품질 (expert, per turn)"),
]


def collect(key: str, getter, per_expert, common) -> list[tuple[str, int, float, float]]:
    pts = []
    for pid in common:
        kor = find_kor_file(pid)
        if kor is None:
            continue
        doctor = doctor_from_kor_path(kor)
        for t, a in getter(doctor, pid).items():
            vals = [e[pid][key].get(t) for e in per_expert if pid in e]
            vals = [v for v in vals if v is not None]
            if vals:
                pts.append((pid, t, a, float(np.mean(vals))))
    return pts


def main() -> None:
    cjk = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    fm.fontManager.addfont(cjk)
    plt.rcParams["font.family"] = [fm.FontProperties(fname=cjk).get_name(), "DejaVu Sans"]

    per_expert = [expert_turn_ratings(p) for p in EXPERT_FILES]
    common = sorted(set(per_expert[0]) & set(per_expert[1]))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))
    for ax, (key, getter, xlabel, ylabel) in zip(axes, PANELS):
        pts = collect(key, getter, per_expert, common)
        x = np.array([p[2] for p in pts])
        y = np.array([p[3] for p in pts])
        slope, intercept = np.polyfit(x, y, 1)
        res = y - (slope * x + intercept)
        q1, q3 = np.percentile(res, [25, 75])
        iqr = q3 - q1
        keep = (res >= q1 - IQR_K * iqr) & (res <= q3 + IQR_K * iqr)

        r, n = pearson(x[keep].tolist(), y[keep].tolist())
        rho, _ = spearman(x[keep].tolist(), y[keep].tolist())
        slope, intercept = np.polyfit(x[keep], y[keep], 1)

        rng = np.random.default_rng(0)
        jx = x + rng.uniform(-0.02, 0.02, x.size)
        jy = y + rng.uniform(-0.12, 0.12, y.size)
        ax.scatter(jx[~keep], jy[~keep], s=40, facecolors="none", edgecolors="#9a9a9a",
                   linewidths=1.0, zorder=2, label=f"excluded (n={(~keep).sum()})")
        ax.scatter(jx[keep], jy[keep], s=34, color="#0072B2", alpha=0.55,
                   edgecolors="white", linewidths=0.4, zorder=3, label=f"kept (n={keep.sum()})")
        grid = np.linspace(x.min(), x.max(), 50)
        ax.plot(grid, slope * grid + intercept, color="#D55E00", linewidth=1.8, zorder=4)

        ax.set_xlabel(xlabel, fontsize=13)
        ax.set_ylabel(ylabel, fontsize=13)
        ax.set_ylim(0.8, 5.2)
        ax.tick_params(labelsize=11)
        ax.grid(color="#E4EBF5", linewidth=0.8, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_title(f"r = {r:.3f},  ρ = {rho:.3f}  (kept turns, {IQR_K}×IQR filter)", fontsize=13)
        ax.legend(loc="upper left", fontsize=10, frameon=False)

    fig.tight_layout()
    out = _THIS_DIR / "expert_vs_metrics_turn_scatter.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out}")


if __name__ == "__main__":
    main()
