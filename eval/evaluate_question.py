#!/usr/bin/env python3
"""
Diagnostic Question Quality — Question Targeting Score (QTS)

For each logged episode:
  1. Load cumulative symptom state and candidate_set per turn from result JSON
  2. Parse doctor questions and inference candidates from the log file
  3. Map each question to targeted symptom IDs with the llm_judge mapper
  4. Compute per-turn QTS (+ its diagnostic_relevance / redundancy_penalty
     components) and every intermediate symptom set used to derive it
     (discriminative/required/candidate/resolved/unresolved symptoms) for
     debugging and case-study inspection.
  5. Compute the per-episode aggregate: mean_qts (mean over all scored turns)

[DEACTIVATED] cosine mapper, ECR, active-turn conditional means, and
safety-critical symptom coverage — not part of the headline metric set.

Outputs:
  results/<run_dir>/question_eval.json
  results/<run_dir>/llm_judge_question_cache.json   (question text -> symptom IDs)
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
    # CosineSemanticMapper,          # [DEACTIVATED] cosine mapper
    LLMJudgeMapper,
    load_all_symptoms,
    load_criteria,
    # safety_screening_compliance,   # [DEACTIVATED] safety coverage
    # SAFETY_CRITICAL_IDS,
)
from eval.question_targeting_score import (
    score_question,
    compute_episode_question_metrics,
)
from utils.llm import get_run_dir as _get_run_dir
from eval.common import load_code2id
# from utils.config import CONFIG  # only used by the deactivated safety horizon

BASE_DIR = Path(__file__).resolve().parent.parent
from utils.paths import ANALYSIS_ROOT, LOGS_ROOT, RESULTS_ROOT
DISORDER_ICD10_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "disorder_icd10.json"

# _SAFETY_HORIZON = (CONFIG.get("evaluation") or {}).get("safety_screening_horizon")  # [DEACTIVATED]

MAPPERS = ("llm_judge",)  # headline mapper; "cosine" deactivated


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=Path, default=None,
                   help="Path to results dir (default: results/<run_dir>)")
    p.add_argument("--logs",    type=Path, default=None,
                   help="Path to logs dir (default: logs/<run_dir>)")
    return p.parse_args()


_args       = _parse_args()
_RUN_DIR    = _get_run_dir()
RESULTS_DIR = _args.results if _args.results else RESULTS_ROOT / _RUN_DIR
LOGS_DIR    = _args.logs    if _args.logs    else LOGS_ROOT    / _RUN_DIR


# ── Log parsing ────────────────────────────────────────────────────────────────

def _extract_questions_and_candidates(
    log_file: Path,
) -> list[tuple[str, list[str]]]:
    """
    Return [(follow_up_question, candidates_after_that_turn), ...] — read from
    the structured .json simulation log's doctor_memory.turns.

    Pair i (0-indexed) is (the question asked after patient turn i+1, that
    turn's inference candidates): turns[k].doctor.question is the question
    that preceded turn k, and turns[k].inference.candidates is the candidate
    state right after turn k concluded, so turns[k+1].doctor.question paired
    with turns[k].inference.candidates captures "the next question, given
    what the candidate set looked like at that point" — matching the old
    .txt-order pairing (opening question dropped, last turn's inference has
    no following question and is dropped too).
    """
    json_path = log_file.with_suffix(".json")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    turns = sorted(data.get("doctor_memory", {}).get("turns", []), key=lambda t: t.get("turn", 0))
    by_turn = {t.get("turn"): t for t in turns}
    max_turn = max(by_turn) if by_turn else 0

    pairs: list[tuple[str, list[str]]] = []
    for k in range(1, max_turn):
        cur, nxt = by_turn.get(k), by_turn.get(k + 1)
        if cur is None or nxt is None:
            continue
        inference   = cur.get("inference")
        doctor_next = nxt.get("doctor")
        if inference is None or doctor_next is None:
            continue
        pairs.append((doctor_next.get("question", ""), inference.get("candidates", [])))
    return pairs


# ── Main evaluation ────────────────────────────────────────────────────────────

def evaluate() -> list[dict]:
    all_symptoms = load_all_symptoms()
    criteria     = load_criteria()
    code2id      = load_code2id()

    # question_text -> symptom_ids, shared across ALL episodes/runs in this
    # results dir — the llm_judge mapper's judgment only depends on the
    # question text + the static symptom catalogue, never on which episode it
    # came from, so a question seen before (e.g. an opening question repeated
    # across many episodes, or an episode being rescored after an unrelated
    # fix upstream) never needs a fresh LLM call. Persisted independently of
    # the episode-level cache below.
    llm_judge_cache_path = RESULTS_DIR / "llm_judge_question_cache.json"
    llm_judge_cache: dict[str, list[str]] = {}
    if llm_judge_cache_path.exists():
        try:
            llm_judge_cache = json.loads(llm_judge_cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            llm_judge_cache = {}

    mappers: dict[str, LLMJudgeMapper] = {
        # "cosine":    CosineSemanticMapper(),  # [DEACTIVATED]
        "llm_judge": LLMJudgeMapper(cache=llm_judge_cache),
    }

    all_episode_results: list[dict] = []
    skipped = 0
    n_cached = 0

    result_paths = sorted(RESULTS_DIR.glob("*_result.json"))
    if not result_paths:
        print("No result files found.", file=sys.stderr)
        sys.exit(1)

    # Cache: reuse a previously-scored episode as-is if its turn count hasn't
    # grown since last time AND it was written with the QTS schema. Episodes
    # from the pre-rename (IAS) schema are rescored — cheap, since the
    # llm_judge mapper's question cache above already holds their questions,
    # so no new judge LLM call is made for them.
    out_path = RESULTS_DIR / "question_eval.json"
    cached: dict[str, dict] = {}
    if out_path.exists():
        try:
            cached = {e["log_file"]: e for e in json.loads(out_path.read_text(encoding="utf-8"))}
        except (json.JSONDecodeError, OSError):
            cached = {}

    for res_path in result_paths:
        result   = json.loads(res_path.read_text(encoding="utf-8"))
        log_name = result["log_file"]
        log_file = LOGS_DIR / f"{log_name}.json"

        cached_ep = cached.get(log_name)
        if (
            cached_ep is not None
            and len(cached_ep.get("turns", [])) == len(result.get("turns", []))
            and "mean_qts" in (cached_ep.get("episode_metrics") or {}).get("llm_judge", {})
        ):
            all_episode_results.append(cached_ep)
            n_cached += 1
            continue

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
                continue

            question, raw_cands = q_and_cands[i]
            candidate_ids = [
                code2id[c.strip().upper()]
                for c in raw_cands
                if code2id.get(c.strip().upper())
            ]

            scores_by_mapper: dict[str, dict] = {}
            for mapper_name, mapper in mappers.items():
                scores_by_mapper[mapper_name] = score_question(
                    question,
                    candidate_ids,
                    cumulative_confirmed,
                    cumulative_denied,
                    all_symptoms,
                    criteria,
                    mapper,
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

        episode_metrics: dict[str, dict] = {
            mapper_name: compute_episode_question_metrics(turns_out, mapper_name)
            for mapper_name in mappers
        }

        # [DEACTIVATED] safety-critical symptom coverage
        # safety = safety_screening_compliance(asked_per_turn, horizon=_SAFETY_HORIZON)

        all_episode_results.append({
            "log_file":        log_name,
            "ground_truth":    gt,
            "episode_metrics": episode_metrics,
            "turns":           turns_out,
        })

    if skipped:
        print(f"\n({skipped} log files not found, skipped)")
    if n_cached:
        print(f"({n_cached} episodes reused from cache, no llm_judge call)")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(all_episode_results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved question evaluation → {out_path}")

    llm_judge_cache_path.write_text(
        json.dumps(llm_judge_cache, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved llm_judge question cache ({len(llm_judge_cache)} questions) → {llm_judge_cache_path}")

    _print_summary(all_episode_results)
    return all_episode_results


# ── Summary printing ───────────────────────────────────────────────────────────

def _print_summary(episode_results: list[dict]) -> None:
    all_metrics: dict[str, dict[str, list]] = {m: defaultdict(list) for m in MAPPERS}
    for ep in episode_results:
        for m in MAPPERS:
            em = ep.get("episode_metrics", {}).get(m, {})
            for k, v in em.items():
                if v is not None:
                    all_metrics[m][k].append(v)

    def _avg(lst: list) -> str:
        return f"{float(np.mean(lst)):.4f}" if lst else "   N/A"

    print("\n=== Diagnostic Question Quality Summary (QTS) ===")
    ROWS = [
        ("mean_qts",        "Mean QTS            (all turns)"),
        ("mean_redundancy", "Mean Redundancy Penalty (QTS component)"),
    ]
    hdr = f"  {'Metric':<42}" + "".join(f" {m:>10}" for m in MAPPERS)
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for key, label in ROWS:
        row = f"  {label:<42}"
        for m in MAPPERS:
            row += f" {_avg(all_metrics[m].get(key, [])):>10}"
        print(row)
    print(f"\n  Episodes evaluated: {len(episode_results)}")


if __name__ == "__main__":
    evaluate()
