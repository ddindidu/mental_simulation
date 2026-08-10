#!/usr/bin/env python3
"""
Radar chart comparing doctor models across headline metrics from the main
(non-outcome-stratified) evaluation — one polygon per model, one axis per
metric, spanning inference / efficiency / question / diagnostic-reasoning.

Sources (analysis/<judge>/<judge>/comparison/):
  inference_eval_comparison.json
  efficiency_eval_comparison.json
  question_eval_comparison.json
  diagnostic_reasoning_comparison.json

Each axis uses a fixed, hand-set [lo, hi] range (not min-max over the
observed models) so absolute distances are comparable across re-runs and
axis position reflects the metric's real scale, not just this batch's
spread. Values are clipped into range before plotting.

Usage:
  python plot_main_eval_radar.py [--judge JUDGE]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_LABELS = {
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite",
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gpt-5.4": "GPT-5.4",
    "gpt-5.4-mini-2026-03-17": "GPT-5.4 Mini",
    "llama-3.3-70b-instruct": "Llama 3.3 70B",
    "qwen3-235b-a22b-2507": "Qwen3-235B",
}

# Colorblind-safe qualitative palette (Okabe-Ito derived), one per model.
MODEL_COLORS = {
    "gemini-3.1-flash-lite": "#0072B2",
    "gemini-3.5-flash": "#D55E00",
    "gpt-5.4": "#009E73",
    "gpt-5.4-mini-2026-03-17": "#CC79A7",
    "llama-3.3-70b-instruct": "#E69F00",
    "qwen3-235b-a22b-2507": "#56B4E9",
}

# (label, source table, field, lo, hi) — lo/hi are fixed axis bounds, not
# derived from the observed data.
AXES = [
    # ("Accuracy\n(Inference)", "inference", "accuracy", 0, 0.25),
    # ("Jaccard\n(Inference)", "inference", "jaccard", 0, 0.5),
    ("Precision\n(Inference)", "inference", "precision", 0.7, 0.9),
    ("Recall\n(Inference)", "inference", "recall", 0.4, 0.6),
    ("Cond. Composite Score\n(Question)", "question", "llm_judge_conditional_mean_composite", 0, 0.6),
    ("Cond. Information Gain\n(Question)", "question", "llm_judge_conditional_mean_ig", 0, 0.1),
    ("Turn Count\n(Efficiency)", "efficiency", "turn_count", 0, 10),
    ("CSSR\n(Efficiency)", "efficiency", "cssr", 0, 0.3),
    ("Final Accuracy", "efficiency", "final_accuracy", 0, 1),
    ("Diagnostic Reasoning Score", "reasoning", "overall_score", 0, 0.8),
]


def _load(path: Path) -> dict[str, dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {r["model"]: r for r in rows}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--judge", default="gemini-3.5-flash",
                    help="Judge model dir name (default: gemini-3.5-flash)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    cmp_dir = BASE_DIR / "analysis" / args.judge / args.judge / "comparison"

    tables = {
        "inference": _load(cmp_dir / "inference_eval_comparison.json"),
        "efficiency": _load(cmp_dir / "efficiency_eval_comparison.json"),
        "question": _load(cmp_dir / "question_eval_comparison.json"),
        "reasoning": _load(cmp_dir / "diagnostic_reasoning_comparison.json"),
    }

    models = [m for m in MODEL_LABELS if m in tables["inference"]]

    # Raw value matrix: axes x models
    raw = np.array([
        [tables[dim][m][field] for m in models]
        for _, dim, field, _lo, _hi in AXES
    ])

    norm = np.zeros_like(raw)
    for i, (_, _dim, _field, lo, hi) in enumerate(AXES):
        norm[i] = np.clip((raw[i] - lo) / (hi - lo), 0.0, 1.0)

    n_axes = len(AXES)
    angles = np.linspace(0, 2 * np.pi, n_axes, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    axis_labels = [f"{label}\n[{lo:g}–{hi:g}]" for label, _dim, _field, lo, hi in AXES]
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(axis_labels, fontsize=9.5)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels([])  # per-axis scales differ; ranges are in axis labels instead
    ax.grid(color="lightgray", linewidth=0.7)
    ax.spines["polar"].set_color("lightgray")

    for j, model in enumerate(models):
        vals = norm[:, j].tolist()
        vals += vals[:1]
        color = MODEL_COLORS[model]
        ax.plot(angles, vals, color=color, linewidth=2, label=MODEL_LABELS[model])
        ax.fill(angles, vals, color=color, alpha=0.08)
        ax.scatter(angles[:-1], vals[:-1], color=color, s=22, zorder=3)

    ax.set_title(
        "Main Evaluation — Cross-Model Comparison on Headline Metrics\n"
        "(each axis on its own fixed [lo–hi] scale, shown in brackets)",
        fontsize=12, pad=30,
    )
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=9, frameon=False)

    fig.tight_layout()
    out_path = cmp_dir / "compare_radar_main_metrics.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.4)
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
