#!/usr/bin/env python3
"""
evaluation_v5.md — QTS vs. Diagnostic Evidence Sufficiency (doctor-average level)

Scatters one point per (judge, doctor) combo from the CSV produced by
reporting/summarize_v4_metrics_csv.py:

  x = qts                                    (§2, Question Targeting Score)
  y = diagnostic_evidence_sufficiency_pred      (§4, evidence sufficiency vs. GT criteria)

Point color = doctor model (same canonical palette as the other v4 scripts);
marker shape = judge. Combos missing either field are skipped (reported on
stderr). Same convention as plot_v4_precision_vs_recall.py.

Usage:
  python reporting/plot_v4_ias_vs_reasoning.py [--csv PATH] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_v4_ias_vs_reasoning.py \\
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

from utils.metric_compat import episode_mean_qts, turn_qts, csv_qts, csv_hypothesis
from utils.paths import ANALYSIS_ROOT
from reporting.plot_v4_radar_by_judge import DOCTOR_NAME_CANONICAL

JUDGE_NAME_CANONICAL = {
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
    "gpt-5.6-terra": "GPT 5.6 Terra",
}

SELECTED_DOCTORS = {
    "gpt-5.4",
    "gemini-3.8-flash",
    "claude-sonnet-5",
    "llama-3.3-70b-instruct",
    "qwen3-235b",
}

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
        x = _to_float(csv_qts(r))
        y = _to_float(r["diagnostic_evidence_sufficiency_pred"])
        if x is None or y is None:
            skipped.append(f"{r['judge']}/{r['doctor']}")
            continue
        points.append((r["judge"], r["doctor"], x, y))

    if skipped:
        print(f"Skipped (missing ias or diagnostic_evidence_sufficiency_pred): {', '.join(skipped)}", file=sys.stderr)
    if not points:
        print("No combo has both ias and diagnostic_evidence_sufficiency_pred.")
        return

    fig, ax = plt.subplots(figsize=(8.5, 7))

    xs = [p[2] for p in points]
    ys = [p[3] for p in points]
    x_pad = (max(xs) - min(xs)) * 0.15 or 0.02
    y_pad = (max(ys) - min(ys)) * 0.15 or 0.02
    x_lo, x_hi = min(xs) - x_pad, max(xs) + x_pad
    y_lo, y_hi = min(ys) - y_pad, max(ys) + y_pad

    seen_models: set[str] = set()
    annotations = []
    for judge, doctor, x, y in points:
        color = color_of[doctor.lower()]
        label = doctor if doctor.lower() not in seen_models else None
        seen_models.add(doctor.lower())
        ax.scatter(x, y, color=color, marker=marker_of[judge], s=170,
                   edgecolors="white", linewidths=0.8, zorder=3, label=label)
        # Same doctor's two judge points often sit close together (same
        # color): stagger the label vertically by judge index so they don't
        # collide, instead of every label defaulting to the same offset.
        y_off = 6 - 18 * judges.index(judge)
        ann = ax.annotate(DOCTOR_NAME_CANONICAL.get(doctor.lower(), doctor), (x, y),
                           textcoords="offset points", xytext=(7, y_off),
                           fontsize=12, color="#3a3a38")
        annotations.append((ann, x, y, y_off))

    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_lo, y_hi)

    ax.set_xlabel("QTS (Question Targeting Score)", fontsize=14, color="#52514e")
    ax.set_ylabel("Diagnostic Evidence Sufficiency", fontsize=14, color="#52514e")
    ax.tick_params(axis="both", labelsize=12)
    # ax.set_title(
    #     "evaluation_v5.md §2 vs §4 — IAS vs. Diagnostic Evidence Sufficiency",
    #     fontsize=12, fontweight="bold",
    # )
    ax.grid(color="#e1e0d9", linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    judge_handles = [
        plt.Line2D([0], [0], marker=marker_of[j], color="w", markerfacecolor="#999999",
                   markeredgecolor="white", markersize=10, label=JUDGE_NAME_CANONICAL.get(j, j))
        for j in judges
    ]
    ax.legend(handles=judge_handles, title="Judge", loc="lower right",
              fontsize=12, frameon=False)

    fig.tight_layout()

    # Resolve remaining label collisions: a label can run into either
    # another label's text OR a nearby point's marker (a label two doctors
    # apart in x can still slide its text right over a closer neighbor's
    # dot). Match the save dpi here — checking at the figure's default
    # (lower) dpi under-detects overlaps that only appear once text is
    # rendered at the larger, actually-saved size.
    fig.set_dpi(180)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    marker_radius_px = 0.5 * (170 ** 0.5) * (180 / 72)  # scatter s=170, pt->px at dpi=180
    marker_bboxes = []
    for _judge, _doctor, x, y in points:
        px, py = ax.transData.transform((x, y))
        marker_bboxes.append(plt.matplotlib.transforms.Bbox(
            [[px - marker_radius_px, py - marker_radius_px],
             [px + marker_radius_px, py + marker_radius_px]]))

    def _flip_left(mover, y_off_m):
        mover.set_ha("right")
        mover.xyann = (-7, y_off_m)

    for _pass in range(2):  # a flip can create a new collision; two passes settles it
        moved_any = False
        for i in range(len(annotations)):
            ann_i, xi, yi, y_off_i = annotations[i]
            bbox_i = ann_i.get_window_extent(renderer)
            for k, mbbox in enumerate(marker_bboxes):
                if k == i:
                    continue
                if bbox_i.overlaps(mbbox):
                    _flip_left(ann_i, y_off_i)
                    bbox_i = ann_i.get_window_extent(renderer)
                    moved_any = True
            for j in range(i + 1, len(annotations)):
                ann_j, xj, yj, y_off_j = annotations[j]
                bbox_j = ann_j.get_window_extent(renderer)
                if bbox_i.overlaps(bbox_j):
                    mover, y_off_m = (ann_i, y_off_i) if xi <= xj else (ann_j, y_off_j)
                    _flip_left(mover, y_off_m)
                    bbox_i = ann_i.get_window_extent(renderer)
                    moved_any = True
        if not moved_any:
            break

    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "v4_ias_vs_reasoning.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
