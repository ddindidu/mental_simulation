# Turn-Level Psychiatric Diagnostic Dialogue Evaluation Pipeline — Technical Spec

## 0. Purpose

This document specifies an evaluation pipeline for assessing the psychiatric diagnostic
capability of LLMs (the "Doctor" model) through multi-turn dialogue with a simulated patient.
Unlike prior work that evaluates only final-diagnosis accuracy, this pipeline scores **four
axes**: (1) diagnostic inference quality (turn-level), (2) question reasonability (turn-level),
(3) dialogue efficiency (episode-level), and (4) diagnostic reasoning quality (final-diagnosis
checklist). Scoring is grounded in a DSM-5-based psychiatric knowledge graph (KG)
reused/extended from MentalKG (Song et al., MentalBench), rather than pattern matching or
unconstrained LLM-as-judge.

This is an implementation spec, not a research description. Build exactly what is specified;
flag ambiguities rather than silently resolving them.

---

## 1. System Architecture

```
[Patient] --utterance--> [Judge: Symptom Extraction (LLM-as-Judge)]
                                  |
                                  v
                      [Reference Candidate Computation (KG-deterministic)]
                                  |
                                  v
                    [Doctor: predict candidates + ask question]
                                  |
              +-------------------+-------------------+
              v                                        v
   [Judge: Inference Scoring]            [Judge: Question Reasonability Scoring]
              |                                        |
              +-------------------+-------------------+
                                  v
                         [question --> Patient] (candidates NEVER shown to Patient)
                                  |
                          (repeat for T turns)
                                  v
          [Overall Evaluation: Final Diagnosis Accuracy + Efficiency + Reasoning Quality]
```

Four roles:
- **Patient**: simulated patient, governed by a `PatientSimulator` with a pluggable
  `DisclosureScheduler` (difficulty-parameterized information release).
- **Doctor**: the LLM under evaluation. Produces structured output every turn.
- **Judge**: scoring logic. Symptom extraction uses LLM-as-judge; reference candidate
  computation and question-discrimination scoring are deterministic KG lookups wherever
  possible. Judge LLM (when used) MUST be a different model than the Doctor model under test,
  to avoid self-evaluation bias. Fix one Judge model across all experiments.
- **Knowledge Graph (KG)**: MentalKG schema — `Disorder`, `SymptomGroup`, `Symptom`,
  `DifferentialDiagnosis` nodes/edges. Reused as-is; do not modify the underlying schema
  without explicit sign-off.

---

## 2. Data Model

```python
from enum import Enum
from typing import Dict, List, Set, Optional, Literal
from pydantic import BaseModel

class SymptomStatus(str, Enum):
    CONFIRMED = "confirmed"
    DENIED = "denied"
    UNKNOWN = "unknown"

class SymptomExtractionResult(BaseModel):
    confirmed: List[str]            # symptom_id list
    denied: List[str]               # symptom_id list
    duration_info: Dict[str, str]   # symptom_id -> raw duration text (e.g. "2 weeks")

class CandidateSet(BaseModel):
    high_likely: Set[str]      # disorder_id: all mandatory groups meet min_count threshold
    moderate_likely: Set[str]  # disorder_id: ≥1 mandatory symptom confirmed, no mandatory denied
    low_likely: Set[str]       # disorder_id: 0 mandatory confirmed, ≥1 optional confirmed, no mandatory denied
    excluded: Set[str]         # disorder_id: ≥1 mandatory symptom explicitly denied

    def all_candidates(self) -> Set[str]:
        """Primary truth set for inference scoring and efficiency metrics."""
        return self.high_likely | self.moderate_likely | self.low_likely

    def strong_candidates(self) -> Set[str]:
        """Ablation axis: mandatory-evidence only (excludes low_likely)."""
        return self.high_likely | self.moderate_likely

class DoctorOutput(BaseModel):
    candidates: List[str]    # disorder names/ids the Doctor currently considers plausible
    question: str            # the ONLY field forwarded to the Patient
    is_final: bool = False
    final_diagnosis: Optional[str] = None
    diagnostic_checklist: Optional[dict] = None  # populated only when is_final=True (see §3, §4.6)
    is_valid_format: bool = True   # set False by the parser on schema-violation; do not let the Doctor set this

class InferenceScoreResult(BaseModel):
    precision: float
    recall: float
    accuracy: float          # strict set-equality against all_candidates(), 1.0 or 0.0
    jaccard: float
    weighted_recall: float   # high_likely misses 2×, moderate_likely 1×, low_likely 0.5× (see §4.3)

class QuestionScoreResult(BaseModel):
    dcs: float                       # Discrimination Coverage Score
    edge_alignment: Optional[float]  # None if no differential-diagnosis edge applies to any candidate pair
    mandatory_first_compliance: float  # 0/1
    redundancy_penalty: float          # 0/1, 1 = violation
    information_gain: Optional[float]  # None if |C_t|≤1; 0.0 if all targeted symptoms already resolved (see §4.4.5)
    composite_score: float
    targeted_symptoms_by_mapper: Dict[str, List[str]]  # mapper_name -> symptom_ids, for the 3-way comparison

class TurnLog(BaseModel):
    turn_id: int
    patient_utterance: str
    extraction: SymptomExtractionResult
    cumulative_symptom_status: Dict[str, SymptomStatus]
    reference_candidates: CandidateSet
    doctor_output: DoctorOutput
    inference_score: InferenceScoreResult
    question_score: QuestionScoreResult
    format_failure: bool

class DisclosureDifficultyConfig(BaseModel):
    duration_difficulty: Literal["easy", "hard"]
    core_symptom_concealment: Literal["easy", "hard"]
```

State invariant: `cumulative_symptom_status` is monotonically informative — once a symptom
is set to `CONFIRMED` or `DENIED`, it does not revert to `UNKNOWN`. If the extraction Judge
produces a conflicting label for an already-resolved symptom in a later turn, do NOT silently
overwrite; log it to a `label_conflict_log` for separate analysis and keep the original label.

---

## 3. Doctor I/O Contract

### 3.1 Mid-interview turns

The Doctor model MUST emit **only** the following JSON shape each turn:

```json
{
  "candidates": ["<disorder_name>", "..."],
  "question": "<single next question to ask the patient, natural conversational language>",
  "is_final": false,
  "final_diagnosis": null
}
```

System prompt template (parameterize disorder name list from KG at runtime):

```
You are a psychiatrist conducting a diagnostic interview with a patient.
At every turn, respond ONLY with JSON in this exact shape:
{"candidates": [...], "question": "...", "is_final": false, "final_diagnosis": null}

"candidates": list every DSM-5 disorder you currently consider plausible given the
conversation so far. Do not reveal this list to the patient under any circumstance.
"question": the single next question you would ask the patient, in natural language.
When you are ready to conclude the interview, set "is_final": true and
"final_diagnosis": "<single disorder name>".
```

- `candidates` is **evaluation-only**: never inserted into dialogue history shown to the
  Patient simulator.
- `question` is the **only** field forwarded to the Patient simulator.
- Parsing failures (invalid JSON, missing fields): set `is_valid_format = False`,
  `inference_score` for that turn = all zeros, log to a `format_failure_log`, and continue the
  dialogue using a fallback minimal question ("Could you tell me more about how you've been
  feeling?") so the episode doesn't crash. Report a per-model **Format Compliance Rate**
  alongside all other metrics — do not silently drop failed turns from aggregates.

### 3.2 Final diagnosis turn

When `is_final=True`, the Doctor MUST additionally emit a `diagnostic_checklist` field
(evaluated in §4.6). The complete final-turn output shape:

```json
{
  "diagnosis": "<single disorder name from allowed list>",
  "candidates": ["<Candidate1>", "<Candidate2>"],
  "reason": "<brief diagnostic rationale>",
  "diagnostic_checklist": {
    "symptom_groups": [
      {
        "group": "<clinical group name, e.g. inattention, manic_episode>",
        "confirmed_symptoms": ["<natural-language description of each confirmed symptom>"],
        "count": "<integer>"
      }
    ],
    "duration_verified": "<description of how duration criterion was established, or null>",
    "functional_impairment": "<true | false | null>",
    "traumatic_stressor": "<true | false | null>",
    "psychosocial_stressor": "<true | false | null>",
    "additional_requirements": ["<each additional criterion explicitly verified>"]
  }
}
```

The `diagnostic_checklist` must enumerate only the symptom groups and criteria that are
relevant to the Doctor's stated diagnosis. Absent groups are treated as unverified by the
Judge (§4.6).

---

## 4. Judge Logic

### 4.1 Symptom Extraction (LLM-as-Judge)

```python
def extract_symptoms_llm_judge(patient_utterance: str, history: list, kg_symptom_list: list) -> SymptomExtractionResult:
    """
    Prompt the Judge LLM with: full symptom list (id + name + description + subtypes from KG),
    conversation history, and the latest patient utterance.
    Output: confirmed symptom ids, denied symptom ids, and any duration/temporal text mapped
    to the relevant symptom id(s).
    Only extract symptoms with clear textual support; do not infer beyond what is stated or
    clearly implied. Err toward leaving a symptom unlabeled (UNKNOWN) over guessing.
    """
```

Merge rule into `cumulative_symptom_status` (see invariant in Section 2): new CONFIRMED/DENIED
labels are added for previously-UNKNOWN symptoms; conflicts with already-resolved symptoms go
to `label_conflict_log`, original label wins.

### 4.2 Reference Candidate Computation (deterministic KG lookup)

Each disorder's `required_criteria` (from `diagnostic_criteria.json`) partitions its symptoms
into **mandatory groups** (`relation: "must_include"`) and **optional groups**
(`relation: "include"`). The four-tier classification is:

| Tier | Condition | Semantics |
|---|---|---|
| `high_likely` | All mandatory groups meet their `min_count` threshold | Full mandatory evidence |
| `moderate_likely` | ≥1 mandatory symptom confirmed; no mandatory symptom denied | Partial mandatory evidence |
| `low_likely` | 0 mandatory symptoms confirmed; ≥1 optional symptom confirmed; no mandatory symptom denied | Optional-only signal |
| `excluded` | ≥1 mandatory symptom denied | Ruled out |

```python
def compute_reference_candidates(
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
    diagnostic_criteria: dict,
) -> tuple[set, set, set, set]:
    """Returns (high_likely, moderate_likely, low_likely, excluded)."""
    high_likely, moderate_likely, low_likely, excluded = set(), set(), set(), set()

    for did, disease_data in diagnostic_criteria.items():
        rc = disease_data.get("required_criteria", {})

        # Collect mandatory and optional symptom pools
        mandatory_groups: list[tuple[set[str], int]] = []
        optional_syms: set[str] = set()

        for grp in rc.values():
            if not isinstance(grp, dict) or "symptom_pool" not in grp:
                continue
            pool = set(grp["symptom_pool"])
            if grp.get("relation") == "must_include":
                mandatory_groups.append((pool, grp.get("min_count", 1)))
            else:
                optional_syms |= pool

        mandatory_syms = {s for pool, _ in mandatory_groups for s in pool}

        # Exclusion: any mandatory symptom denied
        if mandatory_syms & cumulative_denied:
            excluded.add(did)
            continue

        mandatory_confirmed = mandatory_syms & cumulative_confirmed
        optional_confirmed  = optional_syms  & cumulative_confirmed

        # high_likely: every mandatory group meets min_count
        if mandatory_groups and all(
            len(pool & cumulative_confirmed) >= min_count
            for pool, min_count in mandatory_groups
        ):
            high_likely.add(did)
        elif mandatory_confirmed:
            moderate_likely.add(did)
        elif optional_confirmed:
            low_likely.add(did)

    return high_likely, moderate_likely, low_likely, excluded
```

`check_duration_threshold` (not yet integrated above): compare `duration_info` extracted so
far against `disorder.minimum_duration` / `disorder.maximum_duration`. If duration is not yet
known for a disorder that otherwise qualifies for `high_likely`, treat as **not yet satisfied**
→ disorder falls back to `moderate_likely` until duration is resolved.

Within-group constraints (`must_include_all`, `must_include_one_of`) are encoded in
`diagnostic_criteria.json` and must be checked when determining whether a group's `min_count`
threshold is truly satisfied for `high_likely` promotion.

### 4.3 Inference Scoring

```python
def score_inference(predicted: List[str], reference: CandidateSet) -> InferenceScoreResult:
    ref_all = reference.all_candidates()  # high | moderate | low
    pred_set = set(predicted)
    intersection = pred_set & ref_all
    precision = len(intersection) / len(pred_set) if pred_set else 0.0
    recall = len(intersection) / len(ref_all) if ref_all else 0.0
    accuracy = 1.0 if pred_set == ref_all else 0.0
    jaccard = len(intersection) / len(pred_set | ref_all) if (pred_set | ref_all) else 0.0

    # Weighted recall: missing high_likely costs 2×, moderate_likely 1×, low_likely 0.5×
    missed_high = reference.high_likely - pred_set
    missed_mod  = reference.moderate_likely - pred_set
    missed_low  = reference.low_likely - pred_set
    penalty     = 2 * len(missed_high) + 1 * len(missed_mod) + 0.5 * len(missed_low)
    max_penalty = 2 * len(reference.high_likely) + 1 * len(reference.moderate_likely) + 0.5 * len(reference.low_likely)
    weighted_recall = 1.0 - (penalty / max_penalty) if max_penalty else 1.0

    return InferenceScoreResult(precision=precision, recall=recall, accuracy=accuracy,
                                 jaccard=jaccard, weighted_recall=weighted_recall)
```

`truth_set` for all downstream inference calculations is `all_candidates()` (high | moderate |
low). `strong_candidates()` (high | moderate) is available as an ablation axis — compute and
report both but use `all_candidates()` as the primary metric.

Report turn-by-turn trajectories (not just episode-level mean) — averaging hides recovery
patterns and regressions. Always persist the full per-turn series for plotting.

### 4.4 Question Reasonability Scoring

#### 4.4.1 Question-to-Symptom Mapping — implement THREE interchangeable mappers

```python
from abc import ABC, abstractmethod

class QuestionSymptomMapper(ABC):
    @abstractmethod
    def map(self, question: str, kg_symptom_list: list) -> List[str]:
        """Return symptom_ids the question is targeting."""

class SemanticSimilarityMapper(QuestionSymptomMapper):
    # Embed `question` and each symptom's description + subtype strings.
    # Return symptom_ids with cosine similarity > tau.
    # tau tuned on a held-out human-annotated gold set (see 4.4.6).
    ...

class LLMJudgeMapper(QuestionSymptomMapper):
    # Prompt Judge LLM: "Which of the following symptoms (with descriptions) is this question
    # trying to assess? List all that plausibly apply."
    ...

class HybridMapper(QuestionSymptomMapper):
    # LLMJudgeMapper as primary; SemanticSimilarityMapper adds any additional
    # candidate symptom whose similarity exceeds tau but was missed by the LLM.
    # (Direction fixed: LLM-first, embedding-recall-boost. Do not silently invert this.)
    ...
```

Run **all three mappers on every turn** and store results separately
(`targeted_symptoms_by_mapper`). Do not pick one as "the" answer inside the main pipeline —
downstream metrics (DCS, edge alignment, IG) must be computed three times per turn, once per
mapper, and reported as three parallel result sets.

#### 4.4.2 Discrimination Coverage Score (DCS), with set-complement fallback

```python
def discriminating_symptoms_for_pair(d_i, d_j, kg) -> Set[str]:
    edge = kg.get_differential_edge(d_i, d_j)  # check both directions
    if edge is not None:
        return edge.discriminating_symptoms   # KG expert-curated discriminating_rule symptoms
    # Fallback: symmetric difference of full symptom sets (XOR)
    symptoms_i = d_i.all_symptoms  # mandatory + optional/subtype symptoms
    symptoms_j = d_j.all_symptoms
    return symptoms_i.symmetric_difference(symptoms_j)

def score_dcs(question_symptoms: List[str], candidate_disorders: List[str], kg) -> float:
    if len(candidate_disorders) < 2:
        return None  # DCS undefined with a single candidate; handle separately downstream
    pairs = itertools.combinations(candidate_disorders, 2)
    discriminating_total = set()
    for d_i, d_j in pairs:
        discriminating_total |= discriminating_symptoms_for_pair(d_i, d_j, kg)
    if not question_symptoms:
        return 0.0
    overlap = set(question_symptoms) & discriminating_total
    return len(overlap) / len(question_symptoms)
```

Track, per turn and per episode, what fraction of scored pairs used the KG edge path vs. the
symmetric-difference fallback path. Report this ratio alongside DCS — it is a transparency
metric on how much of the score rests on expert-curated edges vs. an approximation.

#### 4.4.3 Auxiliary rules

```python
def mandatory_first_compliance(question_symptoms, candidate_disorders, cumulative_status, kg) -> int:
    unconfirmed_mandatory = set()
    for d_id in candidate_disorders:
        d = kg.get_disorder(d_id)
        unconfirmed_mandatory |= {s for s in d.mandatory_symptoms if cumulative_status.get(s, SymptomStatus.UNKNOWN) == SymptomStatus.UNKNOWN}
    if not unconfirmed_mandatory:
        return 1  # nothing left unconfirmed -> not a violation
    return 1 if set(question_symptoms) & unconfirmed_mandatory else 0

def redundancy_penalty(question_symptoms, cumulative_status) -> int:
    already_resolved = {s for s, status in cumulative_status.items() if status != SymptomStatus.UNKNOWN}
    if not question_symptoms:
        return 0
    return 1 if set(question_symptoms).issubset(already_resolved) else 0
```

Safety-critical symptoms (suicidal ideation, self-harm, psychotic symptoms — tag these
explicitly in the KG symptom metadata as `is_safety_critical: true`) are EXCLUDED from DCS /
mandatory-first / redundancy scoring. Track `safety_screening_compliance` as a fully separate
metric: whether all `is_safety_critical` symptoms have been queried by some fixed turn horizon
(configurable, default = end of episode). Do not penalize a safety-critical question for
having low discrimination value.

#### 4.4.4 Composite turn-level question score

```python
def composite_question_score(dcs, edge_alignment, mandatory_first, redundancy, lam1=0.3, lam2=0.3) -> float:
    base = dcs if dcs is not None else 0.0
    score = base * (1 - lam1 * redundancy) * (1 - lam2 * (1 - mandatory_first))
    if edge_alignment is not None:
        score = min(1.0, score + 0.1 * edge_alignment)  # small bonus, not a separate gate
    return score
```

`lam1`, `lam2`, and the edge-alignment bonus weight are hyperparameters — run an ablation
sweep before fixing final values; do not hardcode without justification in results.

Note: `information_gain` (§4.4.5) is reported as a **separate metric** alongside
`composite_score`, not folded into the composite formula. It measures a different axis
(expected candidate-set reduction) and conflating it with DCS-based scoring would obscure
both signals.

#### 4.4.5 Information Gain (KG-based approximation)

Information Gain measures how much a question is expected to reduce the candidate set size,
regardless of whether the question targets discriminating symptoms.

```python
def score_information_gain(
    question_symptoms: List[str],
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
    diagnostic_criteria: dict,
    current_candidate_size: int,
) -> Optional[float]:
    """
    IG = 1 - E[|C_{t+1}|] / |C_t|

    Approximation: assumes 50/50 probability of confirmed vs. denied for all
    unresolved targeted symptoms (simultaneous batch simulation).

    Returns:
      None   if current_candidate_size <= 1 (IG undefined when already at singleton)
      0.0    if question_symptoms is empty, or all targeted symptoms already resolved
      float  otherwise, in [0, 1]
    """
    if current_candidate_size <= 1:
        return None
    resolved = cumulative_confirmed | cumulative_denied
    unresolved = [s for s in question_symptoms if s not in resolved]
    if not unresolved:
        return 0.0
    unresolved_set = set(unresolved)
    size_if_confirmed = _candidate_set_size(
        cumulative_confirmed | unresolved_set, cumulative_denied, diagnostic_criteria)
    size_if_denied = _candidate_set_size(
        cumulative_confirmed, cumulative_denied | unresolved_set, diagnostic_criteria)
    expected_size = 0.5 * size_if_confirmed + 0.5 * size_if_denied
    return round(1.0 - expected_size / current_candidate_size, 4)
```

where `_candidate_set_size(confirmed, denied, criteria)` returns `|high | moderate | low|`
from `compute_reference_candidates()` — i.e., uses `all_candidates()` as the reference set.

**Interpretation guide for IG distribution:**

| IG value | Meaning |
|---|---|
| `None` | `\|C_t\| ≤ 1` — candidate set already collapsed; IG undefined |
| `0.0` | Mapper returned no symptoms, or all targeted symptoms already resolved (redundant question) |
| `> 0` | Question is expected to reduce the candidate set; higher is better |

A high rate of `IG=None` late in an episode is expected (the candidate set narrows naturally).
A high rate of `IG=0.0` early in an episode indicates either mapper failure or question
redundancy. Distinguish these two cases in reporting.

#### 4.4.6 Mapper validation against human gold standard

Separately from the main pipeline: collect a gold-standard annotation set of 100–200
(question, symptom-targets) pairs labeled by a domain expert. Compute precision/recall of
each of the three mappers against this gold set. This validates the **measurement instrument
itself**, independent of any Doctor model's performance — report as a standalone table.

#### 4.4.7 Episode-level aggregation — macro-mean and outcome stratification

**Aggregation method: macro-mean (episode-weighted)**

All reported question-quality metrics use **macro-mean** over episodes: each episode
contributes one value regardless of its turn count.

```
episode_metric(e) = mean over turns_in(e) of per_turn_score
model_metric      = mean over episodes   of episode_metric(e)
```

Rationale: each clinical case is an independent unit of measurement. A failed episode
that runs to 10 turns must not dominate the model's score simply because it produced
more data points. Micro-mean (averaging over all turns pooled) would over-weight
harder/longer cases, which are already captured by the Efficiency axis (§4.5).

**Confound: episode length is correlated with outcome**

Longer episodes tend to correspond to incorrect or difficult diagnoses. Because
question-quality metrics are defined over *active turns* (`|C_t| > 1`), a model with
more failed episodes will have more active turns contributing to its aggregate.
This creates a selection bias that inflates (or deflates) metrics depending on the
correlation direction.

**Ablation: outcome-stratified question quality**

Report question-quality metrics separately for:
- `correct` episodes: `ground_truth ∈ all_candidates()` at the final turn
- `incorrect` episodes: `ground_truth ∉ all_candidates()` at the final turn

This isolates two distinct behavioral questions:
1. *When the model is on track, is it asking good discriminating questions?* (correct stratum)
2. *When the model has already lost the ground truth, how does question quality degrade?* (incorrect stratum)

Output folder: `analysis/<judge>/<judge>/comparison/outcome_stratified/`

The primary reported metric remains the unconditional macro-mean. Outcome-stratified
results are an ablation to diagnose confounds, not a replacement.

### 4.5 Overall / Efficiency Evaluation

`candidate_sizes` includes all three candidate tiers — `|high ∪ moderate ∪ low|`.

```python
def score_overall(turn_log: List[TurnLog], final_diagnosis: str, ground_truth: str) -> dict:
    final_accuracy = 1.0 if final_diagnosis == ground_truth else 0.0
    candidate_sizes = [len(t.reference_candidates.all_candidates()) for t in turn_log]
    T = len(turn_log)

    cssr = (candidate_sizes[0] - candidate_sizes[-1]) / T if T > 0 else 0.0

    time_to_first_correct_narrowing = next(
        (t.turn_id for t in turn_log
         if ground_truth in t.reference_candidates.high_likely
         and len(t.reference_candidates.high_likely) == 1),
        T + 1  # sentinel: never reached
    )

    monotonicity_violations = sum(
        1 for i in range(1, len(candidate_sizes)) if candidate_sizes[i] > candidate_sizes[i-1]
    )

    redundant_turn_ratio = sum(
        1 for i in range(1, len(candidate_sizes)) if candidate_sizes[i] == candidate_sizes[i-1]
    ) / max(T - 1, 1)

    overcommitment_turns = sum(
        1 for i, size in enumerate(candidate_sizes) if size == 1
    ) - 1 if 1 in candidate_sizes else 0  # turns spent after first reaching size==1; refine indexing in implementation

    return dict(final_accuracy=final_accuracy, turn_count=T, cssr=cssr,
                time_to_first_correct_narrowing=time_to_first_correct_narrowing,
                monotonicity_violations=monotonicity_violations,
                redundant_turn_ratio=redundant_turn_ratio,
                overcommitment_turns=overcommitment_turns)
```

Note on `time_to_first_correct_narrowing`: uses `high_likely` (not `all_candidates()`) because
the ground truth must be the *only* high-confidence candidate, not merely present somewhere in
the candidate set. `overcommitment_turns` indexing: count turns *after* the candidate set
first collapses to size 1 but *before* `is_final=True` — add a unit test with a
hand-constructed trajectory to pin the off-by-one.

Always report `final_accuracy` cross-tabulated with `turn_count` (and CSSR) per model — never
report final accuracy alone.

### 4.6 Diagnostic Reasoning Quality (Final Diagnosis Axis)

#### 4.6.1 Purpose

`final_accuracy` (§4.5) is binary: correct or incorrect. Separately, this axis evaluates
*whether the Doctor's stated diagnostic reasoning covers the required DSM-5 criteria* for the
ground-truth diagnosis, independent of whether the final diagnosis name was correct.

The Doctor outputs a structured `diagnostic_checklist` (§3.2) alongside the final diagnosis.
An LLM judge compares this checklist against the ground-truth criteria from
`diagnostic_criteria.json`.

#### 4.6.2 Scoring rubric

For each disease's `required_criteria`, the judge evaluates the following components:

| Component | Source in KG | Weight | Score |
|---|---|---|---|
| `must_include` symptom group | `relation: "must_include"` | **2** | `min(1.0, valid_count / min_count)` × penalty multipliers |
| `include` symptom group | `relation: "include"` | 1 | Same formula; skip if doctor did not address this group |
| `min_duration` (top-level) | `required_criteria.min_duration` | 1 | Binary: 1 if verified, 0 if not |
| `functional_impairment` | `functional_impairment_required: true` | 1 | Binary; only counted when required |
| `traumatic_stressor` | `traumatic_stressor_required` present | 1 | Binary; only counted when required |
| `psychosocial_stressor` | `psychosocial_stressor_required` present | 1 | Binary; only counted when required |
| `additional_requirements` | `additional_requirements` list | 1 | Fraction of requirements addressed |

**Within-group penalty multipliers** (applied to the group's base coverage score):
- `must_include_one_of` constraint violated → ×0.5
- `must_include_all` constraint violated → ×0.5

**Symptom Satisfaction metric (compliance/threshold view):**

The per-group `symptom_coverage_score` above is continuous and averages over groups by
weight — it does not on its own answer "did the Doctor satisfy the mandatory symptom
groups, and how completely?" as a standalone, reportable number. `symptom_satisfaction_score`
fills that gap: a group counts as **satisfied** (binary) only if its `min_count` threshold is
fully met (`symptom_coverage_score >= 1.0`) AND no `must_include_one_of` /
`must_include_all` constraint was violated. Mandatory groups are weighted 2×, matching the
weighting used elsewhere in this rubric:

```
Symptom Satisfaction = (2 × satisfied_mandatory_groups + satisfied_optional_groups)
                        / (2 × total_mandatory_groups + total_optional_groups)
```

`None` if the disease defines no symptom groups at all (should not occur in practice).
This is reported as its own metric, separate from `overall_score`, and also feeds into
`overall_score` as one of the macro-mean components below.

**Overall score — macro-mean over applicable metrics:**

`overall_score` is the unweighted mean of whichever of the following metrics apply to the
GT disease: `symptom_satisfaction_score`, `duration_score` (if `min_duration` set),
`functional_impairment_score` (if required), `traumatic_stressor_score` (if required),
`psychosocial_stressor_score` (if required), `additional_requirements_score` (if any
additional requirements exist). Each metric contributes **equally**, regardless of how many
symptom groups or sub-requirements it internally aggregates — this avoids letting a disease
with many symptom groups (and therefore many weight-2/weight-1 terms in the old per-group
weighted sum) implicitly dominate the score relative to a disease with few groups but several
scalar requirements.

```python
def compute_diagnostic_reasoning_score(judgment: dict, disease_id: str, criteria: dict) -> float:
    rc = criteria[disease_id]["required_criteria"]

    symptom_satisfaction_score = compute_symptom_satisfaction(judgment, disease_id, criteria)

    def _bin(key: str) -> float | None:
        val = judgment.get(key)
        return None if val is None else (1.0 if val else 0.0)

    duration_score  = _bin("duration_verified")
    fi_score        = _bin("functional_impairment_verified")
    traumatic_score = _bin("traumatic_stressor_verified")
    psycho_score    = _bin("psychosocial_stressor_verified")
    add_score       = judgment.get("additional_requirements_coverage")

    has_top_duration = bool(rc.get("min_duration"))
    add_reqs = rc.get("additional_requirements")

    metrics = []
    if symptom_satisfaction_score is not None:
        metrics.append(symptom_satisfaction_score)
    if has_top_duration and duration_score is not None:
        metrics.append(duration_score)
    if rc.get("functional_impairment_required") and fi_score is not None:
        metrics.append(fi_score)
    if rc.get("traumatic_stressor_required") and traumatic_score is not None:
        metrics.append(traumatic_score)
    if rc.get("psychosocial_stressor_required") and psycho_score is not None:
        metrics.append(psycho_score)
    if add_reqs and isinstance(add_reqs, list) and add_score is not None:
        metrics.append(add_score)

    return round(sum(metrics) / len(metrics), 4) if metrics else 0.0


def compute_symptom_satisfaction(judgment: dict, disease_id: str, criteria: dict) -> float | None:
    rc = criteria[disease_id]["required_criteria"]
    crit_by_group = {c["group"]: c for c in judgment.get("criterion_evaluations", [])}

    mandatory_total = mandatory_satisfied = 0
    optional_total  = optional_satisfied  = 0
    for key, val in rc.items():
        if not isinstance(val, dict) or "symptom_pool" not in val:
            continue
        crit = crit_by_group.get(key, {})
        s = min(1.0, max(0.0, crit.get("symptom_coverage_score", 0.0)))
        satisfied = (
            s >= 1.0
            and crit.get("must_include_one_of_satisfied") is not False
            and crit.get("must_include_all_satisfied") is not False
        )
        if val.get("relation") == "must_include":
            mandatory_total += 1
            mandatory_satisfied += int(satisfied)
        else:
            optional_total += 1
            optional_satisfied += int(satisfied)

    denom = 2 * mandatory_total + optional_total
    if denom == 0:
        return None
    return round((2 * mandatory_satisfied + optional_satisfied) / denom, 4)
```

Note: the symptom-group `weighted_sum / total_weight` formula from earlier spec drafts (each
group weighted 2 or 1, summed together with the scalar criteria into one big weighted average)
is superseded by the macro-mean above. That older formula let diseases with many symptom
groups dominate `overall_score` purely by term count; macro-mean over a fixed set of named
metrics avoids that.

#### 4.6.3 LLM judge

The judge receives:
1. The **formatted GT criteria** (symptom names + descriptions from the symptom JSON files,
   grouped by criterion group, with `min_count`, `must_include_all`, `must_include_one_of`
   requirements spelled out).
2. The **Doctor's `diagnostic_checklist`** formatted as natural language (or the `reason`
   field as fallback for older logs without a structured checklist).

The judge returns per-criterion JSON:

```json
{
  "criterion_evaluations": [
    {
      "group": "<group key>",
      "relation": "must_include | include",
      "min_count_required": N,
      "valid_symptom_count": N,
      "symptom_coverage_score": 0.0–1.0,
      "must_include_one_of_satisfied": true | false | null,
      "must_include_all_satisfied": true | false | null,
      "matched_symptom_descriptions": ["..."],
      "missing_required_symptoms": ["..."]
    }
  ],
  "duration_verified": true | false | null,
  "functional_impairment_verified": true | false | null,
  "traumatic_stressor_verified": true | false | null,
  "psychosocial_stressor_verified": true | false | null,
  "additional_requirements_coverage": 0.0–1.0 | null,
  "additional_requirements_notes": "..."
}
```

Evaluation is always against the **ground-truth disease's criteria**, regardless of whether
the Doctor's stated diagnosis was correct. This decouples "did the Doctor name the right
disease?" (§4.5) from "did the Doctor gather and verify the right evidence?" (§4.6).

#### 4.6.4 Fallback for logs without structured checklist

For logs produced before `diagnostic_checklist` was added to the Doctor's output format
(§3.2), the `reason` free-text field can be used as a freeform checklist input to the judge.
This produces a lower-fidelity score (natural language is less structured than a field-by-field
checklist) — flag this in results with `has_structured_checklist: false`.

### 4.7 Headline Metrics for Cross-Model Reporting

Each axis emits several metrics (§4.3–§4.6). Full metric suites remain the source of truth and
must always be persisted and available for inspection, but cross-model comparison dashboards
and reports MUST lead with exactly two **headline metrics** per axis, with everything else
reported as supporting detail underneath. This section fixes which two numbers lead — it does
not change what is computed.

| Axis | Headline metrics | Supporting metrics |
|---|---|---|
| Inference Quality (§4.3) | `accuracy`, `jaccard` | `recall`, `precision`, `weighted_recall` |
| Question Quality (§4.4) | `composite_score` conditional mean, `information_gain` conditional mean — both **`llm_judge` mapper** | `discriminating_q_rate`, `ig_positive_rate` (llm_judge); `composite_score`/`information_gain` conditional means (cosine, as a cross-mapper check) |
| Efficiency (§4.5) | `turn_count`, `cssr` | `time_to_first_correct_narrowing`, `monotonicity_violations`, `redundant_turn_ratio`, `overcommitment_turns` |
| Diagnostic Reasoning Quality (§4.5 final_accuracy + §4.6 overall_score) | `final_accuracy` (§4.5), `overall_score` (§4.6) | `duration`, `functional_impairment`, `traumatic_stressor`, `psychosocial_stressor`, `additional_requirements` component scores |

Two notes on how this maps back onto the scoring functions above:

- **`final_accuracy` is computed in `score_overall` (§4.5)** — it is not a `diagnostic_checklist`
  field — but it is *reported* alongside `overall_score` under Diagnostic Reasoning Quality in
  cross-model summaries, because both answer "was the diagnosis right," at different grains
  (exact name match vs. DSM-5 criterion coverage), and a reader wants them side by side. It
  still satisfies the §4.5 requirement to report `final_accuracy` cross-tabulated with
  `turn_count` and `cssr` — that cross-tabulation stays in the Efficiency metric table.
  `turn_count` and `cssr` remain the Efficiency headline pair on their own, since they measure
  dialogue process, not diagnostic correctness.
- **Question Quality headlines the `llm_judge` mapper, not `cosine`.** §4.4.1 still requires all
  mappers be computed and persisted in full for every turn — this only fixes which mapper's
  numbers lead the summary table. Report `cosine` mapper numbers alongside as a secondary
  cross-mapper comparison (§4.4.6 already requires validating mapper agreement); do not drop
  them from detailed tables.

This section governs report layout only; it does not relax the §4.4.7 requirement to report the
unconditional macro-mean as primary and outcome-stratified numbers as an ablation, nor any other
aggregation rule defined above.

---

## 5. Patient Simulator (independent, pluggable module)

```python
class DisclosureScheduler(ABC):
    """The only piece expected to change/be extended later. Keep this interface stable
    even as internal scheduling logic is iterated on."""
    @abstractmethod
    def get_disclosable_info(self, turn_id: int, profile, config: DisclosureDifficultyConfig) -> dict:
        """Return which symptoms/duration info become available for the verbalizer to use
        at this turn, given the difficulty config."""

class PatientSimulator:
    def __init__(self, profile, config: DisclosureDifficultyConfig,
                 scheduler: DisclosureScheduler, verbalizer_llm):
        self.profile = profile
        self.config = config
        self.scheduler = scheduler
        self.verbalizer_llm = verbalizer_llm

    def respond(self, history: list, turn_id: int) -> str:
        disclosable = self.scheduler.get_disclosable_info(turn_id, self.profile, self.config)
        # Verbalizer LLM call: produce a natural-language reply consistent with `disclosable`,
        # answering the doctor's latest question, WITHOUT revealing anything not yet disclosable.
        ...
```

Difficulty config (2x2, confirmed scope for v1 — do not expand to more levels without
sign-off):

| `duration_difficulty` | Behavior |
|---|---|
| `easy` | Duration info revealed explicitly within turns 1–2 |
| `hard` | Duration info revealed fragmentarily/vaguely ("it's been a while") across later turns |

| `core_symptom_concealment` | Behavior |
|---|---|
| `easy` | Mandatory/core symptoms present in the first patient utterance |
| `hard` | Mandatory/core symptoms (esp. stigma-sensitive ones, e.g. suicidal ideation) delayed until rapport-building turns have passed (configurable delay, default: not before turn 3) |

Keep `DisclosureScheduler` implementation entirely separate from `PatientSimulator` plumbing —
this is the piece most likely to be redesigned later (finer-grained levels, per-disorder
schedules, etc.). The verbalizer LLM call and the "don't leak undisclosed info" guard should
not need to change when the scheduler logic changes.

---

## 6. Full Episode Loop (reference implementation)

```python
def run_dialogue_episode(patient_profile, difficulty_config, kg, doctor_model,
                          judge_llm, mappers: dict, max_turns: int = 12) -> "EpisodeResult":
    scheduler = DefaultDisclosureScheduler()  # concrete impl, swappable
    patient_sim = PatientSimulator(patient_profile, difficulty_config, scheduler, judge_llm)

    cumulative_confirmed: set[str] = set()
    cumulative_denied:    set[str] = set()
    duration_info: Dict[str, str] = {}
    history = []
    turn_log: List[TurnLog] = []
    format_failures = 0
    label_conflict_log = []

    history.append(("doctor", doctor_model.generate_opener()))

    for turn_id in range(1, max_turns + 1):
        patient_utt = patient_sim.respond(history, turn_id)
        history.append(("patient", patient_utt))

        extraction = extract_symptoms_llm_judge(patient_utt, history, kg.symptom_list)
        for sid in extraction.confirmed:
            merge_symptom_status(cumulative_confirmed, cumulative_denied, sid, "confirmed", label_conflict_log)
        for sid in extraction.denied:
            merge_symptom_status(cumulative_confirmed, cumulative_denied, sid, "denied", label_conflict_log)
        duration_info.update(extraction.duration_info)

        hl, ml, ll, ex = compute_reference_candidates(cumulative_confirmed, cumulative_denied, kg.criteria)
        reference_candidates = CandidateSet(
            high_likely=hl, moderate_likely=ml, low_likely=ll, excluded=ex)

        raw_output = doctor_model.generate(history)
        doctor_out = parse_doctor_output(raw_output)  # sets is_valid_format=False on failure
        if not doctor_out.is_valid_format:
            format_failures += 1

        history.append(("doctor", doctor_out.question))  # candidates NEVER enter history

        inference_score = score_inference(doctor_out.candidates, reference_candidates)

        current_size = len(reference_candidates.all_candidates())
        question_scores_by_mapper = {}
        for name, mapper in mappers.items():
            q_symptoms = mapper.map(doctor_out.question, kg.symptom_list)
            dcs       = score_dcs(q_symptoms, doctor_out.candidates, kg)
            edge_align = score_edge_alignment(q_symptoms, doctor_out.candidates, kg)
            mand_first = mandatory_first_compliance(q_symptoms, doctor_out.candidates, cumulative_confirmed | cumulative_denied, kg)
            redund     = redundancy_penalty(q_symptoms, cumulative_confirmed | cumulative_denied)
            ig         = score_information_gain(q_symptoms, cumulative_confirmed, cumulative_denied, kg.criteria, current_size)
            composite  = composite_question_score(dcs, edge_align, mand_first, redund)
            question_scores_by_mapper[name] = QuestionScoreResult(
                dcs=dcs, edge_alignment=edge_align, mandatory_first_compliance=mand_first,
                redundancy_penalty=redund, information_gain=ig, composite_score=composite,
                targeted_symptoms_by_mapper={name: q_symptoms})

        turn_log.append(TurnLog(
            turn_id=turn_id, patient_utterance=patient_utt, extraction=extraction,
            cumulative_symptom_status={s: "confirmed" for s in cumulative_confirmed} |
                                      {s: "denied" for s in cumulative_denied},
            reference_candidates=reference_candidates, doctor_output=doctor_out,
            inference_score=inference_score,
            question_score=question_scores_by_mapper["hybrid"],  # primary for live control flow
            format_failure=not doctor_out.is_valid_format,
        ))
        # NOTE: question_scores_by_mapper (all three) must be persisted in full at the
        # episode-result level for offline comparison, not just the "hybrid" slot.

        if doctor_out.is_final or len(reference_candidates.high_likely) == 1:
            break

    final_dx = doctor_out.final_diagnosis or doctor_model.final_diagnosis(history)
    overall  = score_overall(turn_log, final_dx, patient_profile.ground_truth_disorder)

    # §4.6: diagnostic reasoning quality
    reasoning_score = score_episode(
        disease_id       = patient_profile.ground_truth_disorder,
        doctor_checklist = doctor_out.diagnostic_checklist,
        criteria         = kg.criteria,
        sym_names        = kg.symptom_names,
        llm_chat         = judge_llm.chat,
    )

    return EpisodeResult(
        turn_log=turn_log, overall=overall,
        reasoning_score=reasoning_score,
        format_failures=format_failures,
        label_conflict_log=label_conflict_log,
    )
```

---

## 7. Open Implementation Decisions

| # | Decision | Current setting | Must flag if changed |
|---|---|---|---|
| 1 | Judge LLM model identity (fixed, ≠ Doctor model) | `gemini-3.5-flash` | Yes |
| 2 | `tau` similarity threshold for `SemanticSimilarityMapper` | `0.7` (placeholder; tune on gold set) | Yes |
| 3 | `lam1`, `lam2`, edge-alignment bonus weight in composite score | `0.3, 0.3, 0.1` (pending ablation) | Yes |
| 4 | `max_turns` | `10` | Yes |
| 5 | Default-turn horizon for `safety_screening_compliance` | end of episode | No |
| 6 | Gold-standard annotation set size for mapper validation | 150 | Yes if expert availability changes |
| 7 | `core_symptom_concealment=hard` delay turn | not before turn 3 | Yes |
| 8 | IG simulation assumption | 50/50 confirmed/denied (batch; all unresolved targeted symptoms simultaneously) | Yes |
| 9 | `low_likely` inclusion in `all_candidates()` | Included (`high \| moderate \| low`); `strong_candidates()` available as ablation | Yes if ablation shows `low_likely` hurts metric validity |
| 10 | Diagnostic reasoning judge: evaluate against GT or Doctor's stated disease | **GT disease** always; Doctor's stated disease is a secondary output | Yes |

Implementers: surface all numeric parameters in `config.json` under `evaluation:` so they can
be swept without touching pipeline logic.

---

## 8. Testing Checklist (minimum, before declaring the pipeline "done")

- [ ] Unit test: `compute_reference_candidates` with a hand-constructed confirmed/denied set
      against 2–3 known disorders. Verify all four tiers (`high_likely`, `moderate_likely`,
      `low_likely`, `excluded`) are assigned correctly, including:
      - mandatory symptom denied → `excluded` (not `low_likely`)
      - 0 mandatory confirmed + 1 optional confirmed → `low_likely`
      - partial mandatory confirmed → `moderate_likely`
      - all mandatory groups at min_count → `high_likely`
- [ ] Unit test: `score_inference` weighted recall with three-tier reference — verify
      `high_likely` miss costs 2×, `moderate_likely` costs 1×, `low_likely` costs 0.5×.
- [ ] Unit test: `score_information_gain` — verify `None` when `current_size ≤ 1`,
      `0.0` when all targeted symptoms already resolved, and a positive value when unresolved.
- [ ] Unit test: `discriminating_symptoms_for_pair` — one case with a KG edge present, one
      case with no edge (verify symmetric-difference fallback fires correctly).
- [ ] Unit test: `score_overall` efficiency metrics on a hand-constructed `candidate_sizes`
      trajectory with a known monotonicity violation and a known overcommitment span — verify
      exact off-by-one behavior for `overcommitment_turns` and `time_to_first_correct_narrowing`.
- [ ] Unit test: `compute_diagnostic_reasoning_score` — one case with all criteria met
      (score → 1.0), one with missing mandatory group (score < 1.0), one with
      `must_include_one_of` violated (verify 0.5× penalty applied).
- [ ] Integration test: full `run_dialogue_episode` on a single scripted/mocked Patient that
      always discloses identically, across all three mappers, confirming all three produce
      valid (possibly different) `QuestionScoreResult`s without crashing.
- [ ] Format-failure path: feed a malformed Doctor output and confirm the episode continues
      with the fallback question and the failure is logged, not silently dropped.
- [ ] Migration test: existing result JSONs without `low_likely` are correctly migrated by
      recomputing from stored `cumulative_confirmed` / `cumulative_denied` without LLM calls.
