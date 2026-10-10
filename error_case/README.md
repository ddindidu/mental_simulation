# Unresolved ICD-10 codes (run_batch_20260912)

Doctor models' final-diagnosis ICD-10 codes that don't map to any of the 23
disorders in `mentalbench/resources/knowledge_graph/EN/disorder_icd10.json`,
so `final_diagnosis_id` (and hence `final_accuracy`) stayed `null` for these
episodes. Generated across all 10 (judge, doctor) combos in
`saved/run_batch_20260912/results/*/*/*/efficiency_eval.json`.

- `unresolved_icd10_codes.txt` — human-readable table, sorted by frequency.
- `unresolved_icd10_codes.csv` — same data, plus up to 2 example
  `doctor/log_file` references per code, for spreadsheet editing.

Both list, per code: how many episodes returned it, and which ground-truth
disorder(s) it most often occurred under (a hint for which disorder it
should probably map to, not a guarantee — some codes are genuinely outside
the 23-disorder taxonomy, e.g. `F90.9` unspecified ADHD subtype, `F23` brief
psychotic disorder, `G47.x` sleep disorders, `Z`-codes).

## Also fixed in this pass

`eval/evaluate_efficiency.py` and `eval/evaluate_final_diagnosis.py` had a
separate parsing bug (unrelated to the ICD-10 mapping itself): some doctor
models — observed for claude-sonnet-5, occasionally gemini-3.8-flash —
return their final-diagnosis step as a raw JSON object string
(`{"diagnosis": "F90.0", "candidates": [...], "reason": "..."}"`) instead of
a bare code, and that whole string was getting stored in `final_diagnosis`
verbatim instead of just the `diagnosis` value. Both scripts now unwrap this
case (`_unwrap_json_diagnosis()`) before ICD-10 lookup. This is a
best-effort deterministic fix at the evaluation layer — the raw simulation
logs themselves (`saved/.../logs/.../*.json`) still contain the unparsed
blob, since fixing that would mean re-running the doctor simulation (new LLM
calls), which wasn't done here.

Two episodes remain genuinely unparseable by either fix (not ICD-10-related
— their `final_diagnosis` field doesn't contain a recognizable code or a
`"diagnosis": "..."` key at all):
  - `gemini-3.8-flash / D003_S005_P003_verbose`
  - `qwen3-235b / D012_S004_P001_plain`

## Regenerating this list

After editing `disorder_icd10.json`, re-run
`eval/evaluate_efficiency.py` per (judge, doctor) combo (see
`script/rerun_icd10_normalized_eval.py` for the config-mutation pattern used
to loop over combos), then regenerate this report from
`saved/run_batch_20260912/results/*/*/*/efficiency_eval.json`.
