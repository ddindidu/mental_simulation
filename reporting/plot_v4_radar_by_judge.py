#!/usr/bin/env python3
"""
evaluation_v4.md — Per-Judge Radar Chart (z-score)

Reads the CSV produced by reporting/summarize_v4_metrics_csv.py and draws one
radar chart per judge (patient/judge model group), one polygon per doctor
model, over 5 headline metrics:

  Jaccard (Inference Quality), IAS (Information Acquisition Quality),
  Turn Count (Efficiency), Final Accuracy (Reliable Diagnosis),
  Diagnostic Reasoning Ability (Reliable Diagnosis)

Each axis is z-scored across the doctor models shown *within that judge's
panel*: z = (x - mean) / std. 0 = that panel's mean on the metric, +1/-1 = one
std above/below it — this puts axes of very different native scale (turn
count vs. a 0-1 rate) on one comparable chart. Turn Count is a lower-is-better
metric, so its z-score is sign-flipped before plotting — on every axis,
farther from center is always "better", not just "more standard deviations
from the mean in whichever direction the raw metric happens to point".

Every doctor model with at least one metric present is plotted. IAS and
Diagnostic Reasoning depend on the LLM-judge stage (evaluate_question.py /
score_diagnostic_reasoning.py), which may still be running for some
doctor/judge combos — a model missing one of those gets 0 filled in for that
axis's *raw* value before z-scoring (i.e. treated as "no signal yet", not
"z-score 0"), and the console notes which axes were filled per model. A
model with every metric missing is skipped entirely (nothing to plot).

Usage:
  python reporting/plot_v4_radar_by_judge.py [--csv PATH] [-o OUT_PREFIX]

  MS_RUN=run_batch_20260912 python reporting/plot_v4_radar_by_judge.py \\
      --csv saved/run_batch_20260912/analysis/v4_metrics_summary_plain.csv
"""
from __future__ import annotations

import argparse
import csv as csv_mod
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.paths import ANALYSIS_ROOT

# (axis label, CSV field)
# Jaccard uses the "rigid" (tier-priority) reference candidate set instead of
# the loose union of high|moderate|low_likely — see eval/evaluate_turns.py's
# rigid_truth_set and reporting/plot_v4_rigid_vs_loose.py.
METRICS = [
    ("Diff. Diag\n(Jaccard, rigid)", "jaccard_rigid"),
    ("Info. Acquisition\n(IAS)", "ias"),
    ("Efficiency\n(Turn Count, reversed)", "turn_count"),
    ("Diag. Decision\n(Final Acc.)", "final_accuracy_pct"),
    ("Diag. Decision\n(Evidence Sufficiency)", "diagnostic_reasoning_overall_score"),
]

# Fields where a lower raw value is better — their z-score is sign-flipped
# before plotting so every axis on the chart points "outward = better".
LOWER_IS_BETTER = {"turn_count"}

ALLOWED_DOCTORS = {
    "gpt-5.4",
    "gemini-3.8-flash",
    "claude-sonnet-5",
    "llama-3.3-70b-instruct",
    "qwen3-235b",
}

DOCTOR_NAME_CANONICAL = {
    "gpt-5.4": "GPT 5.4",
    "gemini-3.8-flash": "Gemini 3.8 Flash",
    "claude-sonnet-5": "Claude Sonnet 5",
    "llama-3.3-70b-instruct": "Llama 3.3 70B Inst.",
    "qwen3-235b": "Qwen3 235B",
}

# Colorblind-safe qualitative palette (Okabe-Ito), assigned per canonical
# (lower-cased) doctor name so the same model gets the same color in both
# judges' plots even if the two runs spelled its directory name differently.
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
           "#56B4E9", "#999999", "#000000", "#F0E442"]


def _to_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_rows(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8") as f:
        return list(csv_mod.DictReader(f))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv", default=None,
        help="Input CSV from summarize_v4_metrics_csv.py "
             "(default: analysis/<run>/v4_metrics_summary_plain.csv)",
    )
    parser.add_argument(
        "-o", "--out-prefix", default=None,
        help="Output PNG path prefix (default: analysis/<run>/v4_radar_)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv) if args.csv else ANALYSIS_ROOT / "v4_metrics_summary_plain.csv"
    out_prefix = Path(args.out_prefix) if args.out_prefix else ANALYSIS_ROOT / "v4_radar_"

    rows = load_rows(csv_path)
    if not rows:
        print(f"No rows in {csv_path}")
        return
    rows = [r for r in rows if r["doctor"].lower() in ALLOWED_DOCTORS]
    if not rows:
        print(f"No rows left after filtering to {sorted(ALLOWED_DOCTORS)}")
        return

    # Global color assignment so a model keeps its color across both judges.
    canonical_doctors = sorted({r["doctor"].lower() for r in rows})
    color_of = {d: PALETTE[i % len(PALETTE)] for i, d in enumerate(canonical_doctors)}

    judges = sorted({r["judge"] for r in rows})

    for judge in judges:
        judge_rows = [r for r in rows if r["judge"] == judge]

        complete, dropped = [], []
        for r in judge_rows:
            values = [_to_float(r[field]) for _, field in METRICS]
            if all(v is None for v in values):
                dropped.append(r["doctor"])
                continue
            missing_labels = [label for (label, _), v in zip(METRICS, values) if v is None]
            filled = [0.0 if v is None else v for v in values]
            complete.append((r["doctor"], filled, missing_labels))

        if dropped:
            print(f"[{judge}] no data at all, skipped: {', '.join(dropped)}")
        for model, _vals, missing_labels in complete:
            if missing_labels:
                axis_names = ", ".join(l.split("\n")[0] for l in missing_labels)
                print(f"[{judge}] {model}: filled 0 for missing {axis_names}")

        if not complete:
            print(f"[{judge}] no models with any data — skipping radar chart.")
            continue
        if len(complete) == 1:
            print(f"[{judge}] only 1 model — z-scores will be 0 on every "
                  f"axis (single point, no spread to compare against).")

        models = [m for m, _v, _ml in complete]
        raw = np.array([v for _m, v, _ml in complete]).T  # metrics x models

        mean = raw.mean(axis=1, keepdims=True)
        std = raw.std(axis=1, keepdims=True)
        std[std == 0] = 1.0
        z = (raw - mean) / std

        for axis_i, (_label, field) in enumerate(METRICS):
            if field in LOWER_IS_BETTER:
                z[axis_i] *= -1

        n_axes = len(METRICS)
        angles = np.linspace(0, 2 * np.pi, n_axes, endpoint=False).tolist()
        angles += angles[:1]

        zlim = max(0.5, np.ceil(np.abs(z).max() * 2) / 2)

        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([label for label, _field in METRICS], fontsize=12)
        ax.set_ylim(-zlim, zlim)
        yticks = np.linspace(-zlim, zlim, 5)
        ax.set_yticks(yticks)
        ax.set_yticklabels([f"{t:+.1f}σ" for t in yticks], fontsize=8, color="gray")
        ax.grid(color="lightgray", linewidth=0.7)
        ax.spines["polar"].set_color("lightgray")

        ax.plot(angles, [0] * len(angles), color="dimgray", linewidth=1.2,
                linestyle="--", zorder=2)

        for j, model in enumerate(models):
            vals = z[:, j].tolist()
            vals += vals[:1]
            color = color_of[model.lower()]
            ax.plot(angles, vals, color=color, linewidth=2, label=DOCTOR_NAME_CANONICAL.get(model, model))
            ax.fill(angles, vals, color=color, alpha=0.08)
            ax.scatter(angles[:-1], vals[:-1], color=color, s=22, zorder=3)

        any_filled = any(missing_labels for _m, _v, missing_labels in complete)
        base_note = "z-score per metric across models shown; 0 = group mean, dashed ring; Turn Count sign-flipped so outward = better"
        if len(complete) == 1:
            subtitle = "only 1 model has data — z-scores are trivially 0, shape not comparative"
        elif any_filled:
            subtitle = (base_note + " — models missing IAS/Diagnostic Reasoning "
                        "(LLM-judge pending) plotted with 0")
        else:
            subtitle = base_note
        # ax.set_title(
        #     f"Diagnostic Profile (judge: {judge})\n({subtitle})",
        #     fontsize=11.5, pad=30,
        # )
        ax.legend(loc="upper right", fontsize=12, frameon=False, bbox_to_anchor=(1.2, 1.1), )

        fig.tight_layout()
        out_path = Path(f"{out_prefix}{judge}.png")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.4)
        plt.close(fig)
        print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
