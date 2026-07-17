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

> **Judge (symptom extraction)** — confirmed: S019 Delusions, S020 Hallucinations
> denied: (none)
> - S019 Delusions: The patient reports constantly feeling like they are being watched and monitored, which is indicative of persecutory or referential delusions.
> - S020 Hallucinations: The patient explicitly states they keep hearing voices that no one else can hear, which indicates auditory hallucinations.

> Doctor's inference — candidates: Schizophrenia, Schizoaffective Disorder (Bipolar Type), Schizoaffective Disorder (Depressive Type), Bipolar I Disorder with Psychotic Features, Major Depressive Disorder with Psychotic Features, Delusional Disorder
> The patient reports persecutory beliefs ('constantly feel like I'm being watched and monitored') and auditory hallucinations ('hearing these voices') lasting for approximately 19 months. This presentation suggests a chronic psychotic process. The differential diagnosis includes Schizophrenia, Schizoaffective Disorder (Bipolar or Depressive type), Mood Disorders with Psychotic Features (Bipolar I or MDD with psychotic features), and Delusional Disorder.

> **Judge (inference scoring)** — predicted: D004, D005, D006, D007, D010, D015
> reference (truth) set: D004, D005, D006, D007, D010, D015
> TP=6 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Along with these voices and feelings of being watched, have you experienced any periods where you felt extremely depressed or, on the other hand, unusually high, energetic, or irritable?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.7333 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, I haven't really felt that way at all. My mood has been pretty much the same, without those kinds of extreme highs or lows. It's really just the voices and the constant monitoring that are the problem.

> **Judge (symptom extraction)** — confirmed: S019 Delusions, S020 Hallucinations
> denied: S024 Depressed_Mood, S033 Elevated_Irritable_Mood
> - S019 Delusions: The patient reports experiencing 'constant monitoring', which indicates persecutory or referential delusions.
> - S020 Hallucinations: The patient explicitly mentions hearing 'the voices', which corresponds to auditory hallucinations.
> - S024 Depressed_Mood: The patient denies experiencing 'extreme lows' and states their mood has been pretty much the same.
> - S033 Elevated_Irritable_Mood: The patient denies experiencing 'extreme highs' and states their mood has been pretty much the same.

> Doctor's inference — candidates: Schizophrenia, Delusional Disorder
> Previously the candidates were ['Schizophrenia', 'Schizoaffective Disorder (Bipolar Type)', 'Schizoaffective Disorder (Depressive Type)', 'Bipolar I Disorder with Psychotic Features', 'Major Depressive Disorder with Psychotic Features', 'Delusional Disorder']. Since the patient denies any significant mood episodes (no extreme highs, lows, or depression), we can rule out Schizoaffective Disorder (both types), Bipolar I Disorder with Psychotic Features, and Major Depressive Disorder with Psychotic Features. This leaves Schizophrenia and Delusional Disorder as the primary candidates.

> **Judge (inference scoring)** — predicted: D004, D005
> reference (truth) set: D004, D005
> TP=2 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Could you tell me more about the voices you hear? For example, do they speak in clear words, talk to each other, or comment on what you are doing?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: Yes, they speak very clearly, and it's usually a couple of voices talking about me and commenting on everything I'm doing. It's been happening almost every day for a year and seven months now, and it's really scary because I can't make them stop.

> **Judge (symptom extraction)** — confirmed: S020 Hallucinations
> denied: (none)
> - S020 Hallucinations: The patient describes hearing multiple clear voices talking about them and commenting on their actions, which directly indicates auditory hallucinations.

> Doctor's inference (final) — candidates: Schizophrenia
> Previously the candidates were ['Schizophrenia', 'Delusional Disorder']. Based on the patient's description of prominent auditory hallucinations (specifically, multiple voices conversing and commenting on their actions) lasting for 19 months, Delusional Disorder is ruled out, as it does not feature prominent auditory hallucinations of this nature. The absence of significant mood symptoms rules out mood disorders with psychotic features or schizoaffective disorder. Thus, the final diagnosis is Schizophrenia.

> **Judge (inference scoring)** — predicted: D005
> reference (truth) set: D004, D005
> TP=1 FP=0 FN=1 | precision=1.00 recall=0.50 accuracy=0.00 jaccard=0.50 weighted_recall=0.67
