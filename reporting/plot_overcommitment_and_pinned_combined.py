#!/usr/bin/env python3
"""
Confidence Timing + Pinned-at-1 Episode Length — Combined, by Judge Model

Stacks plot_overcommitment_by_judge.py (top row) and
plot_pinned_at_1_turn_counts.py (bottom row) into one figure, one column per
judge, sharing the same doctor order top-to-bottom/left-to-right so the two
views of the same models line up:

  Top:    Turn to 1st confident + Overcommitment (predicted |P_t|=1 by
          default) — excludes "pinned@1" episodes (|predicted| already 0-1
          on turn 1); each bar's label reports what fraction that was.
  Bottom: Mean turn_count for those excluded pinned@1 episodes vs. the
          real-differential episodes the top row is computed from — answers
          "do pinned@1 episodes end quickly, or run just as long?" (they run
          just as long, for the models checked so far — see the two
          scripts' docstrings for the full context/history of this metric).

Usage:
  python reporting/plot_overcommitment_and_pinned_combined.py
      [--source reference|predicted] [--csv PATH] [--style plain] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_overcommitment_and_pinned_combined.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from utils.paths import ANALYSIS_ROOT, RUN_ROOT
from reporting.plot_overcommitment_by_judge import (
    COLOR_CONFIDENT,
    COLOR_OVERCOMMIT,
    panels_from_predicted,
    panels_from_reference,
)
from reporting.plot_pinned_at_1_turn_counts import (
    COLOR_PINNED,
    COLOR_REAL,
    turn_counts_by_group,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", choices=["reference", "predicted"], default="predicted",
        help="Top-row data source for the confidence-timing bars (default: predicted, "
             "since the pinned@1 concept below only applies to that source)",
    )
    parser.add_argument(
        "--csv", default=None,
        help="Input CSV for --source reference (default: analysis/<run>/v4_metrics_summary_plain.csv)",
    )
    parser.add_argument(
        "--style", default="plain",
        help="Only include episodes whose log filename ends in _<style> "
             "(default: plain). Pass '' for all styles.",
    )
    parser.add_argument(
        "-o", "--out", default=None,
        help="Output PNG path (default: analysis/<run>/overcommitment_and_pinned_combined.png)",
    )
    args = parser.parse_args()
    style = args.style or None

    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "overcommitment_and_pinned_combined.png"

    pinned_rate: dict[tuple[str, str], float] = {}
    if args.source == "predicted":
        top_panels, pinned_rate = panels_from_predicted(style)
        confident_label = "Turn to 1st confident (predicted |P_t|=1)"
        overcommit_label = "Overcommitment (predicted-confidence-based)"
    else:
        csv_path = Path(args.csv) if args.csv else ANALYSIS_ROOT / "v4_metrics_summary_plain.csv"
        top_panels = panels_from_reference(csv_path)
        confident_label = "Turn to 1st confident"
        overcommit_label = "Overcommitment (confidence-based)"

    if not top_panels:
        print("No judge panel has complete confidence-timing data.")
        return

    turn_count_by_judge = turn_counts_by_group(style)

    judges = [j for j, _rows in top_panels]
    n_judges = len(judges)

    top_xmax = max(t1c + oc for _j, rows in top_panels for _d, t1c, oc in rows) * 1.15
    bottom_all_means = [
        v for j in judges for _d, s in turn_count_by_judge.get(j, [])
        for v in (s["pinned_mean"], s["real_mean"]) if v is not None
    ]
    bottom_ymax = max(bottom_all_means) * 1.3 if bottom_all_means else 20

    n_rows_top = max(len(rows) for _j, rows in top_panels)
    fig = plt.figure(figsize=(9.5 * n_judges, 0.6 * n_rows_top + 7.5))
    gs = fig.add_gridspec(2, n_judges, height_ratios=[0.6 * n_rows_top + 1.5, 5.5], hspace=0.55)

    for col, (judge, judge_rows) in enumerate(top_panels):
        ax = fig.add_subplot(gs[0, col])
        doctors = [d for d, _t1c, _oc in judge_rows]
        t1cs = [t1c for _d, t1c, _oc in judge_rows]
        ocs = [oc for _d, _t1c, oc in judge_rows]
        ys = np.arange(len(doctors))

        ax.barh(ys, t1cs, color=COLOR_CONFIDENT, label=confident_label, zorder=3)
        ax.barh(ys, ocs, left=t1cs, color=COLOR_OVERCOMMIT, label=overcommit_label, zorder=3)

        for yi, (t1c, oc) in enumerate(zip(t1cs, ocs)):
            ax.text(t1c / 2, yi, f"{t1c:.1f}", ha="center", va="center", fontsize=9.5,
                     color="white", fontweight="bold")
            ax.text(t1c + oc + top_xmax * 0.01, yi, f"{t1c + oc:.1f}", ha="left",
                     va="center", fontsize=9.5, color="#1C2333")
            ax.text(t1c + oc / 2, yi + 0.32, f"+{oc:.1f}", ha="center", va="bottom",
                     fontsize=8, color="#4B7FC2")

        ax.set_yticks(ys)
        if pinned_rate:
            ytick_labels = []
            for d in doctors:
                rate = pinned_rate.get((judge, d))
                note = f"  [excl. {rate*100:.0f}% pinned@1]" if rate is not None and rate > 0 else ""
                ytick_labels.append(f"{d}{note}")
            ax.set_yticklabels(ytick_labels, fontsize=8.5)
        else:
            ax.set_yticklabels(doctors, fontsize=9.5)
        ax.set_xlim(0, top_xmax)
        ax.set_xlabel("Turns", fontsize=9)
        ax.set_title(f"Judge: {judge}", fontsize=12.5, fontweight="bold", pad=10)
        ax.grid(axis="x", color="#E4EBF5", linewidth=0.8, zorder=0)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.legend(loc="upper right", fontsize=7.5, frameon=True,
                  framealpha=0.9, edgecolor="none")

        # Bottom row uses the SAME doctor order as the top row for this
        # judge, so the two panels line up model-for-model.
        ax2 = fig.add_subplot(gs[1, col])
        rows_bottom = dict(turn_count_by_judge.get(judge, []))
        xs = np.arange(len(doctors))
        width = 0.36
        pinned_vals = [rows_bottom.get(d, {}).get("pinned_mean") or 0 for d in doctors]
        real_vals = [rows_bottom.get(d, {}).get("real_mean") or 0 for d in doctors]
        pinned_ns = [rows_bottom.get(d, {}).get("pinned_n", 0) for d in doctors]
        real_ns = [rows_bottom.get(d, {}).get("real_n", 0) for d in doctors]

        ax2.bar(xs - width / 2, pinned_vals, width, color=COLOR_PINNED,
                label="pinned@1 episodes", zorder=3)
        ax2.bar(xs + width / 2, real_vals, width, color=COLOR_REAL,
                label="real-differential episodes", zorder=3)

        for xi, v, n in zip(xs - width / 2, pinned_vals, pinned_ns):
            if v > 0:
                ax2.text(xi, v + bottom_ymax * 0.015, f"{v:.1f}\n(n={n})", ha="center",
                          va="bottom", fontsize=7, color=COLOR_PINNED)
        for xi, v, n in zip(xs + width / 2, real_vals, real_ns):
            if v > 0:
                ax2.text(xi, v + bottom_ymax * 0.015, f"{v:.1f}\n(n={n})", ha="center",
                          va="bottom", fontsize=7, color=COLOR_REAL)

        ax2.set_xticks(xs)
        ax2.set_xticklabels(doctors, rotation=30, ha="right", fontsize=8.5)
        ax2.set_ylim(0, bottom_ymax)
        ax2.set_title(f"Judge: {judge} — episode length", fontsize=11, fontweight="bold", pad=8)
        ax2.grid(axis="y", color="#E4EBF5", linewidth=0.8, zorder=0)
        ax2.spines[["top", "right"]].set_visible(False)
        ax2.legend(loc="upper right", fontsize=7.5, frameon=True,
                   framealpha=0.9, edgecolor="none")
        if col == 0:
            ax2.set_ylabel("Mean turn_count", fontsize=9.5)

    source_note = ("doctor's own predicted differential" if args.source == "predicted"
                    else "judge/KG reference candidate_set")
    style_note = f"style={style}" if style else "all styles"
    fig.suptitle(
        "Confidence Timing (top) + Pinned-at-1 Episode Length (bottom) — by judge model\n"
        f"(top: \"confident\" = {source_note}; bottom: does a pinned@1 episode end early, or run just as long?; "
        f"{style_note}; {RUN_ROOT.name})",
        fontsize=13.5, fontweight="bold", y=1.0,
    )

    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
