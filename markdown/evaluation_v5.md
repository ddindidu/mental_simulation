# Evaluation v5: Headline Metric Reference

This doc describes the four evaluation dimensions and their headline metrics,
written against the code as it stands. It replaces `evaluation_v4.md`. Only
the metrics listed here are computed; everything else is commented out in the
code (see [Deactivated](#deactivated-metrics)).

| Dimension | Main | Sub |
|---|---|---|
| **Diagnostic Hypothesis Quality** | Jaccard, Precision, Recall, Weighted Recall | — |
| **Diagnostic Question Quality** | Question Targeting Score (QTS) | — |
| **Diagnostic Efficiency** | Total Turns | 1st-Confidence Turn, Overcommitment Turns |
| **Diagnostic Decision Quality** | Final Accuracy, Diagnostic Evidence Sufficiency | — |

---

## 0. Shared inputs

**Turn numbering** (`utils/turn_policy.py`, shared by `eval/` and `human_validation/`):

- **t = 0** is the doctor's opening question. It is not a turn and is never scored.
- **Turn t ≥ 1** groups three things: patient response *t*, the doctor's
  disorder prediction after it, and the doctor's next question.
- The last turn *T* has no question, so an episode with *T* turns has *T*
  responses and predictions but only *T* − 1 scored questions.

The raw logs group turns the other way: `turns[k].doctor.question` (and
`doctor_question` in `*_result.json`) is the question asked *before* response
*k*, which is turn *k* − 1 under this policy. Always convert with
`policy_turns()` rather than re-deriving the offset in each script.

**Ground truth.** The disease ID comes from the log filename (`D009_S003_P001_plain` → `D009`).

**ICD-10 → disease ID.** The doctor names diseases as ICD-10 codes. These map
to disease IDs through `disorder_icd10.json`, where every code in
`icd10_accepted_codes` maps to its disorder. A final-diagnosis string that
arrives JSON-wrapped is unwrapped first. Both helpers live in `eval/common.py`.

**Symptom evidence.** `eval/symptom_diagnosis.py` runs one LLM-judge call per
patient turn. Each call labels symptoms as CONFIRMED or DENIED; anything not
labeled stays UNKNOWN. The labels accumulate into
`cumulative_confirmed` / `cumulative_denied`.

**KG candidate tiers.** `compute_candidate_set(confirmed, denied)` assigns each
disease to a tier based on the evidence so far:

| tier | condition |
|---|---|
| `excluded` | any mandatory (`must_include`) symptom is denied |
| `high_likely` | every `must_include` group meets its `min_count` |
| `moderate_likely` | at least one mandatory symptom is confirmed, but not every group is met |
| `low_likely` | no mandatory symptom confirmed, at least one optional symptom confirmed |

A disease with no symptom overlap at all is in no tier.

---

## 1. Diagnostic Hypothesis Quality

**What it asks:** at each turn, does the doctor's stated candidate list match
the KG reference?
**Code:** `eval/evaluate_turns.py` → `analysis/<combo>/turn_eval.json`

Let `P` be the doctor's candidate IDs after turn *t*, and `gt` the ground truth.

**Reference candidate set `R` (tier-priority).** Take only the highest
non-empty tier, then always add `gt`:

```
R = high ∪ {gt}       if high ≠ ∅
  = moderate ∪ {gt}   elif moderate ≠ ∅
  = low ∪ {gt}        elif low ≠ ∅
  = {gt}              otherwise
```

```
Precision = |P ∩ R| / |P|          (0 if P = ∅)
Recall    = |P ∩ R| / |R|
Jaccard   = |P ∩ R| / |P ∪ R|
```

**Weighted Recall** uses all three tiers. `gt` is forced into `H`, and the
tiers are made disjoint:

```
WR = 1 − (2·|H∖P| + 1·|M∖P| + 0.5·|L∖P|) / (2·|H| + 1·|M| + 0.5·|L|)
```

**Aggregation:** each metric is computed per (episode, turn). A combo's
reported value is the mean over all (episode, turn) rows.

> `gt` is always in `R` and in `H`, so a doctor who names only the correct
> disease is never penalized for an algorithmic tier miss.

---

## 2. Diagnostic Question Quality: Question Targeting Score (QTS)

**What it asks:** does the doctor's next question target symptoms that are
diagnostically relevant and not yet resolved?
**Code:** `eval/question_targeting_score.py` (scoring), orchestrated by
`eval/evaluate_question.py` → `results/<combo>/question_eval.json`

QTS was renamed from IAS (Information Acquisition Score). The formula did not change.

**Turn pairing.** The question asked after patient turn *t* is scored against
the doctor's own candidate list at turn *t* (`C_t`) and the cumulative
evidence at turn *t*. Two questions are never scored: the opening question,
and the last turn (which has no follow-up question).

**Question → symptoms.** `S(q_t)` is the set of symptom IDs the question
targets. An LLM-judge mapper (`llm_judge`) produces it, with results cached
per question text in `llm_judge_question_cache.json`.

```
S_disc,t = { s : 0 < #{d ∈ C_t : s ∈ pool(d)} < |C_t| }   (empty if |C_t| < 2)
R_t      = ∪_{d ∈ C_t} must_include symptoms of d          (symptom-level, no min_count gating)
I_t      = S_disc,t ∪ R_t

DRS_t = |S(q_t) ∩ I_t| / |S(q_t)|                          diagnostic relevance
RP_t  = |S(q_t) ∩ (confirmed ∪ denied)| / |S(q_t)|         redundancy penalty
QTS_t = DRS_t × (1 − RP_t)                                  (0 if S(q_t) = ∅)
```

- `pool(d)` covers both mandatory and optional symptom pools.
- UNKNOWN never counts as resolved, so re-asking after an ambiguous answer is
  not penalized.
- Non-symptom requirements (duration, impairment, etc.) are out of scope.

**Aggregation:** episode `mean_qts` is the mean of `QTS_t` over all scored
turns. A combo's value is the mean of the episode `mean_qts` values.

---

## 3. Diagnostic Efficiency

**Code:** `eval/evaluate_efficiency.py` → `results/<combo>/efficiency_eval.json`

Here `C_t` is the KG reference set `high ∪ moderate ∪ low`, with **no** forced
`gt`. `T` is the number of patient turns.

| | Metric | Definition | Field |
|---|---|---|---|
| main | **Total Turns** | `T`, the number of patient turns until the doctor gives a final diagnosis | `turn_count` |
| sub | **1st-Confidence Turn** | First turn *t* (1-indexed) where `C_t == {final_dx}`, the disease the doctor finally chose, correct or not. `T+1` if never reached or the final diagnosis is unresolvable | `time_to_first_confident_narrowing` |
| sub | **Overcommitment Turns** | `T − 1st-Confidence Turn`: turns spent after the evidence had already narrowed to the doctor's own final answer. `0` if never reached | `overcommitment_conf` |

By construction, `Total Turns = 1st-Confidence Turn + Overcommitment Turns`
whenever the 1st-confidence turn is reached.

**Aggregation:** the mean over episodes.

---

## 4. Diagnostic Decision Quality

### 4.1 Final Accuracy
The score is 1 if the doctor's final diagnosis (ICD-10, unwrapped, accepted
codes) maps to `gt`, and 0 otherwise. The combo value is the mean over
episodes, reported as a percentage.
Fields: `final_accuracy` in `efficiency_eval.json` / `final_accuracy_pct` in
the CSV, plus the per-disease breakdown in `evaluate_final_diagnosis.py`.

### 4.2 Diagnostic Evidence Sufficiency
**What it asks:** did the interview collect enough evidence to support the
diagnosis **the doctor actually gave**?
**Code:** `eval/evaluate_diagnostic_reasoning.py` + `eval/score_diagnostic_reasoning.py`
→ `results/<combo>/diagnostic_reasoning_eval.json`, field `overall_score_pred`

The target disease `d̂` is the doctor's final diagnosis. If it doesn't map to
a disease ID, the score is `None` and the episode is excluded from the mean.
No LLM call is made in that case.

The score is a hybrid of two parts, both checked against `d̂`'s required
criteria:

**(a) Symptom satisfaction (algorithmic, no LLM).** This part uses the
final-turn `cumulative_confirmed`. For each symptom group *g*:

```
coverage_g  = min(1, |pool_g ∩ confirmed| / min_count_g)
satisfied_g = coverage_g ≥ 1  ∧  must_include_all ⊆ confirmed  ∧  (must_include_one_of ∩ confirmed ≠ ∅)
SymSat      = (2·#satisfied mandatory + #satisfied optional) / (2·#mandatory + #optional)
```

**(b) Non-symptom requirements (LLM judge).** The judge compares the doctor's
final `diagnostic_checklist` against `d̂`'s non-symptom criteria. If no
checklist exists, it falls back to the free-text `reason`. Each item scores 0
or 1, except additional requirements, which score in [0, 1]. An item is
included only if `d̂` requires it:

- duration (top-level `min_duration`)
- functional impairment
- traumatic stressor
- psychosocial stressor
- additional requirements

```
overall_score_pred = mean( SymSat, and each required item from (b) )   — macro-mean, equal weight
```

If the judge's output can't be parsed, only the (b) items are dropped; SymSat
still counts. Results are cached by content hash in
`diagnostic_reasoning_scalar_cache.json`.

**Aggregation:** the mean over episodes with a non-null score.

---

## Outputs & reporting

| Dimension | Per-episode/turn file | Headline fields |
|---|---|---|
| Hypothesis | `analysis/<combo>/turn_eval.json` | `jaccard`, `precision`, `recall`, `weighted_recall` |
| Question | `results/<combo>/question_eval.json` | `episode_metrics.llm_judge.mean_qts`; per turn `scores_by_mapper.llm_judge.qts` |
| Efficiency | `results/<combo>/efficiency_eval.json` | `turn_count`, `time_to_first_confident_narrowing`, `overcommitment_conf` |
| Decision | `efficiency_eval.json`, `diagnostic_reasoning_eval.json` | `final_accuracy`, `overall_score_pred` |

`reporting/summarize_v4_metrics_csv.py` writes one row per (patient, judge,
doctor) combo with the columns `jaccard, precision, recall, weighted_recall,
qts, turn_count, turn_to_1st_confident, overcommitment_conf,
final_accuracy_pct, diagnostic_evidence_sufficiency_pred`.

**Backward compatibility** (`utils/metric_compat.py`):
- **QTS readers.** They read `qts` / `mean_qts` and fall back to `ias` /
  `mean_ias` for older `question_eval.json` files.
- **Hypothesis metrics in old files.** In `turn_eval.json` files written
  before this version, the unsuffixed `jaccard`/`precision`/`recall` hold the
  deactivated union-reference values. New files still write the `*_rigid`
  keys as aliases, so readers use `*_rigid`, which is correct for both old
  and new files.

### Reporting scripts (`reporting/`)

The table below lists each reporting script, where it writes, and what it shows.

| Scope | Script | Output | Shows |
|---|---|---|---|
| per combo | `plot_turn_eval.py` | `analysis/<combo>/turn_eval/turn_eval_cases_plot*.png` | Hypothesis metrics per turn, per disorder (reads `turn_eval.json` only) |
| per combo | `plot_question_eval.py` | `analysis/<combo>/question_eval/question_eval_plot*.png` | QTS, DRS, RP per turn, per disorder |
| per combo | `plot_turn_abs.py` / `plot_turn_rel.py` | `analysis/<combo>/turn_abs/`, `turn_rel/` | Hypothesis metrics and QTS by absolute turn / relative progress |
| per combo | `plot_efficiency_eval.py` | `analysis/<combo>/efficiency/efficiency_eval_plot*.png` | stacked 1st-Confidence + Overcommitment = Total Turns; final accuracy |
| per combo | `summarize_efficiency.py` | `analysis/<combo>/efficiency/efficiency_summary.txt` | per-disorder efficiency table |
| cross combo | `summarize_v4_metrics_csv.py` | `analysis/v4_metrics_summary[_plain].{csv,xlsx}` | all 10 headline metrics per combo (input to the `plot_v4_*` scatters and radar) |
| cross combo | `reporting/headline_metrics.py` | — | shared per-episode loader, same aggregation as the CSV |
| per bucket | `summarize_comparisons.py` → `summarize_main_eval_findings.py` | `analysis/<patient>/<judge>/comparison/headline_comparison.*`, `main_eval_*.png` | model × headline-metric tables, bars, normalized heatmap |
| per bucket | `summarize_ablation_all_dimensions.py`, `summarize_question_eval_outcome.py` | `comparison/outcome_stratified/` | headline metrics split by Final Accuracy (correct vs. incorrect) |
| per bucket | `summarize_question_eval.py` | `comparison/question_eval_comparison.*` | QTS, DRS, RP, and empty-target rate per model |

Cross-model scripts default to `--style plain`.

---

## Deactivated metrics

These are commented out in the code, not deleted. Each can be re-enabled by
un-commenting.

| Was | Where | LLM cost when active |
|---|---|---|
| Union-reference (`high ∪ moderate ∪ low`) Precision/Recall/Jaccard, strict accuracy | `evaluate_turns.py` | none |
| `evaluate_turns_strict.py` (Method-B truth set) | pipeline lists in `script/run_all_doctors_profiles*.py`, `script/rerun_icd10_normalized_eval.py`, `app.py` | **1 judge call per log** |
| ECR (Expected Candidate Reduction), active-turn conditional means, safety-critical coverage | `question_targeting_score.py`, `evaluate_question.py` | none |
| Cosine-similarity question mapper | `evaluate_question.py` | none (local embedding model; compute only) |
| CSSR, Turn to 1st correct, monotonicity violations, redundant-turn ratio, `overcommitment_turns` (first size-1 collapse) | `evaluate_efficiency.py` | none |
| Evidence Sufficiency `_gt` (scored against the ground-truth disease's criteria) | `evaluate_diagnostic_reasoning.py` | **1 scalar-judge call per episode where the final diagnosis ≠ `gt` or is unresolved** |
| Semantic-mapper IAS (`question_eval_semantic.json`) | `reporting/plot_question_eval.py` (now plots the `llm_judge` QTS instead) | none |

**LLM calls that remain:**
1. symptom extraction (`symptom_diagnosis.py`, per turn), which every dimension depends on
2. the QTS question mapper (one call per unique question, cached)
3. the Evidence Sufficiency scalar judge (one call per episode with a resolvable diagnosis, cached)

---

## Changes since v4

1. **Dimensions renamed.**
   - Inference Quality → Diagnostic Hypothesis Quality
   - Information Acquisition Quality → Diagnostic Question Quality
   - Efficiency → Diagnostic Efficiency
   - Reliable Diagnosis → Diagnostic Decision Quality
2. **Reference set.** Precision/Recall/Jaccard now use the tier-priority
   reference set instead of the `high ∪ moderate ∪ low` union. Weighted
   Recall is promoted to a headline metric.
3. **IAS → QTS.** Renamed. The formula is unchanged and the `llm_judge` mapper
   is the only mapper. ECR is dropped.
4. **Efficiency.** The headline set is Total Turns, 1st-Confidence Turn, and
   Overcommitment Turns (the confidence-based variant). Turn-to-1st-correct
   and the size-1-collapse overcommitment variant are dropped.
5. **Evidence Sufficiency.** Now scored against the doctor's own final
   diagnosis (`_pred`), replacing v4's ground-truth-based Diagnostic
   Reasoning Ability.
6. **Accepted ICD-10 codes.** `icd10_accepted_codes` now apply everywhere a
   code is mapped. The CSV summary's final accuracy also unwraps JSON-wrapped
   diagnoses now, consistent with `evaluate_efficiency.py`.
