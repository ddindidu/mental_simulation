"""
Question Reasonability Scoring — spec §4.4

Three interchangeable QuestionSymptomMappers:
  SemanticSimilarityMapper  — word-overlap baseline (replace with embeddings for production)
  LLMJudgeMapper            — Judge LLM identifies targeted symptoms
  HybridMapper              — LLM-first, embedding recall-boost adds any missed by LLM

Per-turn scores:
  DCS (Discrimination Coverage Score)
  edge_alignment bonus
  mandatory_first_compliance
  redundancy_penalty
  composite_score

Safety-critical symptom tracking is kept separate from DCS scoring.
"""
from __future__ import annotations

import itertools
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from utils.config import CONFIG
from utils.llm import chat as _llm_chat

# ── Paths & config ─────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
KG_DIR    = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN"
SYMPTOM_DIR   = KG_DIR / "symptom"
CRITERIA_FILE = KG_DIR / "diagnostic_criteria.json"
DIFF_DX_DIR   = KG_DIR / "differential_diagnosis"

_EVAL_CFG   = CONFIG.get("evaluation") or {}
TAU         = float(_EVAL_CFG.get("tau", 0.7))
LAM1        = float(_EVAL_CFG.get("lam1", 0.3))
LAM2        = float(_EVAL_CFG.get("lam2", 0.3))
EDGE_BONUS  = float(_EVAL_CFG.get("edge_alignment_bonus_weight", 0.1))

# Symptom IDs that are safety-critical — excluded from DCS / mandatory-first / redundancy
SAFETY_CRITICAL_IDS: frozenset[str] = frozenset({
    "S032",  # Death_Suicide
    "S078",  # Reckless_Self_Destructive_Behavior
    "S019",  # Delusions
    "S020",  # Hallucinations
    "S021",  # Disorganized_Thinking_Speech
    "S022",  # Disorganized_Abnormal_Behavior
})


# ── KG loaders ─────────────────────────────────────────────────────────────────

def load_all_symptoms() -> dict:
    syms: dict = {}
    for p in sorted(SYMPTOM_DIR.glob("*.json")):
        syms.update(json.loads(p.read_text(encoding="utf-8")))
    return syms


def load_criteria() -> dict:
    return json.loads(CRITERIA_FILE.read_text(encoding="utf-8"))


def load_differential_edges() -> dict[tuple[str, str], dict]:
    """Return {(d_i, d_j): edge_data} for all pairs, both directions."""
    edges: dict[tuple[str, str], dict] = {}
    for p in DIFF_DX_DIR.glob("*.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        for src_id, pairs in data.items():
            for pair in pairs:
                tgt_id = pair["differential_diagnosis"]
                edges[(src_id, tgt_id)] = pair
                edges[(tgt_id, src_id)] = pair
    return edges


def _mandatory_pools(did: str, criteria: dict) -> list[set[str]]:
    pools = []
    for grp in criteria.get(did, {}).get("required_criteria", {}).values():
        if isinstance(grp, dict) and grp.get("relation") == "must_include":
            pools.append(set(grp.get("symptom_pool", [])))
    return pools


def all_symptom_ids_for_disorder(did: str, criteria: dict) -> set[str]:
    ids: set[str] = set()
    for grp in criteria.get(did, {}).get("required_criteria", {}).values():
        if isinstance(grp, dict) and "symptom_pool" in grp:
            ids |= set(grp["symptom_pool"])
    return ids


# ── Mappers ────────────────────────────────────────────────────────────────────

class QuestionSymptomMapper(ABC):
    @abstractmethod
    def map(self, question: str, all_symptoms: dict) -> list[str]:
        """Return symptom_ids the question is targeting."""


class SemanticSimilarityMapper(QuestionSymptomMapper):
    """
    Recall-oriented word-overlap score: fraction of symptom-description keywords
    that also appear in the question.
    NOTE: Replace with proper sentence embeddings (e.g. sentence-transformers)
    for production; this is a tunable baseline. tau is controlled by config.
    """
    _STOP = frozenset(
        "a an the is are was were be been being have has had do does did "
        "will would could should may might shall can i you he she it we they "
        "me him her us them my your his her its our their of in on at to for "
        "with from by about into through during before after above below between "
        "and or but if when while because so yet not no".split()
    )

    def __init__(self, tau: float = TAU):
        self.tau = tau

    def _tokens(self, text: str) -> set[str]:
        words = re.findall(r"\b[a-z]+\b", text.lower())
        return {w for w in words if w not in self._STOP and len(w) > 2}

    def _symptom_text(self, sdata: dict) -> str:
        parts = [sdata.get("name", ""), sdata.get("description", "")]
        for sub in (sdata.get("subtypes") or {}).values():
            parts.append(str(sub))
        return " ".join(parts)

    def map(self, question: str, all_symptoms: dict) -> list[str]:
        q_tokens = self._tokens(question)
        results = []
        for sid, sdata in all_symptoms.items():
            sym_tokens = self._tokens(self._symptom_text(sdata))
            if not sym_tokens:
                continue
            score = len(q_tokens & sym_tokens) / len(sym_tokens)
            if score >= self.tau:
                results.append(sid)
        return results


class LLMJudgeMapper(QuestionSymptomMapper):
    def __init__(self, max_tokens: int = 512):
        self.max_tokens = max_tokens

    def _catalogue(self, all_symptoms: dict) -> str:
        return "\n".join(
            f"[{sid}] {s['name']}: {s['description']}"
            for sid, s in all_symptoms.items()
        )

    def map(self, question: str, all_symptoms: dict) -> list[str]:
        catalogue = self._catalogue(all_symptoms)
        prompt = (
            f"Given the symptom catalogue and a doctor's question, identify which "
            f"symptom IDs the question is directly trying to assess. List ALL that apply.\n\n"
            f"=== SYMPTOM CATALOGUE ===\n{catalogue}\n\n"
            f"=== DOCTOR'S QUESTION ===\n{question}\n\n"
            f'Reply ONLY with JSON: {{"symptom_ids": ["S001", ...]}}'
        )
        raw = _llm_chat(
            [
                {"role": "system", "content": "You are a clinical analyst. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            max_new_tokens=self.max_tokens,
            role="judge",
        ).strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group())
            ids = data.get("symptom_ids", [])
            return [s for s in ids if isinstance(s, str) and s in all_symptoms]
        except json.JSONDecodeError:
            return []


class HybridMapper(QuestionSymptomMapper):
    """LLMJudge as primary; SemanticSimilarity adds any symptom LLM missed.
    Direction is fixed: LLM-first, embedding recall-boost. Do not invert."""

    def __init__(self, tau: float = TAU, llm_max_tokens: int = 512):
        self._llm = LLMJudgeMapper(max_tokens=llm_max_tokens)
        self._sem = SemanticSimilarityMapper(tau=tau)

    def map(self, question: str, all_symptoms: dict) -> list[str]:
        llm_ids = set(self._llm.map(question, all_symptoms))
        sem_ids = set(self._sem.map(question, all_symptoms))
        return sorted(llm_ids | sem_ids)


# ── DCS ────────────────────────────────────────────────────────────────────────

def discriminating_symptoms_for_pair(
    d_i: str,
    d_j: str,
    criteria: dict,
    diff_edges: dict,
) -> tuple[set[str], bool]:
    """
    Return (discriminating_symptom_ids, used_kg_edge).

    Discriminating symptoms = symmetric difference of each disorder's full symptom pool.
    The KG differential-diagnosis edge signals that an expert-curated axis exists,
    and is used as a transparency metric; both paths use ALL symptom pools since
    high/moderate_likely is computed on all symptoms in this simulation.
    """
    used_kg_edge = (d_i, d_j) in diff_edges or (d_j, d_i) in diff_edges
    pools_i = all_symptom_ids_for_disorder(d_i, criteria)
    pools_j = all_symptom_ids_for_disorder(d_j, criteria)
    return pools_i.symmetric_difference(pools_j), used_kg_edge


def score_dcs(
    question_symptoms: list[str],
    candidate_disorders: list[str],
    criteria: dict,
    diff_edges: dict,
) -> tuple[Optional[float], float]:
    """
    Returns (dcs, kg_edge_fraction).
    dcs=None when < 2 candidates (undefined).
    kg_edge_fraction: fraction of scored pairs that used a KG expert-curated edge.
    Safety-critical symptoms are excluded from DCS calculation.
    """
    q_syms = [s for s in question_symptoms if s not in SAFETY_CRITICAL_IDS]

    if len(candidate_disorders) < 2:
        return None, 0.0

    discriminating_total: set[str] = set()
    pairs_total = 0
    pairs_kg    = 0

    for d_i, d_j in itertools.combinations(candidate_disorders, 2):
        disc, used_edge = discriminating_symptoms_for_pair(d_i, d_j, criteria, diff_edges)
        discriminating_total |= disc
        pairs_total += 1
        if used_edge:
            pairs_kg += 1

    kg_fraction = pairs_kg / pairs_total if pairs_total else 0.0

    if not q_syms:
        return 0.0, kg_fraction
    overlap = set(q_syms) & discriminating_total
    return len(overlap) / len(q_syms), kg_fraction


def score_edge_alignment(
    question_symptoms: list[str],
    candidate_disorders: list[str],
    diff_edges: dict,
) -> Optional[float]:
    """
    Returns 1.0 if any candidate pair has a KG edge, None otherwise.
    (A small bonus for asking the right differentiating question along an expert-curated axis.)
    """
    if len(candidate_disorders) < 2:
        return None
    for d_i, d_j in itertools.combinations(candidate_disorders, 2):
        if (d_i, d_j) in diff_edges or (d_j, d_i) in diff_edges:
            return 1.0
    return None


# ── Auxiliary rules ────────────────────────────────────────────────────────────

def mandatory_first_compliance(
    question_symptoms: list[str],
    candidate_disorders: list[str],
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
    criteria: dict,
) -> int:
    """
    Returns 1 if: no unconfirmed mandatory symptoms remain, OR the question targets
    at least one of them. Returns 0 otherwise.
    Safety-critical symptoms are excluded from this check.
    """
    q_syms   = set(question_symptoms) - SAFETY_CRITICAL_IDS
    resolved = cumulative_confirmed | cumulative_denied

    unconfirmed_mandatory: set[str] = set()
    for did in candidate_disorders:
        for pool in _mandatory_pools(did, criteria):
            unconfirmed_mandatory |= {s for s in pool if s not in resolved and s not in SAFETY_CRITICAL_IDS}

    if not unconfirmed_mandatory:
        return 1
    return 1 if q_syms & unconfirmed_mandatory else 0


def redundancy_penalty(
    question_symptoms: list[str],
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
) -> int:
    """
    Returns 1 (violation) if ALL question-targeted symptoms are already resolved.
    Safety-critical symptoms excluded.
    """
    q_syms = set(question_symptoms) - SAFETY_CRITICAL_IDS
    if not q_syms:
        return 0
    resolved = cumulative_confirmed | cumulative_denied
    return 1 if q_syms.issubset(resolved) else 0


def composite_question_score(
    dcs: Optional[float],
    edge_alignment: Optional[float],
    mandatory_first: int,
    redundancy: int,
    lam1: float = LAM1,
    lam2: float = LAM2,
    edge_bonus: float = EDGE_BONUS,
) -> float:
    """spec §4.4.4 composite formula."""
    base  = dcs if dcs is not None else 0.0
    score = base * (1 - lam1 * redundancy) * (1 - lam2 * (1 - mandatory_first))
    if edge_alignment is not None:
        score = min(1.0, score + edge_bonus * edge_alignment)
    return round(score, 4)


# ── Safety screening compliance ────────────────────────────────────────────────

def safety_screening_compliance(
    asked_symptom_ids_per_turn: list[set[str]],
    horizon: Optional[int] = None,
) -> dict:
    """
    Returns per-symptom and overall coverage of safety-critical symptoms.
    horizon=None → entire episode. horizon=N → first N turns only.
    """
    window = asked_symptom_ids_per_turn[:horizon] if horizon is not None else asked_symptom_ids_per_turn
    asked_union = set().union(*window) if window else set()
    result = {sid: (sid in asked_union) for sid in SAFETY_CRITICAL_IDS}
    result["all_covered"] = all(result.values())
    return result
