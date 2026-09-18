#!/usr/bin/env python3
"""
Turn Count: Pinned-at-1 vs. Real-Differential Episodes — by Judge Model

Companion to plot_overcommitment_by_judge.py --source predicted, which
excludes episodes where the doctor's `predicted` list already has 0-1
candidates on turn 1 ("pinned@1" — a fixed single guess repeated for most
of the conversation, not narrowing behavior; see that script's docstring).
This chart answers the natural follow-up: how long do those excluded
episodes actually run? A model that pins early but then talks for just as
many turns anyway (as opposed to pinning and quickly wrapping up) is
spending most of a long conversation not maintaining any differential at
all.

Grouped bar chart, one panel per judge, two bars per doctor model:
  pinned@1 episodes            solid bar, mean turn_count
                                (|predicted| on turn 1 <= 1)
  real-differential episodes   stacked bar, same split as
                                plot_overcommitment_by_judge.py:
                                turn to 1st confident + overcommitment
                                (mean turn_count is their sum)

Reads analysis/<patient>/<judge>/<doctor>/turn_eval.json directly (same
discovery as plot_overcommitment_by_judge.py's --source predicted).

Usage:
  python reporting/plot_pinned_at_1_turn_counts.py [--style plain] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_pinned_at_1_turn_counts.py
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
    EXCLUDE_DOCTORS,
    MODEL_ORDER,
    _order_rank,
    discover_turn_eval_combos,
    predicted_sizes_per_episode,
    predicted_t1c_overcommit,
)

COLOR_PINNED = "#D55E00"
COLOR_REAL = "#0072B2"  # legend swatch for the (stacked) real-differential bar


def turn_counts_by_group(style: str | None) -> dict[str, list[tuple[str, dict]]]:
    """panels[judge] = list of (doctor, stats). stats:
      pinned_mean/pinned_n           mean turn_count over pinned@1 episodes
      real_t1c_mean/real_oc_mean     mean turn-to-1st-confident / overcommitment
                                      over real-differential episodes (their
                                      sum is that group's mean turn_count)
      real_n
    """
    combos = discover_turn_eval_combos()
    by_judge: dict[str, list[tuple[str, dict]]] = {}
    for patient, judge, doctor, path in combos:
        if doctor.lower() in EXCLUDE_DOCTORS:
            continue
        episodes = predicted_sizes_per_episode(path, style)
        if not episodes:
            continue
        pinned_lens = [len(sizes) for sizes in episodes if sizes and sizes[0] <= 1]
        real_episodes = [sizes for sizes in episodes if sizes and sizes[0] > 1]
        if not pinned_lens and not real_episodes:
            continue
        real_t1cs, real_ocs = [], []
        for sizes in real_episodes:
            t1c, oc = predicted_t1c_overcommit(sizes)
            real_t1cs.append(t1c)
            real_ocs.append(oc)
        stats = {
            "pinned_mean": float(np.mean(pinned_lens)) if pinned_lens else None,
            "pinned_n": len(pinned_lens),
            "real_t1c_mean": float(np.mean(real_t1cs)) if real_t1cs else None,
            "real_oc_mean": float(np.mean(real_ocs)) if real_ocs else None,
            "real_n": len(real_episodes),
        }
        by_judge.setdefault(judge, []).append((doctor, stats))
    return by_judge


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default="plain",
                         help="Only include episodes whose log filename ends in "
                              "_<style> (default: plain). Pass '' for all styles.")
    parser.add_argument("-o", "--out", default=None,
                         help="Output PNG path (default: analysis/<run>/pinned_at_1_turn_counts.png)")
    args = parser.parse_args()
    style = args.style or None

    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "pinned_at_1_turn_counts.png"

    by_judge = turn_counts_by_group(style)
    if not by_judge:
        print(f"No turn_eval.json data found under {ANALYSIS_ROOT}")
        return

    judges = sorted(by_judge)
    fig, axes = plt.subplots(1, len(judges), figsize=(7.5 * len(judges), 6), sharey=True)
    if len(judges) == 1:
        axes = [axes]

    all_means = [
        (s["pinned_mean"] or 0)
        for rows in by_judge.values() for _d, s in rows
    ] + [
        (s["real_t1c_mean"] or 0) + (s["real_oc_mean"] or 0)
        for rows in by_judge.values() for _d, s in rows
    ]
    ymax = max(all_means) * 1.25 if all_means else 20

    for ax, judge in zip(axes, judges):
        rows = sorted(by_judge[judge], key=lambda x: -_order_rank(x[0]))
        doctors = [d for d, _s in rows]
        xs = np.arange(len(doctors))
        width = 0.36

        pinned_vals = [s["pinned_mean"] or 0 for _d, s in rows]
        real_t1c_vals = [s["real_t1c_mean"] or 0 for _d, s in rows]
        real_oc_vals = [s["real_oc_mean"] or 0 for _d, s in rows]
        pinned_ns = [s["pinned_n"] for _d, s in rows]
        real_ns = [s["real_n"] for _d, s in rows]

        ax.bar(xs - width / 2, pinned_vals, width, color=COLOR_PINNED,
               label="pinned@1 episodes", zorder=3)
        ax.bar(xs + width / 2, real_t1c_vals, width, color=COLOR_CONFIDENT,
               label="real-differential: turn to 1st confident", zorder=3)
        ax.bar(xs + width / 2, real_oc_vals, width, bottom=real_t1c_vals,
               color=COLOR_OVERCOMMIT, label="real-differential: overcommitment", zorder=3)

        for xi, v, n in zip(xs - width / 2, pinned_vals, pinned_ns):
            if v > 0:
                ax.text(xi, v + ymax * 0.015, f"{v:.1f}\n(n={n})", ha="center",
                        va="bottom", fontsize=7.5, color=COLOR_PINNED)
        for xi, t1c, oc, n in zip(xs + width / 2, real_t1c_vals, real_oc_vals, real_ns):
            total = t1c + oc
            if total > 0:
                ax.text(xi, total + ymax * 0.015, f"{total:.1f}\n(n={n})", ha="center",
                        va="bottom", fontsize=7.5, color=COLOR_REAL)

        ax.set_xticks(xs)
        ax.set_xticklabels(doctors, rotation=30, ha="right", fontsize=9)
        ax.set_ylim(0, ymax)
        ax.set_title(f"Judge: {judge}", fontsize=12.5, fontweight="bold", pad=10)
        ax.grid(axis="y", color="#E4EBF5", linewidth=0.8, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)

    axes[0].set_ylabel("Mean turn_count", fontsize=10.5)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, fontsize=9.5,
               frameon=False, bbox_to_anchor=(0.5, 1.04))

    style_note = f"style={style}" if style else "all styles"
    fig.suptitle(
        "Episode Length: Pinned-at-1 vs. Real-Differential Episodes — by judge model\n"
        f"(pinned@1 = |predicted| on turn 1 is 0 or 1; {style_note}; {RUN_ROOT.name})",
        fontsize=13, fontweight="bold", y=1.14,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.90])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
