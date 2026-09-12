"""
Information Acquisition Score (IAS) and Expected Candidate Reduction (ECR)
============================================================================

Turn-level scoring for the "정보 수집 능력" (information acquisition) evaluation
dimension — replaces "Question Quality" (DCS / composite_score / mandatory_first
/ edge_alignment, still available in question_score.py for reference/ablation)
as the reported question-quality axis in the evaluation pipeline.

  IAS = DRS * (1 - RP)             "did the question ask for relevant, unresolved info?"
  ECR = 1 - E[|C_t+1|] / |C_t|     "how much does the question narrow the candidate set?"

These are two INDEPENDENT metrics — do not multiply them together. Both are
computed and reported per turn, alongside every intermediate quantity used to
derive them, for debugging / case-study inspection.

Design decisions (locked in with the user):

- Evidence state stays 3-state: CONFIRMED / DENIED / UNKNOWN. No AMBIGUOUS
  label. The symptom-extraction judge (eval/symptom_diagnosis.py) already
  errs toward UNKNOWN on ambiguous patient replies ("Do NOT speculate...
  Err toward UNKNOWN (omit) rather than guessing"), so UNKNOWN already means
  "unresolved" regardless of *why* — a clarifying re-ask of an ambiguous
  answer is never mistaken for a redundant one.

- "Required" criteria = MUST_INCLUDE mandatory-pool symptoms ONLY, tracked at
  individual-symptom granularity (no group/min_count gating — a group is not
  treated as "already satisfied" once min_count members are confirmed, since
  asking about individual mandatory symptoms one at a time is the natural
  conversational unit). Non-symptom requirements (min_duration,
  functional_impairment_required, additional_requirements) are OUT OF SCOPE
  for this MVP — the pipeline has no evidence extraction for them yet.

- mandatory_first_compliance is dropped as an independent axis; required-ness
  now folds directly into `I_t = discriminative ∪ required` for IAS.

- ECR candidate filtering is presence-based (Option A: does the symptom sit in
  the disorder's pool, y/n) but restricted to MANDATORY-pool membership. This
  matters for consistency: under compute_reference_candidates()
  (question_score.py), a candidate is excluded from C_t ONLY when a MANDATORY
  symptom is denied — denying (or confirming) an optional/associated symptom
  never changes candidate-set membership. So:
    - confirming a symptom never excludes a candidate  -> "positive" branch is
      always the full C_t (size unchanged).
    - denying a symptom excludes exactly the candidates for which that
      symptom is mandatory -> "negative" branch shrinks by that count.
  Using plain pool-membership (mandatory ∪ optional) instead would make ECR
  disagree with the candidate-set definition that accuracy/recall/jaccard use
  elsewhere in the pipeline (optional-symptom denial would appear to reduce
  the candidate set when it actually doesn't).

- Multi-symptom questions: ECR = mean over UNRESOLVED targeted symptoms only
  (per_target_mean). Already-resolved targets are dropped from the average
  rather than counted as 0 — IAS's redundancy_penalty already penalizes
  re-asking resolved symptoms, so this avoids double-penalizing the same
  question on two different metrics.

- probability_mode default = "candidate_frequency", using the same
  mandatory-pool-membership rule as the filtering step for consistency.
  Configurable via config.json -> evaluation.information_acquisition.
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

_IAS_CFG = (CONFIG.get("evaluation") or {}).get("information_acquisition") or {}
DEFAULT_PROBABILITY_MODE = _IAS_CFG.get("probability_mode", "candidate_frequency")


# ── KG helpers (mandatory-only, symptom-level) ─────────────────────────────────

def mandatory_symptom_ids(disorder_id: str, criteria: dict) -> set[str]:
    """Flatten a disorder's must_include pools into a single symptom-ID set (no min_count grouping)."""
    return {s for pool in _mandatory_pools(disorder_id, criteria) for s in pool}


# ── §2 Discriminative symptoms ─────────────────────────────────────────────────

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


# ── §3 Required diagnostic requirements (MVP: mandatory symptoms only) ────────

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


# ── §4 Diagnostic Relevance Score ──────────────────────────────────────────────

def diagnostic_relevance_score(
    question_targets: list[str],
    candidates: list[str],
    criteria: dict,
) -> tuple[float, set[str], set[str], set[str]]:
    """
    DRS_t = |S(q_t) ∩ I_t| / |S(q_t)|,  I_t = S_disc,t ∪ R_t
    Returns (drs, discriminative_symptoms, required_symptoms, informative_symptoms).
    DRS = 0.0 when question_targets is empty (edge case §13).
    """
    q = set(question_targets)
    disc = get_discriminative_symptoms(candidates, criteria)
    req = get_required_symptoms(candidates, criteria)
    informative = disc | req
    if not q:
        return 0.0, disc, req, informative
    overlap = q & informative
    return round(len(overlap) / len(q), 4), disc, req, informative


# ── §5 Redundancy Penalty ──────────────────────────────────────────────────────

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


# ── §6 Information Acquisition Score ───────────────────────────────────────────

def information_acquisition_score(
    question_targets: list[str],
    candidates: list[str],
    criteria: dict,
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
) -> dict:
    """
    IAS_t = DRS_t * (1 - RP_t)

    Returns a dict with the score plus every intermediate/debug quantity:
      ias, diagnostic_relevance, redundancy_penalty,
      question_targets, discriminative_targets, required_targets, resolved_targets,
      discriminative_symptoms, required_symptoms, candidate_symptoms,
      resolved_symptoms, unresolved_symptoms
    """
    drs, disc, req, informative = diagnostic_relevance_score(question_targets, candidates, criteria)
    rp, resolved_targets = redundancy_penalty(question_targets, cumulative_confirmed, cumulative_denied)
    ias = round(drs * (1 - rp), 4)

    q = set(question_targets)
    candidate_symptoms = get_candidate_symptoms(candidates, criteria)
    unresolved_candidate_symptoms = get_unresolved_symptoms(candidate_symptoms, cumulative_confirmed, cumulative_denied)
    resolved_candidate_symptoms = candidate_symptoms - unresolved_candidate_symptoms

    return {
        "ias": ias,
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


# ── §7-9 Expected Candidate Reduction ──────────────────────────────────────────

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
    ECR_t = mean over unresolved targeted symptoms of:
        1 - [P(+)*|C_pos| + P(-)*|C_neg|] / |C_t|

    Candidate filtering (Option A, mandatory-only — see module docstring):
      |C_pos| = |C_t|                       (confirming never excludes)
      |C_neg| = |C_t| - |mandatory_holders| (denying excludes mandatory holders)

    multi_target_mode = "per_target_mean" (only mode implemented): resolved
    targets are dropped from the average, not counted as 0 (avoids double-
    penalizing redundancy, which IAS already scores).

    Returns (ecr, debug) where debug holds unresolved_targets + per-target detail.
      ecr = None  if len(candidates) == 0 (undefined)
      ecr = 0.0   if len(candidates) == 1, or question_targets is empty,
                  or all targeted symptoms are already resolved
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
    Map `question` to targeted symptom IDs via `mapper`, then compute IAS and ECR
    for that turn. Returns the full IAS debug dict plus `ecr`, `ecr_debug`,
    `candidate_disorders`, and `probability_mode`.
    """
    q_syms = mapper.map(question, all_symptoms)
    ias_result = information_acquisition_score(
        q_syms, candidates, criteria, cumulative_confirmed, cumulative_denied
    )
    ecr, ecr_debug = expected_candidate_reduction(
        q_syms, candidates, criteria,
        cumulative_confirmed, cumulative_denied,
        probability_mode=probability_mode, answer_probs=answer_probs,
    )
    return {
        **ias_result,
        "ecr": ecr,
        "ecr_debug": ecr_debug,
        "candidate_disorders": sorted(candidates),
        "probability_mode": probability_mode,
    }


# ── Episode-level aggregate metrics ───────────────────────────────────────────

def compute_episode_information_metrics(turns: list[dict], mapper_name: str) -> dict:
    """
    Per-episode aggregate IAS/ECR metrics for one mapper.
    Active turns = candidate_size > 1 (discrimination/reduction still possible).
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

    all_ias = [s.get("ias", 0.0) for s in scored]
    all_ecr = [s["ecr"] for s in scored if s.get("ecr") is not None]
    all_rp = [s.get("redundancy_penalty", 0.0) for s in scored]

    active_s = [s for s, sz in zip(scored, sizes) if sz > 1]
    active_ias = [s.get("ias", 0.0) for s in active_s]
    active_ecr = [s["ecr"] for s in active_s if s.get("ecr") is not None]

    half = max(1, (len(active_ecr) + 1) // 2)
    early_ecr = active_ecr[:half]

    return {
        # all turns
        "mean_ias": _mean(all_ias),
        "mean_ecr": _mean(all_ecr),
        "mean_redundancy": _mean(all_rp),
        # active turns only
        "active_turn_count": len(active_s),
        "conditional_mean_ias": _mean(active_ias),
        "conditional_mean_ecr": _mean(active_ecr),
        "ecr_positive_rate": (
            sum(1 for e in active_ecr if e > 0) / len(active_ecr) if active_ecr else None
        ),
        "redundancy_rate": _mean(all_rp),
        "early_ecr_mean": _mean(early_ecr),
    }
