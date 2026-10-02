#!/usr/bin/env python3
"""
QTS (formerly IAS) Variants — Discriminative-only vs. +Mandatory vs. +Mandatory+Optional

Recomputes IAS under 3 definitions of the "informative target set" I_t (see
reporting/ias_variants.py for the exact formulas — all 3 are re-derived from
fields already stored per turn in results/.../question_eval.json, no KG
re-lookup needed):

  ias_disc           I_t = discriminative symptoms only
  ias_disc_mand      I_t = discriminative + mandatory (current production IAS)
  ias_disc_mand_opt  I_t = discriminative + mandatory + optional

Pools every episode across both judge buckets (gemini-3.1-pro-preview,
gpt-5.6-terra) and the 5 selected doctors, per style (default: plain).
Prints a per-(judge,doctor) summary table of episode-mean IAS for each
variant, the trend across variants (each is a superset of the last, so the
mean is mathematically guaranteed non-decreasing — the interesting number is
how MUCH each addition moves the mean), and draws a grouped bar chart.

Usage:
  python reporting/plot_v4_ias_variants_summary.py [--style plain] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_v4_ias_variants_summary.py
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT
from reporting.plot_v4_radar_by_judge import DOCTOR_NAME_CANONICAL
from reporting.ias_variants import IAS_VARIANT_KEYS, IAS_VARIANT_LABELS, episode_ias_variants

JUDGE_NAME_CANONICAL = {
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
    "gpt-5.6-terra": "GPT 5.6 Terra",
}

SELECTED_DOCTORS = {
    "gpt-5.4",
    "gemini-3.8-flash",
    "claude-sonnet-5",
    "llama-3.3-70b-instruct",
    "qwen3-235b",
}

MODEL_ORDER = ["gpt-5.4", "gemini-3.8-flash", "claude-sonnet-5", "qwen3-235b", "llama-3.3-70b-instruct"]


def _order_rank(doctor: str) -> int:
    d = doctor.lower()
    return MODEL_ORDER.index(d) if d in MODEL_ORDER else len(MODEL_ORDER)


def load_variant_means(style: str | None) -> dict[tuple[str, str], dict[str, list[float]]]:
    """(judge, doctor) -> {variant_key: [episode-mean values]}"""
    by_combo: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: {k: [] for k in IAS_VARIANT_KEYS}
    )
    for qe_path in sorted(RESULTS_ROOT.glob("*/*/*/question_eval.json")):
        judge, doctor = qe_path.parts[-3], qe_path.parts[-2]
        if doctor.lower() not in SELECTED_DOCTORS:
            continue
        episodes = json.loads(qe_path.read_text(encoding="utf-8"))
        for ep in episodes:
            if style and not str(ep.get("log_file", "")).endswith(f"_{style}"):
                continue
            means = episode_ias_variants(ep, mapper="llm_judge")
            if means is None:
                continue
            for k in IAS_VARIANT_KEYS:
                by_combo[(judge, doctor)][k].append(means[k])
    return by_combo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default="plain",
                         help="Only include episodes whose log filename ends in "
                              "_<style> (default: plain). Pass '' for all styles.")
    parser.add_argument("-o", "--out", default=None, help="Output PNG path")
    args = parser.parse_args()
    style = args.style or None

    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "v4_ias_variants_summary.png"

    by_combo = load_variant_means(style)
    if not by_combo:
        print(f"No question_eval.json data found under {RESULTS_ROOT}")
        return

    judges = sorted({j for j, _d in by_combo})
    doctors = sorted({d for _j, d in by_combo}, key=_order_rank)

    # ── per-(judge, doctor) summary table ───────────────────────────────
    print(f"=== IAS variant summary (episode-mean, style={style or 'all'}) ===\n")
    header = f"{'judge':22s} {'doctor':22s}" + "".join(f"{k:>20s}" for k in IAS_VARIANT_KEYS) + "    n"
    print(header)
    print("-" * len(header))
    summary: dict[tuple[str, str], dict[str, float]] = {}
    for judge in judges:
        for doctor in doctors:
            vals = by_combo.get((judge, doctor))
            if not vals or not vals[IAS_VARIANT_KEYS[0]]:
                continue
            means = {k: float(np.mean(vals[k])) for k in IAS_VARIANT_KEYS}
            summary[(judge, doctor)] = means
            n = len(vals[IAS_VARIANT_KEYS[0]])
            row = f"{judge:22s} {doctor:22s}" + "".join(f"{means[k]:20.4f}" for k in IAS_VARIANT_KEYS)
            print(row + f"  {n:4d}")

    # ── overall trend (pooled across all combos) ────────────────────────
    print("\n=== Overall trend (mean across all (judge, doctor) episode-means) ===")
    overall = {k: float(np.mean([m[k] for m in summary.values()])) for k in IAS_VARIANT_KEYS}
    for k in IAS_VARIANT_KEYS:
        print(f"  {IAS_VARIANT_LABELS[k]:52s} {overall[k]:.4f}")
    d1 = overall["ias_disc_mand"] - overall["ias_disc"]
    d2 = overall["ias_disc_mand_opt"] - overall["ias_disc_mand"]
    print(f"\n  disc -> disc+mand       : +{d1:.4f}  ({100*d1/overall['ias_disc']:.1f}% relative increase)"
          if overall["ias_disc"] else f"\n  disc -> disc+mand       : +{d1:.4f}")
    print(f"  disc+mand -> disc+mand+opt: +{d2:.4f}  "
          f"({100*d2/overall['ias_disc_mand']:.1f}% relative increase)"
          if overall["ias_disc_mand"] else f"  disc+mand -> disc+mand+opt: +{d2:.4f}")
    print(f"\n  (guaranteed non-decreasing by construction — each variant's informative "
          f"set is a superset of the previous one, see reporting/ias_variants.py docstring. "
          f"The interesting number is the SIZE of each jump, i.e. how much of the current "
          f"IAS's 'credit' is coming from discriminative symptoms alone vs. needing the "
          f"mandatory/optional pools to count questions as informative.)")

    # ── grouped bar chart: doctor x variant, one panel per judge ───────
    fig, axes = plt.subplots(1, len(judges), figsize=(6.5 * len(judges), 5.5), squeeze=False)
    axes = axes[0]
    colors = ["#0072B2", "#56B4E9", "#009E73"]
    bar_w = 0.25
    for ax, judge in zip(axes, judges):
        combo_doctors = [d for d in doctors if (judge, d) in summary]
        x = np.arange(len(combo_doctors))
        for vi, k in enumerate(IAS_VARIANT_KEYS):
            vals = [summary[(judge, d)][k] for d in combo_doctors]
            ax.bar(x + (vi - 1) * bar_w, vals, width=bar_w, color=colors[vi],
                   label=IAS_VARIANT_LABELS[k], zorder=3)
        ax.set_xticks(x)
        ax.set_xticklabels([DOCTOR_NAME_CANONICAL.get(d, d) for d in combo_doctors],
                            fontsize=10, rotation=20, ha="right")
        ax.set_ylabel("Mean QTS (episode-level)", fontsize=12)
        ax.set_title(f"Judge: {JUDGE_NAME_CANONICAL.get(judge, judge)}", fontsize=12, fontweight="bold")
        ax.grid(axis="y", color="#e1e0d9", linewidth=1, zorder=0)
        ax.set_axisbelow(True)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        ax.tick_params(axis="both", labelsize=10)

    axes[0].legend(fontsize=9, loc="upper left")
    fig.suptitle("QTS Variants by Doctor Model", fontsize=14, fontweight="bold")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"\n[saved] {out_path}")


if __name__ == "__main__":
    main()
