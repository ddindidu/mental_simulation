"""
Question Reasonability Scoring — spec §4.4

Two primary QuestionSymptomMappers:
  CosineSemanticMapper  — sentence-embedding cosine similarity (all-MiniLM-L6-v2)
  LLMJudgeMapper        — Judge LLM identifies targeted symptoms with cosine pre-filter

Legacy:
  SemanticSimilarityMapper — word-overlap baseline (kept for ablation)
  HybridMapper             — cosine union llm_judge

Per-turn scores:
  DCS (Discrimination Coverage Score)
  edge_alignment bonus
  mandatory_first_compliance
  redundancy_penalty
  composite_score
  information_gain

Episode-level aggregate metrics (conditional on active turns):
  ig_positive_rate, discriminating_q_rate, conditional_mean_composite,
  conditional_mean_ig, redundancy_rate, early_ig_mean

Safety-critical symptom tracking is kept separate from DCS scoring.
"""
from __future__ import annotations

import itertools
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))
from typing import Optional

import numpy as np

from utils.config import CONFIG
from utils.llm import chat as _llm_chat

# ── Paths & config ─────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent
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


def _mandatory_pools_with_count(did: str, criteria: dict) -> list[tuple[set[str], int]]:
    pools = []
    for grp in criteria.get(did, {}).get("required_criteria", {}).values():
        if isinstance(grp, dict) and grp.get("relation") == "must_include":
            pools.append((set(grp.get("symptom_pool", [])), grp.get("min_count", 1)))
    return pools


def _optional_symptom_ids_for_disorder(did: str, criteria: dict) -> set[str]:
    ids: set[str] = set()
    for grp in criteria.get(did, {}).get("required_criteria", {}).values():
        if isinstance(grp, dict) and "symptom_pool" in grp and grp.get("relation") != "must_include":
            ids |= set(grp["symptom_pool"])
    return ids


def all_symptom_ids_for_disorder(did: str, criteria: dict) -> set[str]:
    ids: set[str] = set()
    for grp in criteria.get(did, {}).get("required_criteria", {}).values():
        if isinstance(grp, dict) and "symptom_pool" in grp:
            ids |= set(grp["symptom_pool"])
    return ids


def _candidate_set_size(
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
    criteria: dict,
) -> int:
    """
    Count |high_likely ∪ moderate_likely ∪ low_likely| from cumulative symptom state.
    Mirrors compute_candidate_set() in symptom_diagnosis.py; kept local to avoid
    importing that module's side effects.
    """
    count = 0
    for did, ddata in criteria.items():
        pools          = _mandatory_pools_with_count(did, criteria)
        mandatory_syms = {s for pool, _ in pools for s in pool}
        optional_syms  = _optional_symptom_ids_for_disorder(did, criteria)

        if not mandatory_syms and not optional_syms:
            continue

        # excluded: any mandatory symptom denied
        if mandatory_syms & cumulative_denied:
            continue

        mandatory_confirmed = mandatory_syms & cumulative_confirmed
        optional_confirmed  = optional_syms  & cumulative_confirmed

        if mandatory_confirmed or optional_confirmed:
            count += 1   # high, moderate, or low — all are candidates

    return count


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


_COSINE_TAU = float(_EVAL_CFG.get("cosine_tau", 0.35))
_LLM_PREFILTER_K = int(_EVAL_CFG.get("llm_prefilter_k", 30))


class CosineSemanticMapper(QuestionSymptomMapper):
    """
    Sentence-embedding cosine similarity mapper using all-MiniLM-L6-v2.
    Symptom embeddings are cached across calls (stable symptom set assumed).
    threshold is the minimum cosine similarity (config key: cosine_tau, default 0.35).
    """

    def __init__(self, threshold: float = _COSINE_TAU):
        self.threshold = threshold
        self._model: "SentenceTransformer | None" = None
        self._sym_embeddings: "np.ndarray | None" = None
        self._sym_ids: list[str] = []

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

    @staticmethod
    def _sym_text(sdata: dict) -> str:
        return f"{sdata.get('name', '')} {sdata.get('description', '')}".strip()

    def _ensure_embeddings(self, all_symptoms: dict) -> None:
        sids = sorted(all_symptoms.keys())
        if sids == self._sym_ids and self._sym_embeddings is not None:
            return
        model = self._get_model()
        texts = [self._sym_text(all_symptoms[s]) for s in sids]
        self._sym_embeddings = model.encode(
            texts, show_progress_bar=False, batch_size=64, normalize_embeddings=True
        )
        self._sym_ids = sids

    def map(self, question: str, all_symptoms: dict) -> list[str]:
        self._ensure_embeddings(all_symptoms)
        model = self._get_model()
        q_emb = model.encode(
            [question], show_progress_bar=False, normalize_embeddings=True
        )
        # Both sides normalized → dot product == cosine similarity
        sims: np.ndarray = (self._sym_embeddings @ q_emb.T).reshape(-1)
        return [self._sym_ids[i] for i, s in enumerate(sims) if s >= self.threshold]

    def top_k(self, question: str, all_symptoms: dict, k: int) -> list[str]:
        """Return the k highest-similarity symptom IDs (used by LLMJudgeMapper as pre-filter)."""
        self._ensure_embeddings(all_symptoms)
        model = self._get_model()
        q_emb = model.encode(
            [question], show_progress_bar=False, normalize_embeddings=True
        )
        sims = (self._sym_embeddings @ q_emb.T).reshape(-1)
        idx = np.argsort(sims)[::-1][:k]
        return [self._sym_ids[i] for i in idx]


_cosine_prefilter = CosineSemanticMapper()  # shared instance for LLMJudgeMapper pre-filter


class LLMJudgeMapper(QuestionSymptomMapper):
    """
    LLM judge mapper with cosine pre-filtering.

    Pipeline:
      1. CosineSemanticMapper.top_k() selects the top-K most similar symptoms
         (reduces prompt length from all 84 → K candidates).
      2. LLM identifies which of those K actually match the question.

    This keeps token cost low while preserving recall via the semantic pre-filter.
    """

    _SYSTEM = (
        "/no_think\n"
        "You are a clinical symptom analyst. "
        "Given a doctor's question and a list of candidate psychiatric symptoms, "
        "identify which symptom IDs the question is directly attempting to assess. "
        "Output ONLY valid JSON — no explanation, no markdown."
    )

    def __init__(self, max_tokens: int = 4096, prefilter_k: int = _LLM_PREFILTER_K):
        self.max_tokens = max_tokens
        self.prefilter_k = prefilter_k

    def map(self, question: str, all_symptoms: dict) -> list[str]:
        # Step 1: cosine pre-filter to top-K candidates
        top_ids = _cosine_prefilter.top_k(question, all_symptoms, k=self.prefilter_k)
        candidate_text = "\n".join(
            f"[{sid}] {all_symptoms[sid]['name']}: {all_symptoms[sid].get('description','')}"
            for sid in top_ids
        )
        user_msg = (
            f"DOCTOR'S QUESTION:\n{question}\n\n"
            f"CANDIDATE SYMPTOMS (top {self.prefilter_k} by semantic similarity):\n"
            f"{candidate_text}\n\n"
            f'Reply ONLY with JSON: {{"symptom_ids": ["S001", ...]}}\n'
            f"Include only IDs from the candidate list above that the question clearly targets."
        )
        raw = _llm_chat(
            [
                {"role": "system", "content": self._SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
            max_new_tokens=self.max_tokens,
            role="judge",
        ).strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$",       "", raw)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group())
            ids  = data.get("symptom_ids", [])
            return [s for s in ids if isinstance(s, str) and s in all_symptoms]
        except json.JSONDecodeError:
            return []


class HybridMapper(QuestionSymptomMapper):
    """CosineSemanticMapper ∪ LLMJudgeMapper (recall-boost union)."""

    def __init__(self):
        self._cosine  = CosineSemanticMapper()
        self._llm     = LLMJudgeMapper()

    def map(self, question: str, all_symptoms: dict) -> list[str]:
        cosine_ids = set(self._cosine.map(question, all_symptoms))
        llm_ids    = set(self._llm.map(question, all_symptoms))
        return sorted(cosine_ids | llm_ids)


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


# ── Information Gain (KG-based approximation) ─────────────────────────────────

def score_information_gain(
    question_symptoms: list[str],
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
    criteria: dict,
    current_candidate_size: int,
) -> Optional[float]:
    """
    KG-based Information Gain approximation — spec §4.4.x.

      IG = 1 − E[|C_{t+1}|] / |C_t|

    Simulates two equiprobable outcomes for the unresolved targeted symptoms:
      • Scenario A: patient confirms all targeted symptoms  → |C_confirmed|
      • Scenario B: patient denies  all targeted symptoms  → |C_denied|
      E[|C_{t+1}|] = 0.5 · |C_confirmed| + 0.5 · |C_denied|

    Returns None  when |C_t| ≤ 1 (already determined; IG undefined).
    Returns 0.0   when no unresolved symptoms are targeted (zero new information).
    Positive IG   → question is expected to narrow the candidate set.
    Negative IG   → question is expected to grow it (rare; implies KG inconsistency).
    """
    if current_candidate_size <= 1:
        return None

    resolved          = cumulative_confirmed | cumulative_denied
    unresolved        = [s for s in question_symptoms if s not in resolved]

    if not unresolved:
        return 0.0

    unresolved_set = set(unresolved)

    # Scenario A: confirm all targeted unresolved symptoms
    size_confirmed = _candidate_set_size(
        cumulative_confirmed | unresolved_set,
        cumulative_denied,
        criteria,
    )
    # Scenario B: deny all targeted unresolved symptoms
    size_denied = _candidate_set_size(
        cumulative_confirmed,
        cumulative_denied | unresolved_set,
        criteria,
    )

    expected_size = 0.5 * size_confirmed + 0.5 * size_denied
    return round(1.0 - expected_size / current_candidate_size, 4)


# ── Episode-level aggregate metrics ───────────────────────────────────────────

_DISCRIMINATING_Q_THRESHOLD = float(_EVAL_CFG.get("discriminating_q_threshold", 0.3))


def compute_episode_question_metrics(
    turns: list[dict],
    mapper_name: str,
    composite_threshold: float = _DISCRIMINATING_Q_THRESHOLD,
) -> dict:
    """
    Compute per-episode aggregate question-quality metrics for one mapper.

    Active turns: turns where candidate_size > 1 (discrimination still possible).
    IG values exclude None (i.e. turns already at size ≤ 1 are skipped).

    Returns a flat dict with:
      — existing aggregates (over ALL turns): mean_composite, mean_dcs, mean_redundancy
      — new conditional aggregates (over ACTIVE turns only):
          active_turn_count, conditional_mean_composite, conditional_mean_ig,
          ig_positive_rate, discriminating_q_rate, redundancy_rate, early_ig_mean
    """

    def _mean(lst: list) -> Optional[float]:
        return float(np.mean(lst)) if lst else None

    scored: list[dict] = []
    sizes:  list[int]  = []
    for t in turns:
        sbm = t.get("scores_by_mapper", {})
        if mapper_name not in sbm:
            continue
        scored.append(sbm[mapper_name])
        sizes.append(t.get("candidate_size", 0))

    if not scored:
        return {}

    # ── All-turn aggregates (existing behaviour) ──────────────────────────────
    all_composites  = [s.get("composite_score",    0.0) for s in scored]
    all_dcs         = [s["dcs"] for s in scored if s.get("dcs") is not None]
    all_redundancies = [s.get("redundancy_penalty", 0)   for s in scored]

    # ── Active-turn aggregates (NEW) ──────────────────────────────────────────
    active_s = [s for s, sz in zip(scored, sizes) if sz > 1]
    active_composites = [s.get("composite_score", 0.0) for s in active_s]

    # IG values from active turns, excluding None (size was already ≤ 1)
    active_igs: list[float] = [
        s["information_gain"]
        for s in active_s
        if s.get("information_gain") is not None
    ]

    # Early-turn IG: first ceil(len/2) active turns
    half      = max(1, (len(active_igs) + 1) // 2)
    early_igs = active_igs[:half]

    return {
        # existing (all turns)
        "mean_composite":  _mean(all_composites),
        "mean_dcs":        _mean(all_dcs),
        "mean_redundancy": _mean(all_redundancies),

        # new (active turns)
        "active_turn_count":          len(active_s),
        "conditional_mean_composite": _mean(active_composites),
        "conditional_mean_ig":        _mean(active_igs),
        "ig_positive_rate": (
            sum(1 for ig in active_igs if ig > 0) / len(active_igs)
            if active_igs else None
        ),
        "discriminating_q_rate": (
            sum(1 for c in active_composites if c > composite_threshold)
            / len(active_composites)
            if active_composites else None
        ),
        "redundancy_rate": _mean(all_redundancies),
        "early_ig_mean":   _mean(early_igs),
    }


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
