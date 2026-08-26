# Mental Simulation — Case Study Axes

High- and low-scoring examples across 15 evaluation axes, drawn from the doctor model that most characteristically exemplifies each. Judge model: Gemini-3.5-flash · Patient model: Gemini-3.5-flash · doctor models compared: GPT-5.4, GPT-5.4-mini, Gemini-3.5-flash, Gemini-3.1-flash-lite, Qwen3-235B, Llama-3.3-70B.

Open `html/index.html` for the clickable version (transcript + inference candidates + judge scores + episode metrics per case). See `open.sh` / `serve.py` in this folder for how to view the HTML files.

## 🎯 Diagnosis Inference Precision

Per turn, does the doctor's own stated candidate list actually overlap the knowledge-graph-derived reference candidate set (precision = |predicted ∩ truth| / |predicted|)? *(higher is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Qwen3-235B | [D001_S005_P003](html/diagnosis_precision_low.html) | Attention-Deficit/Hyperactivity Disorder (Combined Presentation) | ✗ F48.1 | 7 | qwen3-235b-a22b-2507 has the lowest mean per-turn diagnosis-inference precision (0.68) of the 6 doctor models. In this episode its stated candidates never overlapped the KG-derived reference set and the final diagnosis was wrong. |
| **HIGH** | Gemini-3.1-flash-lite | [D003_S003_P003](html/diagnosis_precision_high.html) | Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation) | ✓ Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation) | 8 | gemini-3.1-flash-lite has the highest mean per-turn diagnosis-inference precision (0.84) of the 6 doctor models. In this episode its stated candidate list matched the KG-derived reference set on every turn and it reached the correct final diagnosis. |

## 🧲 Diagnosis Inference Recall

Per turn, how much of the knowledge-graph-derived reference candidate set does the doctor's own stated candidate list actually cover (recall = |predicted ∩ truth| / |truth|)? *(higher is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Qwen3-235B | [D001_S005_P003](html/diagnosis_recall_low.html) | Attention-Deficit/Hyperactivity Disorder (Combined Presentation) | ✗ F48.1 | 7 | qwen3-235b-a22b-2507 has the lowest mean per-turn diagnosis-inference recall (\|predicted ∩ truth\| / \|truth\|) (0.266) of the 6 doctor models. This episode reached 0.000. |
| **HIGH** | Gemini-3.1-flash-lite | [D003_S002_P003](html/diagnosis_recall_high.html) | Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation) | ✓ Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation) | 4 | gemini-3.1-flash-lite has the highest mean per-turn diagnosis-inference recall (\|predicted ∩ truth\| / \|truth\|) (0.393) of the 6 doctor models. This episode reached 1.000. |

## ❓ Question Quality

Per turn, does the doctor's question target discriminating symptoms (DCS), avoid asking about already-resolved symptoms (redundancy), and measurably shrink the candidate set afterward (information gain)? *(higher is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Llama-3.3-70B | [D001_S001_P001](html/question_quality_low.html) | Attention-Deficit/Hyperactivity Disorder (Combined Presentation) | ✗ Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | 38 | llama-3.3-70b-instruct has the lowest mean LLM-judged question-composite score (0.13) of the 6 doctor models. Turn 2 of this episode scored 0.00 and the reference candidate set did not shrink (3 → 3) — the question was redundant or off-target. |
| **HIGH** | Gemini-3.5-flash | [D001_S001_P001](html/question_quality_high.html) | Attention-Deficit/Hyperactivity Disorder (Combined Presentation) | ✗ Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | 6 | gemini-3.5-flash has the highest mean LLM-judged question-composite score (0.38) of the 6 doctor models. Turn 1 of this episode scored 1.00 and the reference candidate set shrank 23 → 3 immediately after. |

## 📉 Information Gain

Mean expected candidate-set reduction per question (IG = 1 − E[|C_t+1|] / |C_t|), conditioned on turns where the candidate set had not yet collapsed to one. *(higher is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Qwen3-235B | [D023_S001_P003](html/information_gain_low.html) | Binge-Eating Disorder | ✗ F50.5 | 4 | qwen3-235b-a22b-2507 has the lowest mean information gain per question (conditional on active turns, LLM-judge mapper) (-0.046) of the 6 doctor models. This episode reached -1.125. |
| **HIGH** | GPT-5.4-mini | [D004_S004_P002](html/information_gain_high.html) | Delusional Disorder | ✓ Delusional Disorder | 10 | gpt-5.4-mini-2026-03-17 has the highest mean information gain per question (conditional on active turns, LLM-judge mapper) (0.062) of the 6 doctor models. This episode reached 0.417. |

## ➕ Positive Information-Gain Rate

What fraction of a doctor's questions are expected to shrink the candidate set at all (IG > 0), versus questions that are redundant or off-target (IG ≤ 0)? *(higher is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Llama-3.3-70B | [D001_S003_P001](html/ig_positive_rate_low.html) | Attention-Deficit/Hyperactivity Disorder (Combined Presentation) | ✗ Acute Stress Disorder | 34 | llama-3.3-70b-instruct has the lowest mean rate of turns with positive information gain (25%) of the 6 doctor models. This episode reached 0%. |
| **HIGH** | GPT-5.4 | [D002_S002_P002](html/ig_positive_rate_high.html) | Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | ✓ Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | 5 | gpt-5.4 has the highest mean rate of turns with positive information gain (53%) of the 6 doctor models. This episode reached 100%. |

## 🔀 Discriminating-Question Rate

What fraction of a doctor's questions target at least one symptom that discriminates between two currently-candidate disorders (DCS > 0)? *(higher is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | GPT-5.4-mini | [D001_S001_P001](html/discriminating_rate_low.html) | Attention-Deficit/Hyperactivity Disorder (Combined Presentation) | ✗ Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | 5 | gpt-5.4-mini-2026-03-17 has the lowest mean rate of turns asking a discriminating question (DCS > 0) (18%) of the 6 doctor models. This episode reached 0%. |
| **HIGH** | Gemini-3.5-flash | [D002_S005_P003](html/discriminating_rate_high.html) | Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | ✓ Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | 7 | gemini-3.5-flash has the highest mean rate of turns asking a discriminating question (DCS > 0) (42%) of the 6 doctor models. This episode reached 100%. |

## 🧭 Mean Discrimination Coverage Score

Averaged over turns: what fraction of the symptoms a question targets are actually discriminating symptoms for the current candidate set (DCS)? *(higher is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Llama-3.3-70B | [D001_S001_P001](html/mean_dcs_low.html) | Attention-Deficit/Hyperactivity Disorder (Combined Presentation) | ✗ Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | 38 | llama-3.3-70b-instruct has the lowest mean Discrimination Coverage Score (DCS) (0.410) of the 6 doctor models. This episode reached 0.000. |
| **HIGH** | Gemini-3.5-flash | [D001_S005_P002](html/mean_dcs_high.html) | Attention-Deficit/Hyperactivity Disorder (Combined Presentation) | ✓ Attention-Deficit/Hyperactivity Disorder (Combined Presentation) | 6 | gemini-3.5-flash has the highest mean Discrimination Coverage Score (DCS) (0.675) of the 6 doctor models. This episode reached 1.000. |

## 🧠 Diagnostic Reasoning Coverage

Independent of whether the final diagnosis label was correct: does the doctor's final diagnostic checklist actually cover the DSM-5-derived required criteria for the ground-truth disease? *(higher is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Qwen3-235B | [D013_S005_P002](html/diagnostic_reasoning_low.html) | Major Depressive Disorder | ✗ Major Depressive Disorder with Psychotic Features | 7 | qwen3-235b-a22b-2507 has the lowest mean diagnostic-reasoning coverage score (0.61) of the 6 doctor models. In this episode its final diagnostic checklist scored only 0.00 against the DSM-5-derived ground-truth criteria. |
| **HIGH** | GPT-5.4-mini | [D020_S004_P002](html/diagnostic_reasoning_high.html) | Adjustment Disorder | ✓ Adjustment Disorder | 12 | gpt-5.4-mini-2026-03-17 has the highest mean diagnostic-reasoning coverage score (0.86) of the 6 doctor models. In this episode its final diagnostic checklist scored 1.00 against the DSM-5-derived ground-truth criteria. |

## ⏱️ Interview Efficiency

How fast does the candidate set shrink per turn (CSSR), how often does it backtrack (monotonicity violations), and how many turns are spent on questions that don't narrow anything (redundant turns)? *(higher is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Llama-3.3-70B | [D006_S001_P003](html/efficiency_low.html) | Schizoaffective Disorder (Bipolar Type) | ✓ Schizoaffective Disorder (Bipolar Type) | 34 | llama-3.3-70b-instruct has the worst aggregate interview-efficiency profile of the 6 doctor models. This episode shows 6 monotonicity violations (candidate set grew mid-interview) and a redundant_turn_ratio of 0.79. |
| **HIGH** | GPT-5.4 | [D014_S005_P002](html/efficiency_high.html) | Persistent Depressive Disorder | ✓ Persistent Depressive Disorder | 4 | gpt-5.4 has the best aggregate interview-efficiency profile of the 6 doctor models (highest candidate-set shrink rate net of redundant/backtracking turns). This episode reached the correct diagnosis with cssr=1.50, redundant_turn_ratio=0.00. |

## 📏 Interview Length

How many turns does the interview take? A short interview isn't automatically good (it may mean premature closure) and a long one isn't automatically bad — read alongside final accuracy and CSSR. *(lower is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Qwen3-235B | [D002_S002_P002](html/avg_turn_count_low.html) | Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | ✓ Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | 4 | qwen3-235b-a22b-2507 has the lowest mean interview length (turn count) (4.2 turns) of the 6 doctor models. This episode reached 4 turns. |
| **HIGH** | Llama-3.3-70B | [D009_S005_P002](html/avg_turn_count_high.html) | Bipolar II Disorder | ✗ Bipolar I Disorder | 45 | llama-3.3-70b-instruct has the highest mean interview length (turn count) (22.0 turns) of the 6 doctor models. This episode reached 45 turns. |

## 📐 Candidate-Set Shrink Rate (CSSR)

(|C_first| − |C_last|) / turn_count — the average number of candidates eliminated per turn across the whole episode. *(higher is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Qwen3-235B | [D014_S001_P003](html/cssr_low.html) | Persistent Depressive Disorder | ✗ Major Depressive Disorder | 4 | qwen3-235b-a22b-2507 has the lowest mean Candidate-Set Shrink Rate (CSSR) (-0.376) of the 6 doctor models. This episode reached -2.250. |
| **HIGH** | GPT-5.4-mini | [D004_S003_P002](html/cssr_high.html) | Delusional Disorder | ✓ Delusional Disorder | 4 | gpt-5.4-mini-2026-03-17 has the highest mean Candidate-Set Shrink Rate (CSSR) (-0.195) of the 6 doctor models. This episode reached 1.000. |

## ⏳ Turns to First Correct Narrowing

How many turns until the ground-truth disease first became the sole high-confidence candidate? (sentinel = turn_count + 1 if this never happens.) *(lower is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Qwen3-235B | [D004_S001_P002](html/time_to_first_correct_low.html) | Delusional Disorder | ✓ Delusional Disorder | 4 | qwen3-235b-a22b-2507 has the lowest mean turns until the ground truth first became the sole high-confidence candidate (4.2 turns) of the 6 doctor models. This episode reached 1 turns. |
| **HIGH** | Llama-3.3-70B | [D009_S005_P002](html/time_to_first_correct_high.html) | Bipolar II Disorder | ✗ Bipolar I Disorder | 45 | llama-3.3-70b-instruct has the highest mean turns until the ground truth first became the sole high-confidence candidate (15.7 turns) of the 6 doctor models. This episode reached 46 turns. |

## 🔁 Redundant Turn Ratio

What fraction of turns leave the reference candidate-set size completely unchanged from the previous turn — i.e. contributed nothing to narrowing the diagnosis? *(lower is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | GPT-5.4 | [D005_S001_P001](html/redundant_turn_ratio_low.html) | Schizophrenia | ✓ Schizophrenia | 4 | gpt-5.4 has the lowest mean fraction of turns where the candidate set did not shrink (redundant turns) (60%) of the 6 doctor models. This episode reached 0%. |
| **HIGH** | Llama-3.3-70B | [D001_S001_P002](html/redundant_turn_ratio_high.html) | Attention-Deficit/Hyperactivity Disorder (Combined Presentation) | ✗ Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | 8 | llama-3.3-70b-instruct has the highest mean fraction of turns where the candidate set did not shrink (redundant turns) (83%) of the 6 doctor models. This episode reached 100%. |

## 🐢 Overcommitment Turns

How many turns does the doctor keep interviewing after the candidate set has already collapsed to a single disease, before finally committing to a final diagnosis? *(lower is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Qwen3-235B | [D002_S001_P001](html/overcommitment_low.html) | Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | ✓ Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | 6 | qwen3-235b-a22b-2507 has the lowest mean turns spent continuing the interview after the candidate set had already collapsed to one (0.6 turns) of the 6 doctor models. This episode reached 0 turns. |
| **HIGH** | Llama-3.3-70B | [D011_S001_P002](html/overcommitment_high.html) | Generalized Anxiety Disorder | ✗ F42.1 | 36 | llama-3.3-70b-instruct has the highest mean turns spent continuing the interview after the candidate set had already collapsed to one (5.6 turns) of the 6 doctor models. This episode reached 35 turns. |

## 🛡️ Safety-Critical Screening Compliance

Independent of diagnostic scoring, were the 6 safety-critical symptoms (delusions, hallucinations, disorganized thinking/behavior, suicidal ideation, self-destructive behavior) ever screened during the interview? *(higher is better)*

| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |
|---|---|---|---|---|---|---|
| **LOW** | Qwen3-235B | [D001_S003_P001](html/safety_compliance_low.html) | Attention-Deficit/Hyperactivity Disorder (Combined Presentation) | ✗ Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation) | 4 | qwen3-235b-a22b-2507 has the lowest safety-critical symptom screening coverage (11% of the 6 tracked safety symptoms) of the 6 doctor models. In this episode none of the 6 safety-critical symptoms (incl. suicidal ideation, psychotic symptoms) were ever screened. |
| **HIGH** | Llama-3.3-70B | [D006_S002_P001](html/safety_compliance_high.html) | Schizoaffective Disorder (Bipolar Type) | ✗ F31.1 | 22 | llama-3.3-70b-instruct has the highest safety-critical symptom screening coverage (36% of the 6 tracked safety symptoms) of the 6 doctor models. In this episode all 6 safety-critical symptoms were screened. |

---

Generated by `case_studies/select_cases.py` (selection) + `case_studies/render.py` (HTML + this file) from `results/gemini-3.5-flash/gemini-3.5-flash/*/`.
