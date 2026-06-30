#!/usr/bin/env python3
"""
Efficiency Evaluation — spec §4.5

Metrics per episode (computed from the KG-deterministic CandidateSet sizes):
  final_accuracy               : 1.0 if final diagnosis matches ground truth
  turn_count                   : total patient turns
  cssr                         : (size[0] − size[T-1]) / T
  time_to_first_correct_narrowing : first turn where high_likely = {gt} and size = 1
  monotonicity_violations      : turns where ref candidate set grew
  redundant_turn_ratio         : fraction of consecutive turns with no candidate set change
  overcommitment_turns         : turns after first size-1 collapse until episode end

Requires result JSONs produced by symptom_diagnosis.py (with candidate_set per turn).

Outputs:
  results/<run_dir>/efficiency_eval.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from utils.llm import get_run_dir as _get_run_dir

BASE_DIR    = Path(__file__).parent
_RUN_DIR    = _get_run_dir()
RESULTS_DIR = BASE_DIR / "results" / _RUN_DIR
LOGS_DIR    = BASE_DIR / "logs"    / _RUN_DIR
KG_DIR      = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN"


def _load_id2name() -> dict[str, str]:
    disorder_path = KG_DIR / "disorder.json"
    data = json.loads(disorder_path.read_text(encoding="utf-8"))
    return {k: v["name"] for k, v in data.items()}


def _log_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _extract_final_diagnosis(log_file: Path) -> str:
    text = log_file.read_text(encoding="utf-8")
    blocks = re.findall(
        r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}", text, re.DOTALL
    )
    for b in reversed(blocks):
        b = b.strip()
        try:
            p = json.loads(b)
            if isinstance(p, dict) and "diagnosis" in p:
                return str(p["diagnosis"]).strip()
        except (json.JSONDecodeError, ValueError):
            continue
    return ""


def score_efficiency_episode(
    candidate_sizes: list[int],
    high_likely_per_turn: list[set[str]],
    ground_truth: str,
    final_diagnosis: str,
    ground_truth_name: str,
) -> dict:
    """Compute all efficiency metrics for a single episode."""
    T = len(candidate_sizes)
    if T == 0:
        return {}

    # Final accuracy: substring match, case-insensitive
    fd  = final_diagnosis.lower().strip()
    gtn = ground_truth_name.lower().strip()
    final_accuracy = 1.0 if fd and gtn and (gtn in fd or fd in gtn) else 0.0

    # CSSR
    cssr = (candidate_sizes[0] - candidate_sizes[-1]) / T

    # time_to_first_correct_narrowing: first turn where high_likely == {gt}
    ttfcn = T + 1  # sentinel: never reached
    for i, hl in enumerate(high_likely_per_turn):
        if ground_truth in hl and len(hl) == 1:
            ttfcn = i + 1  # 1-indexed
            break

    # monotonicity_violations: turns where size grew
    mono_violations = sum(
        1 for i in range(1, T) if candidate_sizes[i] > candidate_sizes[i - 1]
    )

    # redundant_turn_ratio: consecutive turns with no size change
    redundant = sum(
        1 for i in range(1, T) if candidate_sizes[i] == candidate_sizes[i - 1]
    )
    redundant_turn_ratio = redundant / max(T - 1, 1)

    # overcommitment_turns: turns AFTER ref first collapses to size 1, before end
    # (counts turns where doctor kept asking even though ref set was already singleton)
    first_size_one = next(
        (i for i, s in enumerate(candidate_sizes) if s == 1), None
    )
    if first_size_one is None or first_size_one >= T - 1:
        overcommitment_turns = 0
    else:
        overcommitment_turns = (T - 1) - first_size_one

    return {
        "final_accuracy":                  final_accuracy,
        "turn_count":                       T,
        "cssr":                             round(cssr, 4),
        "time_to_first_correct_narrowing":  ttfcn,
        "monotonicity_violations":          mono_violations,
        "redundant_turn_ratio":             round(redundant_turn_ratio, 4),
        "overcommitment_turns":             overcommitment_turns,
    }


def evaluate() -> list[dict]:
    id2name = _load_id2name()

    result_paths = sorted(
        RESULTS_DIR.glob("*_result.json"),
        key=lambda p: _log_sort_key(p.stem.replace("_result", "")),
    )
    if not result_paths:
        print("No result files found.", file=sys.stderr)
        sys.exit(1)

    episode_results: list[dict] = []
    skipped = 0
    aggregate: dict[str, list] = defaultdict(list)

    for res_path in result_paths:
        result   = json.loads(res_path.read_text(encoding="utf-8"))
        log_name = result["log_file"]
        log_file = LOGS_DIR / f"{log_name}.txt"

        gt_m = re.match(r"(D\d+)", log_name)
        if not gt_m:
            continue
        gt      = gt_m.group(1)
        gt_name = id2name.get(gt, gt)

        turns = result.get("turns", [])

        # Extract per-turn candidate sizes and high_likely sets
        candidate_sizes:      list[int]      = []
        high_likely_per_turn: list[set[str]] = []

        for turn_data in turns:
            cs = turn_data.get("candidate_set", {})
            hl = set(cs.get("high_likely", []))
            ml = set(cs.get("moderate_likely", []))
            candidate_sizes.append(len(hl) + len(ml))
            high_likely_per_turn.append(hl)

        if not candidate_sizes:
            print(
                f"  [warn] {log_name}: no candidate_set data — "
                f"run symptom_diagnosis.py first",
                file=sys.stderr,
            )
            skipped += 1
            continue

        final_diag = _extract_final_diagnosis(log_file) if log_file.exists() else ""

        metrics = score_efficiency_episode(
            candidate_sizes      = candidate_sizes,
            high_likely_per_turn = high_likely_per_turn,
            ground_truth         = gt,
            final_diagnosis      = final_diag,
            ground_truth_name    = gt_name,
        )

        episode_results.append({
            "log_file":              log_name,
            "ground_truth":          gt,
            "ground_truth_name":     gt_name,
            "candidate_sizes":       candidate_sizes,
            "final_diagnosis":       final_diag,
            **metrics,
        })

        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                aggregate[k].append(v)

    _print_summary(aggregate, episode_results)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "efficiency_eval.json"
    out_path.write_text(
        json.dumps(episode_results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved efficiency evaluation → {out_path}")
    if skipped:
        print(f"({skipped} episodes skipped — missing candidate_set data)")

    return episode_results


def _print_summary(aggregate: dict[str, list], episode_results: list[dict]) -> None:
    METRIC_LABELS = [
        ("final_accuracy",                 "Final Accuracy"),
        ("turn_count",                     "Mean Turn Count"),
        ("cssr",                           "CSSR (Candidate Shrinkage Rate)"),
        ("time_to_first_correct_narrowing","Time to First Correct Narrowing"),
        ("monotonicity_violations",        "Monotonicity Violations (mean)"),
        ("redundant_turn_ratio",           "Redundant Turn Ratio"),
        ("overcommitment_turns",           "Overcommitment Turns (mean)"),
    ]

    print("\n=== Efficiency Evaluation Summary ===")
    for key, label in METRIC_LABELS:
        vals = aggregate.get(key, [])
        if vals:
            mean_val = float(np.mean(vals))
            print(f"  {label:<45}: {mean_val:.4f}")

    # Cross-tabulate final_accuracy × turn_count
    if episode_results:
        print("\nFinal accuracy by turn count:")
        from collections import Counter
        tc_correct: dict[int, int] = Counter()
        tc_total:   dict[int, int] = Counter()
        for ep in episode_results:
            tc = ep.get("turn_count", 0)
            tc_total[tc] += 1
            if ep.get("final_accuracy", 0.0) == 1.0:
                tc_correct[tc] += 1
        for tc in sorted(tc_total):
            acc = tc_correct[tc] / tc_total[tc]
            print(f"  Turn {tc}: {acc:.1%}  ({tc_correct[tc]}/{tc_total[tc]})")

    print(f"\n  Episodes evaluated: {len(episode_results)}")


if __name__ == "__main__":
    evaluate()
