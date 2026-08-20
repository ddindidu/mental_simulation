# Case D008_2 — gpt-5.4-mini-2026-03-17

**Category axis:** Classification 2: low_inference_low_question

- Ground truth disease: `D008`
- Final diagnosis: Bipolar I Disorder
- Correct: True
- Closed at patient turn: 2

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.778 | 0.900 | low |
| Recall | 0.311 | 0.500 | low |
| Inference quality (jaccard) | 0.267 | 0.426 | low |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | During this time, have you had any hallucinations, such as hearing or seeing things that others do not, or beliefs that others said were clearly untrue? | 0.00 | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I’m Dr. AI. What brings you in today?

**Patient**: For the past 10 months, I've been experiencing this incredibly high, euphoric mood and just overflowing energy, like I'm completely unstoppable! But at the same time, I've been getting extremely irritable and furious over the smallest little things. It's this weird mix of feeling absolutely amazing but also snapping at everyone.

> **Judge (symptom extraction)** — confirmed: S033 Elevated_Irritable_Mood, S034 Increased_Activity, S060 Irritability
> denied: (none)
> - S033 Elevated_Irritable_Mood: The patient reports experiencing an abnormally elevated, euphoric mood and becoming extremely irritable for the past 10 months.
> - S034 Increased_Activity: The patient describes experiencing overflowing energy.
> - S060 Irritability: The patient reports becoming extremely irritable and angry over minor things, which indicates reacting sharply to minor stimuli.

> Doctor's inference — candidates: Bipolar I Disorder, Bipolar I Disorder with Psychotic Features
> Previously there were no candidates provided, but the new history strongly suggests a manic syndrome: 10 months of persistently elevated/euphoric mood, increased energy, and marked irritability. This makes depressive, anxiety, and trauma-related diagnoses less likely at this point. Psychotic features cannot yet be confirmed or excluded, so the current candidates are Bipolar I Disorder and Bipolar I Disorder with Psychotic Features.

> **Judge (inference scoring)** — predicted: D008, D010
> reference (truth) set: D006, D008, D009, D010, D011
> TP=2 FP=0 FN=3 | precision=1.00 recall=0.40 accuracy=0.00 jaccard=0.40 weighted_recall=0.50

**Doctor**: During this time, have you had any hallucinations, such as hearing or seeing things that others do not, or beliefs that others said were clearly untrue?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: No, I haven't experienced anything like that at all. I haven't seen or heard things that aren't actually there, nor have I held any beliefs that others found untrue.

> **Judge (symptom extraction)** — confirmed: S033 Elevated_Irritable_Mood, S034 Increased_Activity, S060 Irritability
> denied: (none)
> - S033 Elevated_Irritable_Mood: The patient reports experiencing an 'incredibly high, euphoric mood' and feeling 'absolutely amazing' alongside being 'extremely irritable.'
> - S034 Increased_Activity: The patient describes having 'overflowing energy, like I'm completely unstoppable.'
> - S060 Irritability: The patient reports 'getting extremely irritable and furious over the smallest little things' and 'snapping at everyone.'

> Doctor's inference (final) — candidates: Bipolar I Disorder
> Previously the candidates were [Bipolar I Disorder, Bipolar I Disorder with Psychotic Features], but the patient now denies hallucinations and delusions, so psychotic features are not supported. The remaining candidate is Bipolar I Disorder, given the prolonged elevated/euphoric mood, increased energy, and irritability.

> **Judge (inference scoring)** — predicted: D008
> reference (truth) set: D006, D008, D009, D010, D011
> TP=1 FP=0 FN=4 | precision=1.00 recall=0.20 accuracy=0.00 jaccard=0.20 weighted_recall=0.33
