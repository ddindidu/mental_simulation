#!/usr/bin/env python3
"""
Aggregates question_eval.json (new format with episode_metrics + scores_by_mapper)
into per-model and cross-model summaries saved to analysis/.

Usage:
    python summarize_question_eval.py [--judge JUDGE] [--doctor DOCTOR]

Outputs (per model):
    analysis/<judge>/<judge>/<model>/question_eval_summary.json

Outputs (cross-model comparison):
    analysis/<judge>/<judge>/comparison/question_eval_comparison.json
    analysis/<judge>/<judge>/comparison/question_eval_comparison.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

BASE_DIR = Path(__file__).parent

MAPPERS = ("cosine", "llm_judge")

# Metrics to aggregate: (key, description, is_main)
METRICS: list[tuple[str, str, bool]] = [
    # Main metrics
    ("conditional_mean_composite",  "Cond. Mean Composite (active turns)", True),
    ("conditional_mean_ig",         "Cond. Mean IG (active turns)",        True),
    ("ig_positive_rate",            "IG-Positive Rate (active turns)",     True),
    ("discriminating_q_rate",       "Discriminating-Q Rate",               True),
    # Supporting metrics
    ("mean_composite",              "Mean Composite (all turns)",          False),
    ("mean_dcs",                    "Mean DCS (all turns)",                False),
    ("mean_redundancy",             "Mean Redundancy (all turns)",         False),
    ("redundancy_rate",             "Redundancy Rate (all turns)",         False),
    ("early_ig_mean",               "Early IG Mean (first-half active)",   False),
    ("active_turn_count",           "Active Turn Count",                   False),
]


def _mean(vals: list[float | int]) -> float | None:
    clean = [v for v in vals if v is not None]
    return float(np.mean(clean)) if clean else None


def _std(vals: list[float | int]) -> float | None:
    clean = [v for v in vals if v is not None]
    return float(np.std(clean)) if len(clean) > 1 else None


def aggregate_model(question_eval: list[dict]) -> dict[str, Any]:
    """Aggregate episode_metrics across all episodes, per mapper."""
    raw: dict[str, dict[str, list]] = {m: {} for m in MAPPERS}

    safety_covered: list[bool] = []
    total_episodes = len(question_eval)

    for ep in question_eval:
        safety_covered.append(
            ep.get("safety_screening_compliance", {}).get("all_covered", False)
        )
        for mapper in MAPPERS:
            em = ep.get("episode_metrics", {}).get(mapper, {})
            for key, _, _ in METRICS:
                val = em.get(key)
                if val is not None:
                    raw[mapper].setdefault(key, []).append(val)

    # llm_judge empty turn analysis
    llm_empty = 0
    llm_total = 0
    for ep in question_eval:
        for t in ep.get("turns", []):
            sm = t.get("scores_by_mapper", {}).get("llm_judge", {})
            if sm:
                llm_total += 1
                if not sm.get("targeted_symptoms"):
                    llm_empty += 1

    agg: dict[str, Any] = {
        "total_episodes": total_episodes,
        "safety_all_covered_rate": (
            sum(safety_covered) / len(safety_covered) if safety_covered else None
        ),
        "llm_judge_empty_rate": (
            llm_empty / llm_total if llm_total > 0 else None
        ),
        "by_mapper": {},
    }

    for mapper in MAPPERS:
        mapper_agg: dict[str, Any] = {}
        for key, _, _ in METRICS:
            vals = raw[mapper].get(key, [])
            mapper_agg[key] = {
                "mean": _mean(vals),
                "std":  _std(vals),
                "n":    len(vals),
            }
        agg["by_mapper"][mapper] = mapper_agg

    return agg


def print_model_summary(model_name: str, agg: dict) -> None:
    print(f"\n{'='*64}")
    print(f"  {model_name}")
    print(f"  episodes={agg['total_episodes']}, "
          f"safety_cov={agg['safety_all_covered_rate']:.1%}, "
          f"llm_empty={agg['llm_judge_empty_rate']:.1%}")
    print(f"{'='*64}")

    header = f"  {'Metric':<38} {'cosine':>9} {'llm_judge':>10}"
    print(header)
    print("  " + "-" * 58)

    def fmt(v) -> str:
        return f"{v:.4f}" if v is not None else "   N/A"

    print("  [Main Metrics]")
    for key, label, is_main in METRICS:
        if not is_main:
            continue
        cosine_v = (agg["by_mapper"].get("cosine",    {}).get(key) or {}).get("mean")
        llm_v    = (agg["by_mapper"].get("llm_judge", {}).get(key) or {}).get("mean")
        print(f"  {label:<38} {fmt(cosine_v):>9} {fmt(llm_v):>10}")

    print("  [Supporting Metrics]")
    for key, label, is_main in METRICS:
        if is_main:
            continue
        cosine_v = (agg["by_mapper"].get("cosine",    {}).get(key) or {}).get("mean")
        llm_v    = (agg["by_mapper"].get("llm_judge", {}).get(key) or {}).get("mean")
        print(f"  {label:<38} {fmt(cosine_v):>9} {fmt(llm_v):>10}")


def build_comparison_table(
    model_results: dict[str, dict],
) -> list[dict]:
    """Build cross-model flat comparison rows for CSV/JSON export."""
    rows = []
    for model, agg in model_results.items():
        row: dict[str, Any] = {
            "model":                model,
            "total_episodes":       agg["total_episodes"],
            "safety_all_covered":   agg["safety_all_covered_rate"],
            "llm_empty_rate":       agg["llm_judge_empty_rate"],
        }
        for mapper in MAPPERS:
            for key, _, _ in METRICS:
                v = (agg["by_mapper"].get(mapper, {}).get(key) or {}).get("mean")
                row[f"{mapper}_{key}"] = v
        rows.append(row)
    return rows


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--judge",  default="gemini-3.5-flash",
                   help="Judge model dir name (default: gemini-3.5-flash)")
    p.add_argument("--doctor", default=None,
                   help="Single doctor model to process (default: all)")
    p.add_argument("--results-base", type=Path,
                   default=BASE_DIR / "results",
                   help="Base results directory")
    p.add_argument("--analysis-base", type=Path,
                   default=BASE_DIR / "analysis",
                   help="Base analysis directory")
    return p.parse_args()


def main() -> None:
    args   = _parse_args()
    judge  = args.judge
    rb     = args.results_base  / judge / judge
    ab     = args.analysis_base / judge / judge

    # Discover models
    if args.doctor:
        models = [args.doctor]
    else:
        models = sorted(
            d.name for d in rb.iterdir()
            if d.is_dir() and (d / "question_eval.json").exists()
        )

    if not models:
        print(f"No question_eval.json found under {rb}")
        return

    model_results: dict[str, dict] = {}

    for model in models:
        src = rb / model / "question_eval.json"
        if not src.exists():
            print(f"[skip] {model}: {src} not found")
            continue

        question_eval = json.loads(src.read_text(encoding="utf-8"))

        # Check format: new format has episode_metrics
        if question_eval and "episode_metrics" not in question_eval[0]:
            print(f"[skip] {model}: question_eval.json is old format (no episode_metrics)")
            continue

        agg = aggregate_model(question_eval)
        model_results[model] = agg

        # Save per-model summary
        out_dir = ab / model
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "question_eval_summary.json"
        out_path.write_text(
            json.dumps(agg, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[saved] {out_path}")
        print_model_summary(model, agg)

    if not model_results:
        print("No models processed.")
        return

    # Cross-model comparison
    cmp_dir = ab / "comparison"
    cmp_dir.mkdir(parents=True, exist_ok=True)

    rows = build_comparison_table(model_results)

    # JSON
    cmp_json = cmp_dir / "question_eval_comparison.json"
    cmp_json.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n[saved] {cmp_json}")

    # CSV
    cmp_csv = cmp_dir / "question_eval_comparison.csv"
    if rows:
        fieldnames = list(rows[0].keys())
        with open(cmp_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f"[saved] {cmp_csv}")

    # Print cross-model table for main metrics
    print(f"\n{'='*80}")
    print("  Cross-Model Comparison — Main Metrics")
    print(f"{'='*80}")
    main_keys = [(k, l) for k, l, m in METRICS if m]

    col_w = max(len(m) for m in model_results) + 2
    print(f"  {'Model':<{col_w}}", end="")
    for mapper in MAPPERS:
        for key, label in main_keys:
            short = key.replace("conditional_", "cond_")
            print(f"  {mapper[:3]}_{short[:16]:>16}", end="")
    print()
    print("  " + "-" * (col_w + (len(main_keys) * len(MAPPERS)) * 20))

    for row in rows:
        print(f"  {row['model']:<{col_w}}", end="")
        for mapper in MAPPERS:
            for key, _ in main_keys:
                v = row.get(f"{mapper}_{key}")
                s = f"{v:.4f}" if v is not None else "N/A"
                print(f"  {s:>20}", end="")
        print()


if __name__ == "__main__":
    main()
