#!/usr/bin/env python3
"""
Question Reasonability Evaluation — spec §4.4

For each logged episode:
  1. Load cumulative symptom state and candidate_set per turn from result JSON
     (produced by symptom_diagnosis.py with cumulative extraction)
  2. Parse doctor questions and inference candidates from the log file
  3. Run all three mappers (semantic / llm_judge / hybrid) on each question
  4. Compute DCS, edge_alignment, mandatory_first, redundancy, composite per turn
  5. Track safety-critical symptom coverage across the episode
  6. Save turn_eval_question.json + summary table

Outputs:
  results/<run_dir>/question_eval.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from question_score import (
    SemanticSimilarityMapper,
    LLMJudgeMapper,
    HybridMapper,
    load_all_symptoms,
    load_criteria,
    load_differential_edges,
    score_dcs,
    score_edge_alignment,
    mandatory_first_compliance,
    redundancy_penalty,
    composite_question_score,
    safety_screening_compliance,
    SAFETY_CRITICAL_IDS,
)
from utils.llm import get_run_dir as _get_run_dir
from utils.config import CONFIG

BASE_DIR    = Path(__file__).parent
_RUN_DIR    = _get_run_dir()
RESULTS_DIR = BASE_DIR / "results" / _RUN_DIR
LOGS_DIR    = BASE_DIR / "logs"    / _RUN_DIR

_SAFETY_HORIZON = (CONFIG.get("evaluation") or {}).get("safety_screening_horizon")


# ── Log parsing ────────────────────────────────────────────────────────────────

def _extract_questions_and_candidates(
    log_file: Path,
) -> list[tuple[str, list[str]]]:
    """
    Return [(follow_up_question, candidates_after_that_turn), ...].

    Log structure per turn:
      opening question → patient turn 1 → inference 1 → follow-up q 1
      → patient turn 2 → inference 2 → follow-up q 2 → ... → final diagnosis

    So follow-up question i corresponds to inference candidates i.
    """
    text = log_file.read_text(encoding="utf-8")
    blocks = re.findall(
        r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}", text, re.DOTALL
    )

    questions: list[str] = []
    cands_per_turn: list[list[str]] = []

    for b in blocks:
        b = b.strip()
        try:
            p = json.loads(b)
            if isinstance(p, dict) and "question" in p and "category" in p:
                questions.append(p["question"])
            elif isinstance(p, dict) and "candidates" in p and "note" in p and "diagnosis" not in p:
                cands_per_turn.append(p.get("candidates", []))
        except (json.JSONDecodeError, ValueError):
            continue

    # questions[0] = opening, questions[1:] = follow-ups aligned with cands_per_turn
    follow_ups = questions[1:] if len(questions) > 1 else []
    return list(zip(follow_ups, cands_per_turn))


# ── Main evaluation ────────────────────────────────────────────────────────────

def evaluate() -> list[dict]:
    all_symptoms = load_all_symptoms()
    criteria     = load_criteria()
    diff_edges   = load_differential_edges()
    name2id      = {v["name"].lower().strip(): k for k, v in criteria.items()}

    mappers: dict[str, SemanticSimilarityMapper | LLMJudgeMapper | HybridMapper] = {
        "semantic":  SemanticSimilarityMapper(),
        "llm_judge": LLMJudgeMapper(),
        "hybrid":    HybridMapper(),
    }

    all_episode_results: list[dict] = []
    skipped = 0

    result_paths = sorted(RESULTS_DIR.glob("*_result.json"))
    if not result_paths:
        print("No result files found.", file=sys.stderr)
        sys.exit(1)

    for res_path in result_paths:
        result   = json.loads(res_path.read_text(encoding="utf-8"))
        log_name = result["log_file"]
        log_file = LOGS_DIR / f"{log_name}.txt"

        gt_m = re.match(r"(D\d+)", log_name)
        if not gt_m:
            continue
        gt = gt_m.group(1)

        if not log_file.exists():
            print(f"  [warn] Log not found: {log_file}", file=sys.stderr)
            skipped += 1
            continue

        q_and_cands = _extract_questions_and_candidates(log_file)
        turns_data  = result.get("turns", [])

        turns_out: list[dict] = []
        asked_per_turn: list[set[str]] = []

        for i, turn_data in enumerate(turns_data):
            t = turn_data["turn"]
            cumulative_confirmed = set(turn_data.get("cumulative_confirmed", []))
            cumulative_denied    = set(turn_data.get("cumulative_denied", []))

            if i >= len(q_and_cands):
                turns_out.append({"turn": t, "skipped": "no question logged"})
                asked_per_turn.append(set())
                continue

            question, raw_cands = q_and_cands[i]
            candidate_ids = [
                name2id[c.lower().strip()]
                for c in raw_cands
                if name2id.get(c.lower().strip())
            ]

            scores_by_mapper: dict[str, dict] = {}
            for mapper_name, mapper in mappers.items():
                q_syms = mapper.map(question, all_symptoms)
                dcs, kg_frac = score_dcs(q_syms, candidate_ids, criteria, diff_edges)
                edge_align   = score_edge_alignment(q_syms, candidate_ids, diff_edges)
                mand_first   = mandatory_first_compliance(
                    q_syms, candidate_ids,
                    cumulative_confirmed, cumulative_denied, criteria,
                )
                redund       = redundancy_penalty(q_syms, cumulative_confirmed, cumulative_denied)
                composite    = composite_question_score(dcs, edge_align, mand_first, redund)

                scores_by_mapper[mapper_name] = {
                    "targeted_symptoms":     q_syms,
                    "dcs":                   dcs,
                    "kg_edge_fraction":      round(kg_frac, 4),
                    "edge_alignment":        edge_align,
                    "mandatory_first_compliance": mand_first,
                    "redundancy_penalty":    redund,
                    "composite_score":       composite,
                }

            # Track symptoms asked about (use hybrid as primary)
            hybrid_syms = set(scores_by_mapper.get("hybrid", {}).get("targeted_symptoms", []))
            asked_per_turn.append(hybrid_syms)

            turns_out.append({
                "turn":                  t,
                "question":              question,
                "candidate_ids":         candidate_ids,
                "cumulative_confirmed":  sorted(cumulative_confirmed),
                "cumulative_denied":     sorted(cumulative_denied),
                "scores_by_mapper":      scores_by_mapper,
            })

        safety = safety_screening_compliance(asked_per_turn, horizon=_SAFETY_HORIZON)

        all_episode_results.append({
            "log_file":                    log_name,
            "ground_truth":                gt,
            "safety_screening_compliance": safety,
            "turns":                       turns_out,
        })

    if skipped:
        print(f"\n({skipped} log files not found, skipped)")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "question_eval.json"
    out_path.write_text(
        json.dumps(all_episode_results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved question evaluation → {out_path}")

    _print_summary(all_episode_results)
    return all_episode_results


def _print_summary(episode_results: list[dict]) -> None:
    mapper_stats: dict[str, dict[str, list]] = {
        m: {"dcs": [], "composite": [], "mandatory_first": [], "redundancy": [], "kg_frac": []}
        for m in ("semantic", "llm_judge", "hybrid")
    }
    safety_covered: list[bool] = []

    for ep in episode_results:
        safety_covered.append(ep["safety_screening_compliance"].get("all_covered", False))
        for turn in ep["turns"]:
            sbm = turn.get("scores_by_mapper", {})
            for mapper_name, s in sbm.items():
                if mapper_name not in mapper_stats:
                    continue
                if s.get("dcs") is not None:
                    mapper_stats[mapper_name]["dcs"].append(s["dcs"])
                mapper_stats[mapper_name]["composite"].append(s.get("composite_score", 0.0))
                mapper_stats[mapper_name]["mandatory_first"].append(s.get("mandatory_first_compliance", 0))
                mapper_stats[mapper_name]["redundancy"].append(s.get("redundancy_penalty", 0))
                mapper_stats[mapper_name]["kg_frac"].append(s.get("kg_edge_fraction", 0.0))

    print("\n=== Question Reasonability Summary ===")
    header = f"{'Mapper':<12} {'DCS':>8} {'Composite':>10} {'MandFirst':>10} {'Redundancy':>11} {'KG_edge%':>9}"
    sep = "-" * len(header)
    print(header)
    print(sep)
    for mapper in ("semantic", "llm_judge", "hybrid"):
        s = mapper_stats[mapper]
        def _avg(lst: list) -> str:
            return f"{float(np.mean(lst)):.4f}" if lst else "  N/A  "
        print(
            f"{mapper:<12} {_avg(s['dcs']):>8} {_avg(s['composite']):>10} "
            f"{_avg(s['mandatory_first']):>10} {_avg(s['redundancy']):>11} "
            f"{_avg(s['kg_frac']):>9}"
        )

    safety_rate = sum(safety_covered) / len(safety_covered) if safety_covered else 0.0
    print(f"\nSafety-critical coverage: {safety_rate:.1%} of episodes asked about all safety symptoms")

    # Per-safety-symptom breakdown
    from question_score import load_all_symptoms as _load_syms
    try:
        syms = _load_syms()
        print("\nPer safety-symptom coverage:")
        for ep in episode_results:
            ssc = ep["safety_screening_compliance"]
        # aggregate across all episodes
        sid_totals: dict[str, int] = {sid: 0 for sid in SAFETY_CRITICAL_IDS}
        for ep in episode_results:
            ssc = ep["safety_screening_compliance"]
            for sid in SAFETY_CRITICAL_IDS:
                if ssc.get(sid, False):
                    sid_totals[sid] += 1
        n = len(episode_results) or 1
        for sid in sorted(SAFETY_CRITICAL_IDS):
            name = syms.get(sid, {}).get("name", sid)
            print(f"  {sid} {name:<40}: {sid_totals[sid]}/{n} ({sid_totals[sid]/n:.0%})")
    except Exception:
        pass


if __name__ == "__main__":
    evaluate()
