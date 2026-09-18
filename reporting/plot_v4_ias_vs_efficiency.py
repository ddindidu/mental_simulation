#!/usr/bin/env python3
"""
evaluation_v4.md — IAS vs. Efficiency (Turn Count, Overcommitment Turns)

Two side-by-side scatters, one point per (judge, doctor) combo from the CSV
produced by reporting/summarize_v4_metrics_csv.py:

  Left:  x = turn_count            (§3, mean patient turns per episode)
         y = ias                    (§2, Information Acquisition Score)
  Right: x = overcommitment_turns  (§3, mean turns spent after the candidate
                                    set first collapsed to size 1)
         y = ias                    (§2)

Each panel gets its own least-squares trend line + Pearson r. Point color =
doctor model (same canonical palette as the other v4 scripts, so a model
keeps its color everywhere); marker shape = judge. Combos missing either
field in a panel are skipped from that panel (reported on stderr).

Usage:
  python reporting/plot_v4_ias_vs_efficiency.py [--csv PATH] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_v4_ias_vs_efficiency.py \\
      --csv saved/run_batch_20260912/analysis/v4_metrics_summary_plain.csv
"""
from __future__ import annotations

import argparse
import csv as csv_mod
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

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

PANELS = [
    ("turn_count", "Turn Count — §3, mean patient turns per episode"),
    ("overcommitment_turns", "Overcommitment Turns — §3, turns after candidates first hit size 1"),
]


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

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    for ax, (x_field, x_label) in zip(axes, PANELS):
        points, skipped = [], []
        for r in rows:
            x = _to_float(r[x_field])
            y = _to_float(r["ias"])
            if x is None or y is None:
                skipped.append(f"{r['judge']}/{r['doctor']}")
                continue
            points.append((r["judge"], r["doctor"], x, y))

        if skipped:
            print(f"[{x_field}] Skipped (missing {x_field} or ias): {', '.join(skipped)}", file=sys.stderr)
        if not points:
            print(f"[{x_field}] No combo has both {x_field} and ias.")
            continue

        seen_models: set[str] = set()
        for judge, doctor, x, y in points:
            color = color_of[doctor.lower()]
            label = doctor if doctor.lower() not in seen_models else None
            seen_models.add(doctor.lower())
            ax.scatter(x, y, color=color, marker=marker_of[judge], s=170,
                       edgecolors="white", linewidths=0.8, zorder=3, label=label)
            ax.annotate(doctor, (x, y), textcoords="offset points", xytext=(7, 6),
                        fontsize=8.5, color="#3a3a38")

        xs = np.array([p[2] for p in points])
        ys = np.array([p[3] for p in points])
        x_pad = (xs.max() - xs.min()) * 0.15 or 1
        y_pad = (ys.max() - ys.min()) * 0.15 or 0.02
        ax.set_xlim(xs.min() - x_pad, xs.max() + x_pad)
        ax.set_ylim(ys.min() - y_pad, ys.max() + y_pad)

        if len(points) >= 2:
            slope, intercept = np.polyfit(xs, ys, 1)
            r = np.corrcoef(xs, ys)[0, 1]
            xline = np.array(ax.get_xlim())
            ax.plot(xline, slope * xline + intercept, color="#52514e",
                    linewidth=1.6, linestyle="--", zorder=2, alpha=0.75)
            r_note = f"r = {r:+.2f}  (n={len(points)})"
        else:
            r_note = f"n={len(points)} — not enough points for a trend line"

        ax.set_xlabel(x_label, fontsize=10, color="#52514e")
        ax.set_ylabel("IAS — §2, Information Acquisition Score, higher = better", fontsize=10, color="#52514e")
        ax.text(0.02, 0.98, r_note, transform=ax.transAxes, fontsize=10,
                color="#52514e", va="top", ha="left")
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
    leg1 = fig.legend(handles=model_handles, title="Doctor model", loc="upper left",
                       bbox_to_anchor=(1.0, 0.98), fontsize=8.5, frameon=False)
    fig.add_artist(leg1)
    fig.legend(handles=judge_handles, title="Judge", loc="lower left",
               bbox_to_anchor=(1.0, 0.02), fontsize=8.5, frameon=False)

    fig.tight_layout()
    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "v4_ias_vs_efficiency.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
