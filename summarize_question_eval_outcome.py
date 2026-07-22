#!/usr/bin/env python3
"""
Ablation: Outcome-stratified question quality metrics  (spec §4.4.7)

Splits episodes into:
  correct   — ground_truth ∈ all_candidates() at the final turn
  incorrect — ground_truth ∉ all_candidates() at the final turn

For each stratum, applies the same macro-mean aggregation as
summarize_question_eval.py.  Allows diagnosing whether question-quality
differences across models are confounded by the fraction of failed episodes.

Usage:
    python summarize_question_eval_outcome.py [--judge JUDGE] [--doctor DOCTOR]

Outputs (per model):
    analysis/<judge>/<judge>/<model>/question_eval_outcome_stratified.json

Outputs (cross-model):
    analysis/<judge>/<judge>/comparison/outcome_stratified/
        question_eval_outcome_comparison.json
        question_eval_outcome_comparison_correct.csv
        question_eval_outcome_comparison_incorrect.csv
        question_eval_outcome_comparison_delta.csv   ← correct − incorrect
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

METRICS: list[tuple[str, str, bool]] = [
    ("conditional_mean_composite",  "Cond. Mean Composite (active turns)", True),
    ("conditional_mean_ig",         "Cond. Mean IG (active turns)",        True),
    ("ig_positive_rate",            "IG-Positive Rate (active turns)",     True),
    ("discriminating_q_rate",       "Discriminating-Q Rate",               True),
    ("mean_composite",              "Mean Composite (all turns)",          False),
    ("mean_dcs",                    "Mean DCS (all turns)",                False),
    ("mean_redundancy",             "Mean Redundancy (all turns)",         False),
    ("redundancy_rate",             "Redundancy Rate (all turns)",         False),
    ("early_ig_mean",               "Early IG Mean (first-half active)",   False),
    ("active_turn_count",           "Active Turn Count",                   False),
]


def _mean(vals: list) -> float | None:
    clean = [v for v in vals if v is not None]
    return float(np.mean(clean)) if clean else None


def _std(vals: list) -> float | None:
    clean = [v for v in vals if v is not None]
    return float(np.std(clean)) if len(clean) > 1 else None


def _determine_outcome(result_json: dict) -> bool:
    """
    True = correct: ground_truth ∈ all_candidates() at final turn.
    Uses the KG-computed candidate_set from the last turn of _result.json.
    """
    gt = result_json.get("ground_truth") or ""
    turns = result_json.get("turns", [])
    if not turns or not gt:
        return False
    last_turn = max(turns, key=lambda t: t.get("turn", 0))
    cs = last_turn.get("candidate_set", {})
    all_cands = (
        cs.get("high_likely",    [])
        + cs.get("moderate_likely", [])
        + cs.get("low_likely",      [])
    )
    return gt in all_cands


def _load_outcomes(results_model_dir: Path) -> dict[str, bool]:
    """
    Returns {log_file_stem: is_correct} by reading all *_result.json files.
    """
    outcomes: dict[str, bool] = {}
    for p in results_model_dir.glob("*_result.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            log_name = d.get("log_file", p.stem.replace("_result", ""))
            # ground_truth may not be in result JSON; derive from log_file name
            if not d.get("ground_truth"):
                import re
                m = re.match(r"(D\d+)", log_name)
                d["ground_truth"] = m.group(1) if m else ""
            outcomes[log_name] = _determine_outcome(d)
        except Exception:
            continue
    return outcomes


def _aggregate_stratum(episodes: list[dict]) -> dict[str, Any]:
    """Macro-mean (episode-weighted) for a given stratum."""
    raw: dict[str, dict[str, list]] = {m: {} for m in MAPPERS}
    for ep in episodes:
        for mapper in MAPPERS:
            em = ep.get("episode_metrics", {}).get(mapper, {})
            for key, _, _ in METRICS:
                val = em.get(key)
                if val is not None:
                    raw[mapper].setdefault(key, []).append(val)

    agg: dict[str, Any] = {"n_episodes": len(episodes), "by_mapper": {}}
    for mapper in MAPPERS:
        mapper_agg: dict[str, Any] = {}
        for key, _, _ in METRICS:
            vals = raw[mapper].get(key, [])
            mapper_agg[key] = {"mean": _mean(vals), "std": _std(vals), "n": len(vals)}
        agg["by_mapper"][mapper] = mapper_agg
    return agg


def _print_stratum(label: str, agg: dict) -> None:
    n = agg["n_episodes"]
    print(f"\n  [{label}]  n={n}")
    hdr = f"    {'Metric':<38} {'cosine':>9} {'llm_judge':>10}"
    print(hdr)
    print("    " + "-" * 58)

    def fmt(v) -> str:
        return f"{v:.4f}" if v is not None else "   N/A"

    for key, label_str, is_main in METRICS:
        tag = "[M] " if is_main else "    "
        cv = (agg["by_mapper"].get("cosine",    {}).get(key) or {}).get("mean")
        lv = (agg["by_mapper"].get("llm_judge", {}).get(key) or {}).get("mean")
        print(f"    {tag}{label_str:<34} {fmt(cv):>9} {fmt(lv):>10}")


def build_flat_row(model: str, stratum: str, agg: dict) -> dict[str, Any]:
    row: dict[str, Any] = {
        "model":    model,
        "stratum":  stratum,
        "n_episodes": agg["n_episodes"],
    }
    for mapper in MAPPERS:
        for key, _, _ in METRICS:
            v = (agg["by_mapper"].get(mapper, {}).get(key) or {}).get("mean")
            row[f"{mapper}_{key}"] = v
    return row


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--judge",  default="gemini-3.5-flash")
    p.add_argument("--doctor", default=None)
    p.add_argument("--results-base", type=Path, default=BASE_DIR / "results")
    p.add_argument("--analysis-base", type=Path, default=BASE_DIR / "analysis")
    return p.parse_args()


def main() -> None:
    args  = _parse_args()
    judge = args.judge
    rb    = args.results_base  / judge / judge
    ab    = args.analysis_base / judge / judge

    if args.doctor:
        models = [args.doctor]
    else:
        models = sorted(
            d.name for d in rb.iterdir()
            if d.is_dir() and (d / "question_eval.json").exists()
        )

    all_rows: list[dict] = []

    for model in models:
        q_eval_path = rb / model / "question_eval.json"
        if not q_eval_path.exists():
            print(f"[skip] {model}: question_eval.json not found")
            continue

        question_eval = json.loads(q_eval_path.read_text(encoding="utf-8"))
        if question_eval and "episode_metrics" not in question_eval[0]:
            print(f"[skip] {model}: old format (no episode_metrics)")
            continue

        outcomes = _load_outcomes(rb / model)

        correct_eps   = []
        incorrect_eps = []
        unmatched     = 0

        for ep in question_eval:
            log_name = ep.get("log_file", "")
            outcome  = outcomes.get(log_name)
            if outcome is None:
                unmatched += 1
                continue
            (correct_eps if outcome else incorrect_eps).append(ep)

        if unmatched:
            print(f"  [warn] {model}: {unmatched} episodes without matching result file")

        strata = {
            "correct":   correct_eps,
            "incorrect": incorrect_eps,
            "all":       correct_eps + incorrect_eps,
        }

        agg_strata: dict[str, dict] = {
            name: _aggregate_stratum(eps) for name, eps in strata.items()
        }

        # Save per-model
        out_dir  = ab / model
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "question_eval_outcome_stratified.json"
        out_path.write_text(
            json.dumps(agg_strata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\n[saved] {out_path}")

        # Print
        print(f"\n{'='*64}")
        print(f"  {model}")
        print(f"  total={len(question_eval)}, correct={len(correct_eps)}, "
              f"incorrect={len(incorrect_eps)} "
              f"(correct_rate={len(correct_eps)/max(len(question_eval),1):.1%})")
        print(f"{'='*64}")
        for stratum_name, agg in agg_strata.items():
            _print_stratum(stratum_name.upper(), agg)

        for stratum_name, agg in agg_strata.items():
            all_rows.append(build_flat_row(model, stratum_name, agg))

    if not all_rows:
        print("No models processed.")
        return

    # Save cross-model comparison
    cmp_dir = ab / "comparison" / "outcome_stratified"
    cmp_dir.mkdir(parents=True, exist_ok=True)

    # Full JSON
    out_json = cmp_dir / "question_eval_outcome_comparison.json"
    out_json.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[saved] {out_json}")

    # Per-stratum CSVs
    fieldnames = list(all_rows[0].keys())
    for stratum_name in ("correct", "incorrect", "all"):
        rows = [r for r in all_rows if r["stratum"] == stratum_name]
        if not rows:
            continue
        csv_path = cmp_dir / f"question_eval_outcome_comparison_{stratum_name}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f"[saved] {csv_path}")

    # Delta CSV: correct − incorrect per model, per mapper key
    delta_rows = []
    models_seen = [r["model"] for r in all_rows if r["stratum"] == "correct"]
    metric_keys = [f"{m}_{k}" for m in MAPPERS for k, _, _ in METRICS]
    for model in models_seen:
        c_row = next((r for r in all_rows if r["model"] == model and r["stratum"] == "correct"),   None)
        i_row = next((r for r in all_rows if r["model"] == model and r["stratum"] == "incorrect"), None)
        if not c_row or not i_row:
            continue
        delta: dict[str, Any] = {
            "model":               model,
            "n_correct":           c_row["n_episodes"],
            "n_incorrect":         i_row["n_episodes"],
        }
        for k in metric_keys:
            cv = c_row.get(k)
            iv = i_row.get(k)
            delta[f"delta_{k}"] = (
                round(cv - iv, 6) if (cv is not None and iv is not None) else None
            )
        delta_rows.append(delta)

    if delta_rows:
        delta_path = cmp_dir / "question_eval_outcome_comparison_delta.csv"
        with open(delta_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(delta_rows[0].keys()))
            w.writeheader()
            w.writerows(delta_rows)
        print(f"[saved] {delta_path}")

    # Print cross-model summary for main metrics (cosine mapper)
    main_keys = [(k, l) for k, l, m in METRICS if m]
    print(f"\n{'='*90}")
    print("  Cross-Model — Cosine Mapper Main Metrics by Outcome Stratum")
    print(f"{'='*90}")
    model_w = max(len(m) for m in models_seen) + 2

    for stratum_name in ("correct", "incorrect"):
        print(f"\n  {stratum_name.upper()}")
        print(f"  {'Model':<{model_w}}", end="")
        for _, label in main_keys:
            short = label[:18]
            print(f"  {short:>18}", end="")
        print()
        print("  " + "-" * (model_w + len(main_keys) * 20))
        for row in [r for r in all_rows if r["stratum"] == stratum_name]:
            print(f"  {row['model']:<{model_w}}", end="")
            for key, _ in main_keys:
                v = row.get(f"cosine_{key}")
                s = f"{v:.4f}" if v is not None else "N/A"
                print(f"  {s:>18}", end="")
            print()


if __name__ == "__main__":
    main()
