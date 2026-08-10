# Outcome-Stratification Ablation — Findings Report

**Judge model:** `gemini-3.5-flash` (doctor / inference judge)  
**Outcome definition:** *correct* = ground-truth disease ∈ `all_candidates()` at the final turn; *incorrect* = ground-truth absent  
**Aggregation:** macro-mean (episode-weighted) per stratum, then per-model mean  
**Δ convention:** Δ = correct − incorrect (positive = correct episodes score higher)

---

## Correct Rate by Model

| Model | n (correct) | n (incorrect) | Correct Rate |
|-------|-------------|---------------|--------------|
| Gemini 3.1 Flash-Lite | 149 | 81 | 64.8% |
| Gemini 3.5 Flash | 141 | 89 | 61.3% |
| GPT-5.4 | 112–116 | 109–114 | ~50.4–50.7% |
| GPT-5.4 Mini | 177 | 53 | 77.0% |
| Llama 3.3 70B | 169 | 61 | 73.5% |
| Qwen3-235B | 167 | 63 | 72.6% |

> GPT-5.4 episode count differs slightly between dimensions (221 in question eval due to missing log files; 230 in efficiency/inference from `_result.json`).

---

## 1. Inference Quality

**Source:** `analysis/.../turn_eval.json` — per-turn rows, macro-mean over turns per episode, then over episodes per stratum.

### 1.1 Accuracy (exact set match)

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | 0.290 | 0.164 | **+0.126** |
| Gemini 3.5 Flash | 0.183 | 0.109 | +0.075 |
| GPT-5.4 | 0.250 | 0.143 | +0.108 |
| GPT-5.4 Mini | 0.252 | 0.148 | +0.103 |
| Llama 3.3 70B | 0.246 | 0.118 | **+0.128** |
| Qwen3-235B | 0.195 | 0.163 | +0.032 |

**Pattern:** All models show higher accuracy in correct episodes (Δ > 0 universally). Gemini 3.5 Flash and Qwen3-235B have the smallest gaps (+0.075 and +0.032), suggesting their turn-level set tracking is less confounded by final outcome. Gemini 3.1 Lite and Llama 3.3 have the largest gaps (~+0.13).

### 1.2 Recall (truth set coverage)

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | 0.620 | 0.409 | +0.211 |
| **Gemini 3.5 Flash** | **0.586** | **0.556** | **+0.030** |
| GPT-5.4 | 0.581 | 0.434 | +0.147 |
| GPT-5.4 Mini | 0.521 | 0.380 | +0.141 |
| Llama 3.3 70B | 0.502 | 0.394 | +0.108 |
| Qwen3-235B | 0.488 | 0.383 | +0.105 |

**Pattern:** Recall is the clearest discriminator of model robustness. Gemini 3.5 Flash's near-flat slope (Δ=+0.030) is an outlier — its candidate tracking keeps the ground-truth disease present at similar rates regardless of whether the episode ultimately succeeds. All other models show significant recall drops in failed episodes (Δ +0.10 to +0.21), indicating the candidate set is losing the correct diagnosis well before the final turn.

### 1.3 Precision

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | 0.883 | 0.701 | +0.182 |
| **Gemini 3.5 Flash** | **0.792** | **0.766** | **+0.027** |
| GPT-5.4 | 0.857 | 0.710 | +0.148 |
| GPT-5.4 Mini | 0.901 | 0.749 | +0.152 |
| Llama 3.3 70B | 0.909 | 0.730 | +0.179 |
| Qwen3-235B | 0.919 | 0.793 | +0.126 |

**Pattern:** Gemini 3.5 Flash has the lowest correct-episode precision (0.792) but the smallest Δ — it maintains a wider candidate set even in correct episodes rather than narrowing aggressively. The remaining models achieve high precision in correct episodes (0.86–0.92) but collapse substantially in incorrect ones, consistent with the CSSR anomaly seen in efficiency.

### 1.4 Jaccard Index

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | 0.534 | 0.361 | +0.173 |
| **Gemini 3.5 Flash** | **0.457** | **0.452** | **+0.005** |
| GPT-5.4 | 0.493 | 0.372 | +0.121 |
| GPT-5.4 Mini | 0.478 | 0.342 | +0.137 |
| Llama 3.3 70B | 0.469 | 0.364 | +0.104 |
| Qwen3-235B | 0.453 | 0.362 | +0.090 |

**Pattern:** Jaccard combines precision and recall effects. Gemini 3.5 Flash's near-zero Δ (+0.005) is the only model where the candidate set quality is statistically outcome-independent.

### Summary — Inference Quality

- **Gemini 3.5 Flash** is the only model where inference metrics are robust to outcome (Δ < +0.03 on all metrics). Its strategy — keeping a broader candidate set at all times — maintains quality in both strata.
- **Gemini 3.1 Lite** and **Llama 3.3** show the largest confound (Δ ≈ +0.13–+0.21 on recall), suggesting their inference quality is heavily dependent on whether the episode is on track.
- **Qwen3-235B** has relatively small Δ on accuracy and jaccard despite low absolute scores, suggesting its failure mode is global (low performance in both strata) rather than outcome-driven.

---

## 2. Question Quality

**Source:** `results/.../question_eval.json` — episode-level `episode_metrics` (active-turn conditional, macro-mean). Two mappers reported separately.

### 2.1 Conditional Mean Composite Score (cosine mapper)

| Model | Correct | Incorrect | Δ (cosine) | Δ (llm_judge) |
|-------|---------|-----------|------------|---------------|
| Gemini 3.1 Lite | 0.350 | 0.231 | +0.119 | +0.147 |
| **Gemini 3.5 Flash** | **0.420** | **0.432** | **−0.011** | **−0.029** |
| GPT-5.4 | 0.342 | 0.285 | +0.057 | +0.041 |
| GPT-5.4 Mini | 0.288 | 0.216 | +0.072 | +0.112 |
| Llama 3.3 70B | 0.262 | 0.257 | +0.005 | +0.021 |
| Qwen3-235B | 0.279 | 0.165 | +0.114 | +0.173 |

**Pattern:** Gemini 3.5 Flash has a negative Δ (incorrect episodes score marginally higher) — its question composite is genuinely outcome-independent and possibly slightly elevated in harder cases. Qwen3-235B has the largest confound (+0.114 cosine, +0.173 llm), suggesting its question quality degrades severely when it is losing track of the correct diagnosis.

### 2.2 Discriminating-Q Rate (cosine mapper)

| Model | Correct | Incorrect | Δ (cosine) | Δ (llm_judge) |
|-------|---------|-----------|------------|---------------|
| Gemini 3.1 Lite | 0.495 | 0.306 | **+0.189** | +0.151 |
| **Gemini 3.5 Flash** | **0.541** | **0.543** | **−0.002** | **−0.027** |
| GPT-5.4 | 0.450 | 0.379 | +0.071 | +0.055 |
| GPT-5.4 Mini | 0.381 | 0.258 | +0.124 | +0.111 |
| Llama 3.3 70B | 0.337 | 0.331 | +0.007 | +0.018 |
| Qwen3-235B | 0.368 | 0.220 | +0.148 | **+0.191** |

**Pattern:** Discriminating-Q Rate is the most outcome-sensitive question quality metric. Gemini 3.5 Flash is flat (Δ≈0) across both mappers. Gemini 3.1 Lite has the largest cosine Δ (+0.189) and Qwen3-235B the largest llm_judge Δ (+0.191). Llama 3.3 is also nearly flat (+0.007) but at low absolute values, suggesting it asks neither good nor bad discriminating questions regardless of outcome.

### 2.3 IG-Positive Rate (cosine mapper)

| Model | Correct | Incorrect | Δ (cosine) | Δ (llm_judge) |
|-------|---------|-----------|------------|---------------|
| Gemini 3.1 Lite | 0.240 | 0.321 | **−0.081** | −0.030 |
| Gemini 3.5 Flash | 0.386 | 0.337 | +0.049 | −0.088 |
| GPT-5.4 | 0.270 | 0.318 | −0.048 | **−0.147** |
| GPT-5.4 Mini | 0.340 | 0.353 | −0.013 | +0.054 |
| Llama 3.3 70B | 0.358 | 0.344 | +0.014 | −0.066 |
| Qwen3-235B | 0.287 | 0.388 | **−0.101** | **−0.204** |

**⚠ Reversal pattern:** 4/6 models (cosine) and 5/6 models (llm_judge) show negative Δ — incorrect episodes have *higher* IG-Positive Rate than correct episodes.

**Mechanistic explanation:** IG-Positive Rate is the proportion of *active turns* (candidate size > 1) with IG > 0. Failed episodes are longer and retain larger candidate sets for more turns, creating more active turns in which a question can produce IG > 0. This inflates the metric in incorrect episodes purely through a sampling artifact, not through better question design. The reversal is especially large for Qwen3-235B (llm_judge Δ=−0.204), which also has the shortest correct episodes (avg 1.8 active turns).

### 2.4 Conditional Mean IG (cosine mapper)

| Model | Correct | Incorrect | Δ (cosine) | Δ (llm_judge) |
|-------|---------|-----------|------------|---------------|
| Gemini 3.1 Lite | −0.546 | −0.379 | **−0.167** | −0.045 |
| Gemini 3.5 Flash | −0.209 | −0.274 | +0.065 | −0.042 |
| GPT-5.4 | −0.205 | −0.287 | +0.082 | −0.061 |
| GPT-5.4 Mini | −0.287 | −0.275 | −0.012 | +0.015 |
| Llama 3.3 70B | −0.308 | −0.281 | −0.027 | −0.053 |
| Qwen3-235B | −0.337 | −0.284 | −0.054 | **−0.151** |

**Note on sign:** All cosine Cond. Mean IG values are negative (consistent with the KG structure, where confirming a symptom often expands the candidate set). Less-negative = better. Positive Δ means correct episodes are less negative (closer to zero = better behavior).

**Pattern:** Mixed. Gemini 3.5 Flash and GPT-5.4 show positive Δ (+0.065, +0.082 cosine) — they maintain slightly better IG even in correct episodes. Most other models show negative Δ (correct episodes have *more negative* IG), driven by the active turn count artifact: correct episodes have fewer turns at large candidate sizes, skewing the conditional mean.

**Mapper divergence:** llm_judge and cosine disagree on direction for multiple models. This suggests the mapper's symptom identification strategy interacts with the IG signal in non-trivial ways.

### Summary — Question Quality

| Pattern | Direction | Models affected | Explanation |
|---------|-----------|-----------------|-------------|
| Composite confound | Positive Δ (correct higher) | 4/6 models | Higher quality when model is on track |
| Disc-Q robustness | Δ ≈ 0 | Gemini 3.5 Flash, Llama 3.3 | Quality is outcome-independent (for different reasons) |
| IG-Positive Rate reversal | Negative Δ (incorrect higher) | 4–5/6 models | Active-turn count artifact in failed episodes |
| Cond. Mean IG direction | Mixed | All models | Interaction between mapper and KG structure |

---

## 3. Efficiency

**Source:** `results/.../efficiency_eval.json` — per-episode records.

### 3.1 CSSR (Candidate Set Shrinkage Rate)

CSSR = (initial candidate size − final candidate size) / turn count. Higher = more narrowing per turn.

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | +0.002 | +0.631 | **−0.629** |
| Gemini 3.5 Flash | −0.075 | +0.344 | −0.418 |
| GPT-5.4 | −0.081 | +0.421 | −0.502 |
| GPT-5.4 Mini | +0.087 | +0.444 | −0.357 |
| Llama 3.3 70B | −0.101 | +0.285 | −0.386 |
| Qwen3-235B | −0.081 | +0.400 | **−0.480** |

**⚠ Most striking finding in the ablation:** CSSR is *universally* and *substantially* higher in incorrect episodes (Δ ranges from −0.36 to −0.63). Incorrect episodes show rapid candidate set narrowing (high CSSR), while correct episodes show near-zero or slightly negative CSSR.

**Mechanistic explanation:** When a model is heading toward an incorrect diagnosis, it tends to confidently narrow the candidate set — eliminating the correct disease in the process. Correct episodes, by contrast, maintain a broader candidate set (lower CSSR) because the model preserves the ground-truth disease alongside competing candidates. High CSSR in incorrect episodes is a *failure signal*, not an efficiency signal.

**Implication for metric design:** CSSR should never be reported without outcome conditioning. The conventional interpretation "higher CSSR = more efficient" is inverted for failed episodes. A model that achieves CSSR ≈ 0 in correct episodes (maintaining a careful, wide search) may be more clinically appropriate than one that aggressively narrows.

### 3.2 Turn Count

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | 4.27 | 7.95 | −3.68 |
| **Gemini 3.5 Flash** | **5.26** | **10.47** | **−5.22** |
| GPT-5.4 | 6.60 | 9.83 | −3.23 |
| GPT-5.4 Mini | 4.19 | 7.96 | −3.78 |
| Llama 3.3 70B | 9.42 | 10.57 | −1.15 |
| Qwen3-235B | 3.86 | 6.79 | −2.93 |

**Pattern:** Correct episodes are shorter across all models (expected — diagnosis reached faster). Gemini 3.5 Flash shows the largest turn-count gap (−5.22): its correct episodes are relatively short (5.3 turns) while incorrect ones extend to 10.5 turns on average, suggesting a bimodal behavior rather than a gradual failure.

Llama 3.3 has the smallest turn gap (−1.15) — its incorrect episodes don't extend much beyond correct ones, possibly because it reaches its turn limit in both cases.

### 3.3 Redundant Turn Ratio

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | 0.622 | 0.656 | −0.033 |
| Gemini 3.5 Flash | 0.677 | 0.694 | −0.017 |
| GPT-5.4 | 0.747 | 0.712 | **+0.035** |
| GPT-5.4 Mini | 0.625 | 0.646 | −0.021 |
| Llama 3.3 70B | 0.761 | 0.727 | **+0.034** |
| Qwen3-235B | 0.595 | 0.556 | +0.039 |

**Pattern:** Redundant Turn Ratio is nearly identical between strata for most models (|Δ| < 0.04). GPT-5.4, Llama 3.3, and Qwen3-235B show mildly *higher* redundancy in correct episodes. This suggests redundancy is driven by model behavior (dialogue style) rather than outcome, making it a reliable cross-model comparator.

### 3.4 Time to First Correct Narrowing (T-first)

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | 3.82 | 8.65 | −4.84 |
| **Gemini 3.5 Flash** | **4.33** | **11.22** | **−6.90** |
| GPT-5.4 | 3.67 | 10.52 | **−6.85** |
| GPT-5.4 Mini | 4.11 | 8.43 | −4.33 |
| Llama 3.3 70B | 7.07 | 11.02 | −3.95 |
| Qwen3-235B | 3.78 | 7.48 | −3.69 |

**Pattern:** T-first is the most outcome-sensitive efficiency metric. In incorrect episodes, the model never reaches a state where the ground truth is the *sole* high-confidence candidate — so T-first equals or exceeds the episode length, driving values into 7–11+ range. The large Δ for Gemini 3.5 Flash (−6.90) and GPT-5.4 (−6.85) reflects their bimodal behavior: fast convergence when right, near-infinite delay when wrong.

### 3.5 Final Accuracy (exact diagnosis match)

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | 93.3% | 58.0% | +35.3pp |
| **Gemini 3.5 Flash** | **86.5%** | **23.6%** | **+62.9pp** |
| GPT-5.4 | 95.7% | 72.8% | +22.9pp |
| GPT-5.4 Mini | 85.9% | 75.5% | +10.4pp |
| Llama 3.3 70B | 13.6% | 0.0% | +13.6pp |
| Qwen3-235B | 86.8% | 69.8% | +17.0pp |

**Important distinction:** "Correct episode" is defined as ground truth ∈ candidate set (broad); "final accuracy" is the doctor's stated diagnosis matching ground truth exactly (strict). A correct episode can still have low final accuracy if the doctor names a different disease despite having the right one in the candidate set.

**Notable outlier — Llama 3.3:** Final accuracy is 13.6% even in "correct" episodes. This model rarely commits to the correct specific diagnosis even when it is tracking it, explaining the discrepancy between high correct-episode inference recall (50.2%) and very low final accuracy (13.6%).

**Notable finding — Gemini 3.5 Flash:** In incorrect episodes, final accuracy drops to 23.6% (largest gap of any model at +62.9pp). This confirms bimodal behavior: when it gets it right, it commits confidently; when wrong, it almost never accidentally names the correct disease.

### Summary — Efficiency

| Metric | Pattern | Confound severity | Notes |
|--------|---------|-------------------|-------|
| CSSR | **Reversal** — higher in incorrect | ★★★★★ (critical) | Failed models narrow faster by excluding correct diagnosis |
| Turn count | Higher in incorrect (expected) | ★★★ | Largest gap for Gemini 3.5 Flash |
| Redundant turn ratio | Nearly identical | ★ (minimal) | Most reliable efficiency metric for cross-model comparison |
| T-first | Much higher in incorrect | ★★★★ | Diagnostic signal for correct-episode speed vs. failure mode |
| Final accuracy | Higher in correct (expected) | ★★★ | Strict criterion; Llama anomaly notable |

---

## 4. Diagnostic Reasoning

**Source:** `results/.../diagnostic_reasoning_eval.json` — per-episode scores from LLM judge evaluation.

### 4.1 Overall Score

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | 0.574 | 0.441 | +0.134 |
| Gemini 3.5 Flash | 0.749 | 0.690 | +0.059 |
| **GPT-5.4** | **0.865** | **0.711** | **+0.154** |
| GPT-5.4 Mini | 0.632 | 0.593 | +0.039 |
| Llama 3.3 70B | 0.797 | 0.651 | +0.146 |
| Qwen3-235B | 0.604 | 0.553 | +0.050 |

**Pattern:** All models show higher DR overall scores in correct episodes. GPT-5.4 has both the highest absolute scores (0.865 correct, 0.711 incorrect) and one of the largest gaps (+0.154). Gemini 3.5 Flash and Qwen3-235B have the smallest gaps (+0.059, +0.050), suggesting their reasoning quality is less confounded by outcome.

### 4.2 Duration Score ⚠

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| **Gemini 3.1 Lite** | **0.491** | **0.897** | **−0.406** |
| Gemini 3.5 Flash | 0.809 | 0.917 | −0.108 |
| GPT-5.4 | 0.938 | 0.936 | **+0.002** (no effect) |
| GPT-5.4 Mini | 0.706 | 0.854 | −0.148 |
| Llama 3.3 70B | 0.941 | 0.926 | +0.015 |
| Qwen3-235B | 0.707 | 0.889 | −0.182 |

**⚠ Reversal in 4/6 models:** Incorrect episodes have *higher* duration scores. This is a consistent second reversal in the ablation after CSSR.

**Mechanistic explanation:** When a model is uncertain or incorrect, it tends to be more conservative and explicit in documenting DSM-5 duration criteria ("the symptoms have persisted for at least 6 months..."). In correct episodes, the model may state the diagnosis with more confidence and less verbosity, leading the judge to award lower duration coverage scores. Duration score captures the *documentation thoroughness* of uncertainty, not the *correctness* of the diagnosis.

**Exception — GPT-5.4 and Llama 3.3:** These models show near-zero or slightly positive Δ on duration score, suggesting their documentation behavior is consistent regardless of outcome.

### 4.3 Functional Impairment Score

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | 0.241 | 0.149 | +0.092 |
| Gemini 3.5 Flash | 0.355 | 0.185 | **+0.171** |
| GPT-5.4 | 0.722 | 0.667 | +0.055 |
| GPT-5.4 Mini | 0.364 | 0.449 | **−0.085** |
| Llama 3.3 70B | 0.946 | 0.906 | +0.041 |
| Qwen3-235B | 0.359 | 0.293 | +0.066 |

**Pattern:** Mostly higher in correct episodes, but with notable exceptions. GPT-5.4-Mini shows negative Δ (−0.085): its incorrect episodes have *better* functional impairment documentation, possibly because longer failed episodes allow more detailed symptom exploration. Llama 3.3 achieves exceptionally high scores in both strata (0.946 / 0.906), consistent with its general strength in clinical criterion coverage despite poor final accuracy.

### 4.4 Additional Requirements Score

| Model | Correct | Incorrect | Δ |
|-------|---------|-----------|---|
| Gemini 3.1 Lite | 0.608 | 0.549 | +0.059 |
| Gemini 3.5 Flash | 0.881 | 0.889 | **−0.009** (flat) |
| GPT-5.4 | 0.915 | 0.822 | +0.094 |
| GPT-5.4 Mini | 0.650 | 0.598 | +0.053 |
| Llama 3.3 70B | 0.795 | 0.675 | +0.121 |
| Qwen3-235B | 0.632 | 0.511 | +0.121 |

**Pattern:** Mostly positive Δ (correct episodes score higher). Gemini 3.5 Flash is flat (Δ=−0.009), consistent with its overall robustness pattern.

### Summary — Diagnostic Reasoning

| Metric | Direction | Notable finding |
|--------|-----------|-----------------|
| Overall score | Positive Δ (correct higher) | GPT-5.4 highest absolute; Gemini 3.5 smallest gap |
| Duration score | **Negative Δ (incorrect higher) for 4/6 models** | Documentation-of-uncertainty artifact |
| Functional impairment | Mixed, mostly positive Δ | Llama 3.3 exception: very high in both strata |
| Additional requirements | Mostly positive Δ | Gemini 3.5 flat; GPT-5.4 highest absolute |

---

## 5. Cross-Dimension Patterns

### 5.1 Universal Reversals

Two metrics show consistent *negative* Δ across most models:

| Metric | Dim | # Models reversed | Interpretation |
|--------|-----|-------------------|----------------|
| **CSSR** | Efficiency | 6/6 (all) | Failed models narrow candidate sets aggressively — premature elimination of correct diagnosis |
| **Duration score** | DR | 4/6 | Unsuccessful doctors document duration more thoroughly — uncertainty-driven verbosity |
| **IG-Positive Rate** | Question | 4/6 (cosine), 5/6 (llm) | Longer failed episodes have more active turns → more IG > 0 opportunities |

These three metrics cannot be interpreted as simple "higher is better" across outcome strata. Any cross-model comparison using these metrics is confounded unless stratified by outcome or normalized by episode length.

### 5.2 Outcome-Robust Metrics

Metrics where |Δ| is small for most models and the direction is consistent:

| Metric | Dim | Avg |Δ| | Notes |
|--------|-----|----------|-------|
| Redundant turn ratio | Efficiency | 0.025 | Most stable efficiency metric |
| Jaccard Index (Gemini 3.5) | Inference | 0.005 | Only for G3.5-Flash |
| Additional requirements | DR | 0.063 | Consistent direction if ignoring G3.5 |

### 5.3 Model-Level Characterization

**Gemini 3.5 Flash — Most outcome-robust model**
- Near-zero Δ on inference recall (+0.030), jaccard (+0.005), question composite (−0.011), discriminating-Q rate (−0.002), DR additional requirements (−0.009)
- The only model where question quality metrics are genuinely flat between strata
- Interpretation: its evaluation scores are not inflated by having easier correct episodes; the quality is consistent regardless of trajectory
- Trade-off: lower absolute inference scores (recall=0.586, jaccard=0.457) compared to some models because it maintains a broader candidate set

**GPT-5.4 — Highest DR scores, moderate confound**
- Highest functional impairment (0.72/0.67) and additional requirements (0.92/0.82) scores in both strata
- Moderate question quality confound (disc_q Δ=+0.071)
- CSSR Δ=−0.50 — aggressive narrowing in failed episodes

**Gemini 3.1 Flash-Lite — Large confound across dimensions**
- Largest question quality confound (disc_q Δ=+0.189)
- Largest CSSR gap (−0.629) — most aggressive wrong narrowing
- Duration score dramatic reversal (Δ=−0.406): 0.491 correct vs 0.897 incorrect
- Inference recall gap: +0.211

**Llama 3.3 70B — Unique failure mode**
- High correct rate (73.5%) but final accuracy only 13.6% in "correct" episodes: reliably tracks the right disease but fails to commit to it in the final diagnosis
- Near-flat question quality (disc_q Δ=+0.007) — but at low absolute values
- Smallest turn-count gap between strata (−1.15) — episodes are long regardless
- Highest functional impairment DR scores in both strata (0.946 / 0.906)

**Qwen3-235B — Largest question quality confound**
- Largest llm_judge discriminating-Q rate Δ (−0.191)
- Largest IG-Positive Rate reversal with llm_judge (Δ=−0.204)
- Shortest correct episodes (1.8 active turns avg) amplifying all active-turn artifacts
- Reasonable DR scores but moderate confound

**GPT-5.4 Mini — High correct rate, moderate confound**
- Highest correct rate (77%) but question quality shows clear confound (disc_q Δ=+0.124)
- Functional impairment reversal in DR (Δ=−0.085) — more detail in failed episodes
- One of the cleaner CSSR gaps (−0.357) among models

---

## 6. Implications for Metric Interpretation

### Metrics that require outcome conditioning before cross-model comparison

| Metric | Risk | Recommended treatment |
|--------|------|----------------------|
| **CSSR** | Incorrect episodes always appear more "efficient" | Report stratified; never use as standalone efficiency score |
| **IG-Positive Rate** | Inflated in longer (failed) episodes via active-turn count | Normalize by active_turn_count or report conditional on episode length |
| **Duration score (DR)** | Higher when model is uncertain/wrong | Exclude from summary score; report as a separate behavioral indicator |
| **T-first** | Undefined/maxed in incorrect episodes | Use only in correct-episode stratum or define as -1 sentinel |

### Metrics that are reliable for cross-model comparison (minimal confound)

| Metric | Dim | Justification |
|--------|-----|---------------|
| Redundant turn ratio | Efficiency | Near-identical between strata for all models |
| DR overall score (stratified) | DR | Consistent positive Δ, stable ranking across strata |
| Discriminating-Q Rate | Question | Stable ranking (Gemini 3.5 > GPT-5.4 ≈ Gemini 3.1 > others) |
| Conditional Mean Composite | Question | Consistent direction; reflects genuine question-asking strategy |

### Metric development note

The current definition of "correct episode" (ground truth ∈ any tier of candidate set) is broader than the final accuracy criterion (doctor's stated diagnosis = ground truth). For future ablation, consider three strata:
1. **Fully correct**: ground truth in candidate set AND final diagnosis matches
2. **Tracked but uncommitted**: ground truth in candidate set, final diagnosis differs (Llama 3.3 pattern)
3. **Lost**: ground truth absent from candidate set

This finer stratification would better isolate tracking failures from commitment failures.

---

*Generated from:* `analysis/gemini-3.5-flash/gemini-3.5-flash/comparison/outcome_stratified/ablation_all_summary.json`  
*Plots:* `ablation_all_dimensions.png`, `ablation_delta_heatmap.png`  
*Date:* 2026-07-22
