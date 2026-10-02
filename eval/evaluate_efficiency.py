#!/usr/bin/env python3
"""
Diagnostic Efficiency (+ Final Accuracy for Diagnostic Decision Quality)

Metrics per episode. C_t = high_likely ∪ moderate_likely ∪ low_likely from
the per-turn candidate_set written by symptom_diagnosis.py.
Turns follow utils/turn_policy.py: the opening question is t = 0 and is
not counted; T = number of patient responses.

  turn_count                        (main) total patient turns T
  time_to_first_confident_narrowing (sub)  "1st-confidence turn": first turn t
                                           (1-indexed) with C_t == {final_diagnosis_id},
                                           regardless of correctness; sentinel T+1
                                           if never reached / no resolvable final dx
  overcommitment_conf               (sub)  "overcommitment turns": T − ttfin, or 0
                                           if ttfin was never reached
  final_accuracy                    (Decision Quality) 1.0 if the final dx's
                                           ICD-10 code maps to the ground-truth id

[DEACTIVATED] cssr, time_to_first_correct_narrowing, monotonicity_violations,
redundant_turn_ratio, overcommitment_turns — not part of the headline set.

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

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

import numpy as np

import argparse

from utils.llm import get_run_dir as _get_run_dir
from eval.common import load_code2id as _load_code2id, read_final_diagnosis

BASE_DIR = Path(__file__).resolve().parent.parent
from utils.paths import ANALYSIS_ROOT, LOGS_ROOT, RESULTS_ROOT
KG_DIR   = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN"

def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=None,
                        help="Path to results dir (default: results/<run_dir>)")
    parser.add_argument("--logs",    type=Path, default=None,
                        help="Path to logs dir (default: logs/<run_dir>)")
    return parser.parse_args()

_args       = _parse_args()
_RUN_DIR    = _get_run_dir()
RESULTS_DIR = _args.results if _args.results else RESULTS_ROOT / _RUN_DIR
LOGS_DIR    = _args.logs    if _args.logs    else LOGS_ROOT    / _RUN_DIR


def _load_id2name() -> dict[str, str]:
    disorder_path = KG_DIR / "disorder.json"
    data = json.loads(disorder_path.read_text(encoding="utf-8"))
    return {k: v["name"] for k, v in data.items()}


def _log_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def score_efficiency_episode(
    candidate_sizes: list[int],
    all_candidates_per_turn: list[set[str]],
    ground_truth: str,
    final_diagnosis_id: str | None,
) -> dict:
    """Compute all efficiency metrics for a single episode."""
    T = len(candidate_sizes)
    if T == 0:
        return {}

    # Final accuracy: final diagnosis' ICD-10 code resolves to the ground-truth disease ID
    final_accuracy = 1.0 if final_diagnosis_id and final_diagnosis_id == ground_truth else 0.0

    # time_to_first_confident_narrowing ("1st-confidence turn"): first turn
    # where the reference candidate set has collapsed to exactly
    # {final_diagnosis_id} — the disease the doctor actually settled on,
    # regardless of correctness.
    ttfin = T + 1  # sentinel: never reached
    if final_diagnosis_id:
        for i, ids in enumerate(all_candidates_per_turn):
            if ids == {final_diagnosis_id}:
                ttfin = i + 1  # 1-indexed
                break

    # overcommitment_conf: turns spent after ttfin until the episode ends.
    # turn_count == ttfin + overcommitment_conf whenever ttfin is reached.
    overcommitment_conf = 0 if ttfin > T else T - ttfin

    # [DEACTIVATED] non-headline efficiency metrics.
    # cssr = (candidate_sizes[0] - candidate_sizes[-1]) / T
    # ttfcn = next((i + 1 for i, ids in enumerate(all_candidates_per_turn)
    #               if ids == {ground_truth}), T + 1)
    # mono_violations = sum(1 for i in range(1, T) if candidate_sizes[i] > candidate_sizes[i - 1])
    # redundant_turn_ratio = sum(1 for i in range(1, T)
    #                            if candidate_sizes[i] == candidate_sizes[i - 1]) / max(T - 1, 1)
    # first_size_one = next((i for i, s in enumerate(candidate_sizes) if s == 1), None)
    # overcommitment_turns = (0 if first_size_one is None or first_size_one >= T - 1
    #                         else (T - 1) - first_size_one)

    return {
        "final_accuracy":                    final_accuracy,
        "turn_count":                        T,
        "time_to_first_confident_narrowing": ttfin,
        "overcommitment_conf":               overcommitment_conf,
    }


def evaluate() -> list[dict]:
    id2name = _load_id2name()
    code2id = _load_code2id()

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
        log_file = LOGS_DIR / f"{log_name}.json"

        gt_m = re.match(r"(D\d+)", log_name)
        if not gt_m:
            continue
        gt      = gt_m.group(1)
        gt_name = id2name.get(gt, gt)

        turns = result.get("turns", [])

        # Extract per-turn candidate sizes and full candidate-id sets
        candidate_sizes:         list[int]      = []
        all_candidates_per_turn: list[set[str]] = []

        for turn_data in turns:
            cs = turn_data.get("candidate_set", {})
            hl = set(cs.get("high_likely", []))
            ml = set(cs.get("moderate_likely", []))
            ll = set(cs.get("low_likely", []))
            all_ids = hl | ml | ll
            candidate_sizes.append(len(all_ids))
            all_candidates_per_turn.append(all_ids)

        if not candidate_sizes:
            print(
                f"  [warn] {log_name}: no candidate_set data — "
                f"run symptom_diagnosis.py first",
                file=sys.stderr,
            )
            skipped += 1
            continue

        final_diag = read_final_diagnosis(log_file) if log_file.exists() else ""
        final_diag_id = code2id.get(final_diag.strip().upper()) if final_diag else None

        metrics = score_efficiency_episode(
            candidate_sizes         = candidate_sizes,
            all_candidates_per_turn = all_candidates_per_turn,
            ground_truth            = gt,
            final_diagnosis_id      = final_diag_id,
        )

        episode_results.append({
            "log_file":              log_name,
            "ground_truth":          gt,
            "ground_truth_name":     gt_name,
            "candidate_sizes":       candidate_sizes,
            "final_diagnosis":       final_diag,
            "final_diagnosis_id":    final_diag_id,
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
        ("turn_count",                        "Total Turns (mean)"),
        ("time_to_first_confident_narrowing", "1st-Confidence Turn (mean)"),
        ("overcommitment_conf",               "Overcommitment Turns (mean)"),
        ("final_accuracy",                    "Final Accuracy"),
    ]

    print("\n=== Diagnostic Efficiency Summary ===")
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

