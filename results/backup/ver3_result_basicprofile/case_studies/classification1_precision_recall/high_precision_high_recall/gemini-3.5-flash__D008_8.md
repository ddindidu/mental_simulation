# Case D008_8 — gemini-3.5-flash

**Category axis:** Classification 1: high_precision_high_recall

- Ground truth disease: `D008`
- Final diagnosis: Bipolar I Disorder
- Correct: True
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 1.000 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | During those times when you feel incredibly high or on top of the world, has this ever caused major disruptions in your daily life or work, or have you ever needed to be hospitalized because of it? | 0.00 | 0 | 0 | 0.10 |
| 2 | During these high periods, or even when your mood feels normal, have you ever heard voices, seen things others couldn't, or had strong beliefs that other people found highly unusual? | 0.00 | 0 | 0 | 0.10 |
| 3 | Have you ever experienced periods lasting two weeks or more where you felt consistently sad, down, or lost interest in almost all of your usual activities? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, welcome. What brings you in to see me today?

**Patient**: I'm here because for the last year and seven months, I've been dealing with this overwhelming surge of energy and extreme mood swings. I keep shifting between feeling incredibly high and on top of the world, to being intensely irritable and angry at the smallest things. It's just exhausting because my mood is constantly bouncing back and forth like this.

> **Judge (symptom extraction)** — confirmed: S033 Elevated_Irritable_Mood, S034 Increased_Activity
> denied: (none)
> - S033 Elevated_Irritable_Mood: The patient describes extreme mood swings, shifting between feeling 'incredibly high and on top of the world' (elevated mood) and being 'intensely irritable and angry' (irritable mood).
> - S034 Increased_Activity: The patient explicitly reports experiencing an 'overwhelming surge of energy' over the last year and seven months.

> Doctor's inference — candidates: Bipolar I Disorder, Bipolar II Disorder, Bipolar I Disorder with Psychotic Features, Schizoaffective Disorder (Bipolar Type)
> The patient describes a 19-month history of overwhelming surges of energy and extreme mood swings, shifting between feeling 'high' and intensely irritable. This presentation is highly suggestive of a bipolar spectrum disorder. I need to differentiate between Bipolar I, Bipolar II, Bipolar I with Psychotic Features, and Schizoaffective Disorder (Bipolar Type) by exploring the severity and duration of these 'high' episodes, the presence of depressive episodes, and any potential psychotic symptoms.

> **Judge (inference scoring)** — predicted: D006, D008, D009, D010
> reference (truth) set: D006, D008, D009, D010
> TP=4 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: During those times when you feel incredibly high or on top of the world, has this ever caused major disruptions in your daily life or work, or have you ever needed to be hospitalized because of it?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.3333 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: Yes, these high periods have caused major disruptions over the past year and seven months, especially since my reckless spending and foolish business investments have put me in severe financial distress. However, I have never been hospitalized because of it.

> **Judge (symptom extraction)** — confirmed: S033 Elevated_Irritable_Mood, S041 Painful_Consequence_Behavior
> denied: (none)
> - S033 Elevated_Irritable_Mood: The patient directly references experiencing 'high periods' that have caused major disruptions.
> - S041 Painful_Consequence_Behavior: The patient explicitly reports engaging in reckless spending and foolish business investments resulting in financial distress.

> Doctor's inference — candidates: Bipolar I Disorder, Bipolar II Disorder, Bipolar I Disorder with Psychotic Features, Schizoaffective Disorder (Bipolar Type)
> The patient describes high-energy phases causing major life disruptions (reckless spending, financial distress) over the past 19 months, which suggests manic episodes (pointing towards Bipolar I) rather than hypomanic episodes (Bipolar II). However, both remain candidates. I need to investigate the presence of psychotic symptoms (hallucinations, delusions) during these high periods and during periods of normal mood to rule in/out Bipolar I with Psychotic Features and Schizoaffective Disorder (Bipolar Type).

> **Judge (inference scoring)** — predicted: D006, D008, D009, D010
> reference (truth) set: D006, D008, D009, D010
> TP=4 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: During these high periods, or even when your mood feels normal, have you ever heard voices, seen things others couldn't, or had strong beliefs that other people found highly unusual?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.3333 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, I've never heard any voices or seen things that weren't really there. I also haven't held any unusual beliefs that other people found strange.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S019 Delusions, S020 Hallucinations
> - S019 Delusions: The patient explicitly denies holding any unusual beliefs that other people found strange, which corresponds to delusions.
> - S020 Hallucinations: The patient explicitly denies hearing voices or seeing things that weren't really there, which corresponds to hallucinations.

> Doctor's inference — candidates: Bipolar I Disorder, Bipolar II Disorder
> The patient denied any history of psychotic symptoms (hallucinations or delusions), allowing us to rule out Schizoaffective Disorder (Bipolar Type) and Bipolar I Disorder with Psychotic Features. The remaining candidates are Bipolar I Disorder and Bipolar II Disorder, as the patient describes episodes of elevated mood and energy with functional impairment (reckless spending), but we need to further clarify the severity of these manic/hypomanic episodes and whether major depressive episodes have occurred.

> **Judge (inference scoring)** — predicted: D008, D009
> reference (truth) set: D008, D009
> TP=2 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Have you ever experienced periods lasting two weeks or more where you felt consistently sad, down, or lost interest in almost all of your usual activities?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, I haven't really experienced anything like that. I don't recall ever feeling consistently sad or losing interest in my usual activities for weeks at a time.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S024 Depressed_Mood, S025 Loss_of_Interest
> - S024 Depressed_Mood: The patient explicitly denies experiencing persistent sadness.
> - S025 Loss_of_Interest: The patient explicitly denies experiencing a loss of interest in activities.

> Doctor's inference (final) — candidates: Bipolar I Disorder
> Previously, the candidates were Bipolar I Disorder and Bipolar II Disorder. Bipolar II Disorder is now ruled out because the patient has never experienced a major depressive episode, which is a required criterion for Bipolar II. Furthermore, the patient's high periods have caused marked impairment (major disruptions and severe financial distress due to reckless spending), which meets the criteria for a manic episode rather than a hypomanic episode, confirming a diagnosis of Bipolar I Disorder.

> **Judge (inference scoring)** — predicted: D008
> reference (truth) set: D008
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
