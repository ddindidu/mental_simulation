#!/usr/bin/env python3
"""
evaluation_v4.md — Main Metrics by Disease x Doctor Model

Heatmaps (one per main metric, §1/§2/§3/§4 of evaluation_v4.md) with disease
(ground-truth D-code) on the y-axis and doctor model on the x-axis, pooled
across judges and patients (this run has 2 judges; a cell averages whatever
episodes exist for that disease/doctor across both):

  Jaccard        <- analysis/<patient>/<judge>/<doctor>/turn_eval.json (turn-pooled mean)
  IAS            <- results/<patient>/<judge>/<doctor>/question_eval.json
                    (episode_metrics.llm_judge.mean_ias, episode-pooled mean)
  Turn Count     <- results/<patient>/<judge>/<doctor>/efficiency_eval.json
  Final Accuracy <- results/<patient>/<judge>/<doctor>/efficiency_eval.json

Reads raw per-episode/per-turn files directly (disease-level breakdown isn't
in the summarize_v4_metrics_csv.py CSV, which only aggregates per combo), so
this always reflects RESULTS_ROOT / ANALYSIS_ROOT for the resolved run
(MS_RUN), filtered the same way as that CSV's --style plain.

Color direction: for every panel, DARKER = BETTER — Jaccard/IAS/Final
Accuracy use a normal sequential ramp (high value = dark), Turn Count uses
the reversed ramp (low turn count = dark), so a reader can scan all four
panels with one rule instead of remembering per-metric direction. Each
panel's color scale is normalized to that metric's own min-max across cells
(not shared across panels — the four metrics have unrelated units/ranges).
A gray hatched cell means no data for that disease/doctor pair (this run:
none expected, since efficiency_eval.json covers all disease/doctor pairs,
but IAS/Jaccard can have gaps if the LLM-judge or symptom-extraction stage
hasn't finished for a combo).

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
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT

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

METRICS = [
    ("jaccard", "Jaccard (Inference Quality)", "Blues", False),
    ("ias", "IAS (Information Acquisition)", "Blues", False),
    ("turn_count", "Turn Count (Efficiency)", "Blues_r", False),
    ("final_accuracy_pct", "Final Accuracy % (Reliable Dx)", "Blues", True),
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
            jac = row.get("jaccard")
            if gt is None or jac is None:
                continue
            values["jaccard"][(gt, doctor)].append(jac)

    for qe_path in sorted(RESULTS_ROOT.glob("*/*/*/question_eval.json")):
        doctor = qe_path.parts[-2]
        if doctor.lower() not in SELECTED_DOCTORS:
            continue
        for ep in json.loads(qe_path.read_text(encoding="utf-8")):
            if not _style_ok(ep.get("log_file", ""), style):
                continue
            gt = ep.get("ground_truth")
            jm = (ep.get("episode_metrics") or {}).get("llm_judge") or {}
            ias = jm.get("mean_ias")
            if gt is None or ias is None:
                continue
            values["ias"][(gt, doctor)].append(ias)

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

    fig, axes = plt.subplots(2, 2, figsize=(5.2 + 0.85 * len(doctors), 2.4 + 0.42 * len(diseases)))
    axes = axes.flatten()

    for ax, (key, title, cmap, is_pct) in zip(axes, METRICS):
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
        ax.set_xticklabels(doctors, rotation=45, ha="right", fontsize=7.5)
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
    #     "evaluation_v4.md — Main Metrics by Disease x Doctor Model\n"
    #     "(darker = better in every panel; hatched = no data; pooled across judges/patients)",
    #     fontsize=13, fontweight="bold", y=1.01,
    # )

    fig.tight_layout()
    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "v4_metrics_by_disease.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=170, bbox_inches="tight")
    print(f"[saved] {out_path}")

    # legend of disease id -> name, since only the D-code fits on the y-axis
    print("\nDisease ID -> name:")
    for d in diseases:
        print(f"  {d}: {disease_name[d]}")


if __name__ == "__main__":
    main()
