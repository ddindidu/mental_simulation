#!/usr/bin/env python3
"""
Main Evaluation — Cross-Model Comparison Visualization (evaluation_v5.md headline metrics)

For every (patient, judge) bucket with a
analysis/<patient>/<judge>/comparison/headline_comparison.json (written by
reporting/summarize_comparisons.py), renders:

  comparison/main_eval_all_dimensions.png
      one row per dimension, one bar panel per headline metric
  comparison/main_eval_normalized_heatmap.png
      model x metric heatmap of per-column min-max normalized scores
      (darker = better; lower-is-better metrics sign-flipped first)

Usage:
  MS_RUN=run_batch_20260912 python reporting/summarize_main_eval_findings.py
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
from utils.paths import ANALYSIS_ROOT
from reporting.headline_metrics import HEADLINE, DIMENSION_NAMES

MODEL_ORDER = [
    "gpt-5.4",
    "gpt-5.6-luna",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "claude-sonnet-5",
    "claude-haiku-4.5",
    "llama-3.3-70b-instruct",
    "qwen3-235b",
    "qwen3-235b-a22b-2507",
]
MODEL_LABELS = {
    "gpt-5.4":                 "GPT-5.4",
    "gpt-5.6-luna": "GPT-5.6 Luna",
    "gemini-3.8-flash":        "Gemini 3.8 Flash",
    "gemini-3.5-flash":        "Gemini 3.5 Flash",
    "gemini-3.1-flash-lite":   "Gemini 3.1 Lite",
    "claude-sonnet-5":     "Claude Sonnet 5",
    "claude-haiku-4.5":    "Claude Haiku 4.5",
    "llama-3.3-70b-instruct":  "Llama 3.3 70B",
    "qwen3-235b":              "Qwen3 235B",
    "qwen3-235b-a22b-2507":    "Qwen3 235B",
}

MODEL_COLORS = {
    "gpt-5.4":                 "#C94040",
    "gpt-5.6-luna": "#3AA89C",
    "gemini-3.1-flash-lite":   "#4580C4",
    "gemini-3.5-flash":        "#F07C35",
    "gemini-3.8-flash":        "#F07C35",
    "claude-sonnet-5":     "#D9A03C",
    "claude-haiku-4.5":    "#A0A0A0",   
    "llama-3.3-70b-instruct":  "#5BA04E",
    "qwen3-235b":              "#9B6ABE",
    "qwen3-235b-a22b-2507":    "#9B6ABE",
}


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _plot_bucket(cmp_dir: Path, rows: list[dict], plt) -> None:
    by_model = {r["model"]: r for r in rows}
    models = [m for m in MODEL_ORDER if m in by_model] + sorted(m for m in by_model if m not in MODEL_ORDER)
    labels = [MODEL_LABELS.get(m, m).replace(" ", "\n") for m in models]
    colors = [MODEL_COLORS.get(m, "#777777") for m in models]

    # ── Figure 1: one row per dimension, one panel per headline metric ─────
    dims = list(DIMENSION_NAMES)
    n_cols = max(sum(1 for *_, d, _ in HEADLINE if d == dim) for dim in dims)
    fig, axes = plt.subplots(len(dims), n_cols, figsize=(4.2 * n_cols, 4.2 * len(dims)), squeeze=False)
    fig.patch.set_facecolor("#F1F4F9")
    for row_i, dim in enumerate(dims):
        metrics = [(k, lbl, lower) for k, lbl, d, lower in HEADLINE if d == dim]
        for col_i in range(n_cols):
            ax = axes[row_i][col_i]
            if col_i >= len(metrics):
                ax.set_visible(False)
                continue
            key, m_label, lower_better = metrics[col_i]
            ax.set_facecolor("#FFFFFF")
            xs = np.arange(len(models))
            vals = [by_model[m].get(key) for m in models]
            ax.bar(xs, [v if v is not None else 0 for v in vals], 0.6, color=colors, alpha=0.88,
                   zorder=3, edgecolor="white", linewidth=0.6)
            for xi, v in zip(xs, vals):
                ax.text(xi, v or 0, f"{v:.3f}" if v is not None else "n/a", ha="center",
                        va="bottom", fontsize=6.5, color="#1C2333")
            ax.set_xticks(xs)
            ax.set_xticklabels(labels, fontsize=6.5, ha="center")
            ax.tick_params(axis="y", labelsize=7)
            ax.set_title(m_label + ("  (↓ lower better)" if lower_better else ""),
                         fontsize=8.5, fontweight="bold", pad=4)
            ax.grid(axis="y", color="#E4EBF5", linewidth=0.8, zorder=0)
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.spines["bottom"].set_color("#DDE3EF")
            if col_i == 0:
                ax.set_ylabel(DIMENSION_NAMES[dim], fontsize=8.5, color="#6B7A99", fontweight="bold")
    fig.suptitle(f"Main Evaluation — Headline Metrics by Doctor Model ({cmp_dir.parent.relative_to(ANALYSIS_ROOT)})",
                 fontsize=13, fontweight="bold", y=1.001, color="#1C2333")
    plt.tight_layout()
    out1 = cmp_dir / "main_eval_all_dimensions.png"
    fig.savefig(out1, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[saved] {out1}")

    # ── Figure 2: normalized model x metric heatmap ───────────────────────
    raw = np.full((len(models), len(HEADLINE)), np.nan)
    for mi, model in enumerate(models):
        for ci, (key, _, _, lower_better) in enumerate(HEADLINE):
            v = by_model[model].get(key)
            if v is not None:
                raw[mi, ci] = -v if lower_better else v
    norm = np.full_like(raw, np.nan)
    for ci in range(raw.shape[1]):
        col = raw[:, ci]
        valid = col[~np.isnan(col)]
        if len(valid) == 0:
            continue
        lo, hi = valid.min(), valid.max()
        norm[:, ci] = 0.5 if hi == lo else (col - lo) / (hi - lo)

    fig2, ax2 = plt.subplots(figsize=(13, 0.6 * len(models) + 2.5))
    fig2.patch.set_facecolor("#F1F4F9")
    im = ax2.imshow(norm, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax2.set_xticks(range(len(HEADLINE)))
    ax2.set_xticklabels([f"{lbl}{' (↓)' if lower else ''}" for _, lbl, _, lower in HEADLINE],
                        rotation=35, ha="right", fontsize=8)
    ax2.set_yticks(range(len(models)))
    ax2.set_yticklabels([MODEL_LABELS.get(m, m) for m in models], fontsize=9)
    for ri in range(len(models)):
        for ci, (_, _, _, lower_better) in enumerate(HEADLINE):
            v = raw[ri, ci]
            if not np.isnan(v):
                ax2.text(ci, ri, f"{-v if lower_better else v:.3f}", ha="center", va="center",
                         fontsize=6.5, color="white" if norm[ri, ci] > 0.6 else "#1C2333",
                         fontweight="bold")
    cbar = fig2.colorbar(im, ax=ax2, shrink=0.7, pad=0.02)
    cbar.set_label("Normalized within metric\n(darker = better)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    ax2.set_title("Main Evaluation — Normalized Cross-Model Profile "
                  "(lower-is-better metrics sign-flipped; blank = not available)",
                  fontsize=10, fontweight="bold", color="#1C2333", pad=14)
    plt.tight_layout()
    out2 = cmp_dir / "main_eval_normalized_heatmap.png"
    fig2.savefig(out2, dpi=150, bbox_inches="tight", facecolor=fig2.get_facecolor())
    plt.close(fig2)
    print(f"[saved] {out2}")


def main() -> None:
    argparse.ArgumentParser().parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cmp_dirs = sorted(p.parent for p in ANALYSIS_ROOT.glob("*/*/comparison/headline_comparison.json"))
    if not cmp_dirs:
        print("No headline_comparison.json found — run reporting/summarize_comparisons.py first")
    for cmp_dir in cmp_dirs:
        _plot_bucket(cmp_dir, _load(cmp_dir / "headline_comparison.json"), plt)


if __name__ == "__main__":
    main()
