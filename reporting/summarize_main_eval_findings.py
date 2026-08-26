#!/usr/bin/env python3
"""
Main Evaluation — Cross-Model Comparison Visualization (non-stratified)

Companion to summarize_ablation_all_dimensions.py, but over the full episode
set (no correct/incorrect split). Reads the comparison tables already produced
by summarize_comparisons.py and summarize_question_eval.py and renders:

  analysis/<judge>/<judge>/comparison/main_eval_all_dimensions.png
      12-panel bar chart, one panel per metric, grouped by the 4 dimensions
  analysis/<judge>/<judge>/comparison/main_eval_normalized_heatmap.png
      model x metric heatmap of min-max normalized scores (higher = better,
      lower-is-better metrics sign-flipped before normalizing)

Sources (per doctor model), already aggregated by other scripts:
  analysis/<j>/<j>/comparison/inference_eval_comparison.json
  analysis/<j>/<j>/comparison/efficiency_eval_comparison.json
  analysis/<j>/<j>/comparison/diagnostic_reasoning_comparison.json
  analysis/<j>/<j>/comparison/question_eval_comparison.json

Usage:
  python reporting/summarize_main_eval_findings.py [--judge JUDGE]
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent.parent
from utils.paths import ANALYSIS_ROOT, LOGS_ROOT, RESULTS_ROOT

MODEL_ORDER = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gpt-5.4",
    "gpt-5.4-mini-2026-03-17",
    "llama-3.3-70b-instruct",
    "qwen3-235b-a22b-2507",
]
MODEL_LABELS = {
    "gemini-3.1-flash-lite":   "Gemini 3.1 Lite",
    "gemini-3.5-flash":        "Gemini 3.5 Flash",
    "gpt-5.4":                 "GPT-5.4",
    "gpt-5.4-mini-2026-03-17": "GPT-5.4 Mini",
    "llama-3.3-70b-instruct":  "Llama 3.3 70B",
    "qwen3-235b-a22b-2507":    "Qwen3 235B",
}
MODEL_COLORS = {
    "gemini-3.1-flash-lite":   "#4580C4",
    "gemini-3.5-flash":        "#F07C35",
    "gpt-5.4":                 "#C94040",
    "gpt-5.4-mini-2026-03-17": "#3AA89C",
    "llama-3.3-70b-instruct":  "#5BA04E",
    "qwen3-235b-a22b-2507":    "#9B6ABE",
}


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _index_by_model(rows: list[dict]) -> dict[str, dict]:
    return {r["model"]: r for r in rows}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--judge", default="gemini-3.5-flash")
    args = p.parse_args()

    cmp_dir = ANALYSIS_ROOT / args.judge / args.judge / "comparison"

    inf = _index_by_model(_load(cmp_dir / "inference_eval_comparison.json"))
    eff = _index_by_model(_load(cmp_dir / "efficiency_eval_comparison.json"))
    dr  = _index_by_model(_load(cmp_dir / "diagnostic_reasoning_comparison.json"))
    q   = _index_by_model(_load(cmp_dir / "question_eval_comparison.json"))

    models = [m for m in MODEL_ORDER if m in inf]

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[skip] matplotlib not available")
        return

    labels = [MODEL_LABELS[m].replace(" ", "\n") for m in models]
    colors = [MODEL_COLORS[m] for m in models]

    # ── Figure 1: 12-panel bar chart ──────────────────────────────────────
    PANELS = [
        ("Inference Quality", [
            ("accuracy",        "Accuracy\n(exact set match)",  inf, False),
            ("recall",          "Recall\n(truth coverage)",     inf, False),
            ("jaccard",         "Jaccard Index",                inf, False),
        ]),
        ("Question Quality (cosine)", [
            ("cosine_conditional_mean_composite", "Cond. Mean\nComposite",       q, False),
            ("cosine_discriminating_q_rate",      "Discriminating-Q\nRate",      q, False),
            ("cosine_ig_positive_rate",           "IG-Positive\nRate",           q, False),
        ]),
        ("Efficiency", [
            ("final_accuracy",        "Final Accuracy\n(exact diagnosis)", eff, False),
            ("cssr",                  "CSSR\n(candidate narrowing)",       eff, False),
            ("redundant_turn_ratio",  "Redundant Turn\nRatio (↓ better)",  eff, True),
        ]),
        ("Diagnostic Reasoning", [
            ("overall_score",                 "Overall Score",            dr, False),
            ("functional_impairment_score",   "Functional\nImpairment",   dr, False),
            ("additional_requirements_score", "Additional\nRequirements", dr, False),
        ]),
    ]

    fig, axes = plt.subplots(4, 3, figsize=(15, 18))
    fig.patch.set_facecolor("#F1F4F9")

    for row_i, (dim_label, metrics) in enumerate(PANELS):
        for col_i, (metric, m_label, table, lower_better) in enumerate(metrics):
            ax = axes[row_i][col_i]
            ax.set_facecolor("#FFFFFF")

            xs = np.arange(len(models))
            vals = [table.get(m, {}).get(metric, 0) or 0 for m in models]

            bars = ax.bar(xs, vals, 0.6, color=colors, alpha=0.88, zorder=3,
                          edgecolor="white", linewidth=0.6)

            for xi, v in zip(xs, vals):
                ax.text(xi, v, f"{v:.3f}", ha="center",
                        va="bottom" if v >= 0 else "top", fontsize=6.5,
                        color="#1C2333")

            ax.set_xticks(xs)
            ax.set_xticklabels(labels, fontsize=6.5, ha="center")
            ax.tick_params(axis="y", labelsize=7)
            title = m_label + ("  (↓ lower better)" if lower_better and "↓" not in m_label else "")
            ax.set_title(title, fontsize=8, fontweight="bold", pad=4)
            ax.grid(axis="y", color="#E4EBF5", linewidth=0.8, zorder=0)
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.spines["bottom"].set_color("#DDE3EF")
            ax.axhline(0, color="#B9C3D6", linewidth=0.7, zorder=1)

            if col_i == 0:
                ax.set_ylabel(dim_label, fontsize=8.5, color="#6B7A99", fontweight="bold")

    fig.suptitle("Main Evaluation — Cross-Model Comparison (all episodes, unstratified)",
                 fontsize=13, fontweight="bold", y=1.001, color="#1C2333")
    plt.tight_layout(rect=[0, 0, 1, 1])
    out1 = cmp_dir / "main_eval_all_dimensions.png"
    fig.savefig(out1, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[saved] {out1}")

    # ── Figure 2: normalized model x metric heatmap ───────────────────────
    HEATMAP_METRICS = [
        ("Accuracy",              inf, "accuracy",                           False),
        ("Recall",                inf, "recall",                             False),
        ("Jaccard",               inf, "jaccard",                            False),
        ("Weighted Recall",       inf, "weighted_recall",                    False),
        ("Q: Cond. Composite",    q,   "cosine_conditional_mean_composite",  False),
        ("Q: Disc-Q Rate",        q,   "cosine_discriminating_q_rate",       False),
        ("Final Accuracy",        eff, "final_accuracy",                     False),
        ("CSSR",                  eff, "cssr",                               False),
        ("Turn Count",            eff, "turn_count",                         True),
        ("Redundant Turn Ratio",  eff, "redundant_turn_ratio",               True),
        ("DR: Overall",           dr,  "overall_score",                      False),
        ("DR: Symptom Satisfaction", dr, "symptom_satisfaction_score",       False),
        ("DR: Func. Impairment",  dr,  "functional_impairment_score",        False),
        ("DR: Addl. Requirements",dr,  "additional_requirements_score",      False),
    ]

    raw = np.full((len(models), len(HEATMAP_METRICS)), np.nan)
    for mi, model in enumerate(models):
        for ci, (_, table, metric, lower_better) in enumerate(HEATMAP_METRICS):
            v = table.get(model, {}).get(metric)
            if v is not None:
                raw[mi, ci] = -v if lower_better else v

    # min-max normalize per column to [0, 1] so metrics of different scale
    # are visually comparable on one heatmap
    norm = np.full_like(raw, np.nan)
    for ci in range(raw.shape[1]):
        col = raw[:, ci]
        valid = col[~np.isnan(col)]
        if len(valid) == 0:
            continue
        lo, hi = valid.min(), valid.max()
        norm[:, ci] = 0.5 if hi == lo else (col - lo) / (hi - lo)

    col_labels = [h[0] for h in HEATMAP_METRICS]
    row_labels = [MODEL_LABELS[m] for m in models]

    fig2, ax2 = plt.subplots(figsize=(15, 5))
    fig2.patch.set_facecolor("#F1F4F9")
    ax2.set_facecolor("#F1F4F9")

    im = ax2.imshow(norm, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")

    ax2.set_xticks(range(len(col_labels)))
    ax2.set_xticklabels(col_labels, rotation=35, ha="right", fontsize=8)
    ax2.set_yticks(range(len(row_labels)))
    ax2.set_yticklabels(row_labels, fontsize=9)

    for yi, model in enumerate(models):
        ax2.add_patch(plt.Rectangle((-0.55 - 0.35, yi - 0.5), 0.35, 1,
                                     color=MODEL_COLORS[model], transform=ax2.transData,
                                     clip_on=False))

    for ri in range(len(models)):
        for ci in range(len(HEATMAP_METRICS)):
            v = raw[ri, ci]
            if not np.isnan(v):
                shown = -v if HEATMAP_METRICS[ci][3] else v
                text_color = "white" if norm[ri, ci] > 0.6 else "#1C2333"
                ax2.text(ci, ri, f"{shown:.3f}", ha="center", va="center",
                         fontsize=6.5, color=text_color, fontweight="bold")

    cbar = fig2.colorbar(im, ax=ax2, shrink=0.7, pad=0.02)
    cbar.set_label("Normalized rank within metric\n(darker = better, per-column min-max)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    ax2.set_title(
        "Main Evaluation — Normalized Cross-Model Profile "
        "(lower-is-better metrics sign-flipped before normalizing)",
        fontsize=10, fontweight="bold", color="#1C2333", pad=14,
    )
    plt.tight_layout()
    out2 = cmp_dir / "main_eval_normalized_heatmap.png"
    fig2.savefig(out2, dpi=150, bbox_inches="tight", facecolor=fig2.get_facecolor())
    plt.close(fig2)
    print(f"[saved] {out2}")


if __name__ == "__main__":
    main()
