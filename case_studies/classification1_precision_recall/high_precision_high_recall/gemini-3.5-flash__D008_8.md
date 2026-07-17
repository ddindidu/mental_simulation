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

> Doctor's inference — candidates: Bipolar I Disorder, Bipolar II Disorder, Bipolar I Disorder with Psychotic Features, Schizoaffective Disorder (Bipolar Type)
> The patient describes a 19-month history of overwhelming surges of energy and extreme mood swings, shifting between feeling 'high' and intensely irritable. This presentation is highly suggestive of a bipolar spectrum disorder. I need to differentiate between Bipolar I, Bipolar II, Bipolar I with Psychotic Features, and Schizoaffective Disorder (Bipolar Type) by exploring the severity and duration of these 'high' episodes, the presence of depressive episodes, and any potential psychotic symptoms.

**Doctor**: During those times when you feel incredibly high or on top of the world, has this ever caused major disruptions in your daily life or work, or have you ever needed to be hospitalized because of it?

**Patient**: Yes, these high periods have caused major disruptions over the past year and seven months, especially since my reckless spending and foolish business investments have put me in severe financial distress. However, I have never been hospitalized because of it.

> Doctor's inference — candidates: Bipolar I Disorder, Bipolar II Disorder, Bipolar I Disorder with Psychotic Features, Schizoaffective Disorder (Bipolar Type)
> The patient describes high-energy phases causing major life disruptions (reckless spending, financial distress) over the past 19 months, which suggests manic episodes (pointing towards Bipolar I) rather than hypomanic episodes (Bipolar II). However, both remain candidates. I need to investigate the presence of psychotic symptoms (hallucinations, delusions) during these high periods and during periods of normal mood to rule in/out Bipolar I with Psychotic Features and Schizoaffective Disorder (Bipolar Type).

**Doctor**: During these high periods, or even when your mood feels normal, have you ever heard voices, seen things others couldn't, or had strong beliefs that other people found highly unusual?

**Patient**: No, I've never heard any voices or seen things that weren't really there. I also haven't held any unusual beliefs that other people found strange.

> Doctor's inference — candidates: Bipolar I Disorder, Bipolar II Disorder
> The patient denied any history of psychotic symptoms (hallucinations or delusions), allowing us to rule out Schizoaffective Disorder (Bipolar Type) and Bipolar I Disorder with Psychotic Features. The remaining candidates are Bipolar I Disorder and Bipolar II Disorder, as the patient describes episodes of elevated mood and energy with functional impairment (reckless spending), but we need to further clarify the severity of these manic/hypomanic episodes and whether major depressive episodes have occurred.

**Doctor**: Have you ever experienced periods lasting two weeks or more where you felt consistently sad, down, or lost interest in almost all of your usual activities?

**Patient**: No, I haven't really experienced anything like that. I don't recall ever feeling consistently sad or losing interest in my usual activities for weeks at a time.

> Doctor's inference (final) — candidates: Bipolar I Disorder
> Previously, the candidates were Bipolar I Disorder and Bipolar II Disorder. Bipolar II Disorder is now ruled out because the patient has never experienced a major depressive episode, which is a required criterion for Bipolar II. Furthermore, the patient's high periods have caused marked impairment (major disruptions and severe financial distress due to reckless spending), which meets the criteria for a manic episode rather than a hypomanic episode, confirming a diagnosis of Bipolar I Disorder.
