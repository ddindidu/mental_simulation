#!/usr/bin/env python3
"""
Question Reasonability Evaluation — spec §4.4

For each logged episode:
  1. Load cumulative symptom state and candidate_set per turn from result JSON
  2. Parse doctor questions and inference candidates from the log file
  3. Run cosine and llm_judge mappers on each question
  4. Compute per-turn scores: DCS, edge_alignment, mandatory_first, redundancy,
     composite, information_gain, candidate_size
  5. Compute per-episode aggregate metrics (all-turn + active-turn conditional)
  6. Track safety-critical symptom coverage across the episode

Outputs:
  results/<run_dir>/question_eval.json
"""
from __future__ import annotations

import argparse
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

from eval.question_score import (
    CosineSemanticMapper,
    LLMJudgeMapper,
    HybridMapper,
    SemanticSimilarityMapper,
    load_all_symptoms,
    load_criteria,
    load_differential_edges,
    score_dcs,
    score_edge_alignment,
    mandatory_first_compliance,
    redundancy_penalty,
    composite_question_score,
    score_information_gain,
    safety_screening_compliance,
    compute_episode_question_metrics,
    SAFETY_CRITICAL_IDS,
)
from utils.llm import get_run_dir as _get_run_dir
from utils.config import CONFIG

BASE_DIR = Path(__file__).resolve().parent.parent
DISORDER_ICD10_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "disorder_icd10.json"

_SAFETY_HORIZON = (CONFIG.get("evaluation") or {}).get("safety_screening_horizon")


def _build_code_to_id() -> dict[str, str]:
    """Return {icd10_code: disease_id} from disorder_icd10.json."""
    with open(DISORDER_ICD10_FILE, encoding="utf-8") as f:
        mapping = json.load(f)
    code2id: dict[str, str] = {}
    for k, v in mapping.items():
        for code in v.get("icd10_accepted_codes") or [v["icd10_code"]]:
            code2id[code.strip().upper()] = k
    return code2id


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=Path, default=None,
                   help="Path to results dir (default: results/<run_dir>)")
    p.add_argument("--logs",    type=Path, default=None,
                   help="Path to logs dir (default: logs/<run_dir>)")
    return p.parse_args()


_args       = _parse_args()
_RUN_DIR    = _get_run_dir()
RESULTS_DIR = _args.results if _args.results else BASE_DIR / "results" / _RUN_DIR
LOGS_DIR    = _args.logs    if _args.logs    else BASE_DIR / "logs"    / _RUN_DIR


# ── Log parsing ────────────────────────────────────────────────────────────────

def _extract_questions_and_candidates(
    log_file: Path,
) -> list[tuple[str, list[str]]]:
    """
    Return [(follow_up_question, candidates_after_that_turn), ...].

    Follow-up question i corresponds to inference candidates i (0-indexed after
    the opening question which is skipped).
    """
    text   = log_file.read_text(encoding="utf-8")
    blocks = re.findall(
        r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}", text, re.DOTALL
    )

    questions:      list[str]       = []
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

    follow_ups = questions[1:] if len(questions) > 1 else []
    return list(zip(follow_ups, cands_per_turn))


# ── Main evaluation ────────────────────────────────────────────────────────────

def evaluate() -> list[dict]:
    all_symptoms = load_all_symptoms()
    criteria     = load_criteria()
    diff_edges   = load_differential_edges()
    code2id      = _build_code_to_id()

    mappers: dict[str, CosineSemanticMapper | LLMJudgeMapper] = {
        "cosine":    CosineSemanticMapper(),
        "llm_judge": LLMJudgeMapper(),
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

        turns_out:      list[dict]       = []
        asked_per_turn: list[set[str]]   = []

        for i, turn_data in enumerate(turns_data):
            t = turn_data["turn"]
            cumulative_confirmed = set(turn_data.get("cumulative_confirmed", []))
            cumulative_denied    = set(turn_data.get("cumulative_denied", []))

            # Candidate set size from result JSON (KG-deterministic)
            cs = turn_data.get("candidate_set", {})
            candidate_size = (
                len(cs.get("high_likely",    []))
                + len(cs.get("moderate_likely", []))
                + len(cs.get("low_likely",     []))
            )

            if i >= len(q_and_cands):
                turns_out.append({
                    "turn": t,
                    "candidate_size": candidate_size,
                    "skipped": "no question logged",
                })
                asked_per_turn.append(set())
                continue

            question, raw_cands = q_and_cands[i]
            candidate_ids = [
                code2id[c.strip().upper()]
                for c in raw_cands
                if code2id.get(c.strip().upper())
            ]

            scores_by_mapper: dict[str, dict] = {}
            for mapper_name, mapper in mappers.items():
                q_syms   = mapper.map(question, all_symptoms)
                dcs, kg_frac = score_dcs(q_syms, candidate_ids, criteria, diff_edges)
                edge_align   = score_edge_alignment(q_syms, candidate_ids, diff_edges)
                mand_first   = mandatory_first_compliance(
                    q_syms, candidate_ids,
                    cumulative_confirmed, cumulative_denied, criteria,
                )
                redund    = redundancy_penalty(q_syms, cumulative_confirmed, cumulative_denied)
                composite = composite_question_score(dcs, edge_align, mand_first, redund)
                ig        = score_information_gain(
                    q_syms,
                    cumulative_confirmed,
                    cumulative_denied,
                    criteria,
                    candidate_size,
                )

                scores_by_mapper[mapper_name] = {
                    "targeted_symptoms":          q_syms,
                    "dcs":                        dcs,
                    "kg_edge_fraction":           round(kg_frac, 4),
                    "edge_alignment":             edge_align,
                    "mandatory_first_compliance": mand_first,
                    "redundancy_penalty":         redund,
                    "composite_score":            composite,
                    "information_gain":           ig,
                }

            # Safety tracking: union of cosine symptoms as reference
            asked_per_turn.append(
                set(scores_by_mapper.get("cosine", {}).get("targeted_symptoms", []))
            )

            turns_out.append({
                "turn":                  t,
                "question":              question,
                "candidate_size":        candidate_size,
                "candidate_ids":         candidate_ids,
                "cumulative_confirmed":  sorted(cumulative_confirmed),
                "cumulative_denied":     sorted(cumulative_denied),
                "scores_by_mapper":      scores_by_mapper,
            })

        # Per-episode aggregate metrics (new conditional metrics included)
        episode_metrics: dict[str, dict] = {
            mapper_name: compute_episode_question_metrics(turns_out, mapper_name)
            for mapper_name in mappers
        }

        safety = safety_screening_compliance(asked_per_turn, horizon=_SAFETY_HORIZON)

        all_episode_results.append({
            "log_file":                    log_name,
            "ground_truth":                gt,
            "safety_screening_compliance": safety,
            "episode_metrics":             episode_metrics,
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


# ── Summary printing ───────────────────────────────────────────────────────────

def _print_summary(episode_results: list[dict]) -> None:
    mappers     = ("cosine", "llm_judge")
    all_metrics: dict[str, dict[str, list]] = {m: defaultdict(list) for m in mappers}
    safety_covered: list[bool] = []

    for ep in episode_results:
        safety_covered.append(
            ep["safety_screening_compliance"].get("all_covered", False)
        )
        for m in mappers:
            em = ep.get("episode_metrics", {}).get(m, {})
            for k, v in em.items():
                if v is not None:
                    all_metrics[m][k].append(v)

    def _avg(lst: list) -> str:
        return f"{float(np.mean(lst)):.4f}" if lst else "   N/A"

    print("\n=== Question Quality Summary ===")

    # ── Main metrics ───────────────────────────────────────────────────────────
    MAIN = [
        ("conditional_mean_composite", "Cond. Mean Composite (active turns)"),
        ("conditional_mean_ig",        "Cond. Mean IG        (active turns)"),
        ("ig_positive_rate",           "IG-Positive Rate     (active turns)"),
        ("discriminating_q_rate",      "Discriminating-Q Rate (composite>0.3)"),
    ]
    print(f"\n{'── Main Metrics':-<60}")
    hdr = f"  {'Metric':<42} {'cosine':>9} {'llm_judge':>10}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for key, label in MAIN:
        row = f"  {label:<42}"
        for m in mappers:
            row += f" {_avg(all_metrics[m].get(key, [])):>9}"
        print(row)

    # ── Supporting metrics ─────────────────────────────────────────────────────
    SUB = [
        ("mean_composite",   "Mean Composite      (all turns)"),
        ("mean_dcs",         "Mean DCS            (all turns)"),
        ("redundancy_rate",  "Redundancy Rate     (all turns)"),
        ("early_ig_mean",    "Early IG Mean       (first half active)"),
        ("active_turn_count","Active Turn Count"),
    ]
    print(f"\n{'── Supporting Metrics':-<60}")
    hdr2 = f"  {'Metric':<42} {'cosine':>9} {'llm_judge':>10}"
    print(hdr2)
    print("  " + "-" * (len(hdr2) - 2))
    for key, label in SUB:
        row = f"  {label:<42}"
        for m in mappers:
            row += f" {_avg(all_metrics[m].get(key, [])):>9}"
        print(row)

    safety_rate = sum(safety_covered) / len(safety_covered) if safety_covered else 0.0
    print(f"\n{'── Safety':-<60}")
    print(f"  All-safety-symptom coverage: {safety_rate:.1%} of episodes")

    # Per-safety-symptom breakdown
    try:
        from eval.question_score import load_all_symptoms as _load_syms
        syms = _load_syms()
        sid_totals: dict[str, int] = {sid: 0 for sid in SAFETY_CRITICAL_IDS}
        for ep in episode_results:
            ssc = ep["safety_screening_compliance"]
            for sid in SAFETY_CRITICAL_IDS:
                if ssc.get(sid, False):
                    sid_totals[sid] += 1
        n = len(episode_results) or 1
        for sid in sorted(SAFETY_CRITICAL_IDS):
            name = syms.get(sid, {}).get("name", sid)
            print(f"    {sid} {name:<40}: {sid_totals[sid]}/{n} ({sid_totals[sid]/n:.0%})")
    except Exception:
        pass


if __name__ == "__main__":
    evaluate()
