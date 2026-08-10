# Main Evaluation — Cross-Model Findings Report

**Judge model:** `gemini-3.5-flash` (doctor / inference judge)
**Scope:** All logged episodes, **not** stratified by outcome (see [`outcome_stratified/ablation_findings.md`](outcome_stratified/ablation_findings.md) for the correct/incorrect split of these same dimensions)
**Aggregation:** macro-mean (episode-weighted) per model, per spec §4.4.7 — inference quality is a turn-level mean rolled up to an episode mean, then averaged across episodes; efficiency / question / diagnostic-reasoning are per-episode records averaged directly

---

## Episode Coverage

| Model | Inference (turn_eval) | Question Eval | Efficiency | Diagnostic Reasoning |
|-------|-----------------------|----------------|------------|-----------------------|
| Gemini 3.1 Flash-Lite | 199 | 230 | 230 | 230 (222 valid) |
| Gemini 3.5 Flash | 120 | 230 | 230 | 213 (212 valid) |
| GPT-5.4 | 169 | 221 | 230 | 230 (219 valid) |
| GPT-5.4 Mini | 202 | 230 | 230 | 230 (222 valid) |
| Llama 3.3 70B | 68 | 230 | 230 | 221 (217 valid) |
| Qwen3-235B | 200 | 230 | 230 | 230 (226 valid) |

**⚠ Coverage caveat:** the inference-quality sample size varies sharply by model (68–202 episodes vs. a near-complete 230 for every other model/dimension). Gemini 3.5 Flash (120) and especially Llama 3.3 70B (68) are missing a large fraction of `turn_eval.json` rows relative to their efficiency/DR/question-eval coverage (230/221 each), most likely from incomplete or unparsed turn logs. Treat the inference-quality ranking for these two models as the noisier of the four dimensions until log coverage is backfilled.

---

## Visual Overview

![Cross-model comparison across all four dimensions](main_eval_all_dimensions.png)

![Normalized cross-model profile heatmap](main_eval_normalized_heatmap.png)

The heatmap min-max normalizes each metric column across the 6 models (darker = better within that column) so that metrics on very different scales — accuracy (0–1) next to turn count (4–10) — can be scanned as one profile per model. Raw values are printed in each cell; lower-is-better metrics (turn count, redundant turn ratio) are sign-flipped before normalizing but shown as their true value in the cell text.

---

## 1. Inference Quality

**Source:** `analysis/.../turn_eval.json` — per-turn rows, macro-mean over turns per episode, then over episodes per model.

| Model | Accuracy | Recall | Precision | Jaccard | Weighted Recall |
|-------|----------|--------|-----------|---------|------------------|
| Gemini 3.1 Lite | **0.202** | 0.493 | 0.780 | 0.427 | 0.564 |
| Gemini 3.5 Flash | 0.164 | **0.572** | 0.787 | **0.453** | **0.645** |
| GPT-5.4 | 0.194 | 0.501 | 0.761 | 0.424 | 0.584 |
| GPT-5.4 Mini | 0.177 | 0.438 | 0.815 | 0.396 | 0.512 |
| Llama 3.3 70B | 0.175 | 0.442 | 0.850 | 0.407 | 0.518 |
| Qwen3-235B | 0.137 | 0.411 | **0.866** | 0.383 | 0.490 |

**Pattern:** Two distinct strategies emerge. **Gemini 3.5 Flash** trades exact-set accuracy for coverage — lowest accuracy (0.164) but highest recall (0.572), jaccard (0.453), and weighted recall (0.645), consistent with keeping the ground-truth disease in a wider candidate set for longer. **Qwen3-235B** is the mirror image — highest precision (0.866) but lowest accuracy (0.137), recall (0.411), and jaccard (0.383): a narrow, conservative candidate set that is often wrong about what it excludes. **Gemini 3.1 Flash-Lite** has the highest exact-match accuracy (0.202) despite unremarkable recall/precision, suggesting its candidate sets are simply smaller and easier to match exactly.

---

## 2. Question Quality

**Source:** `results/.../question_eval.json` — episode-level `episode_metrics` (active-turn conditional, macro-mean), reported for both mappers.

### 2.1 Conditional Mean Composite Score

| Model | cosine | llm_judge |
|-------|--------|-----------|
| Gemini 3.1 Lite | 0.302 | 0.464 |
| **Gemini 3.5 Flash** | **0.425** | **0.567** |
| GPT-5.4 | 0.311 | 0.449 |
| GPT-5.4 Mini | 0.270 | 0.379 |
| Llama 3.3 70B | 0.261 | 0.329 |
| Qwen3-235B | 0.243 | 0.367 |

### 2.2 Discriminating-Q Rate

| Model | cosine | llm_judge |
|-------|--------|-----------|
| Gemini 3.1 Lite | 0.419 | 0.489 |
| **Gemini 3.5 Flash** | **0.542** | **0.604** |
| GPT-5.4 | 0.411 | 0.494 |
| GPT-5.4 Mini | 0.350 | 0.396 |
| Llama 3.3 70B | 0.335 | 0.379 |
| Qwen3-235B | 0.321 | 0.377 |

### 2.3 IG-Positive Rate

| Model | cosine | llm_judge |
|-------|--------|-----------|
| Gemini 3.1 Lite | 0.272 | 0.538 |
| **Gemini 3.5 Flash** | **0.365** | 0.460 |
| GPT-5.4 | 0.296 | 0.408 |
| GPT-5.4 Mini | 0.343 | 0.432 |
| Llama 3.3 70B | 0.354 | 0.371 |
| Qwen3-235B | 0.319 | 0.385 |

### 2.4 Conditional Mean IG

| Model | cosine | llm_judge |
|-------|--------|-----------|
| Gemini 3.1 Lite | −0.480 | 0.081 |
| **Gemini 3.5 Flash** | **−0.237** | 0.019 |
| GPT-5.4 | −0.250 | 0.050 |
| GPT-5.4 Mini | −0.284 | 0.084 |
| Llama 3.3 70B | −0.300 | 0.043 |
| Qwen3-235B | −0.320 | 0.008 |

**Pattern:** **Gemini 3.5 Flash is the clear leader on question quality**, ranking first on both mappers for composite score, discriminating-Q rate, and cosine IG-positive rate — consistent with its inference-side strategy of exploring broadly before committing. **Qwen3-235B and Llama 3.3 70B cluster at the bottom** on both mappers' composite and discriminating-Q scores, matching their inference-side pattern of narrow, low-recall candidate tracking. **Gemini 3.1 Flash-Lite** stands out with the most negative cosine conditional-mean IG (−0.480) despite mid-table composite/disc-Q scores — its questions expand the candidate set unusually often relative to peers (see also its highest CSSR in §3, which is a same-side inconsistency worth investigating: an aggressive final narrowing after a period of expansive questioning).

---

## 3. Efficiency

**Source:** `results/.../efficiency_eval.json` — per-episode records.

| Model | Final Accuracy | Turn Count | CSSR | T-first | Monotonicity Viol. | Redundant Turn Ratio | Overcommitment Turns |
|-------|-----------------|------------|------|---------|---------------------|------------------------|------------------------|
| Gemini 3.1 Lite | 0.809 | 5.57 | **0.223** | 5.52 | 0.483 | 0.634 | 1.09 |
| Gemini 3.5 Flash | 0.622 | 7.27 | 0.087 | 7.00 | 0.652 | 0.683 | 1.93 |
| GPT-5.4 | **0.844** | 8.20 | 0.168 | 7.07 | 0.570 | 0.729 | 2.36 |
| GPT-5.4 Mini | 0.835 | 5.06 | 0.169 | 5.10 | 0.470 | 0.630 | 0.82 |
| Llama 3.3 70B | 0.100 | 9.73 | 0.001 | 8.11 | 0.952 | 0.752 | 2.57 |
| Qwen3-235B | 0.822 | **4.67** | 0.051 | **4.80** | 0.522 | **0.584** | **0.77** |

**Pattern:** **Qwen3-235B is the most efficient model** overall — shortest episodes (4.67 turns), fastest first correct narrowing (4.80), lowest redundant-turn ratio (0.584), lowest overcommitment (0.77) — while still landing high final accuracy (0.822). **GPT-5.4 Mini** is a close second on efficiency and slightly ahead on final accuracy (0.835 vs 0.822). **GPT-5.4** achieves the single highest final accuracy (0.844) but takes nearly twice Qwen3's turns to get there (8.20) with the highest overcommitment (2.36 turns spent after the candidate set has already collapsed to one).

**⚠ Llama 3.3 70B is a severe outlier**: final accuracy of **0.100** despite reasonable recall/jaccard on the inference side (§1) — this is the "tracks but doesn't commit" failure mode. It has the lowest CSSR by an order of magnitude (0.001, i.e. it essentially never narrows its candidate set), the highest monotonicity violations (0.952 — its candidate set grows almost every other turn), the longest episodes (9.73 turns), and the highest overcommitment (2.57). The model appears to keep exploring rather than converging on a final answer, even when it likely has already identified the correct disease among its candidates.

**Note on aggregation:** these are pooled means across all episodes regardless of outcome. Per the outcome-stratified ablation (`outcome_stratified/ablation_findings.md`), CSSR and turn count in particular differ dramatically between correct and incorrect episodes for every model — a pooled CSSR of, say, 0.087 for Gemini 3.5 Flash is an average of roughly −0.075 (correct) and +0.344 (incorrect), not a stable per-episode value. Use the pooled numbers here for overall ranking, and the ablation report for diagnosing *why* a model lands where it does.

---

## 4. Diagnostic Reasoning

**Source:** `results/.../diagnostic_reasoning_eval.json` — per-episode LLM-judge scores.

| Model | Overall | Duration | Functional Impairment | Traumatic Stressor | Psychosocial Stressor | Additional Requirements |
|-------|---------|----------|------------------------|----------------------|--------------------------|----------------------------|
| Gemini 3.1 Lite | 0.546 | 0.656 | 0.203 | 0.706 | 0.900 | 0.589 |
| Gemini 3.5 Flash | 0.733 | 0.852 | 0.291 | 0.895 | 1.000 | 0.883 |
| **GPT-5.4** | **0.828** | 0.937 | 0.691 | 0.850 | 1.000 | 0.867 |
| GPT-5.4 Mini | 0.646 | 0.744 | 0.387 | 0.800 | 1.000 | 0.638 |
| Llama 3.3 70B | 0.773 | 0.937 | **0.934** | 0.813 | 0.900 | 0.774 |
| Qwen3-235B | 0.600 | 0.765 | 0.339 | **0.950** | 1.000 | 0.599 |

**Pattern:** **GPT-5.4 has the highest overall diagnostic-reasoning score** (0.828), driven by strong duration (0.937) and by far the best functional-impairment coverage among non-Llama models (0.691). It is also the only model besides Llama with `has_structured_checklist` output (230/230 episodes), which likely helps its criterion-by-criterion coverage. **Llama 3.3 70B** is a close second overall (0.773) and wins outright on functional impairment (0.934) — its DSM-5 documentation is thorough even though (per §3) it almost never commits to the documented diagnosis. **Gemini 3.1 Flash-Lite** is the weakest on both overall score (0.546) and functional impairment (0.203), the same model that showed the most aggressive candidate narrowing (§3) — its reasoning transcripts appear terser and less criterion-complete than its peers'.

---

## 5. Cross-Dimension Model Characterization

**GPT-5.4 — Highest ceiling, highest cost**
Best final diagnostic accuracy (0.844) and best diagnostic-reasoning overall score (0.828), with solid inference recall (0.501, 2nd) and question quality (2nd on cosine composite). Pays for this with the 2nd-longest episodes (8.20 turns) and the highest overcommitment (2.36 turns spent after narrowing to one candidate) among non-Llama models — it keeps talking after it has effectively decided.

**Gemini 3.5 Flash — Broadest search, weakest commitment**
#1 on inference recall (0.572), jaccard (0.453), and both question-quality mappers (composite, discriminating-Q). But this breadth-first strategy costs it on final accuracy (0.622, 2nd-lowest) and CSSR (0.087, narrows slowly) — it explores well but converges less decisively than GPT-5.4 or the leaner models.

**Gemini 3.1 Flash-Lite — Fast exact-match, thin reasoning**
Highest inference accuracy (0.202) and highest CSSR (0.223, most aggressive narrowing) but the weakest diagnostic-reasoning overall score (0.546) and functional-impairment coverage (0.203) of all six models. Its candidate-set management looks decisive, but its clinical documentation is the thinnest.

**GPT-5.4 Mini — Best accuracy-per-turn**
2nd-highest final accuracy (0.835) achieved in the 2nd-fewest turns (5.06) with the 2nd-lowest overcommitment (0.82) — an efficient middle-of-the-pack performer on inference and question quality, but a strong efficiency profile.

**Llama 3.3 70B — Tracks but never commits**
The standout anomaly of the whole table: reasonable inference recall (0.442) and jaccard (0.407), the best diagnostic-reasoning functional-impairment score by a wide margin (0.934), yet a final accuracy of just **0.100** — the lowest of any model by more than 5x. Its efficiency numbers explain why: CSSR ≈ 0 (never narrows), monotonicity violations 0.952 (candidate set keeps re-expanding), longest episodes (9.73 turns), highest overcommitment (2.57). This model appears to gather clinical detail thoroughly but never converges on — or never outputs — its final answer, a commitment failure rather than a tracking failure.

**Qwen3-235B — Leanest and most precise, shallowest questions**
Shortest episodes (4.67 turns), fastest T-first (4.80), lowest redundant-turn ratio (0.584), highest inference precision (0.866), and strong final accuracy (0.822) — the most efficient model in the table. Trade-off: lowest question-quality composite and discriminating-Q rate on the cosine mapper (0.243 / 0.321) and lowest inference accuracy/jaccard — it gets to a good answer fast but by asking comparatively less discriminating questions along the way.

---

## 6. Cross-Reference to Outcome-Stratified Ablation

The pooled numbers here should not be read as outcome-independent — see `outcome_stratified/ablation_findings.md` for the correct/incorrect split. Three findings from that report are directly relevant to interpreting the main-eval table above:

- **CSSR** (§3) is universally much higher in incorrect episodes for every model — the pooled CSSR values above are a blend of two very different regimes, not a stable behavioral constant.
- **Duration score** (DR, §4) is *higher* in incorrect episodes for 4/6 models — a documentation-of-uncertainty artifact, not a reasoning-quality signal.
- **IG-Positive Rate** (question quality, §2) is inflated in longer (failed) episodes via the active-turn-count denominator.

When ranking models by CSSR, duration score, or IG-positive rate alone, prefer the outcome-stratified tables over the pooled ones above.

---

*Generated from:* `analysis/gemini-3.5-flash/gemini-3.5-flash/comparison/{inference,efficiency,diagnostic_reasoning,question_eval}_comparison.json`
*Plots:* `main_eval_all_dimensions.png`, `main_eval_normalized_heatmap.png` (via `reporting/summarize_main_eval_findings.py`)
*Date:* 2026-07-22
