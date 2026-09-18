#!/usr/bin/env python3
"""
evaluation_v4.md — Turn Count vs. Diagnostic Reasoning Ability, Open vs. Closed (combined)

Single-panel version of plot_v4_turncount_vs_reasoning_by_openness.py: all
(judge, doctor) points from the CSV produced by reporting/summarize_v4_metrics_csv.py
on one axes, colored by model openness (OPEN_MODELS below) rather than by
individual model, with one least-squares trend line per group overlaid on
the same plot — so the two within-group turn-count -> reasoning-ability
relationships are visible together instead of split across two panels.

  x = turn_count                             (§3, mean patient turns per episode)
  y = diagnostic_reasoning_overall_score     (§4)

Point color = open-weight vs. closed/proprietary (2-way categorical); marker
shape = judge; each point is direct-labeled with its doctor model name since
color no longer carries model identity here. Combos missing either field are
skipped (reported on stderr).

Usage:
  python reporting/plot_v4_turncount_vs_reasoning_combined.py [--csv PATH] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_v4_turncount_vs_reasoning_combined.py \\
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

# Canonical (lower-cased) doctor names that are open-weight; everything else
# in the CSV is treated as closed/proprietary.
OPEN_MODELS = {"qwen3-235b", "llama-3.3-70b-instruct"}

# Categorical slots 1 (blue) and 2 (orange) from the shared v4 palette.
GROUP_COLOR = {"Open-weight": "#0072B2", "Closed / proprietary": "#D55E00"}
MARKERS = ["o", "^", "s", "D", "P", "X"]


def _to_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def group_of(doctor: str) -> str:
    return "Open-weight" if doctor.lower() in OPEN_MODELS else "Closed / proprietary"


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

    judges = sorted({r["judge"] for r in rows})
    marker_of = {j: MARKERS[i % len(MARKERS)] for i, j in enumerate(judges)}

    points, skipped = [], []
    for r in rows:
        x = _to_float(r["turn_count"])
        y = _to_float(r["diagnostic_reasoning_overall_score"])
        if x is None or y is None:
            skipped.append(f"{r['judge']}/{r['doctor']}")
            continue
        points.append((r["judge"], r["doctor"], x, y))

    if skipped:
        print(f"Skipped (missing turn_count or diagnostic reasoning score): {', '.join(skipped)}", file=sys.stderr)
    if not points:
        print("No combo has both turn_count and diagnostic_reasoning_overall_score.")
        return

    fig, ax = plt.subplots(figsize=(10.5, 7.2))

    xs_all = [p[2] for p in points]
    x_pad = (max(xs_all) - min(xs_all)) * 0.1 or 2
    xline = np.array([min(xs_all) - x_pad, max(xs_all) + x_pad])

    seen_groups: set[str] = set()
    for group in ["Open-weight", "Closed / proprietary"]:
        group_points = [p for p in points if group_of(p[1]) == group]
        for judge, doctor, x, y in group_points:
            label = group if group not in seen_groups else None
            seen_groups.add(group)
            ax.scatter(x, y, color=GROUP_COLOR[group], marker=marker_of[judge], s=170,
                       edgecolors="white", linewidths=0.8, zorder=3, label=label)
            ax.annotate(doctor, (x, y), textcoords="offset points", xytext=(7, 6),
                        fontsize=8.5, color="#3a3a38")

        if len(group_points) >= 2:
            xs = np.array([p[2] for p in group_points])
            ys = np.array([p[3] for p in group_points])
            slope, intercept = np.polyfit(xs, ys, 1)
            r = np.corrcoef(xs, ys)[0, 1]
            short = "Open" if group == "Open-weight" else "Closed"
            ax.plot(xline, slope * xline + intercept, color=GROUP_COLOR[group],
                    linewidth=2, linestyle="--", zorder=2, alpha=0.8,
                    label=f"{short} fit: r={r:+.2f}")

    ax.set_xlim(xline[0], xline[1])
    ys_all = [p[3] for p in points]
    y_pad = (max(ys_all) - min(ys_all)) * 0.12 or 0.02
    ax.set_ylim(min(ys_all) - y_pad, max(ys_all) + y_pad)

    ax.set_xlabel("Turn Count — §3, mean patient turns per episode", fontsize=10, color="#52514e")
    ax.set_ylabel("Diagnostic Reasoning Ability (overall_score) — §4, higher = better", fontsize=10, color="#52514e")
    # ax.set_title(
    #     "evaluation_v4.md — Turn Count vs. Diagnostic Reasoning Ability\n"
    #     "(color = open-weight vs. closed/proprietary; marker shape = judge; dashed = within-group fit)",
    #     fontsize=12, fontweight="bold",
    # )
    ax.grid(color="#e1e0d9", linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    judge_handles = [
        plt.Line2D([0], [0], marker=marker_of[j], color="w", markerfacecolor="#999999",
                   markeredgecolor="white", markersize=9, label=j)
        for j in judges
    ]
    leg1 = ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=9, frameon=False,
                      title="Group / fit")
    ax.add_artist(leg1)
    ax.legend(handles=judge_handles, title="Judge", loc="lower left",
              bbox_to_anchor=(1.02, 0.0), fontsize=9, frameon=False)

    fig.tight_layout()
    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "v4_turncount_vs_reasoning_combined.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
