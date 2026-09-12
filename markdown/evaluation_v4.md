# Evaluation v4 — Headline Metric Reference

Four reporting dimensions, each backed by KG-deterministic ground truth
(`mentalbench/resources/knowledge_graph/EN/diagnostic_criteria.json`). This
doc is a short, implementation-verified reference — for full formulas /
edge cases see `evaluation_v3.md` (still the canonical spec for machinery
this file doesn't repeat) and the module docstrings linked below.

All four dimensions share one ground-truth object computed per turn:

```
compute_candidate_set(confirmed, denied, diagnostic_criteria)
  -> (high_likely, moderate_likely, low_likely, excluded)
```
— `eval/symptom_diagnosis.py:compute_candidate_set()`. A disease is
`high_likely` once every `must_include` group meets its `min_count`,
`moderate_likely` with partial mandatory evidence, `low_likely` with only
optional-symptom evidence, `excluded` once any mandatory symptom is denied.
**`truth_set` / "the reference candidate set" everywhere below =
`high_likely ∪ moderate_likely ∪ low_likely`.**

---

## 1. Inference Quality

Per-turn: does the doctor's stated candidate list match the reference set?
`eval/evaluate_turns.py` (writes `analysis/<run>/turn_eval.json`, the file
every reporting script reads).

```
TP = |predicted ∩ truth_set|,  FP = |predicted − truth_set|,  FN = |truth_set − predicted|
precision = TP / |predicted|
recall    = TP / |truth_set|
jaccard   = TP / |predicted ∪ truth_set|
```

| | Metric | Status |
|---|---|---|
| **main** | **Jaccard Index** | ✅ implemented |
| sub | Precision | ✅ implemented |
| sub | Recall | ✅ implemented |

(`accuracy`/`weighted_recall` are also computed and kept in the JSON for
ablation, but are not part of this headline set.)

---

## 2. Information Acquisition Quality

Per-turn: is the doctor's question relevant + non-redundant, and does it
narrow the candidate set? `eval/informative_question_score.py` (see its
module docstring for full design rationale and locked-in decisions),
orchestrated per-episode by `eval/evaluate_question.py`.

Evidence state stays 3-way: `CONFIRMED / DENIED / UNKNOWN` — the symptom
extraction judge (`eval/symptom_diagnosis.py`) already errs toward `UNKNOWN`
on ambiguous patient replies, so a clarifying re-ask is never mistaken for a
redundant one.

### (main) Information Acquisition Score (IAS)

```
I_t  = discriminative_symptoms(C_t) ∪ required_symptoms(C_t)
DRS  = |S(q_t) ∩ I_t| / |S(q_t)|                       — diagnostic relevance
RP   = |S(q_t) ∩ resolved| / |S(q_t)|                  — redundancy penalty
IAS  = DRS × (1 − RP)
```
- `discriminative_symptoms(C_t)`: symptoms present in *some* but not *all*
  current candidates (`0 < |D_t(s)| < |C_t|`).
- `required_symptoms(C_t)`: union of `must_include` mandatory-pool symptom
  IDs across current candidates — **symptom-level, no `min_count` group
  gating** (a group is never treated as "already satisfied"; asking about
  individual mandatory symptoms one at a time is the natural unit).
  Non-symptom requirements (duration, functional impairment, additional
  requirements) are **out of scope** — the pipeline has no evidence
  extraction for them yet (tracked as an open gap, see §4 below).
- `mandatory_first_compliance` (question_score.py) is **not** part of this
  axis anymore — required-ness now folds directly into `I_t`.

### (sub) Information Gain — Expected Candidate Reduction (ECR)

```
ECR(s) = 1 − [P(+)·|C_t| + P(−)·(|C_t| − k)] / |C_t|      k = |{d ∈ C_t : s mandatory for d}|
ECR(q_t) = mean over UNRESOLVED targeted symptoms of ECR(s)   (per_target_mean)
```
Filtering is presence-based but **restricted to mandatory-pool membership**:
under `compute_candidate_set`, only a *mandatory*-symptom denial excludes a
candidate, so confirming a symptom never shrinks `C_t` (the "positive"
branch is always the full set) — this keeps ECR consistent with the same
candidate-set definition Inference Quality uses. `P(+)` defaults to
`candidate_frequency` (`k / |C_t|`), configurable via
`config.json → evaluation.information_acquisition.probability_mode`
(`uniform_answer` / `candidate_frequency` / `provided`).

| | Metric | Status |
|---|---|---|
| **main** | **Information Acquisition Score (IAS)** | ✅ implemented |
| sub | Information Gain (ECR) | ✅ implemented |

Every intermediate set used to derive these (`discriminative_symptoms`,
`required_symptoms`, `candidate_symptoms`, `resolved_symptoms`,
`unresolved_symptoms`, per-target ECR detail) is saved alongside the score
in `question_eval.json` for debugging / case study.

---

## 3. Efficiency

Per-episode, from the per-turn candidate-set sizes. `eval/evaluate_efficiency.py`
(writes `results/<run>/efficiency_eval.json`).

| | Metric | Definition | Status |
|---|---|---|---|
| main | **Turn count** | total patient turns until the doctor declares `is_final=true` | ✅ implemented (`turn_count`) |
| sub | **Turn to 1st correct** | first turn where the reference candidate set collapses to exactly `{ground_truth}` (`high∣moderate∣low` union `== {gt}`); sentinel `turn_count + 1` if never reached | ✅ implemented (`time_to_first_correct_narrowing`) |
| sub | **Overcommitment Turns** | `(turn_count − 1) − first_turn_where_|C_t|==1`; turns spent continuing after the candidate set (regardless of correctness) already collapsed to one, before ending | ✅ implemented (`overcommitment_turns`) |

**Fix applied in this pass:** `time_to_first_correct_narrowing` previously
checked the `high_likely` tier only, while `overcommitment_turns` checked
the full `high∣moderate∣low` union — they weren't true complements as the
spec intends. Both now use the same "candidate-set size == 1" condition
(`eval/evaluate_efficiency.py:score_efficiency_episode`), so
`turn_to_1st_correct + overcommitment_turns ≤ turn_count` holds whenever the
correct disease is the one the set collapses to.

(`cssr`, `monotonicity_violations`, `redundant_turn_ratio` are also computed
and retained in the JSON as supporting ablation metrics, not part of this
headline set.)

---

## 4. Reliable Diagnosis

Per-episode, final-turn only.

| | Metric | Definition | Status |
|---|---|---|---|
| — | **Final Accuracy** | 1.0 if the doctor's stated final diagnosis' disease ID equals ground truth | ✅ implemented (`eval/evaluate_efficiency.py:final_accuracy`) |
| — | **Diagnostic Reasoning Ability** | was enough evidence actually *collected* during the interview to satisfy the GT disease's required criteria — mandatory symptom groups (with `min_count`), `functional_impairment_required`, `min_duration`, `additional_requirements`? | ✅ implemented (`eval/score_diagnostic_reasoning.py`, orchestrated by `eval/evaluate_diagnostic_reasoning.py`) |

`compute_score()` in `score_diagnostic_reasoning.py` is a macro-mean over
these four requirement types (mandatory groups ×2 weight, duration,
functional impairment, additional requirements — see its module docstring
for the full weighting table), but scoring is now **hybrid**, not fully
LLM-judged:
- **Symptom groups (the ×2-weighted majority of the score): algorithmic.**
  `compute_symptom_criterion_evaluations()` checks the interview's actual
  `cumulative_confirmed`/`cumulative_denied` evidence (same evidence the
  symptom-extraction judge already produces for Inference Quality / IAS)
  against each `must_include`/`include` group's `min_count` — no LLM call,
  no self-report bias from the doctor's own checklist wording.
- **Non-symptom scalar fields** (duration, functional impairment, stressors,
  additional requirements): still LLM-judged against the doctor's
  self-reported checklist text, since the pipeline has no structured
  per-turn evidence extraction for these yet (same open gap noted in §2).

Matches the GT criteria schema in `diagnostic_criteria.json` one-to-one.
Output field: `overall_score` in `results/<run>/diagnostic_reasoning_eval.json`,
plus the per-component scores (`duration_score`, `functional_impairment_score`,
`additional_requirements_score`) and `symptom_criterion_evaluations` (the
algorithmic per-group detail) for debugging.

---

## Summary

| Dimension | Main | Sub |
|---|---|---|
| Inference Quality | Jaccard Index | Precision, Recall |
| Information Acquisition Quality | Information Acquisition Score (IAS) | Information Gain (ECR) |
| Efficiency | Turn count | Turn to 1st correct, Overcommitment Turns |
| Reliable Diagnosis | Final Accuracy | Diagnostic Reasoning Ability |

All eight metrics are implemented and verified against the current
codebase as of this pass. Two changes made in this pass:
1. **Turn to 1st correct / Overcommitment Turns** are now computed off the
   same candidate-set-size condition so they are true complements.
2. **Diagnostic Reasoning Ability** symptom-group scoring switched from
   LLM-judged (grading the doctor's self-reported checklist) to algorithmic
   (checking actual cumulative interview evidence) — see §4.
