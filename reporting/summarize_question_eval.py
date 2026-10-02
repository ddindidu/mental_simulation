#!/usr/bin/env python3
"""
Diagnostic Question Quality summary — QTS (evaluation_v5.md §2)

Aggregates question_eval.json (llm_judge mapper) into per-model and
cross-model summaries.

Aggregation (macro / episode-weighted): each episode contributes one value
regardless of its turn count.
  episode value = mean over that episode's scored turns
  model value   = mean over episodes

Metrics:
  mean_qts               QTS = DRS × (1 − RP)            (headline)
  mean_relevance         DRS, diagnostic relevance        (QTS component)
  mean_redundancy        RP, redundancy penalty           (QTS component)
  empty_target_rate      share of turns whose question mapped to no symptom (QTS = 0)

Usage:
    python summarize_question_eval.py [--patient P --judge J] [--doctor DOCTOR]

Outputs (per model):
    analysis/<patient>/<judge>/<model>/question_eval_summary.json
Outputs (cross-model comparison, per patient/judge bucket):
    analysis/<patient>/<judge>/comparison/question_eval_comparison.{json,csv}
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT
from utils.metric_compat import episode_mean_qts

MAPPER = "llm_judge"

# (key, label)
METRICS: list[tuple[str, str]] = [
    ("mean_qts",          "Mean QTS"),
    ("mean_relevance",    "Mean Diagnostic Relevance (DRS)"),
    ("mean_redundancy",   "Mean Redundancy Penalty (RP)"),
    ("empty_target_rate", "Empty-Target Turn Rate"),
]


def _mean(vals: list) -> float | None:
    clean = [v for v in vals if v is not None]
    return float(np.mean(clean)) if clean else None


def _std(vals: list) -> float | None:
    clean = [v for v in vals if v is not None]
    return float(np.std(clean)) if len(clean) > 1 else None


def episode_values(ep: dict) -> dict[str, float | None]:
    """Episode-level QTS metrics from one question_eval.json entry."""
    scored = [sc for t in ep.get("turns", [])
              if (sc := (t.get("scores_by_mapper") or {}).get(MAPPER)) is not None]
    return {
        "mean_qts":          episode_mean_qts(ep, MAPPER),
        "mean_relevance":    _mean([sc.get("diagnostic_relevance") for sc in scored]),
        "mean_redundancy":   _mean([sc.get("redundancy_penalty") for sc in scored]),
        "empty_target_rate": (sum(not sc.get("question_targets") for sc in scored) / len(scored)
                              if scored else None),
    }


def aggregate_model(question_eval: list[dict]) -> dict[str, Any]:
    per_ep = [episode_values(ep) for ep in question_eval]
    return {
        "total_episodes": len(question_eval),
        "mapper": MAPPER,
        "metrics": {
            key: {"mean": _mean([e[key] for e in per_ep]),
                  "std":  _std([e[key] for e in per_ep]),
                  "n":    sum(e[key] is not None for e in per_ep)}
            for key, _ in METRICS
        },
    }


def summarize_bucket(rb: Path, ab: Path, doctor: str | None) -> None:
    models = [doctor] if doctor else sorted(
        d.name for d in rb.iterdir() if d.is_dir() and (d / "question_eval.json").exists()
    )
    rows = []
    for model in models:
        src = rb / model / "question_eval.json"
        if not src.exists():
            print(f"[skip] {model}: {src} not found")
            continue
        agg = aggregate_model(json.loads(src.read_text(encoding="utf-8")))
        out_dir = ab / model
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "question_eval_summary.json").write_text(
            json.dumps(agg, indent=2, ensure_ascii=False), encoding="utf-8")
        rows.append({"model": model, "total_episodes": agg["total_episodes"],
                     **{k: agg["metrics"][k]["mean"] for k, _ in METRICS}})

    if not rows:
        return
    cmp_dir = ab / "comparison"
    cmp_dir.mkdir(parents=True, exist_ok=True)
    (cmp_dir / "question_eval_comparison.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(cmp_dir / "question_eval_comparison.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    col_w = max(len(r["model"]) for r in rows) + 2
    print(f"\n=== {rb.relative_to(RESULTS_ROOT)} — Diagnostic Question Quality ({MAPPER}) ===")
    print(f"  {'Model':<{col_w}}{'N':>5}" + "".join(f"{k:>19}" for k, _ in METRICS))
    for r in rows:
        print(f"  {r['model']:<{col_w}}{r['total_episodes']:>5}"
              + "".join(f"{r[k]:>19.4f}" if r[k] is not None else f"{'N/A':>19}" for k, _ in METRICS))
    print(f"[saved] {cmp_dir}/question_eval_comparison.{{json,csv}}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--patient", default=None, help="Patient model dir (default: all buckets)")
    p.add_argument("--judge",   default=None, help="Judge model dir (default: same as --patient)")
    p.add_argument("--doctor",  default=None, help="Single doctor model to process (default: all)")
    args = p.parse_args()

    if args.patient:
        buckets = [(args.patient, args.judge or args.patient)]
    else:
        buckets = sorted({(q.parts[-4], q.parts[-3])
                          for q in RESULTS_ROOT.glob("*/*/*/question_eval.json")})
    for patient, judge in buckets:
        summarize_bucket(RESULTS_ROOT / patient / judge, ANALYSIS_ROOT / patient / judge, args.doctor)


if __name__ == "__main__":
    main()
