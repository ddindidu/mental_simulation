#!/usr/bin/env python3
"""
Two disorder-level analyses on top of plot_v4_metrics_by_disease.py's data:

(1) Cross-model variability by disorder (plot_disorder_variability.png)
    For each disorder, computes the mean and std-dev ACROSS THE 5 DOCTOR
    MODELS of Final Accuracy, Jaccard, and QTS (each model's own value is
    first pooled over its own episodes for that disorder). One scatter panel
    per metric: x = mean across models, y = std across models.
      - low mean, low std   -> "universally hard" (every model struggles)
      - any mean, high std  -> "model-specific weakness" (some models do
                                fine, others don't)
      - high mean, low std  -> "universally easy"
    Quadrant guide lines are drawn at the median mean / median std. Points
    are colored by DSM-5 category (same mapping/colors as panel 2) so it's
    visible whether variance clusters by category. Spearman correlation
    between each metric's per-disorder std and Final Accuracy's per-disorder
    std is printed/annotated, to see whether a disorder that splits models
    apart on Accuracy also splits them apart on Jaccard/QTS.

(2) DSM-5 diagnostic category summary (plot_dsm5_category_summary.png)
    Groups the 23 disorders into 8 DSM-5 categories and bar-charts each
    category's mean Jaccard / QTS / Diagnostic Evidence Sufficiency / Final
    Accuracy, averaged first per disorder (across models/episodes) then
    across the disorders in that category — so a category with more
    disorders doesn't just get more episodes' worth of weight. Error bars =
    std across disorders within the category (descriptive spread, not a CI
    — several categories have only 2-3 disorders, so this is presented as
    descriptive, not a statistically powered comparison).

Usage:
  MS_RUN=run_batch_20260912 python reporting/plot_disorder_variability_and_category.py [--style plain]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as scipy_stats

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.paths import ANALYSIS_ROOT
from reporting.cross_model.plot_v4_metrics_by_disease import load_data, MODEL_ORDER
from reporting.cross_model.plot_v4_radar_by_judge import DOCTOR_NAME_CANONICAL

# DSM-5 category per disorder ID (mentalbench/resources/knowledge_graph has no
# explicit category field, so this is hand-mapped from each disorder's name
# in disorder.json against standard DSM-5-TR chapter groupings).
DSM5_CATEGORY = {
    "D001": "Neurodevelopmental", "D002": "Neurodevelopmental", "D003": "Neurodevelopmental",
    "D004": "Psychotic", "D005": "Psychotic", "D006": "Psychotic", "D007": "Psychotic",
    "D008": "Bipolar", "D009": "Bipolar", "D010": "Bipolar",
    "D011": "Anxiety", "D012": "Anxiety",
    "D013": "Depressive", "D014": "Depressive", "D015": "Depressive",
    "D016": "OCD-Related", "D017": "OCD-Related",
    "D018": "Trauma/Stressor", "D019": "Trauma/Stressor", "D020": "Trauma/Stressor",
    "D021": "Eating", "D022": "Eating", "D023": "Eating",
}
CATEGORY_ORDER = ["Neurodevelopmental", "Psychotic", "Bipolar", "Anxiety",
                   "Depressive", "OCD-Related", "Trauma/Stressor", "Eating"]
CATEGORY_PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7",
                     "#E69F00", "#56B4E9", "#999999", "#CA3435"]
CATEGORY_COLOR = dict(zip(CATEGORY_ORDER, CATEGORY_PALETTE))


def _disorder_model_means(m_vals: dict, diseases: list[str], doctors: list[str]) -> dict[str, list[float]]:
    """{disease: [one mean per doctor that has data]}."""
    out = {}
    for d in diseases:
        means = []
        for doc in doctors:
            vals = m_vals.get((d, doc))
            if vals:
                means.append(float(np.mean(vals)))
        out[d] = means
    return out


def plot_variability(values: dict, diseases: list[str], doctors: list[str], out_path: Path) -> None:
    metrics = [("jaccard_rigid", "Jaccard"), ("ias", "QTS"), ("final_accuracy_pct", "Final Accuracy")]

    per_metric_stats = {}
    for key, _label in metrics:
        dm = _disorder_model_means(values[key], diseases, doctors)
        mean_arr = np.array([np.mean(dm[d]) if dm[d] else np.nan for d in diseases])
        std_arr = np.array([np.std(dm[d], ddof=1) if len(dm[d]) > 1 else np.nan for d in diseases])
        per_metric_stats[key] = (mean_arr, std_arr)

    acc_std = per_metric_stats["final_accuracy_pct"][1]

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.8))
    for ax, (key, label) in zip(axes, metrics):
        mean_arr, std_arr = per_metric_stats[key]
        valid = ~(np.isnan(mean_arr) | np.isnan(std_arr))
        mean_v, std_v = mean_arr[valid], std_arr[valid]
        diseases_v = [d for d, ok in zip(diseases, valid) if ok]
        colors = [CATEGORY_COLOR[DSM5_CATEGORY[d]] for d in diseases_v]

        ax.scatter(mean_v, std_v, c=colors, s=70, edgecolors="white", linewidths=0.8, zorder=3)
        for x, y, d in zip(mean_v, std_v, diseases_v):
            ax.annotate(d, (x, y), textcoords="offset points", xytext=(5, 4), fontsize=8, color="#3a3a38")

        med_x, med_y = np.median(mean_v), np.median(std_v)
        ax.axvline(med_x, color="#bbbbbb", linewidth=1, linestyle="--", zorder=1)
        ax.axhline(med_y, color="#bbbbbb", linewidth=1, linestyle="--", zorder=1)

        if key == "final_accuracy_pct":
            rho_txt = ""
        else:
            valid_acc = ~(np.isnan(acc_std) | np.isnan(std_arr))
            rho, p = scipy_stats.spearmanr(acc_std[valid_acc], std_arr[valid_acc])
            rho_txt = f"\nSpearman ρ(std vs. Accuracy-std)={rho:.2f} (p={p:.2g})"

        ax.set_xlabel(f"Mean {label} across models (per disorder)", fontsize=11.5)
        ax.set_ylabel(f"Std-dev of {label} across models (per disorder)", fontsize=11.5)
        ax.set_title(f"{label}{rho_txt}", fontsize=11.5)
        ax.grid(color="#eceae3", linewidth=0.8, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)

    axes[0].annotate("low mean + low std\n= universally hard", xy=(0.03, 0.03), xycoords="axes fraction",
                      fontsize=9, color="#5c5b55", va="bottom", style="italic")
    axes[0].annotate("high std\n= model-specific", xy=(0.03, 0.96), xycoords="axes fraction",
                      fontsize=9, color="#5c5b55", va="top", style="italic")

    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=CATEGORY_COLOR[c],
                           markeredgecolor="white", markersize=9, label=c) for c in CATEGORY_ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=8, fontsize=9.5, frameon=False,
               bbox_to_anchor=(0.5, -0.06))

    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out_path}")


def plot_category_summary(values: dict, diseases: list[str], doctors: list[str], out_path: Path) -> None:
    metrics = [
        ("jaccard_rigid", "Jaccard", "#0072B2"),
        ("ias", "QTS", "#7B5EA7"),
        ("evidence_sufficiency_pred", "Diagnostic Evidence Sufficiency", "#1C8C5B"),
        ("final_accuracy_pct", "Final Accuracy (%)", "#C97A1E"),
    ]

    fig, axes = plt.subplots(1, 4, figsize=(19, 5.6))
    for ax, (key, label, color) in zip(axes, metrics):
        dm = _disorder_model_means(values[key], diseases, doctors)
        disorder_mean = {d: float(np.mean(v)) for d, v in dm.items() if v}

        cat_means, cat_stds, cat_ns = [], [], []
        for cat in CATEGORY_ORDER:
            cat_disorders = [d for d in diseases if DSM5_CATEGORY[d] == cat and d in disorder_mean]
            vals = [disorder_mean[d] for d in cat_disorders]
            cat_means.append(np.mean(vals) if vals else np.nan)
            cat_stds.append(np.std(vals, ddof=1) if len(vals) > 1 else 0.0)
            cat_ns.append(len(vals))

        x = np.arange(len(CATEGORY_ORDER))
        ax.bar(x, cat_means, yerr=cat_stds, color=color, alpha=0.85, capsize=4,
               edgecolor="white", linewidth=0.8, error_kw=dict(ecolor="#5c5b55", linewidth=1.1))
        for xi, (m, n) in enumerate(zip(cat_means, cat_ns)):
            if not np.isnan(m):
                ax.text(xi, 0.02 * max(cat_means), f"n={n}", ha="center", va="bottom",
                        fontsize=8.5, color="white" if m > 0.15 * max(cat_means) else "#3a3a38",
                        fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels(CATEGORY_ORDER, rotation=40, ha="right", fontsize=9.5)
        ax.set_title(label, fontsize=12, fontweight="bold")
        ax.grid(axis="y", color="#eceae3", linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle(
        "Descriptive — category sizes range 2-4 disorders; error bars = std across disorders "
        "within category, not a confidence interval.",
        fontsize=10, color="#5c5b55", y=1.03,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default="plain", help="Filter episodes by log filename suffix.")
    args = parser.parse_args()
    style = args.style or None

    values, disease_name = load_data(style)
    if not disease_name:
        print("No efficiency_eval.json data found under RESULTS_ROOT.")
        return

    diseases = sorted(disease_name.keys(), key=lambda d: int(d[1:]))
    unmapped = [d for d in diseases if d not in DSM5_CATEGORY]
    if unmapped:
        print(f"[warn] no DSM-5 category mapped for: {unmapped} — skipped from category summary", file=_sys.stderr)

    all_doctors: set[str] = set()
    for m_vals in values.values():
        for _gt, doctor in m_vals:
            all_doctors.add(doctor)
    order_rank = {name: i for i, name in enumerate(MODEL_ORDER)}
    doctors = sorted(all_doctors, key=lambda d: (order_rank.get(d, len(MODEL_ORDER)), d))

    plot_variability(values, diseases, doctors, ANALYSIS_ROOT / "disorder_variability_by_model.png")
    plot_category_summary(values, diseases, doctors, ANALYSIS_ROOT / "dsm5_category_summary.png")


if __name__ == "__main__":
    main()
