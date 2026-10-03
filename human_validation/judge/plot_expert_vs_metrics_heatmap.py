#!/usr/bin/env python3
"""
Heatmap: rows = our automated metrics, columns = expert ratings (3 dimensions,
each for Expert 2, Expert 3, and their mean). Cell = Pearson r at episode level
(46 cases), no binarization.

Usage:
  MS_RUN=run_batch_20260912 python human_validation/judge/plot_expert_vs_metrics_heatmap.py
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as scipy_stats

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent
for p in (_REPO_ROOT, _THIS_DIR):
    if str(p) not in _sys.path:
        _sys.path.insert(0, str(_THIS_DIR if p == _THIS_DIR else _REPO_ROOT))

from plot_expert_vs_llm_correlation import (  # noqa: E402
    authoritative_mean_ias,
    authoritative_overall_score_pred,
    authoritative_rigid_means,
    doctor_from_kor_path,
    find_kor_file,
    parse_kor_metrics,
    pearson,
)
from correlate_expert_3 import DIMS, EXPERT_FILES, parse_expert  # noqa: E402

METRIC_ROWS = [
    ("jaccard", "Jaccard (rigid)"),
    # ("precision", "Precision (rigid)"),
    # ("recall", "Recall (rigid)"),
    ("ias", "QTS"),
    # ("ecr", "ECR"),
    # ("turn_count", "Turn count"),
    # ("turn_to_1st_confident", "Turns to 1st confident"),
    # ("final_accuracy", "Final accuracy"),
    ("diagnostic_evidence_sufficiency_pred", "DES (_pred)"),
]
RATERS = ["Mean (2, 3)"]
# ["Expert 2", "Expert 3", "Mean (2, 3)"]


def metrics_for(pid: str) -> dict[str, float | None] | None:
    kor = find_kor_file(pid)
    if kor is None:
        return None
    doctor = doctor_from_kor_path(kor)
    m = dict(parse_kor_metrics(kor))
    ias = authoritative_mean_ias(doctor, pid)
    if ias is not None:
        m["ias"] = ias
    for k, v in authoritative_rigid_means(doctor, pid).items():
        if v is not None:
            m[k] = v
    pred = authoritative_overall_score_pred(doctor, pid)
    if pred is not None:
        m["diagnostic_evidence_sufficiency_pred"] = pred
    return m


def main() -> None:
    cjk = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    fm.fontManager.addfont(cjk)
    plt.rcParams["font.family"] = [fm.FontProperties(fname=cjk).get_name(), "DejaVu Sans"]

    experts = [parse_expert(p) for p in EXPERT_FILES]
    common = sorted(set(experts[0]) & set(experts[1]))
    auto = {pid: metrics_for(pid) or {} for pid in common}

    col_specs = []
    for key, label, _idx, _metric in DIMS:
        for rater in RATERS:
            col_specs.append((key, label, rater))

    def expert_value(pid: str, key: str, rater: str) -> float | None:
        if rater == "Expert 2":
            return experts[0][pid][key]
        if rater == "Expert 3":
            return experts[1][pid][key]
        vals = [v for v in (experts[0][pid][key], experts[1][pid][key]) if v is not None]
        return float(np.mean(vals)) if vals else None

    grid = np.full((len(METRIC_ROWS), len(col_specs)), np.nan)
    ns = np.zeros(grid.shape, dtype=int)
    pgrid = np.full(grid.shape, np.nan)
    for i, (mkey, _mlabel) in enumerate(METRIC_ROWS):
        for j, (ekey, _elabel, rater) in enumerate(col_specs):
            xs, ys = [], []
            for pid in common:
                a = auto[pid].get(mkey)
                e = expert_value(pid, ekey, rater)
                if a is None or e is None:
                    continue
                xs.append(a)
                ys.append(e)
            if len(xs) >= 3:
                r, n = pearson(xs, ys)
                grid[i, j] = np.nan if r is None else r
                ns[i, j] = n
                if r is not None and abs(r) < 1:
                    t = r * np.sqrt((n - 2) / (1 - r * r))
                    pgrid[i, j] = 2 * scipy_stats.t.sf(abs(t), n - 2)

    fig, ax = plt.subplots(figsize=(17, 7.2))
    im = ax.imshow(grid, cmap="RdBu", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(col_specs)))
    ax.set_xticklabels([f"{rater}" for _k, _l, rater in col_specs], rotation=0, fontsize=10)
    group_centers = [(g * len(RATERS) + (len(RATERS) - 1) / 2) for g in range(len(DIMS))]
    for g, (_k, label, _i, _m) in enumerate(DIMS):
        ax.text(group_centers[g], -1.35, label, ha="center", va="bottom", fontsize=12, fontweight="bold")
        if g:
            ax.axvline(g * len(RATERS) - 0.5, color="white", linewidth=4)
    ax.set_yticks(range(len(METRIC_ROWS)))
    ax.set_yticklabels([m for _k, m in METRIC_ROWS], fontsize=11)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            v = grid[i, j]
            if np.isnan(v):
                txt, color = "n/a", "#1C2333"
            else:
                pv = pgrid[i, j]
                p_txt = "p<0.001" if pv < 0.001 else f"p={pv:.3f}"
                txt = f"r={v:.2f}\n{p_txt}\n(n={ns[i, j]})"
                color = "white" if abs(v) > 0.55 else "#1C2333"
            ax.text(j, i, txt, ha="center", va="center", fontsize=10, color=color)
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Pearson r", fontsize=11)
    ax.set_xlabel("Expert rating (column)", fontsize=12, labelpad=8)
    ax.set_ylabel("Automated metric (row)", fontsize=12)
    fig.suptitle("Automated metric vs. expert rating (episode level)", fontsize=13, y=1.07)
    fig.tight_layout()
    out = _THIS_DIR / "expert_vs_metrics_correlation.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out}")


if __name__ == "__main__":
    main()
