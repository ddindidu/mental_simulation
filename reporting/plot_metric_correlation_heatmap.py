#!/usr/bin/env python3
"""
evaluation_v5.md — Cross-Metric Correlation Heatmap, by Judge Model x Doctor Model (episode-wise)

For each (judge, doctor) combo, builds the Pearson correlation matrix across
8 headline metrics on that combo's episode-level data (style=plain by
default) — one matrix per doctor model per judge, e.g. ~345 rows for a
combo that ran 345 plain episodes (not pooled across doctors):

  Jaccard, Precision, Recall                           — §1 Diagnostic Hypothesis Quality
                                                           (turn_eval.json,
                                                           LAST turn per episode)
  QTS                                                   — §2 Diagnostic Question Quality
                                                           (question_eval.json,
                                                           episode_metrics.llm_judge.mean_qts)
  Total Turns, 1st-Confidence Turn                     — §3 Diagnostic Efficiency
                                                           (efficiency_eval.json)
  Diagnostic Evidence Sufficiency (_pred), Final Accuracy — §4 Diagnostic Decision Quality
                                                           (diagnostic_reasoning_eval.json,
                                                           efficiency_eval.json)

All four sources are joined by log_file within each (patient, judge, doctor)
combo; an episode missing any of the 8 fields still contributes to every
pairwise correlation that doesn't need the missing field (pairwise-complete,
not listwise-complete).

Usage:
  python reporting/plot_metric_correlation_heatmap.py [--style plain] [-o OUT_PREFIX]

  MS_RUN=run_batch_20260912 python reporting/plot_metric_correlation_heatmap.py

Output: <out_prefix><judge>_<doctor>.png, one file per (judge, doctor) combo.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

import os
os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.metric_compat import episode_mean_qts, turn_qts, csv_qts, csv_hypothesis
from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT
from reporting.plot_v4_radar_by_judge import DOCTOR_NAME_CANONICAL

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

# (row key, axis label) — row key indexes into each episode's dict, built below.
METRICS = [
    ("jaccard_rigid", "Jaccard\n"),
    #("precision_rigid", "Precision\n"),
    #("recall_rigid", "Recall\n"),
    ("qts", "QTS"),
    ("turn_count", "Total\nTurns"),
    # ("turn_to_1st_confident", "1st-Confidence\nTurn"),
    ("diagnostic_evidence_sufficiency_pred", "Evidence\nSufficiency"),
    ("final_accuracy", "Final\nAccuracy"),
]


def discover_combos() -> list[tuple[str, str, str]]:
    combos = []
    for te_path in sorted(ANALYSIS_ROOT.rglob("turn_eval.json")):
        rel = te_path.parent.relative_to(ANALYSIS_ROOT)
        if len(rel.parts) != 3:
            continue
        patient, judge, doctor = rel.parts
        if doctor.lower() not in SELECTED_DOCTORS:
            continue
        combos.append((patient, judge, doctor))
    return combos


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _filter_style(data: list[dict], style: str | None) -> list[dict]:
    if not style:
        return data
    return [row for row in data if str(row.get("log_file", "")).endswith(f"_{style}")]


def episode_rows(patient: str, judge: str, doctor: str, style: str | None) -> list[dict]:
    """One dict per episode (log_file) with the 8 METRICS fields, pooled from
    turn_eval.json (last turn), efficiency_eval.json, diagnostic_reasoning_eval.json,
    and question_eval.json."""
    turn_data = _filter_style(
        _load(ANALYSIS_ROOT / patient / judge / doctor / "turn_eval.json"), style)
    eff_data = _filter_style(
        _load(RESULTS_ROOT / patient / judge / doctor / "efficiency_eval.json"), style)
    dr_data = _filter_style(
        _load(RESULTS_ROOT / patient / judge / doctor / "diagnostic_reasoning_eval.json"), style)
    q_data = _filter_style(
        _load(RESULTS_ROOT / patient / judge / doctor / "question_eval.json"), style)

    last_turn_by_log: dict[str, dict] = {}
    for row in turn_data:
        log_file = row.get("log_file")
        turn = row.get("turn")
        if log_file is None or turn is None:
            continue
        prev = last_turn_by_log.get(log_file)
        if prev is None or turn > prev["turn"]:
            last_turn_by_log[log_file] = row

    eff_by_log = {r["log_file"]: r for r in eff_data if r.get("log_file")}
    dr_by_log = {r["log_file"]: r for r in dr_data if r.get("log_file")}
    ias_by_log = {}
    for r in q_data:
        log_file = r.get("log_file")
        if not log_file:
            continue
        v = episode_mean_qts(r)
        if v is not None:
            ias_by_log[log_file] = v

    log_files = set(last_turn_by_log) | set(eff_by_log) | set(dr_by_log) | set(ias_by_log)
    rows = []
    for log_file in log_files:
        turn_row = last_turn_by_log.get(log_file, {})
        eff_row = eff_by_log.get(log_file, {})
        dr_row = dr_by_log.get(log_file, {})
        rows.append({
            "jaccard_rigid": turn_row.get("jaccard_rigid"),
            "precision_rigid": turn_row.get("precision_rigid"),
            "recall_rigid": turn_row.get("recall_rigid"),
            "qts": ias_by_log.get(log_file),
            "turn_count": eff_row.get("turn_count"),
            "turn_to_1st_confident": eff_row.get("time_to_first_confident_narrowing"),
            "diagnostic_evidence_sufficiency_pred": dr_row.get("overall_score_pred"),
            "final_accuracy": eff_row.get("final_accuracy"),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default="plain",
                         help="Only include episodes whose log filename ends in "
                              "_<style> (default: plain). Pass '' for all styles.")
    parser.add_argument("-o", "--out-prefix", default=None,
                         help="Output PNG path prefix, one file per judge: "
                              "<prefix><judge>.png (default: analysis/<run>/metric_correlation_)")
    args = parser.parse_args()
    style = args.style or None

    out_prefix = Path(args.out_prefix) if args.out_prefix else ANALYSIS_ROOT / "metric_correlation_"

    combos = discover_combos()
    if not combos:
        print(f"No turn_eval.json found under {ANALYSIS_ROOT} for doctors {sorted(SELECTED_DOCTORS)}")
        return

    by_combo: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for patient, judge, doctor in combos:
        by_combo[(judge, doctor)].extend(episode_rows(patient, judge, doctor, style))

    n_metrics = len(METRICS)
    for judge, doctor in sorted(by_combo):
        rows = by_combo[(judge, doctor)]
        data = np.full((n_metrics, len(rows)), np.nan)
        for mi, (key, _label) in enumerate(METRICS):
            for ri, row in enumerate(rows):
                v = row.get(key)
                if v is not None:
                    data[mi, ri] = float(v)

        n_present = [int(np.sum(~np.isnan(data[mi]))) for mi in range(n_metrics)]
        print(f"[{judge}/{doctor}] {len(rows)} episodes; non-missing per metric: "
              + ", ".join(f"{label.split(chr(10))[0]}={n}" for (_k, label), n in zip(METRICS, n_present)))

        corr = np.full((n_metrics, n_metrics), np.nan)
        for a in range(n_metrics):
            for b in range(n_metrics):
                va, vb = data[a], data[b]
                mask = ~np.isnan(va) & ~np.isnan(vb)
                if mask.sum() >= 2 and np.std(va[mask]) > 0 and np.std(vb[mask]) > 0:
                    corr[a, b] = np.corrcoef(va[mask], vb[mask])[0, 1]

        # Upper triangle only (strictly above the diagonal) — the matrix is
        # symmetric and the diagonal is trivially 1.00, so both are masked
        # out rather than drawn. The last row (a = n_metrics-1) would have
        # no b > a left to show, so it's dropped entirely rather than kept
        # as a blank row.
        n_rows = n_metrics - 1
        disp = corr[:n_rows, :].copy()
        disp[np.tril_indices(n_rows, m=n_metrics)] = np.nan
        masked = np.ma.masked_invalid(disp)
        cmap = plt.get_cmap("RdBu").copy()
        cmap.set_bad(color="white")

        fig, ax = plt.subplots(figsize=(9.5, 7.6))
        im = ax.imshow(masked, cmap=cmap, vmin=-1, vmax=1, aspect="equal")

        for a in range(n_rows):
            for b in range(a + 1, n_metrics):
                v = corr[a, b]
                text = "n/a" if np.isnan(v) else f"{v:.2f}"
                color = "white" if (not np.isnan(v) and abs(v) > 0.6) else "#2a2a28"
                ax.text(b, a, text, ha="center", va="center", fontsize=10.5, color=color)

        labels = [label for _k, label in METRICS]
        ax.set_xticks(range(n_metrics))
        ax.set_xticklabels(labels, fontsize=10, rotation=40, ha="right")
        ax.set_yticks(range(n_rows))
        ax.set_yticklabels(labels[:n_rows], fontsize=10)
        ax.set_xticks(np.arange(-0.5, n_metrics, 1), minor=True)
        ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.5)
        ax.tick_params(which="minor", length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Pearson correlation (r)", fontsize=11)
        cbar.ax.tick_params(labelsize=9)

        # ax.set_title(
        #     f"Judge: {JUDGE_NAME_CANONICAL.get(judge, judge)} — "
        #     f"Doctor: {DOCTOR_NAME_CANONICAL.get(doctor, doctor)}\n"
        #     f"(n = {len(rows)} episodes)",
        #     fontsize=12.5, fontweight="bold", pad=14,
        # )

        fig.tight_layout()
        out_path = Path(f"{out_prefix}{judge}_{doctor}.png")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=170, bbox_inches="tight", pad_inches=0.3)
        plt.close(fig)
        print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
