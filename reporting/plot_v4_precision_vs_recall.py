#!/usr/bin/env python3
"""
evaluation_v4.md — Precision vs. Recall (Inference Quality, §1)

Scatters one point per (judge, doctor) combo from the CSV produced by
reporting/summarize_v4_metrics_csv.py:

  x = recall      (§1, TP / |truth_set| — coverage of the reference candidate set)
  y = precision   (§1, TP / |predicted| — how much of what the doctor named was right)

Recall on x, precision on y (the conventional PR-curve orientation). A
dashed F1=const contour grid is not drawn (only ~10 points, not a curve
sweep), but the plot area is annotated with the diagonal precision=recall
line so points above it favor precision, below it favor recall. Point color
= doctor model (same canonical palette as the other v4 scripts); marker
shape = judge. Combos missing either field are skipped (reported on stderr).

Usage:
  python reporting/plot_v4_precision_vs_recall.py [--csv PATH] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_v4_precision_vs_recall.py \\
      --csv saved/run_batch_20260912/analysis/v4_metrics_summary_plain.csv
"""
from __future__ import annotations

import argparse
import csv as csv_mod
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.paths import ANALYSIS_ROOT

SELECTED_DOCTORS = {
    "gpt-5.4",
    "gemini-3.8-flash",
    "claude-sonnet-5",
    "llama-3.3-70b-instruct",
    "qwen3-235b",
}

# Same palette + per-model assignment convention as the other v4 scripts,
# so a model keeps its color across all v4 figures.
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
           "#56B4E9", "#999999", "#000000", "#F0E442"]
MARKERS = ["o", "^", "s", "D", "P", "X"]


def _to_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None, help="Input CSV from summarize_v4_metrics_csv.py")
    parser.add_argument("-o", "--out", default=None, help="Output PNG path")
    args = parser.parse_args()

    csv_path = Path(args.csv) if args.csv else ANALYSIS_ROOT / "v4_metrics_summary_plain.csv"
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv_mod.DictReader(f))
    rows = [r for r in rows if r["doctor"].lower() in SELECTED_DOCTORS]
    if not rows:
        print(f"No rows in {csv_path}")
        return

    canonical_doctors = sorted({r["doctor"].lower() for r in rows})
    color_of = {d: PALETTE[i % len(PALETTE)] for i, d in enumerate(canonical_doctors)}
    judges = sorted({r["judge"] for r in rows})
    marker_of = {j: MARKERS[i % len(MARKERS)] for i, j in enumerate(judges)}

    points, skipped = [], []
    for r in rows:
        # "rigid" (tier-priority) reference candidate set, not the loose union —
        # see eval/evaluate_turns.py's rigid_truth_set.
        x = _to_float(r["recall_rigid"])
        y = _to_float(r["precision_rigid"])
        if x is None or y is None:
            skipped.append(f"{r['judge']}/{r['doctor']}")
            continue
        points.append((r["judge"], r["doctor"], x, y))

    if skipped:
        print(f"Skipped (missing precision or recall): {', '.join(skipped)}", file=sys.stderr)
    if not points:
        print("No combo has both precision and recall.")
        return

    fig, ax = plt.subplots(figsize=(8.5, 7))

    xs = [p[2] for p in points]
    ys = [p[3] for p in points]
    x_pad = (max(xs) - min(xs)) * 0.15 or 0.02
    y_pad = (max(ys) - min(ys)) * 0.15 or 0.02
    x_lo, x_hi = min(xs) - x_pad, max(xs) + x_pad
    y_lo, y_hi = min(ys) - y_pad, max(ys) + y_pad

    diag_lo = min(x_lo, y_lo)
    diag_hi = max(x_hi, y_hi)
    ax.plot([diag_lo, diag_hi], [diag_lo, diag_hi], color="#c3c2b7", linewidth=1.2,
            linestyle=":", zorder=1, clip_on=True)
    ax.annotate("precision = recall", (x_hi, min(x_hi, y_hi)), textcoords="offset points",
                xytext=(-6, 4), ha="right", fontsize=8, color="#898781", style="italic")

    seen_models: set[str] = set()
    for judge, doctor, x, y in points:
        color = color_of[doctor.lower()]
        label = doctor if doctor.lower() not in seen_models else None
        seen_models.add(doctor.lower())
        ax.scatter(x, y, color=color, marker=marker_of[judge], s=170,
                   edgecolors="white", linewidths=0.8, zorder=3, label=label)
        ax.annotate(doctor, (x, y), textcoords="offset points", xytext=(7, 6),
                    fontsize=8.5, color="#3a3a38")

    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_lo, y_hi)

    ax.set_xlabel("Recall (rigid) — §1, TP / |rigid_truth_set|, higher = better", fontsize=10, color="#52514e")
    ax.set_ylabel("Precision (rigid) — §1, TP / |predicted|, higher = better", fontsize=10, color="#52514e")
    # ax.set_title(
    #     "evaluation_v4.md §1 — Precision vs. Recall",
    #     fontsize=12, fontweight="bold",
    # )
    ax.grid(color="#e1e0d9", linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    model_handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color_of[d],
                   markeredgecolor="white", markersize=9, label=d)
        for d in canonical_doctors
    ]
    judge_handles = [
        plt.Line2D([0], [0], marker=marker_of[j], color="w", markerfacecolor="#999999",
                   markeredgecolor="white", markersize=9, label=j)
        for j in judges
    ]
    leg1 = ax.legend(handles=model_handles, title="Doctor model", loc="upper left",
                      bbox_to_anchor=(1.02, 1.0), fontsize=8.5, frameon=False)
    ax.add_artist(leg1)
    ax.legend(handles=judge_handles, title="Judge", loc="lower left",
              bbox_to_anchor=(1.02, 0.0), fontsize=8.5, frameon=False)

    fig.tight_layout()
    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "v4_precision_vs_recall.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
