"""
Question Targeting Score (QTS)
==============================

Turn-level scoring for the **Diagnostic Question Quality** evaluation
dimension (formerly "Information Acquisition Score (IAS)" — renamed; the
formula is unchanged).

  QTS = DRS * (1 - RP)     "did the question target relevant, still-unresolved symptoms?"

Computed and reported per turn, alongside every intermediate quantity used to
derive it, for debugging / case-study inspection.

Design decisions:

- Evidence state stays 3-state: CONFIRMED / DENIED / UNKNOWN. No AMBIGUOUS
  label. The symptom-extraction judge (eval/symptom_diagnosis.py) already
  errs toward UNKNOWN on ambiguous patient replies, so UNKNOWN already means
  "unresolved" regardless of *why* — a clarifying re-ask of an ambiguous
  answer is never mistaken for a redundant one.

- C_t (the candidate set QTS is computed against) is the DOCTOR'S OWN stated
  candidate list at that turn (ICD-10 → disease ID), not the KG reference
  candidate set — QTS asks "given what the doctor is considering, was this
  question well-targeted?".

- "Required" symptoms = MUST_INCLUDE mandatory-pool symptoms ONLY, tracked at
  individual-symptom granularity (no group/min_count gating — a group is not
  treated as "already satisfied" once min_count members are confirmed, since
  asking about individual mandatory symptoms one at a time is the natural
  conversational unit). Non-symptom requirements (min_duration,
  functional_impairment_required, additional_requirements) are OUT OF SCOPE
  — the pipeline has no per-turn evidence extraction for them yet.

DEACTIVATED (kept below for reference / easy reactivation, not called by the
pipeline): Expected Candidate Reduction (ECR). See
expected_candidate_reduction() and the commented-out call in score_question().
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

import numpy as np

from utils.config import CONFIG
from eval.question_score import (  # reuse KG loaders + mappers, do not duplicate
    load_all_symptoms,
    load_criteria,
    all_symptom_ids_for_disorder,
    _mandatory_pools,
    QuestionSymptomMapper,
    CosineSemanticMapper,
    LLMJudgeMapper,
    HybridMapper,
    SemanticSimilarityMapper,
    SAFETY_CRITICAL_IDS,
    safety_screening_compliance,
)

_QTS_CFG = (CONFIG.get("evaluation") or {}).get("information_acquisition") or {}
DEFAULT_PROBABILITY_MODE = _QTS_CFG.get("probability_mode", "candidate_frequency")  # ECR only (deactivated)


# ── KG helpers (mandatory-only, symptom-level) ─────────────────────────────────

def mandatory_symptom_ids(disorder_id: str, criteria: dict) -> set[str]:
    """Flatten a disorder's must_include pools into a single symptom-ID set (no min_count grouping)."""
    return {s for pool in _mandatory_pools(disorder_id, criteria) for s in pool}


# ── Discriminative symptoms ────────────────────────────────────────────────────

def get_discriminative_symptoms(candidates: list[str], criteria: dict) -> set[str]:
    """
    S_disc,t = {s : 0 < |D_t(s)| < |C_t|}
    A symptom is discriminative if it's associated with SOME but not ALL current
    candidates. Undefined (empty) when |C_t| < 2 — nothing left to discriminate.
    """
    if len(candidates) < 2:
        return set()
    counts: dict[str, int] = {}
    for d in candidates:
        for s in all_symptom_ids_for_disorder(d, criteria):
            counts[s] = counts.get(s, 0) + 1
    n = len(candidates)
    return {s for s, c in counts.items() if 0 < c < n}


# ── Required symptoms (mandatory symptoms only) ───────────────────────────────

def get_required_symptoms(candidates: list[str], criteria: dict) -> set[str]:
    """
    R_t = union of MUST_INCLUDE mandatory-pool symptom IDs across current candidates.
    Symptom-level, ungated by group min_count (see module docstring).
    Non-symptom requirements (duration, impairment, additional) are out of scope.
    """
    req: set[str] = set()
    for d in candidates:
        req |= mandatory_symptom_ids(d, criteria)
    return req


def get_candidate_symptoms(candidates: list[str], criteria: dict) -> set[str]:
    """Union of ALL symptoms (mandatory + optional pools) tied to current candidates — debug context field."""
    out: set[str] = set()
    for d in candidates:
        out |= all_symptom_ids_for_disorder(d, criteria)
    return out


def get_resolved_symptoms(symptom_universe: set[str], confirmed: set[str], denied: set[str]) -> set[str]:
    return symptom_universe & (confirmed | denied)


def get_unresolved_symptoms(symptom_universe: set[str], confirmed: set[str], denied: set[str]) -> set[str]:
    return symptom_universe - (confirmed | denied)


# ── Diagnostic Relevance Score ─────────────────────────────────────────────────

def diagnostic_relevance_score(
    question_targets: list[str],
    candidates: list[str],
    criteria: dict,
) -> tuple[float, set[str], set[str], set[str]]:
    """
    DRS_t = |S(q_t) ∩ I_t| / |S(q_t)|,  I_t = S_disc,t ∪ R_t
    Returns (drs, discriminative_symptoms, required_symptoms, informative_symptoms).
    DRS = 0.0 when question_targets is empty.
    """
    q = set(question_targets)
    disc = get_discriminative_symptoms(candidates, criteria)
    req = get_required_symptoms(candidates, criteria)
    informative = disc | req
    if not q:
        return 0.0, disc, req, informative
    overlap = q & informative
    return round(len(overlap) / len(q), 4), disc, req, informative


# ── Redundancy Penalty ─────────────────────────────────────────────────────────

def redundancy_penalty(
    question_targets: list[str],
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
) -> tuple[float, set[str]]:
    """
    RP_t = |S(q_t) ∩ S_resolved,t| / |S(q_t)|
    S_resolved,t = cumulative_confirmed ∪ cumulative_denied (3-state: UNKNOWN is
    never "resolved", which already covers ambiguous previous answers — see
    module docstring).
    Returns (rp, resolved_targets). RP = 0.0 when question_targets is empty.
    """
    q = set(question_targets)
    if not q:
        return 0.0, set()
    resolved = cumulative_confirmed | cumulative_denied
    resolved_targets = q & resolved
    return round(len(resolved_targets) / len(q), 4), resolved_targets


# ── Question Targeting Score ───────────────────────────────────────────────────

def question_targeting_score(
    question_targets: list[str],
    candidates: list[str],
    criteria: dict,
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
) -> dict:
    """
    QTS_t = DRS_t * (1 - RP_t)

    Returns a dict with the score plus every intermediate/debug quantity:
      qts, diagnostic_relevance, redundancy_penalty,
      question_targets, discriminative_targets, required_targets, resolved_targets,
      discriminative_symptoms, required_symptoms, candidate_symptoms,
      resolved_symptoms, unresolved_symptoms
    """
    drs, disc, req, informative = diagnostic_relevance_score(question_targets, candidates, criteria)
    rp, resolved_targets = redundancy_penalty(question_targets, cumulative_confirmed, cumulative_denied)
    qts = round(drs * (1 - rp), 4)

    q = set(question_targets)
    candidate_symptoms = get_candidate_symptoms(candidates, criteria)
    unresolved_candidate_symptoms = get_unresolved_symptoms(candidate_symptoms, cumulative_confirmed, cumulative_denied)
    resolved_candidate_symptoms = candidate_symptoms - unresolved_candidate_symptoms

    return {
        "qts": qts,
        "diagnostic_relevance": drs,
        "redundancy_penalty": rp,
        "question_targets": sorted(q),
        "discriminative_targets": sorted(q & disc),
        "required_targets": sorted(q & req),
        "resolved_targets": sorted(resolved_targets),
        # full context sets, for debugging / case study — not just the question's overlap
        "discriminative_symptoms": sorted(disc),
        "required_symptoms": sorted(req),
        "candidate_symptoms": sorted(candidate_symptoms),
        "resolved_symptoms": sorted(resolved_candidate_symptoms),
        "unresolved_symptoms": sorted(unresolved_candidate_symptoms),
    }


# ── [DEACTIVATED] Expected Candidate Reduction ────────────────────────────────
# Not part of the headline metric set. Kept for reference; re-enable by
# un-commenting the call in score_question() and the ECR aggregates in
# compute_episode_question_metrics().

def _answer_probability(
    symptom_id: str,
    mandatory_holder_count: int,
    n_candidates: int,
    probability_mode: str,
    answer_probs: Optional[dict],
) -> tuple[float, float]:
    if probability_mode == "uniform_answer":
        return 0.5, 0.5
    if probability_mode == "provided":
        if not answer_probs:
            raise ValueError('probability_mode="provided" requires answer_probs')
        entry = answer_probs.get(symptom_id, answer_probs)
        p_pos = float(entry.get("positive", 0.5))
        p_neg = float(entry.get("negative", 1.0 - p_pos))
        return p_pos, p_neg
    if probability_mode == "candidate_frequency":
        p_pos = mandatory_holder_count / n_candidates if n_candidates else 0.5
        return p_pos, 1.0 - p_pos
    raise ValueError(f"Unknown probability_mode: {probability_mode!r}")


def expected_candidate_reduction(
    question_targets: list[str],
    candidates: list[str],
    criteria: dict,
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
    probability_mode: str = DEFAULT_PROBABILITY_MODE,
    answer_probs: Optional[dict] = None,
) -> tuple[Optional[float], dict]:
    """
    [DEACTIVATED] ECR_t = mean over unresolved targeted symptoms of:
        1 - [P(+)*|C_pos| + P(-)*|C_neg|] / |C_t|
    with |C_pos| = |C_t| (confirming never excludes) and
    |C_neg| = |C_t| - |mandatory_holders| (denying excludes mandatory holders).
    """
    n = len(candidates)
    q = set(question_targets)

    if n == 0:
        return None, {"reason": "no_candidates", "unresolved_targets": [], "per_target": {}}
    if n == 1:
        return 0.0, {"reason": "single_candidate", "unresolved_targets": [], "per_target": {}}
    if not q:
        return 0.0, {"reason": "no_question_targets", "unresolved_targets": [], "per_target": {}}

    resolved = cumulative_confirmed | cumulative_denied
    unresolved_targets = sorted(q - resolved)
    if not unresolved_targets:
        return 0.0, {"reason": "all_targets_resolved", "unresolved_targets": [], "per_target": {}}

    per_target: dict[str, dict] = {}
    for s in unresolved_targets:
        holders = {d for d in candidates if s in mandatory_symptom_ids(d, criteria)}
        k = len(holders)
        p_pos, p_neg = _answer_probability(s, k, n, probability_mode, answer_probs)
        size_pos = n
        size_neg = n - k
        expected = p_pos * size_pos + p_neg * size_neg
        per_target[s] = {
            "ecr": round(1.0 - expected / n, 4),
            "mandatory_holders": sorted(holders),
            "p_positive": round(p_pos, 4),
            "p_negative": round(p_neg, 4),
            "size_if_positive": size_pos,
            "size_if_negative": size_neg,
        }

    ecr = round(sum(v["ecr"] for v in per_target.values()) / len(per_target), 4)
    return ecr, {
        "unresolved_targets": unresolved_targets,
        "multi_target_mode": "per_target_mean",
        "probability_mode": probability_mode,
        "per_target": per_target,
    }


# ── Combined per-turn scoring entry point ──────────────────────────────────────

def score_question(
    question: str,
    candidates: list[str],
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
    all_symptoms: dict,
    criteria: dict,
    mapper: QuestionSymptomMapper,
    probability_mode: str = DEFAULT_PROBABILITY_MODE,
    answer_probs: Optional[dict] = None,
) -> dict:
    """
    Map `question` to targeted symptom IDs via `mapper`, then compute QTS for
    that turn. Returns the full QTS debug dict plus `candidate_disorders`.
    """
    q_syms = mapper.map(question, all_symptoms)
    qts_result = question_targeting_score(
        q_syms, candidates, criteria, cumulative_confirmed, cumulative_denied
    )
    # [DEACTIVATED] ECR — not a headline metric.
    # ecr, ecr_debug = expected_candidate_reduction(
    #     q_syms, candidates, criteria,
    #     cumulative_confirmed, cumulative_denied,
    #     probability_mode=probability_mode, answer_probs=answer_probs,
    # )
    return {
        **qts_result,
        # "ecr": ecr,
        # "ecr_debug": ecr_debug,
        # "probability_mode": probability_mode,
        "candidate_disorders": sorted(candidates),
    }


# ── Episode-level aggregate metrics ───────────────────────────────────────────

def compute_episode_question_metrics(turns: list[dict], mapper_name: str) -> dict:
    """
    Per-episode QTS aggregate for one mapper.

    Headline: mean_qts = mean of per-turn QTS over ALL scored turns.
    """

    def _mean(lst: list) -> Optional[float]:
        return float(np.mean(lst)) if lst else None

    scored: list[dict] = []
    sizes: list[int] = []
    for t in turns:
        sbm = t.get("scores_by_mapper", {})
        if mapper_name not in sbm:
            continue
        scored.append(sbm[mapper_name])
        sizes.append(t.get("candidate_size", 0))

    if not scored:
        return {}

    all_qts = [s.get("qts", 0.0) for s in scored]
    all_rp = [s.get("redundancy_penalty", 0.0) for s in scored]

    # [DEACTIVATED] active-turn (|C_t| > 1) conditional means and ECR aggregates.
    # active_s = [s for s, sz in zip(scored, sizes) if sz > 1]
    # active_qts = [s.get("qts", 0.0) for s in active_s]
    # all_ecr = [s["ecr"] for s in scored if s.get("ecr") is not None]
    # active_ecr = [s["ecr"] for s in active_s if s.get("ecr") is not None]
    # half = max(1, (len(active_ecr) + 1) // 2)
    # early_ecr = active_ecr[:half]

    return {
        "mean_qts": _mean(all_qts),
        "mean_redundancy": _mean(all_rp),  # QTS component, kept for debugging
        # "active_turn_count": len(active_s),
        # "conditional_mean_qts": _mean(active_qts),
        # "mean_ecr": _mean(all_ecr),
        # "conditional_mean_ecr": _mean(active_ecr),
        # "ecr_positive_rate": (
        #     sum(1 for e in active_ecr if e > 0) / len(active_ecr) if active_ecr else None
        # ),
        # "early_ecr_mean": _mean(early_ecr),
    }
