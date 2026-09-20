#!/usr/bin/env python3
"""
Correctness x Evidence Sufficiency — Stacked Bars, by Judge Model

For each doctor model, splits all episodes into four mutually exclusive
categories (correct = final_accuracy==1, "supported" = diagnostic_reasoning
overall_score >= threshold):

  correct_high   ("Correct & Supported"):            correct   + high reasoning
  correct_low    ("Correct but Under-supported"):     correct   + low reasoning
  incorrect_high ("Incorrect but Supported"):          incorrect + high reasoning
  incorrect_low  ("Incorrect & Under-supported"):      incorrect + low reasoning

Draws one 100%-stacked bar per doctor model (one panel per judge), each bar
split into the four categories above (share of that model's episodes), so
models can be compared directly by how much of each bar each category takes.

Joins results/<patient>/<judge>/<doctor>/efficiency_eval.json (final_accuracy
per episode) with .../diagnostic_reasoning_eval.json (overall_score per
episode) by log_file — same data source as plot_lucky_guess_rate.py.

Usage:
  python reporting/plot_quadrant_flower.py [--style plain] [--threshold 0.5] [-o OUT_PREFIX]

  MS_RUN=run_batch_20260912 python reporting/plot_quadrant_flower.py
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

from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT, RUN_ROOT
from reporting.plot_overcommitment_by_judge import EXCLUDE_DOCTORS, _order_rank
from reporting.plot_v4_radar_by_judge import DOCTOR_NAME_CANONICAL


def discover_combos() -> list[tuple[str, str, str, Path, Path]]:
    """(patient, judge, doctor, efficiency_eval.json, diagnostic_reasoning_eval.json)
    for every doctor dir that has both files."""
    combos = []
    for eff_path in sorted(RESULTS_ROOT.rglob("efficiency_eval.json")):
        combo_dir = eff_path.parent
        dr_path = combo_dir / "diagnostic_reasoning_eval.json"
        if not dr_path.exists():
            continue
        rel = combo_dir.relative_to(RESULTS_ROOT)
        if len(rel.parts) != 3:
            continue
        patient, judge, doctor = rel.parts
        combos.append((patient, judge, doctor, eff_path, dr_path))
    return combos


def joined_episodes(eff_path: Path, dr_path: Path, style: str | None) -> list[tuple[float, float]]:
    """(overall_score, final_accuracy) pairs joined by log_file."""
    eff_data = json.loads(eff_path.read_text(encoding="utf-8"))
    dr_data = json.loads(dr_path.read_text(encoding="utf-8"))
    if not isinstance(eff_data, list) or not isinstance(dr_data, list):
        return []
    acc_by_log = {row["log_file"]: row.get("final_accuracy") for row in eff_data if row.get("log_file")}
    pairs = []
    for row in dr_data:
        log_file = row.get("log_file")
        if not log_file or (style and not log_file.endswith(f"_{style}")):
            continue
        score = row.get("overall_score")
        acc = acc_by_log.get(log_file)
        if score is None or acc is None:
            continue
        pairs.append((float(score), float(acc)))
    return pairs

# Stack order bottom-to-top: correct segments first, then incorrect;
# "supported" (high reasoning) before "under-supported" (low reasoning)
# within each. Colors: green family = correct, red family = incorrect;
# darker = supported, lighter = under-supported. "Supported" segments also
# get a diagonal-dash hatch so the correct/incorrect vs. supported/
# under-supported split reads even without color (e.g. print, CVD).
CATEGORIES = [
    ("correct_high", "Correct and Supported", "#083D77", "//"),
    ("correct_low", "Correct but Under-supported", "#9BD1E5", None),
    ("incorrect_high", "Incorrect but Supported", "#FFA5AB", "//"),
    ("incorrect_low", "Incorrect and Under-supported", "#BF2829", None),
]


def category_shares(eps: list[tuple[float, float]], threshold: float) -> dict[str, float]:
    total = len(eps)
    if total == 0:
        return {k: 0.0 for k, *_r in CATEGORIES}
    counts = {k: 0 for k, *_r in CATEGORIES}
    for score, acc in eps:
        high = score >= threshold
        correct = acc == 1.0
        if correct and high:
            counts["correct_high"] += 1
        elif correct and not high:
            counts["correct_low"] += 1
        elif not correct and not high:
            counts["incorrect_low"] += 1
        else:
            counts["incorrect_high"] += 1
    return {k: 100.0 * v / total for k, v in counts.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default="plain",
                         help="Only include episodes whose log filename ends in "
                              "_<style> (default: plain). Pass '' for all styles.")
    parser.add_argument("--threshold", type=float, default=0.5,
                         help="overall_score >= this counts as 'supported' (default: 0.5)")
    parser.add_argument("-o", "--out-prefix", default=None,
                         help="Output PNG path prefix, one file per judge: "
                              "<prefix><judge>.png (default: analysis/<run>/quadrant_flower_)")
    args = parser.parse_args()
    style = args.style or None
    threshold = args.threshold

    out_prefix = Path(args.out_prefix) if args.out_prefix else ANALYSIS_ROOT / "quadrant_flower_"

    combos = discover_combos()
    combos = [c for c in combos if c[2].lower() not in EXCLUDE_DOCTORS]
    if not combos:
        print("No combos with both efficiency_eval.json and diagnostic_reasoning_eval.json found.")
        return

    judges = sorted({j for _p, j, _d, _e, _dr in combos})
    panels: dict[str, list[tuple[str, dict, int]]] = {}
    for patient, judge, doctor, eff_path, dr_path in combos:
        eps = joined_episodes(eff_path, dr_path, style)
        if not eps:
            continue
        shares = category_shares(eps, threshold)
        panels.setdefault(judge, []).append((doctor, shares, len(eps)))

    judges = [j for j in judges if j in panels]
    if not judges:
        print("No judge panel produced data.")
        return

    for judge in judges:
        rows = sorted(panels[judge], key=lambda x: _order_rank(x[0]))
        doctors = [d for d, _s, _n in rows]
        x = np.arange(len(doctors))

        fig, ax = plt.subplots(figsize=(1.55 * len(doctors) + 2.5, 6.5))

        bottom = np.zeros(len(doctors))
        for key, label, color, hatch in CATEGORIES:
            vals = np.array([shares[key] for _d, shares, _n in rows])
            ax.bar(x, vals, bottom=bottom, width=0.62, color=color, hatch=hatch,
                   edgecolor="white", linewidth=0.8, zorder=3, label=label)
            for xi, (v, b) in enumerate(zip(vals, bottom)):
                if v > 4:
                    ax.text(xi, b + v / 2, f"{v:.0f}%", ha="center", va="center",
                            fontsize=14, color="white", fontweight="bold",
                            backgroundcolor=color,
                            zorder=4)
            bottom += vals

        ax.set_xticks(x)
        ax.set_xticklabels([DOCTOR_NAME_CANONICAL.get(d, d) for d in doctors], fontsize=16)
        ax.set_ylim(0, 100)
        ax.set_ylabel("Share of Interviews (%)", fontsize=17)
        ax.tick_params(axis="y", labelsize=15)
        ax.grid(axis="y", color="#E4EBF5", linewidth=0.8, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        # ax.set_title(f"Judge: {judge}", fontsize=13, fontweight="bold", pad=14)

        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2,
                  fontsize=14, frameon=False)

        # style_note = f"style={style}" if style else "all styles"
        # fig.suptitle(
        #     f"Correctness x Evidence Sufficiency — judge: {judge}\n"
        #     f"(share of that model's episodes in each category; threshold={threshold}; "
        #     f"{style_note}; {RUN_ROOT.name})",
        #     fontsize=13, fontweight="bold", y=1.02,
        # )

        fig.tight_layout()
        out_path = Path(f"{out_prefix}{judge}.png")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.35)
        plt.close(fig)
        print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
