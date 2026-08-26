#!/usr/bin/env python3
"""
Cross-model comparison tables for inference quality, efficiency, and
diagnostic reasoning quality — companions to summarize_question_eval.py's
question_eval_comparison.csv, in the same analysis/<judge>/<judge>/comparison/
folder.

Sources (per doctor model):
  analysis/<judge>/<judge>/<model>/turn_eval.json           → inference quality
  results/<judge>/<judge>/<model>/efficiency_eval.json      → efficiency
  results/<judge>/<judge>/<model>/diagnostic_reasoning_eval.json → reasoning quality

Aggregation: simple mean over all rows (same convention already used for
analysis/summary_doctor_models.xlsx) — one row per sample-turn for inference,
one row per episode for efficiency / reasoning.

Outputs (per category, under analysis/<judge>/<judge>/comparison/):
  inference_eval_comparison.{json,csv}
  efficiency_eval_comparison.{json,csv}
  diagnostic_reasoning_comparison.{json,csv}

Usage:
  python summarize_comparisons.py [--judge JUDGE]
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

BASE_DIR = Path(__file__).resolve().parent.parent
from utils.paths import ANALYSIS_ROOT, LOGS_ROOT, RESULTS_ROOT


def _mean(vals) -> float | None:
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _discover_models(results_root: Path) -> list[str]:
    return sorted(d.name for d in results_root.iterdir() if d.is_dir())


def build_inference_row(model: str, analysis_root: Path) -> dict[str, Any] | None:
    rows = _load(analysis_root / model / "turn_eval.json")
    if not rows:
        return None
    log_files = {r["log_file"] for r in rows}
    return {
        "model": model,
        "n_episodes": len(log_files),
        "n_turn_rows": len(rows),
        "accuracy": _mean(r["accuracy"] for r in rows),
        "precision": _mean(r["precision"] for r in rows),
        "recall": _mean(r["recall"] for r in rows),
        "jaccard": _mean(r["jaccard"] for r in rows),
        "weighted_recall": _mean(r["weighted_recall"] for r in rows),
    }


def build_efficiency_row(model: str, results_root: Path) -> dict[str, Any] | None:
    rows = _load(results_root / model / "efficiency_eval.json")
    if not rows:
        return None
    return {
        "model": model,
        "n_episodes": len(rows),
        "turn_count": _mean(r.get("turn_count") for r in rows),
        "cssr": _mean(r.get("cssr") for r in rows),
        "t_first": _mean(r.get("time_to_first_correct_narrowing") for r in rows),
        "monotonicity_violations": _mean(r.get("monotonicity_violations") for r in rows),
        "redundant_turn_ratio": _mean(r.get("redundant_turn_ratio") for r in rows),
        "overcommitment_turns": _mean(r.get("overcommitment_turns") for r in rows),
        "final_accuracy": _mean(r.get("final_accuracy") for r in rows),
    }


def build_reasoning_row(model: str, results_root: Path) -> dict[str, Any] | None:
    rows = _load(results_root / model / "diagnostic_reasoning_eval.json")
    if not rows:
        return None
    n_parse_errors = sum(1 for r in rows if r.get("_parse_error"))
    n_structured = sum(1 for r in rows if r.get("has_structured_checklist"))
    valid = [r for r in rows if not r.get("_parse_error")]
    return {
        "model": model,
        "n_episodes": len(rows),
        "n_valid": len(valid),
        "n_parse_errors": n_parse_errors,
        "n_structured_checklist": n_structured,
        "overall_score": _mean(r.get("overall_score") for r in valid),
        "symptom_satisfaction_score": _mean(r.get("symptom_satisfaction_score") for r in valid),
        "duration_score": _mean(r.get("duration_score") for r in valid),
        "functional_impairment_score": _mean(r.get("functional_impairment_score") for r in valid),
        "traumatic_stressor_score": _mean(r.get("traumatic_stressor_score") for r in valid),
        "psychosocial_stressor_score": _mean(r.get("psychosocial_stressor_score") for r in valid),
        "additional_requirements_score": _mean(r.get("additional_requirements_score") for r in valid),
    }


def _write(cmp_dir: Path, name: str, rows: list[dict]) -> None:
    if not rows:
        print(f"[skip] {name}: no data")
        return
    cmp_dir.mkdir(parents=True, exist_ok=True)
    json_path = cmp_dir / f"{name}.json"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    csv_path = cmp_dir / f"{name}.csv"
    fieldnames = list(rows[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"[saved] {json_path}")
    print(f"[saved] {csv_path}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--judge", default="gemini-3.5-flash",
                    help="Judge model dir name (default: gemini-3.5-flash)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    results_root = RESULTS_ROOT / args.judge / args.judge
    analysis_root = ANALYSIS_ROOT / args.judge / args.judge
    cmp_dir = analysis_root / "comparison"

    models = _discover_models(results_root)

    inference_rows, efficiency_rows, reasoning_rows = [], [], []
    for model in models:
        r = build_inference_row(model, analysis_root)
        if r:
            inference_rows.append(r)
        else:
            print(f"[skip] {model}: no turn_eval.json")

        r = build_efficiency_row(model, results_root)
        if r:
            efficiency_rows.append(r)
        else:
            print(f"[skip] {model}: no efficiency_eval.json")

        r = build_reasoning_row(model, results_root)
        if r:
            reasoning_rows.append(r)
        else:
            print(f"[skip] {model}: no diagnostic_reasoning_eval.json")

    _write(cmp_dir, "inference_eval_comparison", inference_rows)
    _write(cmp_dir, "efficiency_eval_comparison", efficiency_rows)
    _write(cmp_dir, "diagnostic_reasoning_comparison", reasoning_rows)


if __name__ == "__main__":
    main()
