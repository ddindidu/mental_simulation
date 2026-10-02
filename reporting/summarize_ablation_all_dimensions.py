#!/usr/bin/env python3
"""
Outcome-Stratification Ablation — evaluation_v5.md headline metrics

Splits each doctor model's episodes by Final Accuracy:
  correct   — the final diagnosis maps to the ground truth
  incorrect — it does not
and recomputes every other headline metric per stratum (same aggregation as
reporting/headline_metrics.pooled_means). Shows whether a model's
hypothesis / question / efficiency / evidence profile differs between the
cases it gets right and the ones it gets wrong.

Outputs (per (patient, judge) bucket):
  analysis/<patient>/<judge>/comparison/outcome_stratified/
    ablation_all_summary.json      {model: {stratum: {metric: value}}}
    ablation_all_dimensions.csv    one row per (model, stratum) incl. delta = correct − incorrect
    ablation_all_dimensions.png    per-metric grouped bars, correct vs. incorrect per model
    ablation_delta_heatmap.png     model × metric Δ (correct − incorrect), sign-flipped for ↓ metrics

Usage:
  MS_RUN=run_batch_20260912 python reporting/summarize_ablation_all_dimensions.py [--style plain]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from utils.paths import ANALYSIS_ROOT
from reporting.headline_metrics import HEADLINE, discover_combos, load_combo, pooled_means

METRICS = [(k, lbl, dim, lower) for k, lbl, dim, lower in HEADLINE if k != "final_accuracy"]
STRATA = ("correct", "incorrect", "all")


def stratify(episodes: list[dict]) -> dict[str, dict]:
    groups = {
        "correct":   [e for e in episodes if e.get("final_accuracy") == 1.0],
        "incorrect": [e for e in episodes if e.get("final_accuracy") != 1.0],
        "all":       episodes,
    }
    return {s: pooled_means(eps) for s, eps in groups.items()}


def _delta(by_stratum: dict, key: str) -> float | None:
    c, i = by_stratum["correct"].get(key), by_stratum["incorrect"].get(key)
    return c - i if c is not None and i is not None else None


def plot_bars(results: dict[str, dict], out_path: Path) -> None:
    models = list(results)
    n_cols = 3
    n_rows = (len(METRICS) + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5.5 * n_cols, 3.8 * n_rows), squeeze=False)
    xs = np.arange(len(models))
    for ax, (key, label, dim, lower) in zip(axes.flat, METRICS):
        for off, stratum, color in ((-0.2, "correct", "#0072B2"), (0.2, "incorrect", "#D55E00")):
            vals = [results[m][stratum].get(key) for m in models]
            ax.bar(xs + off, [v if v is not None else 0 for v in vals], 0.38, color=color,
                   alpha=0.85, label=stratum, zorder=3)
        ax.set_xticks(xs)
        ax.set_xticklabels([m.replace("-", "-\n", 1) for m in models], fontsize=6.5)
        ax.set_title(f"{label}{' (↓)' if lower else ''} — {dim}", fontsize=9, fontweight="bold")
        ax.grid(axis="y", color="#e1e0d9", zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
    for ax in list(axes.flat)[len(METRICS):]:
        ax.set_visible(False)
    axes.flat[0].legend(fontsize=8, frameon=False)
    fig.suptitle(f"Outcome-stratified headline metrics — correct vs. incorrect final diagnosis "
                 f"({out_path.parent.parent.parent.relative_to(ANALYSIS_ROOT)})",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out_path}")


def plot_delta_heatmap(results: dict[str, dict], out_path: Path) -> None:
    models = list(results)
    raw = np.full((len(models), len(METRICS)), np.nan)
    for mi, m in enumerate(models):
        for ci, (key, _, _, lower) in enumerate(METRICS):
            d = _delta(results[m], key)
            if d is not None:
                raw[mi, ci] = -d if lower else d
    fig, ax = plt.subplots(figsize=(12, 0.6 * len(models) + 2.5))
    # Per-column scaling so metrics on different scales share one colormap;
    # cells show the raw (unflipped) delta.
    scale = np.nanmax(np.abs(raw), axis=0)
    scale[~np.isfinite(scale) | (scale == 0)] = 1
    im = ax.imshow(raw / scale, cmap="RdBu", vmin=-1, vmax=1, aspect="auto")
    for mi in range(len(models)):
        for ci, (key, _, _, lower) in enumerate(METRICS):
            if not np.isnan(raw[mi, ci]):
                ax.text(ci, mi, f"{(-raw[mi, ci] if lower else raw[mi, ci]):+.3f}",
                        ha="center", va="center", fontsize=7)
    ax.set_xticks(range(len(METRICS)))
    ax.set_xticklabels([f"{lbl}{' (↓)' if lower else ''}" for _, lbl, _, lower in METRICS],
                       rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models, fontsize=9)
    cbar = fig.colorbar(im, ax=ax, shrink=0.7)
    cbar.set_label("Δ (correct − incorrect), column-scaled;\nblue = better on correct episodes", fontsize=8)
    ax.set_title("Outcome ablation — Δ = correct − incorrect (cell text: raw Δ)", fontsize=10, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out_path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--style", default="plain", help="Episode style filter ('' = all styles)")
    args = p.parse_args()

    buckets: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for patient, judge, doctor in discover_combos():
        eps = load_combo(patient, judge, doctor, args.style or None)
        if eps:
            buckets[(patient, judge)][doctor] = stratify(eps)

    for (patient, judge), results in buckets.items():
        out_dir = ANALYSIS_ROOT / patient / judge / "comparison" / "outcome_stratified"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "ablation_all_summary.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

        fields = ["model", "stratum", "n_episodes", *[k for k, *_ in METRICS]]
        with open(out_dir / "ablation_all_dimensions.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for model, by_s in results.items():
                for s in STRATA:
                    w.writerow({"model": model, "stratum": s, **{k: by_s[s].get(k) for k in fields[2:]}})
                w.writerow({"model": model, "stratum": "delta", "n_episodes": None,
                            **{k: _delta(by_s, k) for k, *_ in METRICS}})

        print(f"\n=== {patient}/{judge}: correct vs. incorrect (n) and Δ ===")
        for model, by_s in results.items():
            deltas = "  ".join(f"{lbl[:9]}={d:+.3f}" for k, lbl, *_ in METRICS
                               if (d := _delta(by_s, k)) is not None)
            print(f"  {model:<24} n={by_s['correct']['n_episodes']}/{by_s['incorrect']['n_episodes']}  {deltas}")
        plot_bars(results, out_dir / "ablation_all_dimensions.png")
        plot_delta_heatmap(results, out_dir / "ablation_delta_heatmap.png")


if __name__ == "__main__":
    main()
