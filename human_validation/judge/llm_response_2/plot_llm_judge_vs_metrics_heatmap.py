#!/usr/bin/env python3
"""
Heatmap: rows = our automated metrics, columns = LLM-as-judge ratings (3 dims),
cell = Pearson r with p-value and n, episode level, from llm_judge_vs_metrics.csv
(written by correlate_llm_judge.py). No binarization.

Usage:
  python human_validation/judge/llm_response_2/plot_llm_judge_vs_metrics_heatmap.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as scipy_stats

THIS_DIR = Path(__file__).resolve().parent
CSV_PATH = THIS_DIR / "llm_judge_vs_metrics.csv"

METRIC_ROWS = [
    ("jaccard_rigid_mean", "Jaccard (rigid)"),
    ("ias_mean", "QTS"),
    ("evidence_sufficiency_pred", "DES (_pred)"),
]
JUDGE_COLS = [
    ("llm_mean_h", "진단 가설 품질"),
    ("llm_mean_q", "질문 품질"),
    ("llm_evidence_sufficiency", "진단 근거 충분성"),
]


def _to_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def pearson_p(xs: list[float], ys: list[float]) -> tuple[float | None, float | None, int]:
    n = len(xs)
    if n < 3:
        return None, None, n
    r, p = scipy_stats.pearsonr(xs, ys)
    return float(r), float(p), n


def main() -> None:
    cjk = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    fm.fontManager.addfont(cjk)
    plt.rcParams["font.family"] = [fm.FontProperties(fname=cjk).get_name(), "DejaVu Sans"]

    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    grid = np.full((len(METRIC_ROWS), len(JUDGE_COLS)), np.nan)
    pgrid = np.full(grid.shape, np.nan)
    ns = np.zeros(grid.shape, dtype=int)
    for i, (mkey, _mlabel) in enumerate(METRIC_ROWS):
        for j, (jkey, _jlabel) in enumerate(JUDGE_COLS):
            xs, ys = [], []
            for row in rows:
                a = _to_float(row.get(mkey))
                b = _to_float(row.get(jkey))
                if a is None or b is None:
                    continue
                xs.append(a)
                ys.append(b)
            r, p, n = pearson_p(xs, ys)
            if r is not None:
                grid[i, j] = r
                pgrid[i, j] = p
            ns[i, j] = n

    fig, ax = plt.subplots(figsize=(10, 5.2))
    im = ax.imshow(grid, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(JUDGE_COLS)))
    ax.set_xticklabels([f"{label}\n(LLM-as-judge)" for _k, label in JUDGE_COLS], fontsize=11)
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
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03)
    cbar.set_label("Pearson r", fontsize=11)
    ax.set_xlabel("LLM-as-judge rating (column)", fontsize=12, labelpad=8)
    ax.set_ylabel("Automated metric (row)", fontsize=12)
    fig.suptitle("Automated metric vs. LLM-as-judge rating (episode level)", fontsize=13, y=1.02)
    fig.tight_layout()
    out = THIS_DIR / "llm_judge_vs_metrics_correlation.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out}")


if __name__ == "__main__":
    main()
