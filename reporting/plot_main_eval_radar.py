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

Each axis is z-scored across the compared models: z = (x - mean) / std,
computed per metric over the models shown. 0 = the group mean on that
metric, +1/-1 = one standard deviation above/below it. This makes axes
with very different native scales (e.g. turn_count vs. a 0-1 rate)
comparable by how unusual a model is on each metric, not by absolute
magnitude.

Usage:
  python plot_main_eval_radar.py [--judge JUDGE]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

BASE_DIR = Path(__file__).resolve().parent.parent
from utils.paths import ANALYSIS_ROOT, LOGS_ROOT, RESULTS_ROOT

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

# (label, source table, field)
AXES = [
    ("Precision\n(Inference)", "inference", "precision"),
    ("Recall\n(Inference)", "inference", "recall"),
    ("Cond. IAS\n(Question)", "question", "llm_judge_conditional_mean_ias"),
    ("Cond. ECR\n(Question)", "question", "llm_judge_conditional_mean_ecr"),
    ("Turn Count\n(Efficiency)", "efficiency", "turn_count"),
    ("CSSR\n(Efficiency)", "efficiency", "cssr"),
    ("Final Accuracy", "efficiency", "final_accuracy"),
    ("Diagnostic Reasoning Score", "reasoning", "overall_score"),
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
    cmp_dir = ANALYSIS_ROOT / args.judge / args.judge / "comparison"

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
        for _, dim, field in AXES
    ])

    mean = raw.mean(axis=1, keepdims=True)
    std = raw.std(axis=1, keepdims=True)
    z = (raw - mean) / std

    n_axes = len(AXES)
    angles = np.linspace(0, 2 * np.pi, n_axes, endpoint=False).tolist()
    angles += angles[:1]

    # Symmetric radial range so 0 (group mean) sits at the same fraction of
    # every axis; round outward to the nearest 0.5 sigma for clean ticks.
    zlim = max(0.5, np.ceil(np.abs(z).max() * 2) / 2)

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([label for label, _dim, _field in AXES], fontsize=9.5)
    ax.set_ylim(-zlim, zlim)
    yticks = np.linspace(-zlim, zlim, 5)
    ax.set_yticks(yticks)
    ax.set_yticklabels([f"{t:+.1f}σ" for t in yticks], fontsize=8, color="gray")
    ax.grid(color="lightgray", linewidth=0.7)
    ax.spines["polar"].set_color("lightgray")

    # Highlight the 0 (group-mean) ring since it's the reference line, not
    # an arbitrary gridline.
    ax.plot(angles, [0] * len(angles), color="dimgray", linewidth=1.2, linestyle="--", zorder=2)

    for j, model in enumerate(models):
        vals = z[:, j].tolist()
        vals += vals[:1]
        color = MODEL_COLORS[model]
        ax.plot(angles, vals, color=color, linewidth=2, label=MODEL_LABELS[model])
        ax.fill(angles, vals, color=color, alpha=0.08)
        ax.scatter(angles[:-1], vals[:-1], color=color, s=22, zorder=3)

    ax.set_title(
        "Main Evaluation — Cross-Model Comparison on Headline Metrics\n"
        "(z-score per metric across models; 0 = group mean, dashed ring)",
        fontsize=12, pad=30,
    )
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=9, frameon=False)

    fig.tight_layout()
    out_path = cmp_dir / "compare_radar_main_metrics.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.4)
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
