# Case Study Index

Cases are drawn from 704 (model, dialogue) pairs across 4 doctor models
(gemini-3.5-flash, gemini-3.1-flash-lite, gpt-5.4-mini-2026-03-17,
qwen3-235b-a22b-2507), aggregated per dialogue as the turn-wise mean of each
metric. High/low is a global median split across all 704 cases:

| Metric | Global median | Source |
|---|---|---|
| Precision | 0.900 | `analysis/**/turn_eval.json` (spec §4.3) |
| Recall | 0.500 | `analysis/**/turn_eval.json` (spec §4.3) |
| Inference quality (jaccard) | 0.426 | `analysis/**/turn_eval.json` (spec §4.3) |
| Question reasonability (composite_score) | 0.100 | `analysis/**/question_eval_semantic.json` (spec §4.4) |

Note: "inference quality" uses `jaccard` (precision/recall overlap combined
into one scalar) since Classification 1 already isolates precision and
recall separately — flag if you'd rather use `accuracy` or `weighted_recall`
instead.

Within each bucket, the 5 cases shown are the most "extreme" examples (largest
margin from the median on the relevant axis/axes), diversified across models
(max 2 per model where possible).

## Classification 1 — precision / recall
(low_precision_low_recall intentionally omitted per request)

- [classification1_precision_recall/high_precision_high_recall/](classification1_precision_recall/high_precision_high_recall/)
- [classification1_precision_recall/high_precision_low_recall/](classification1_precision_recall/high_precision_low_recall/)
- [classification1_precision_recall/low_precision_high_recall/](classification1_precision_recall/low_precision_high_recall/)

## Classification 2 — inference quality / question reasonability

- [classification2_inference_question/high_inference_high_question/](classification2_inference_question/high_inference_high_question/)
- [classification2_inference_question/high_inference_low_question/](classification2_inference_question/high_inference_low_question/)
- [classification2_inference_question/low_inference_high_question/](classification2_inference_question/low_inference_high_question/)
- [classification2_inference_question/low_inference_low_question/](classification2_inference_question/low_inference_low_question/)

Each case file (`<model>__<log_file>.md`) contains: ground truth / final
diagnosis / correctness, a metrics table (case mean vs. global median), and
the full doctor–patient dialogue transcript.

Regenerate with: `python3 script/build_case_studies.py`
