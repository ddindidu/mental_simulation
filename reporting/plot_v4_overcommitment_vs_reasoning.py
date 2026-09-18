#!/usr/bin/env python3
"""
evaluation_v4.md — Overcommitment vs. Diagnostic Reasoning Ability

Scatters one point per (judge, doctor) combo from the CSV produced by
reporting/summarize_v4_metrics_csv.py:

  x = overcommitment_conf                    (§3, mean turns spent continuing
                                              *after* the candidate set first
                                              collapsed to the doctor's own
                                              final diagnosis — the true
                                              complement of turn_to_1st_confident)
  y = diagnostic_reasoning_overall_score     (§4, whether enough evidence was
                                              actually collected during the
                                              interview to satisfy the GT
                                              disease's required criteria)

Tests whether the extra turns spent "confirming" a diagnosis after the
candidate set has already narrowed to it actually buy better evidence
coverage (high x, high y — the extra turns are doing real diagnostic work)
or are just redundant re-asking (high x, low y — overcommitment without
payoff). Point color = doctor model (same canonical palette as the other v4
scripts, so a model keeps its color everywhere); marker shape = judge.
Combos missing either field are skipped and reported on stderr rather than
silently dropped.

Usage:
  python reporting/plot_v4_overcommitment_vs_reasoning.py [--csv PATH] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_v4_overcommitment_vs_reasoning.py \\
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

X_FIELD = "overcommitment_conf"
X_LABEL = "Overcommitment (confidence-based) — §3, mean extra turns after 1st confident narrowing"
TITLE = "evaluation_v4.md — Overcommitment vs. Diagnostic Reasoning Ability"


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
        x = _to_float(r[X_FIELD])
        y = _to_float(r["diagnostic_reasoning_overall_score"])
        if x is None or y is None:
            skipped.append(f"{r['judge']}/{r['doctor']}")
            continue
        points.append((r["judge"], r["doctor"], x, y))

    if skipped:
        print(f"Skipped (missing {X_FIELD} or diagnostic reasoning score): {', '.join(skipped)}", file=sys.stderr)
    if not points:
        print(f"No combo has both {X_FIELD} and diagnostic_reasoning_overall_score.")
        return

    fig, ax = plt.subplots(figsize=(8.5, 7))
    seen_models: set[str] = set()
    for judge, doctor, x, y in points:
        color = color_of[doctor.lower()]
        label = doctor if doctor.lower() not in seen_models else None
        seen_models.add(doctor.lower())
        ax.scatter(x, y, color=color, marker=marker_of[judge], s=170,
                   edgecolors="white", linewidths=0.8, zorder=3, label=label)
        ax.annotate(doctor, (x, y), textcoords="offset points", xytext=(7, 6),
                    fontsize=8.5, color="#3a3a38")

    xs = [p[2] for p in points]
    ys = [p[3] for p in points]
    x_pad = (max(xs) - min(xs)) * 0.15 or 0.2
    y_pad = (max(ys) - min(ys)) * 0.15 or 0.02
    ax.set_xlim(min(xs) - x_pad, max(xs) + x_pad)
    ax.set_ylim(min(ys) - y_pad, max(ys) + y_pad)

    ax.set_xlabel(X_LABEL, fontsize=10, color="#52514e")
    ax.set_ylabel("Diagnostic Reasoning Ability (overall_score) — §4, higher = better", fontsize=10, color="#52514e")
    # ax.set_title(
    #     f"{TITLE}\n(color = doctor model; marker shape = judge)",
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
    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "v4_overcommitment_vs_reasoning.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
