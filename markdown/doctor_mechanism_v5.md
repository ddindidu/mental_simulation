# Doctor LLM — Inputs/Outputs per Stage

Source: `doctor.py` (prompt builders), `simulation_core.py` (call orchestration).

Three LLM calls happen per turn (inference → questioning), plus one closing call
(final diagnosis, which also produces the diagnostic checklist in the same
output). The doctor is **never** given the knowledge graph, DSM-5 criteria,
symptom catalogue, or a restricted disease candidate list — every stage below
is grounded only in the plain-text dialogue transcript and the doctor's own
prior outputs.

## 1. Disorder-candidate inference

`doctor.build_inference_prompt()` — [doctor.py:45](../doctor.py#L45)

**Input:**
- Current turn number, `max_turns`
- Its own previous-turn candidate list (empty on turn 1)
- Full dialogue transcript so far (`Doctor: ... / Patient: ...` plain text, nothing else embedded)

**Output (JSON):**
- `candidates`: updated differential list, as ICD-10 codes
- `note`: what changed vs. the previous candidate list (empty if unchanged)
- `is_final`: whether the model is confident enough to stop and move to final diagnosis

## 2. Follow-up question

`doctor.build_questioning_prompt()` — [doctor.py:96](../doctor.py#L96)

**Input:**
- Current turn number, `max_turns`
- The candidate list just produced by stage 1 this same turn
- Full dialogue transcript so far

**Output (JSON):**
- `intent`: what the question is meant to find out
- `question`: the actual text asked to the patient

Prompt explicitly constrains: ask about exactly ONE thing (never bundle
symptoms or attributes), prefer whatever best discriminates the current
candidates.

*Turn 1 exception:* no transcript/candidates exist yet — the doctor instead
gets a fixed instruction to greet the patient and ask what brings them in
(`doctor.opening_user_message()`, [doctor.py:239](../doctor.py#L239)).

## 3. Final diagnosis + 4. Diagnostic checklist

Same single call — `doctor.get_final_diagnosis_system_prompt()` /
`doctor.final_diagnosis_user_payload()` — [doctor.py:130](../doctor.py#L130),
[doctor.py:255](../doctor.py#L255). Triggered once `is_final=True` from stage 1,
or `max_turns` is reached.

**Input:**
- Final candidate list (from the last inference call)
- Full dialogue transcript

**Output (JSON):**
- `diagnosis`: single ICD-10 code, the doctor's final answer
- `candidates`: top 2–3 differentials considered (ICD-10 codes)
- `reason`: brief rationale
- `diagnostic_checklist` (self-reported, not re-verified against the transcript by the model itself):
  - `symptom_groups`: list of `{group, confirmed_symptoms[], count}` — only groups the doctor judges relevant
  - `duration_verified`: free-text description or null
  - `functional_impairment`: true/false/null
  - `traumatic_stressor`: true/null
  - `psychosocial_stressor`: true/null
  - `additional_requirements`: list of verified extra criteria (e.g. "onset before age 12")

## Notes

- `/no_think` is silently prepended to every prompt when the doctor model is Qwen3 ([doctor.py:14](../doctor.py#L14)); no-op for other models.
- The `diagnostic_checklist` is the doctor's own self-report — downstream scoring
  (`eval/score_diagnostic_reasoning.py`) cross-checks only the symptom-group
  portion against independently-extracted patient evidence; the scalar fields
  (duration/functional impairment/stressors/additional requirements) are taken
  as stated, not re-verified against the transcript.
