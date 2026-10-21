#!/usr/bin/env python3
"""
evaluation_v5.md — Main Metrics by Disease x Doctor Model

Heatmaps (one per metric) with disease (ground-truth D-code) on the y-axis
and doctor model on the x-axis, pooled across judges and patients (this run
has 2 judges; a cell averages whatever episodes exist for that
disease/doctor across both). 7 panels, grouped into the same 4 dimensions
reporting/cross_model/plot_v4_radar_by_judge.py uses (Hypothesis Q. /
Question Q. / Efficiency / Decision Q.):

  row 1 - Hypothesis Quality: Jaccard, Precision, Recall
          <- analysis/<patient>/<judge>/<doctor>/turn_eval.json (turn-pooled mean, *_rigid fields)
  row 2 - Question Quality (QTS), Efficiency (Total Turn),
          Decision Quality (Diagnostic Evidence Sufficiency, Accuracy)
          <- results/<patient>/<judge>/<doctor>/question_eval.json
             (episode_metrics.llm_judge.mean_qts, episode-pooled mean)
          <- results/<patient>/<judge>/<doctor>/efficiency_eval.json (turn_count, final_accuracy)
          <- results/<patient>/<judge>/<doctor>/diagnostic_reasoning_eval.json
             (overall_score_pred, episode-pooled mean)

Reads raw per-episode/per-turn files directly (disease-level breakdown isn't
in the summarize_v4_metrics_csv.py CSV, which only aggregates per combo), so
this always reflects RESULTS_ROOT / ANALYSIS_ROOT for the resolved run
(MS_RUN), filtered the same way as that CSV's --style plain.

Color: one colormap family per dimension (matching how
plot_v4_radar_by_judge.py groups its 5 radar axes into those same 4
dimensions), so every panel in a dimension reads as "the same kind of
thing" at a glance: Hypothesis Quality = Blues, Question Quality = Purples,
Efficiency = Oranges, Decision Quality = Greens. DARKER = BETTER in every
panel — Efficiency uses the reversed ramp (low turn count = dark) since
fewer turns is better, everything else uses the normal ramp (high value =
dark). Each panel's color scale is normalized to that metric's own min-max
across cells (not shared across panels or dimensions). A gray hatched cell
means no data for that disease/doctor pair (this run: none expected for
Efficiency/Accuracy, since efficiency_eval.json covers all disease/doctor
pairs, but Hypothesis/Question/Decision metrics can have gaps if the
LLM-judge or symptom-extraction stage hasn't finished for a combo).

Usage:
  python reporting/plot_v4_metrics_by_disease.py [--style plain] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_v4_metrics_by_disease.py --style plain
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
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.metric_compat import episode_mean_qts, turn_qts, csv_qts, csv_hypothesis
from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT
from reporting.cross_model.plot_v4_radar_by_judge import DOCTOR_NAME_CANONICAL

SELECTED_DOCTORS = {
    "gpt-5.4",
    "gemini-3.8-flash",
    "claude-sonnet-5",
    "llama-3.3-70b-instruct",
    "qwen3-235b",
}

# Fixed column order (provider-grouped), matching the other v4 scripts;
# models not listed here are appended, alphabetically, at the end.
MODEL_ORDER = [
    "gpt-5.4", "gpt-5.6-luna",
    "gemini-3.8-flash", "gemini-3.1-flash-lite",
    "claude-sonnet-5", "claude-haiku-4.5",
    "qwen3-235b",
    "llama-3.3-70b-instruct",
]

# One colormap per dimension, matching plot_v4_radar_by_judge.py's grouping
# of its 5 axes into these same 4 dimensions (Hypothesis Q. / Question Q. /
# Efficiency / Decision Q.) — every panel in a dimension shares its hue.
DIMENSION_CMAP = {
    "Hypothesis Quality": "Purples",
    "Question Quality": "Blues",
    "Efficiency": "Oranges",
    "Decision Quality": "Greens",
}

# (key, dimension, metric label, reversed-ramp (low value = dark), is-percent)
METRICS = [
    ("jaccard_rigid", "Hypothesis Quality", "Jaccard", False, False),
    ("precision_rigid", "Hypothesis Quality", "Precision", False, False),
    ("recall_rigid", "Hypothesis Quality", "Recall", False, False),
    ("ias", "Question Quality", "QTS", False, False),
    ("turn_count", "Efficiency", "Total Turn", True, False),
    ("evidence_sufficiency_pred", "Decision Quality", "Diagnostic Evidence Sufficiency", False, False),
    ("final_accuracy_pct", "Decision Quality", "Accuracy", False, True),
]


def _style_ok(log_file: str, style: str | None) -> bool:
    return not style or str(log_file).endswith(f"_{style}")


def load_data(style: str | None) -> tuple[dict[str, dict[tuple[str, str], list]], dict[str, str]]:
    """Returns ({metric_key: {(disease, doctor): [values]}}, {disease: name})."""
    values: dict[str, dict[tuple[str, str], list]] = {k: defaultdict(list) for k, *_ in METRICS}
    disease_name: dict[str, str] = {}

    for te_path in sorted(ANALYSIS_ROOT.glob("*/*/*/turn_eval.json")):
        doctor = te_path.parts[-2]
        if doctor.lower() not in SELECTED_DOCTORS:
            continue
        for row in json.loads(te_path.read_text(encoding="utf-8")):
            if not _style_ok(row.get("log_file", ""), style):
                continue
            gt = row.get("ground_truth")
            if gt is None:
                continue
            for key in ("jaccard_rigid", "precision_rigid", "recall_rigid"):
                v = row.get(key)
                if v is not None:
                    values[key][(gt, doctor)].append(v)

    for qe_path in sorted(RESULTS_ROOT.glob("*/*/*/question_eval.json")):
        doctor = qe_path.parts[-2]
        if doctor.lower() not in SELECTED_DOCTORS:
            continue
        for ep in json.loads(qe_path.read_text(encoding="utf-8")):
            if not _style_ok(ep.get("log_file", ""), style):
                continue
            gt = ep.get("ground_truth")
            ias = episode_mean_qts(ep)
            if gt is None or ias is None:
                continue
            values["ias"][(gt, doctor)].append(ias)

    for dr_path in sorted(RESULTS_ROOT.glob("*/*/*/diagnostic_reasoning_eval.json")):
        doctor = dr_path.parts[-2]
        if doctor.lower() not in SELECTED_DOCTORS:
            continue
        for ep in json.loads(dr_path.read_text(encoding="utf-8")):
            if not _style_ok(ep.get("log_file", ""), style):
                continue
            gt = ep.get("ground_truth")
            score = ep.get("overall_score_pred")
            if gt is None or score is None:
                continue
            values["evidence_sufficiency_pred"][(gt, doctor)].append(score)

    for ee_path in sorted(RESULTS_ROOT.glob("*/*/*/efficiency_eval.json")):
        doctor = ee_path.parts[-2]
        if doctor.lower() not in SELECTED_DOCTORS:
            continue
        for ep in json.loads(ee_path.read_text(encoding="utf-8")):
            if not _style_ok(ep.get("log_file", ""), style):
                continue
            gt = ep.get("ground_truth")
            if gt is None:
                continue
            disease_name.setdefault(gt, ep.get("ground_truth_name", gt))
            if ep.get("turn_count") is not None:
                values["turn_count"][(gt, doctor)].append(ep["turn_count"])
            if ep.get("final_accuracy") is not None:
                values["final_accuracy_pct"][(gt, doctor)].append(100.0 * ep["final_accuracy"])

    return values, disease_name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default=None, help="Filter episodes by log filename suffix (e.g. 'plain').")
    parser.add_argument("-o", "--out", default=None, help="Output PNG path.")
    args = parser.parse_args()

    values, disease_name = load_data(args.style)
    if not disease_name:
        print("No efficiency_eval.json data found under RESULTS_ROOT.")
        return

    diseases = sorted(disease_name.keys(), key=lambda d: int(d[1:]))

    all_doctors: set[str] = set()
    for m_vals in values.values():
        for _gt, doctor in m_vals:
            all_doctors.add(doctor)
    order_rank = {name: i for i, name in enumerate(MODEL_ORDER)}
    doctors = sorted(all_doctors, key=lambda d: (order_rank.get(d, len(MODEL_ORDER)), d))

    panel_w = (5.2 + 0.85 * len(doctors)) / 2
    panel_h = (2.4 + 0.42 * len(diseases)) / 2
    fig, axes = plt.subplots(2, 4, figsize=(panel_w * 4, panel_h * 2))
    # Row 1: Hypothesis Quality x3 (col 3 unused). Row 2: Question Quality,
    # Efficiency, Decision Quality x2.
    axes[0, 3].axis("off")
    panel_axes = [axes[0, 0], axes[0, 1], axes[0, 2],
                  axes[1, 0], axes[1, 1], axes[1, 2], axes[1, 3]]

    for ax, (key, dimension, metric_label, reversed_ramp, is_pct) in zip(panel_axes, METRICS):
        title = f"{dimension} ({metric_label})"
        cmap = DIMENSION_CMAP[dimension] + ("_r" if reversed_ramp else "")
        m_vals = values[key]
        grid = np.full((len(diseases), len(doctors)), np.nan)
        for i, d in enumerate(diseases):
            for j, doc in enumerate(doctors):
                vals = m_vals.get((d, doc))
                if vals:
                    grid[i, j] = float(np.mean(vals))

        masked = np.ma.masked_invalid(grid)
        im = ax.imshow(masked, cmap=cmap, aspect="auto")

        # Hatch the missing cells so "no data" reads distinctly from "low value".
        for i in range(len(diseases)):
            for j in range(len(doctors)):
                if np.isnan(grid[i, j]):
                    ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, hatch="////",
                                                fill=False, edgecolor="#c3c2b7", linewidth=0))

        ax.set_xticks(range(len(doctors)))
        ax.set_xticklabels([DOCTOR_NAME_CANONICAL.get(d.lower(), d) for d in doctors],
                           rotation=45, ha="right", fontsize=7.5)
        ax.set_yticks(range(len(diseases)))
        ax.set_yticklabels(diseases, fontsize=7.5)
        ax.set_title(title, fontsize=10.5, fontweight="bold")
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_xticks(np.arange(-0.5, len(doctors), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(diseases), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.2)
        ax.tick_params(which="minor", length=0)

        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cbar.ax.tick_params(labelsize=7.5)
        if is_pct:
            cbar.set_label("%", fontsize=8, color="#52514e")

    # fig.suptitle(
    #     "evaluation_v5.md — Main Metrics by Disease x Doctor Model\n"
    #     "(darker = better in every panel; hatched = no data; pooled across judges/patients)",
    #     fontsize=13, fontweight="bold", y=1.01,
    # )

    fig.tight_layout()
    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "v4_metrics_by_disease.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=170, bbox_inches="tight")
    print(f"[saved] {out_path}")

    # legend of disease id -> name, since only the D-code fits on the y-axis
    print("\nDisease ID -> name:")
    for d in diseases:
        print(f"  {d}: {disease_name[d]}")


if __name__ == "__main__":
    main()
