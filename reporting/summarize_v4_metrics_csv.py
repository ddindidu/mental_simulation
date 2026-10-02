#!/usr/bin/env python3
"""
evaluation_v5.md — Cross-Combo CSV Summary of the headline metrics

Scans a run's results/ tree for every (patient, judge, doctor) combo that has
already been evaluated, and writes one CSV row per combo covering the four
evaluation dimensions:

  Diagnostic Hypothesis Quality <- analysis/<patient>/<judge>/<doctor>/turn_eval.json
                                    (jaccard / precision / recall / weighted_recall)
  Diagnostic Question Quality   <- results/<patient>/<judge>/<doctor>/question_eval.json (QTS)
  Diagnostic Efficiency         <- results/<patient>/<judge>/<doctor>/efficiency_eval.json
  Diagnostic Decision Quality   <- dialogue logs (final accuracy)
                                    + diagnostic_reasoning_eval.json (_pred)

Does not compute anything itself — it only aggregates whatever the eval/*.py
scripts have already written to disk, so a combo whose LLM-judge stage
(evaluate_question.py / score_diagnostic_reasoning.py) hasn't run yet simply
gets blank QTS / Diagnostic Evidence Sufficiency cells rather than failing.

Combo discovery: every results/<patient>/<judge>/<doctor>/final_diagnosis_eval.txt
found under RESULTS_ROOT marks one row (that script runs independent of the
candidate-set pipeline, so its presence is the cheapest "this combo has been
touched" signal).

Usage:
  python reporting/summarize_v4_metrics_csv.py [--run RUN] [--style STYLE] [-o OUT.csv]

  MS_RUN=run_batch_20260912 python reporting/summarize_v4_metrics_csv.py --style plain

--style filters every dimension down to episodes whose log filename ends in
_<style> (e.g. 'plain', 'verbose', 'reserved', 'tangent', 'pleasing'). Final
Accuracy is recomputed directly from the LOGS_ROOT dialogue logs (mirroring
eval/evaluate_final_diagnosis.py) since final_diagnosis_eval.txt only stores
the all-styles-combined aggregate; the other three dimensions filter the
already-computed per-episode JSON by its log_file field.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics as st
from pathlib import Path

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from eval.common import load_code2id, read_final_diagnosis, resolve_disease_id
from utils.metric_compat import episode_mean_qts
from utils.paths import ANALYSIS_ROOT, LOGS_ROOT, RESULTS_ROOT


FIELDS = [
    "patient", "judge", "doctor",
    "final_accuracy_pct", "final_accuracy_frac",
    "n_turns", "jaccard", "precision", "recall", "weighted_recall",
    "n_episodes_question_eval", "qts",
    "n_episodes_efficiency", "turn_count", "turn_to_1st_confident", "overcommitment_conf",
    "n_episodes_diagnostic_reasoning", "diagnostic_evidence_sufficiency_pred",
]

SELECTED_FIELDS = [
        "patient", "judge", "doctor",

        # Diagnostic Hypothesis Quality
        "jaccard", "precision", "recall", "weighted_recall",
        # Diagnostic Question Quality
        "qts",
        # Diagnostic Efficiency
        "turn_count", "turn_to_1st_confident", "overcommitment_conf",
        # Diagnostic Decision Quality
        "final_accuracy_pct", "diagnostic_evidence_sufficiency_pred",
    ]

DOCTOR_ORDER = [
    "gpt-5.4",
    "gpt-5.6-luna",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
    "claude-sonnet-5",
    "claude-haiku-4.5",
    "llama-3.3-70b-instruct",
    "qwen3-235b",
]


def _mean(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return st.mean(clean) if clean else None


def _load_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _filter_style(episodes: list[dict], style: str | None) -> list[dict]:
    if not style:
        return episodes
    return [ep for ep in episodes if str(ep.get("log_file", "")).endswith(f"_{style}")]


def _ground_truth_id(log_stem: str) -> str | None:
    m = re.match(r"(D\d+)", log_stem)
    return m.group(1) if m else None


def compute_final_accuracy(logs_dir: Path, style: str | None) -> tuple[float | None, str | None]:
    """Recomputed directly from dialogue logs (final_diagnosis_eval.txt has no
    per-style breakdown — it's always the all-styles-combined aggregate)."""
    if not logs_dir.exists():
        return None, None
    log_files = sorted(logs_dir.glob("*.json"))
    if style:
        log_files = [p for p in log_files if p.stem.endswith(f"_{style}")]
    code2id = load_code2id()
    total = correct = 0
    for log_file in log_files:
        gt = _ground_truth_id(log_file.stem)
        if gt is None:
            continue
        total += 1
        if resolve_disease_id(read_final_diagnosis(log_file), code2id) == gt:
            correct += 1
    if total == 0:
        return None, None
    return 100 * correct / total, f"{correct}/{total}"


def load_turn_eval(path: Path, style: str | None) -> dict | None:
    data = _filter_style(_load_list(path), style)
    if not data:
        return None
    # Mean over all (episode, turn) rows. *_rigid holds the tier-priority
    # reference-set value in both pre- and post-refactor turn_eval.json.
    return {
        "n": len(data),
        "jaccard":         _mean([d.get("jaccard_rigid") for d in data]),
        "precision":       _mean([d.get("precision_rigid") for d in data]),
        "recall":          _mean([d.get("recall_rigid") for d in data]),
        "weighted_recall": _mean([d.get("weighted_recall") for d in data]),
    }


def load_efficiency(path: Path, style: str | None) -> dict | None:
    data = _filter_style(_load_list(path), style)
    if not data:
        return None
    return {
        "n": len(data),
        "turn_count": _mean([d.get("turn_count") for d in data]),
        "t1_confident": _mean([d.get("time_to_first_confident_narrowing") for d in data]),
        "overcommit_conf": _mean([d.get("overcommitment_conf") for d in data]),
    }


def load_question_eval(path: Path, style: str | None) -> dict | None:
    data = _filter_style(_load_list(path), style)
    if not data:
        return None
    return {
        "n": len(data),
        "qts": _mean([episode_mean_qts(ep) for ep in data]),
    }


def load_diagnostic_reasoning(path: Path, style: str | None) -> dict | None:
    """overall_score_pred = evidence sufficiency for the doctor's own final
    diagnosis (None when that diagnosis couldn't be resolved to a disease
    id). Mean over episodes with a non-null value."""
    data = _filter_style(_load_list(path), style)
    if not data:
        return None
    pred_vals = [ep.get("overall_score_pred") for ep in data if ep.get("overall_score_pred") is not None]
    return {
        "n": len(pred_vals),
        "pred": _mean(pred_vals) if pred_vals else None,
    }


def discover_combos() -> list[tuple[str, str, str, Path]]:
    combos = []
    for fd_path in sorted(RESULTS_ROOT.rglob("final_diagnosis_eval.txt")):
        combo_dir = fd_path.parent
        rel = combo_dir.relative_to(RESULTS_ROOT)
        if len(rel.parts) != 3:
            continue
        patient, judge, doctor = rel.parts
        combos.append((patient, judge, doctor, combo_dir))
    return combos


def build_rows(style: str | None) -> list[dict]:
    rows = []
    for patient, judge, doctor, results_dir in discover_combos():        
        analysis_dir = ANALYSIS_ROOT / patient / judge / doctor
        logs_dir = LOGS_ROOT / patient / judge / doctor

        acc_pct, acc_frac = compute_final_accuracy(logs_dir, style)
        te = load_turn_eval(analysis_dir / "turn_eval.json", style)
        eff = load_efficiency(results_dir / "efficiency_eval.json", style)
        qe = load_question_eval(results_dir / "question_eval.json", style)
        dr = load_diagnostic_reasoning(results_dir / "diagnostic_reasoning_eval.json", style)

        rows.append({
            "patient": patient, "judge": judge, "doctor": doctor,
            "final_accuracy_pct": acc_pct,
            "final_accuracy_frac": acc_frac,
            "n_turns": te["n"] if te else None,
            "jaccard": te["jaccard"] if te else None,
            "precision": te["precision"] if te else None,
            "recall": te["recall"] if te else None,
            "weighted_recall": te["weighted_recall"] if te else None,
            "n_episodes_question_eval": qe["n"] if qe else None,
            "qts": qe["qts"] if qe else None,
            "n_episodes_efficiency": eff["n"] if eff else None,
            "turn_count": eff["turn_count"] if eff else None,
            "turn_to_1st_confident": eff["t1_confident"] if eff else None,
            "overcommitment_conf": eff["overcommit_conf"] if eff else None,
            "n_episodes_diagnostic_reasoning": dr["n"] if dr else None,
            "diagnostic_evidence_sufficiency_pred": dr["pred"] if dr else None,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--style", default=None,
        help="Only include episodes whose log filename ends in _<style> "
             "(e.g. 'plain'). Default: all styles combined.",
    )
    parser.add_argument(
        "-o", "--out", default=None,
        help="Output CSV path (default: analysis/<run>/v4_metrics_summary[_<style>].csv); "
             "an .xlsx with the same rows is saved alongside it",
    )
    args = parser.parse_args()

    rows = build_rows(args.style)
    if not rows:
        print(f"No combos found under {RESULTS_ROOT} (no final_diagnosis_eval.txt).")
        return

    doctor_rank = {d: i for i, d in enumerate(DOCTOR_ORDER)}
    rows.sort(key=lambda r: (
        r["patient"], r["judge"],
        doctor_rank.get(r["doctor"], len(DOCTOR_ORDER)), r["doctor"],
    ))

    rows = [{field: row[field] for field in SELECTED_FIELDS} for row in rows]

    default_name = f"v4_metrics_summary_{args.style}.csv" if args.style else "v4_metrics_summary.csv"
    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / default_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SELECTED_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} combo(s) to {out_path}")

    xlsx_path = out_path.with_suffix(".xlsx")
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "v4_metrics"
    ws.append(SELECTED_FIELDS)
    for row in rows:
        ws.append([row[field] for field in SELECTED_FIELDS])
    wb.save(xlsx_path)
    print(f"Saved {len(rows)} combo(s) to {xlsx_path}")


if __name__ == "__main__":
    main()
