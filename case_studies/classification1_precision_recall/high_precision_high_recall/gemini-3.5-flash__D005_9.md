# Case D005_9 — gemini-3.5-flash

**Category axis:** Classification 1: high_precision_high_recall

- Ground truth disease: `D005`
- Final diagnosis: Schizophrenia
- Correct: True
- Closed at patient turn: 3

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.833 | 0.500 | high |
| Inference quality (jaccard) | 0.833 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Along with these voices and feelings of being watched, have you experienced any periods where you felt extremely depressed or, on the other hand, unusually high, energetic, or irritable? | 0.00 | 0 | 0 | 0.10 |
| 2 | Could you tell me more about the voices you hear? For example, do they speak in clear words, talk to each other, or comment on what you are doing? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, welcome. What brings you in to see me today?

**Patient**: I'm here because I finally decided I need help with something that's been happening for about a year and seven months. I constantly feel like I'm being watched and monitored, and I keep hearing these voices that no one else can hear. It's just getting to be too much to handle.

> Doctor's inference — candidates: Schizophrenia, Schizoaffective Disorder (Bipolar Type), Schizoaffective Disorder (Depressive Type), Bipolar I Disorder with Psychotic Features, Major Depressive Disorder with Psychotic Features, Delusional Disorder
> The patient reports persecutory beliefs ('constantly feel like I'm being watched and monitored') and auditory hallucinations ('hearing these voices') lasting for approximately 19 months. This presentation suggests a chronic psychotic process. The differential diagnosis includes Schizophrenia, Schizoaffective Disorder (Bipolar or Depressive type), Mood Disorders with Psychotic Features (Bipolar I or MDD with psychotic features), and Delusional Disorder.

**Doctor**: Along with these voices and feelings of being watched, have you experienced any periods where you felt extremely depressed or, on the other hand, unusually high, energetic, or irritable?

**Patient**: No, I haven't really felt that way at all. My mood has been pretty much the same, without those kinds of extreme highs or lows. It's really just the voices and the constant monitoring that are the problem.

> Doctor's inference — candidates: Schizophrenia, Delusional Disorder
> Previously the candidates were ['Schizophrenia', 'Schizoaffective Disorder (Bipolar Type)', 'Schizoaffective Disorder (Depressive Type)', 'Bipolar I Disorder with Psychotic Features', 'Major Depressive Disorder with Psychotic Features', 'Delusional Disorder']. Since the patient denies any significant mood episodes (no extreme highs, lows, or depression), we can rule out Schizoaffective Disorder (both types), Bipolar I Disorder with Psychotic Features, and Major Depressive Disorder with Psychotic Features. This leaves Schizophrenia and Delusional Disorder as the primary candidates.

**Doctor**: Could you tell me more about the voices you hear? For example, do they speak in clear words, talk to each other, or comment on what you are doing?

**Patient**: Yes, they speak very clearly, and it's usually a couple of voices talking about me and commenting on everything I'm doing. It's been happening almost every day for a year and seven months now, and it's really scary because I can't make them stop.

> Doctor's inference (final) — candidates: Schizophrenia
> Previously the candidates were ['Schizophrenia', 'Delusional Disorder']. Based on the patient's description of prominent auditory hallucinations (specifically, multiple voices conversing and commenting on their actions) lasting for 19 months, Delusional Disorder is ruled out, as it does not feature prominent auditory hallucinations of this nature. The absence of significant mood symptoms rules out mood disorders with psychotic features or schizoaffective disorder. Thus, the final diagnosis is Schizophrenia.
