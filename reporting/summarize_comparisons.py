#!/usr/bin/env python3
"""
Cross-model comparison table of the evaluation_v5.md headline metrics, one
table per (patient, judge) bucket.

Rows = doctor models; columns = the 10 headline metrics (see
reporting/headline_metrics.py for definitions and aggregation — identical
to reporting/summarize_v4_metrics_csv.py).

Outputs (per bucket):
  analysis/<patient>/<judge>/comparison/headline_comparison.json
  analysis/<patient>/<judge>/comparison/headline_comparison.csv

Usage:
  MS_RUN=run_batch_20260912 python reporting/summarize_comparisons.py [--style plain]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from utils.paths import ANALYSIS_ROOT
from reporting.headline_metrics import HEADLINE, HEADLINE_KEYS, discover_combos, load_combo, pooled_means


def build_tables(style: str | None) -> dict[tuple[str, str], list[dict]]:
    tables: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for patient, judge, doctor in discover_combos():
        episodes = load_combo(patient, judge, doctor, style)
        if not episodes:
            continue
        tables[(patient, judge)].append({"model": doctor, **pooled_means(episodes)})
    return tables


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--style", default="plain", help="Episode style filter ('' = all styles)")
    args = p.parse_args()

    for (patient, judge), rows in build_tables(args.style or None).items():
        out_dir = ANALYSIS_ROOT / patient / judge / "comparison"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "headline_comparison.json").write_text(
            json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        fields = ["model", "n_episodes", *HEADLINE_KEYS]
        with open(out_dir / "headline_comparison.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows({k: r[k] for k in fields} for r in rows)

        col_w = max(len(r["model"]) for r in rows) + 2
        print(f"\n=== {patient}/{judge} (style={args.style or 'all'}) ===")
        print(f"  {'Model':<{col_w}}{'N':>5}" + "".join(f"{lbl[:10]:>11}" for _, lbl, _, _ in HEADLINE))
        for r in rows:
            cells = "".join(f"{r[k]:>11.3f}" if r[k] is not None else f"{'N/A':>11}" for k in HEADLINE_KEYS)
            print(f"  {r['model']:<{col_w}}{r['n_episodes']:>5}{cells}")
        print(f"[saved] {out_dir}/headline_comparison.{{json,csv}}")


if __name__ == "__main__":
    main()
