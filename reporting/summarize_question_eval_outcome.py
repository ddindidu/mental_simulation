#!/usr/bin/env python3
"""
Ablation: Diagnostic Question Quality stratified by outcome (evaluation_v5.md §2)

Splits each doctor model's episodes by Final Accuracy (correct vs. incorrect
final diagnosis, from efficiency_eval.json) and aggregates the question
metrics of reporting/summarize_question_eval.py per stratum — QTS and its
components DRS (diagnostic relevance) and RP (redundancy penalty).
Question-only companion of summarize_ablation_all_dimensions.py.

Outputs (per (patient, judge) bucket):
  analysis/<patient>/<judge>/comparison/outcome_stratified/
    question_eval_outcome_comparison.json
    question_eval_outcome_comparison.csv     rows: (model, stratum ∈ correct/incorrect/delta)

Usage:
  MS_RUN=run_batch_20260912 python reporting/summarize_question_eval_outcome.py [--style plain]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT
from reporting.summarize_question_eval import METRICS, episode_values


def _mean(vals: list) -> float | None:
    clean = [v for v in vals if v is not None]
    return float(np.mean(clean)) if clean else None


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--style", default="plain", help="Episode style filter ('' = all styles)")
    args = p.parse_args()

    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for q_path in sorted(RESULTS_ROOT.glob("*/*/*/question_eval.json")):
        patient, judge, model = q_path.parts[-4], q_path.parts[-3], q_path.parts[-2]
        outcome = {e["log_file"]: e.get("final_accuracy") == 1.0
                   for e in _load(q_path.parent / "efficiency_eval.json")}
        strata: dict[str, list[dict]] = {"correct": [], "incorrect": []}
        for ep in _load(q_path):
            lf = ep["log_file"]
            if (args.style and not lf.endswith(f"_{args.style}")) or lf not in outcome:
                continue
            strata["correct" if outcome[lf] else "incorrect"].append(episode_values(ep))
        agg = {s: {"n": len(v), **{k: _mean([e[k] for e in v]) for k, _ in METRICS}}
               for s, v in strata.items()}
        agg["delta"] = {"n": None, **{
            k: (agg["correct"][k] - agg["incorrect"][k])
            if agg["correct"][k] is not None and agg["incorrect"][k] is not None else None
            for k, _ in METRICS}}
        buckets[(patient, judge)].append({"model": model, **agg})

    for (patient, judge), rows in buckets.items():
        out_dir = ANALYSIS_ROOT / patient / judge / "comparison" / "outcome_stratified"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "question_eval_outcome_comparison.json").write_text(
            json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        fields = ["model", "stratum", "n", *[k for k, _ in METRICS]]
        with open(out_dir / "question_eval_outcome_comparison.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                for s in ("correct", "incorrect", "delta"):
                    w.writerow({"model": r["model"], "stratum": s, **r[s]})

        print(f"\n=== {patient}/{judge}: QTS by outcome (correct / incorrect / Δ) ===")
        for r in rows:
            c, i, d = r["correct"], r["incorrect"], r["delta"]
            fmt = lambda v: f"{v:.3f}" if v is not None else "n/a"
            print(f"  {r['model']:<24} n={c['n']}/{i['n']}  QTS {fmt(c['mean_qts'])} / "
                  f"{fmt(i['mean_qts'])} / {d['mean_qts']:+.3f}" if d["mean_qts"] is not None else
                  f"  {r['model']:<24} n={c['n']}/{i['n']}  QTS n/a")
        print(f"[saved] {out_dir}/question_eval_outcome_comparison.{{json,csv}}")


if __name__ == "__main__":
    main()
