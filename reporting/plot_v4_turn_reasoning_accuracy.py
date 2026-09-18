#!/usr/bin/env python3
"""
evaluation_v4.md — Turn Count, Diagnostic Reasoning Ability, and Final Accuracy (combined)

Three metrics, one figure. A 2D scatter can only give two axes cleanly, so
the third (final accuracy) rides as point color on a sequential ramp rather
than as a third spatial axis — this is the same "two axes + color = magnitude"
pattern used by plot_v4_ias_components.py for IAS. One point per (judge,
doctor) combo from the CSV produced by reporting/summarize_v4_metrics_csv.py:

  x = turn_count                             (§3, mean patient turns per episode)
  y = diagnostic_reasoning_overall_score     (§4, evidence-gathering thoroughness)
  color = final_accuracy_pct                 (§4, whether the stated diagnosis
                                              was actually correct)

Reading it: up-right + dark = thorough AND correct (the target quadrant);
down-right + dark = many turns, thin evidence, but still landed on the right
answer (lucky/pattern-matched); up-left + light = efficient and thorough but
still wrong (good process, bad conclusion). Marker shape = judge; each point
is direct-labeled with its doctor model name. Combos missing any of the three
fields are skipped (reported on stderr).

Usage:
  python reporting/plot_v4_turn_reasoning_accuracy.py [--csv PATH] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_v4_turn_reasoning_accuracy.py \\
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

MARKERS = ["o", "^", "s", "D", "P", "X"]

SELECTED_DOCTORS = {
    "gpt-5.4",
    "gemini-3.8-flash",
    "claude-sonnet-5",
    "llama-3.3-70b-instruct",
    "qwen3-235b",
}


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

    judges = sorted({r["judge"] for r in rows})
    marker_of = {j: MARKERS[i % len(MARKERS)] for i, j in enumerate(judges)}

    points, skipped = [], []
    for r in rows:
        x = _to_float(r["turn_count"])
        y = _to_float(r["diagnostic_reasoning_overall_score"])
        c = _to_float(r["final_accuracy_pct"])
        if x is None or y is None or c is None:
            skipped.append(f"{r['judge']}/{r['doctor']}")
            continue
        points.append((r["judge"], r["doctor"], x, y, c))

    if skipped:
        print(f"Skipped (missing turn_count / diagnostic reasoning / final accuracy): {', '.join(skipped)}", file=sys.stderr)
    if not points:
        print("No combo has turn_count, diagnostic_reasoning_overall_score, and final_accuracy_pct all present.")
        return

    xs = [p[2] for p in points]
    ys = [p[3] for p in points]
    cs = [p[4] for p in points]

    fig, ax = plt.subplots(figsize=(9, 7.2))
    x_right_cutoff = min(xs) + 0.8 * (max(xs) - min(xs))
    sc = None
    for judge, doctor, x, y, c in points:
        sc = ax.scatter(x, y, c=[c], cmap="Blues", vmin=min(cs), vmax=max(cs),
                         s=180, marker=marker_of[judge], edgecolors="#0d366b",
                         linewidths=0.8, zorder=3)
        # labels on the rightmost points would otherwise run under the colorbar panel
        if x > x_right_cutoff:
            ax.annotate(doctor, (x, y), textcoords="offset points", xytext=(-7, 6),
                        ha="right", fontsize=8.5, color="#3a3a38")
        else:
            ax.annotate(doctor, (x, y), textcoords="offset points", xytext=(7, 6),
                        fontsize=8.5, color="#3a3a38")

    x_pad = (max(xs) - min(xs)) * 0.20 or 2
    y_pad = (max(ys) - min(ys)) * 0.12 or 0.02
    ax.set_xlim(min(xs) - x_pad, max(xs) + x_pad)
    ax.set_ylim(min(ys) - y_pad, max(ys) + y_pad)

    ax.set_xlabel("Turn Count — §3, mean patient turns per episode", fontsize=10, color="#52514e")
    ax.set_ylabel("Diagnostic Reasoning Ability (overall_score) — §4, higher = better", fontsize=10, color="#52514e")
    # ax.set_title(
    #     "evaluation_v4.md — Turn Count x Diagnostic Reasoning x Final Accuracy\n"
    #     "(point color = final accuracy; marker shape = judge)",
    #     fontsize=12, fontweight="bold",
    # )
    ax.grid(color="#e1e0d9", linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Final Accuracy (%)", fontsize=9.5, color="#52514e")

    judge_handles = [
        plt.Line2D([0], [0], marker=marker_of[j], color="w", markerfacecolor="#6da7ec",
                   markeredgecolor="#0d366b", markersize=10, label=j)
        for j in judges
    ]
    ax.legend(handles=judge_handles, title="Judge", loc="upper left", fontsize=9, frameon=False)

    fig.tight_layout()
    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "v4_turn_reasoning_accuracy.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
