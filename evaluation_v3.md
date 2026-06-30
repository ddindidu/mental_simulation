# Turn-Level Psychiatric Diagnostic Dialogue Evaluation Pipeline — Technical Spec

## 0. Purpose

This document specifies an evaluation pipeline for assessing the psychiatric diagnostic
capability of LLMs (the "Doctor" model) through multi-turn dialogue with a simulated patient.
Unlike prior work that evaluates only final-diagnosis accuracy, this pipeline scores **three
axes at the turn level**: (1) diagnostic inference quality, (2) question reasonability, and
(3) dialogue efficiency. Scoring is grounded in a DSM-5-based psychiatric knowledge graph
(KG) reused/extended from MentalKG (Song et al., MentalBench), rather than pattern matching
or unconstrained LLM-as-judge.

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
                  [Overall Evaluation: Final Diagnosis + Efficiency]
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
    high_likely: Set[str]   # disorder_id: ALL mandatory symptoms confirmed + duration/threshold satisfied
    moderate_likely: Set[str]  # disorder_id: PARTIAL mandatory symptoms confirmed, not excluded
    excluded: Set[str]      # disorder_id: explicitly ruled out by a DENIED mandatory symptom

    def all_candidates(self) -> Set[str]:
        return self.high_likely | self.moderate_likely

class DoctorOutput(BaseModel):
    candidates: List[str]    # disorder names/ids the Doctor currently considers plausible
    question: str            # the ONLY field forwarded to the Patient
    is_final: bool = False
    final_diagnosis: Optional[str] = None
    is_valid_format: bool = True   # set False by the parser on schema-violation; do not let the Doctor set this

class InferenceScoreResult(BaseModel):
    precision: float
    recall: float
    accuracy: float          # strict set-equality, 1.0 or 0.0
    jaccard: float
    weighted_recall: float   # high_likely misses weighted 2x vs moderate_likely misses (see 4.2)

class QuestionScoreResult(BaseModel):
    dcs: float                       # Discrimination Coverage Score
    edge_alignment: Optional[float]  # None if no differential-diagnosis edge applies to any candidate pair
    mandatory_first_compliance: float  # 0/1
    redundancy_penalty: float          # 0/1, 1 = violation
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

The Doctor model MUST be prompted to emit **only** the following JSON shape per turn:

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

```python
def compute_reference_candidates(cumulative_symptom_status: dict, kg) -> CandidateSet:
    high_likely, moderate_likely, excluded = set(), set(), set()
    for disorder in kg.disorders:
        mandatory = disorder.mandatory_symptoms
        confirmed_in_d = {s for s in mandatory if cumulative_symptom_status.get(s) == SymptomStatus.CONFIRMED}
        denied_in_d   = {s for s in mandatory if cumulative_symptom_status.get(s) == SymptomStatus.DENIED}

        if denied_in_d:
            excluded.add(disorder.id)
            continue

        duration_ok = check_duration_threshold(disorder, cumulative_symptom_status)  # see below
        count_ok = len(confirmed_in_d) >= disorder.min_symptom_count if disorder.min_symptom_count else True

        if confirmed_in_d == mandatory and duration_ok and count_ok:
            high_likely.add(disorder.id)
        elif confirmed_in_d:
            moderate_likely.add(disorder.id)
        # disorders with zero symptom overlap are never added to any set

    return CandidateSet(high_likely=high_likely, moderate_likely=moderate_likely, excluded=excluded)
```

`check_duration_threshold`: compare `duration_info` extracted so far against
`disorder.minimum_duration` / `disorder.maximum_duration`. If duration is not yet known for a
disorder that otherwise has all mandatory symptoms confirmed, treat as **not yet satisfied**
→ disorder goes to `moderate_likely`, not `high_likely`, until duration is resolved.

### 4.3 Inference Scoring

```python
def score_inference(predicted: List[str], reference: CandidateSet) -> InferenceScoreResult:
    ref_all = reference.all_candidates()
    pred_set = set(predicted)
    intersection = pred_set & ref_all
    precision = len(intersection) / len(pred_set) if pred_set else 0.0
    recall = len(intersection) / len(ref_all) if ref_all else 0.0
    accuracy = 1.0 if pred_set == ref_all else 0.0
    jaccard = len(intersection) / len(pred_set | ref_all) if (pred_set | ref_all) else 0.0

    # weighted recall: missing a high_likely disorder costs 2x a missing moderate_likely one
    missed_high = reference.high_likely - pred_set
    missed_mod = reference.moderate_likely - pred_set
    penalty = 2 * len(missed_high) + 1 * len(missed_mod)
    max_penalty = 2 * len(reference.high_likely) + 1 * len(reference.moderate_likely)
    weighted_recall = 1.0 - (penalty / max_penalty) if max_penalty else 1.0

    return InferenceScoreResult(precision=precision, recall=recall, accuracy=accuracy,
                                 jaccard=jaccard, weighted_recall=weighted_recall)
```

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
    # tau tuned on a held-out human-annotated gold set (see 4.4.4).
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
downstream metrics (DCS, edge alignment) must be computed three times per turn, once per
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

#### 4.4.5 Mapper validation against human gold standard

Separately from the main pipeline: collect a gold-standard annotation set of 100–200
(question, symptom-targets) pairs labeled by a domain expert. Compute precision/recall of
each of the three mappers against this gold set. This validates the **measurement instrument
itself**, independent of any Doctor model's performance — report as a standalone table.

### 4.5 Overall / Efficiency Evaluation

```python
def score_overall(turn_log: List[TurnLog], final_diagnosis: str, ground_truth: str) -> dict:
    final_accuracy = 1.0 if final_diagnosis == ground_truth else 0.0
    candidate_sizes = [len(t.reference_candidates.all_candidates()) for t in turn_log]
    T = len(turn_log)

    cssr = (candidate_sizes[0] - candidate_sizes[-1]) / T if T > 0 else 0.0

    time_to_first_correct_narrowing = next(
        (t.turn_id for t in turn_log
         if ground_truth in t.reference_candidates.all_candidates()
         and len(t.reference_candidates.all_candidates()) == 1),
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
    ) - 1 if 1 in candidate_sizes else 0  # turns spent after first reaching size==1, before final dx; refine indexing in implementation

    return dict(final_accuracy=final_accuracy, turn_count=T, cssr=cssr,
                time_to_first_correct_narrowing=time_to_first_correct_narrowing,
                monotonicity_violations=monotonicity_violations,
                redundant_turn_ratio=redundant_turn_ratio,
                overcommitment_turns=overcommitment_turns)
```

Note on `overcommitment_turns` indexing: implement carefully so it counts turns *after* the
candidate set first collapses to size 1 but *before* `is_final=True` is issued — the
pseudocode above is illustrative, not exact; get the off-by-one right in implementation and
add a unit test with a hand-constructed `candidate_sizes` trajectory.

Always report `final_accuracy` cross-tabulated with `turn_count` (and CSSR) per model — never
report final accuracy alone, since two models with identical final accuracy can differ
sharply in efficiency and inference trajectory quality.

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

    cumulative_symptom_status: Dict[str, SymptomStatus] = {}
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
            merge_symptom_status(cumulative_symptom_status, sid, SymptomStatus.CONFIRMED, label_conflict_log)
        for sid in extraction.denied:
            merge_symptom_status(cumulative_symptom_status, sid, SymptomStatus.DENIED, label_conflict_log)
        duration_info.update(extraction.duration_info)

        reference_candidates = compute_reference_candidates(cumulative_symptom_status, kg)

        raw_output = doctor_model.generate(history)
        doctor_out = parse_doctor_output(raw_output)  # sets is_valid_format=False on failure
        if not doctor_out.is_valid_format:
            format_failures += 1

        history.append(("doctor", doctor_out.question))  # candidates NEVER enter history

        inference_score = score_inference(doctor_out.candidates, reference_candidates)

        question_scores_by_mapper = {}
        for name, mapper in mappers.items():
            q_symptoms = mapper.map(doctor_out.question, kg.symptom_list)
            dcs = score_dcs(q_symptoms, doctor_out.candidates, kg)
            edge_align = score_edge_alignment(q_symptoms, doctor_out.candidates, kg)  # None if no edge applies
            mand_first = mandatory_first_compliance(q_symptoms, doctor_out.candidates, cumulative_symptom_status, kg)
            redund = redundancy_penalty(q_symptoms, cumulative_symptom_status)
            composite = composite_question_score(dcs, edge_align, mand_first, redund)
            question_scores_by_mapper[name] = QuestionScoreResult(
                dcs=dcs, edge_alignment=edge_align, mandatory_first_compliance=mand_first,
                redundancy_penalty=redund, composite_score=composite,
                targeted_symptoms_by_mapper={name: q_symptoms})

        turn_log.append(TurnLog(
            turn_id=turn_id, patient_utterance=patient_utt, extraction=extraction,
            cumulative_symptom_status=dict(cumulative_symptom_status),
            reference_candidates=reference_candidates, doctor_output=doctor_out,
            inference_score=inference_score,
            question_score=question_scores_by_mapper["hybrid"],  # primary metric for live control flow
            format_failure=not doctor_out.is_valid_format,
        ))
        # NOTE: question_scores_by_mapper (all three) must still be persisted in full at the
        # episode-result level for offline comparison, not just the "hybrid" slot used above.

        if doctor_out.is_final or len(reference_candidates.high_likely) == 1:
            break

    final_dx = doctor_out.final_diagnosis or doctor_model.final_diagnosis(history)
    overall = score_overall(turn_log, final_dx, patient_profile.ground_truth_disorder)

    return EpisodeResult(turn_log=turn_log, overall=overall, format_failures=format_failures,
                          label_conflict_log=label_conflict_log)
```

---

## 7. Open Implementation Decisions (must resolve before/during build; do not guess silently)

| # | Decision | Default if no input given | Must flag to requester if changed |
|---|---|---|---|
| 1 | Judge LLM model identity (fixed, ≠ Doctor model) | TBD — placeholder constant `JUDGE_MODEL_ID` | Yes |
| 2 | `tau` similarity threshold for `SemanticSimilarityMapper` | tune on gold set; placeholder `0.7` until tuned | Yes |
| 3 | `lam1`, `lam2`, edge-alignment bonus weight in composite score | `0.3, 0.3, 0.1` placeholders pending ablation | Yes |
| 4 | `max_turns` | `12`, revisit jointly with `hard` difficulty configs (must allow enough turns for delayed disclosure to surface) | Yes |
| 5 | Default-turn horizon for `safety_screening_compliance` | end of episode | No (low risk) |
| 6 | Gold-standard annotation set size for mapper validation | 150 | Yes if expert availability changes this |
| 7 | `core_symptom_concealment=hard` delay turn | not before turn 3 | Yes |

Implementers: treat column 3 values as placeholders, not final settings. Surface them in a
single `config.py` / `config.yaml` so they can be swept/changed without touching pipeline
logic.

---

## 8. Testing Checklist (minimum, before declaring the pipeline "done")

- [ ] Unit test: `compute_reference_candidates` with a hand-constructed symptom-status dict
      against 2–3 known disorders (verify high/moderate/excluded classification, including a
      DENIED-mandatory-symptom exclusion case).
- [ ] Unit test: `score_inference` precision/recall/jaccard/weighted_recall on a constructed
      predicted vs. reference pair.
- [ ] Unit test: `discriminating_symptoms_for_pair` — one case with a KG edge present, one
      case with no edge (verify symmetric-difference fallback fires correctly).
- [ ] Unit test: `score_overall` efficiency metrics on a hand-constructed `candidate_sizes`
      trajectory with a known monotonicity violation and a known overcommitment span — verify
      exact off-by-one behavior for `overcommitment_turns` and `time_to_first_correct_narrowing`.
- [ ] Integration test: full `run_dialogue_episode` on a single scripted/mocked Patient that
      always discloses identically, across all three mappers, confirming all three produce
      valid (possibly different) `QuestionScoreResult`s without crashing.
- [ ] Format-failure path: feed a malformed Doctor output and confirm the episode continues
      with the fallback question and the failure is logged, not silently dropped.