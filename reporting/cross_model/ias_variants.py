#!/usr/bin/env python3
"""
Three definitions of QTS's (formerly IAS) "informative target set" I_t, re-derived from
fields already stored per turn in results/.../question_eval.json
(eval/question_targeting_score.py's llm_judge-mapper output) — no KG
re-lookup or re-mapping needed:

  ias_disc          I_t = S_disc,t                         (discriminative only)
  ias_disc_mand     I_t = S_disc,t ∪ R_t                    (+ mandatory pool)  <- current production QTS
  ias_disc_mand_opt I_t = S_disc,t ∪ candidate_symptoms,t    (+ optional pool too;
                                                               candidate_symptoms is
                                                               already mandatory ∪ optional)

R_t ⊆ candidate_symptoms,t by construction (get_required_symptoms only pulls
must_include pools; get_candidate_symptoms pulls every pool regardless of
relation — see eval/question_targeting_score.py), so
S_disc ⊆ (S_disc ∪ R_t) ⊆ (S_disc ∪ candidate_symptoms,t): each variant's
informative set is a superset of the previous one, so DRS_t (and hence QTS_t,
since redundancy_penalty is identical across variants) is monotonically
non-decreasing disc -> disc_mand -> disc_mand_opt for every turn.
"""
from __future__ import annotations

IAS_VARIANT_KEYS = ["ias_disc", "ias_disc_mand", "ias_disc_mand_opt"]
IAS_VARIANT_LABELS = {
    "ias_disc": "QTS (discriminative only)",
    "ias_disc_mand": "QTS (discriminative + mandatory)  [current]",
    "ias_disc_mand_opt": "QTS (discriminative + mandatory + optional)",
}


def turn_ias_variants(scores: dict) -> dict[str, float]:
    """scores = one turn's scores_by_mapper[<mapper>] dict. Returns the 3
    variant IAS values for that turn (redundancy_penalty is shared across
    all three — only the informative-set definition changes)."""
    q = set(scores.get("question_targets") or [])
    disc = set(scores.get("discriminative_symptoms") or [])
    req = set(scores.get("required_symptoms") or [])
    cand_all = set(scores.get("candidate_symptoms") or [])  # mandatory + optional
    rp = scores.get("redundancy_penalty") or 0.0

    def drs(informative: set[str]) -> float:
        return (len(q & informative) / len(q)) if q else 0.0

    informative_sets = {
        "ias_disc": disc,
        "ias_disc_mand": disc | req,
        "ias_disc_mand_opt": disc | cand_all,
    }
    return {k: round(drs(s) * (1 - rp), 4) for k, s in informative_sets.items()}


def episode_ias_variants(entry: dict, mapper: str = "llm_judge") -> dict[str, float] | None:
    """entry = one question_eval.json list item (one episode). Returns
    {variant_key: mean-over-all-turns value}, or None if no turn has `mapper`
    scores. Mirrors compute_episode_question_metrics()'s all-turns mean_qts."""
    per_variant: dict[str, list[float]] = {k: [] for k in IAS_VARIANT_KEYS}
    found = False
    for t in entry.get("turns", []):
        scores = (t.get("scores_by_mapper") or {}).get(mapper)
        if scores is None:
            continue
        found = True
        variants = turn_ias_variants(scores)
        for k, v in variants.items():
            per_variant[k].append(v)
    if not found:
        return None
    return {k: (sum(vals) / len(vals) if vals else 0.0) for k, vals in per_variant.items()}
