# Case D004_3 — gemini-3.1-flash-lite

**Category axis:** Classification 2: high_inference_high_question

- Ground truth disease: `D004`
- Final diagnosis: Delusional Disorder
- Correct: True
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.750 | 0.500 | high |
| Inference quality (jaccard) | 0.750 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Besides these feelings of being followed, have you experienced any significant periods where your mood felt unusually high, energetic, or conversely, very low and hopeless? | 0.00 | 0 | 0 | 0.10 |
| 2 | Beyond the feeling of being followed, have you noticed any changes in your ability to keep up with daily tasks, or have you found yourself becoming more withdrawn from friends and social activities? | 0.00 | 0 | 0 | 0.10 |
| 3 | Have you ever heard voices or seen things that others around you do not seem to hear or see, or have you had any other unusual sensory experiences? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: I'm here because I'm being constantly monitored and followed by a specific group of people. I can't shake the feeling that they are tracking my every move, and I just don't feel safe anymore.

> **Judge (symptom extraction)** — confirmed: S019 Delusions
> denied: (none)
> - S019 Delusions: The patient expresses a fixed belief that they are being constantly monitored and followed by a specific group tracking their every move, which is characteristic of persecutory delusions.

> Doctor's inference — candidates: Delusional Disorder, Schizophrenia, Schizoaffective Disorder (Bipolar Type), Schizoaffective Disorder (Depressive Type), Bipolar I Disorder with Psychotic Features, Major Depressive Disorder with Psychotic Features
> The patient is presenting with persecutory delusions. This is the initial assessment, so the differential includes primary psychotic disorders, mood disorders with psychotic features, and other conditions where psychosis may manifest.

> **Judge (inference scoring)** — predicted: D004, D005, D006, D007, D010, D015
> reference (truth) set: D004, D005, D006, D007, D010, D015
> TP=6 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Besides these feelings of being followed, have you experienced any significant periods where your mood felt unusually high, energetic, or conversely, very low and hopeless?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.7333 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: I haven't really experienced those kinds of extreme mood swings. My mood generally stays pretty level, and I don't have periods of feeling unusually high or very hopeless. I'm mostly just stressed about the constant monitoring.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S033 Elevated_Irritable_Mood, S083 Hopelessness
> - S033 Elevated_Irritable_Mood: The patient explicitly denies experiencing extreme mood swings or periods of feeling unusually high.
> - S083 Hopelessness: The patient explicitly denies experiencing periods of feeling very hopeless.

> Doctor's inference — candidates: Delusional Disorder, Schizophrenia
> The patient explicitly denied significant mood episodes (mania or depression), which makes Bipolar I Disorder with Psychotic Features, Schizoaffective Disorder (Bipolar/Depressive types), and Major Depressive Disorder with Psychotic Features much less likely. I have narrowed the list to Delusional Disorder and Schizophrenia, as we need to determine if there are other psychotic symptoms (e.g., hallucinations, disorganized speech/behavior) or functional impairment that would differentiate these two.

> **Judge (inference scoring)** — predicted: D004, D005
> reference (truth) set: D004, D005, D007, D015
> TP=2 FP=0 FN=2 | precision=1.00 recall=0.50 accuracy=0.00 jaccard=0.50 weighted_recall=0.50

**Doctor**: Beyond the feeling of being followed, have you noticed any changes in your ability to keep up with daily tasks, or have you found yourself becoming more withdrawn from friends and social activities?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: My ability to handle my daily chores and tasks is generally fine, and I can take care of myself. However, I have been staying inside much more and avoiding social activities lately. I'm only doing that to stay safe and avoid the people who are constantly tracking and monitoring me.

> **Judge (symptom extraction)** — confirmed: S019 Delusions
> denied: (none)
> - S019 Delusions: The patient expresses a fixed belief that they are being constantly tracked and monitored, which is indicative of persecutory delusions.

> Doctor's inference — candidates: Delusional Disorder, Schizophrenia
> The patient denies significant mood episodes, making schizoaffective disorder less likely. The patient maintains daily functioning despite the persecutory beliefs, which aligns with the diagnostic criteria for Delusional Disorder, but Schizophrenia remains a candidate as we have not yet fully explored the duration of symptoms or the presence of other associated features like disorganized speech or negative symptoms beyond social withdrawal.

> **Judge (inference scoring)** — predicted: D004, D005
> reference (truth) set: D004, D005, D007, D015
> TP=2 FP=0 FN=2 | precision=1.00 recall=0.50 accuracy=0.00 jaccard=0.50 weighted_recall=0.50

**Doctor**: Have you ever heard voices or seen things that others around you do not seem to hear or see, or have you had any other unusual sensory experiences?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, I have never experienced anything like that. I don't hear voices or see things that aren't there, and my senses are completely normal. My concern is strictly about the very real people who are physically following and monitoring me.

> **Judge (symptom extraction)** — confirmed: S019 Delusions
> denied: S020 Hallucinations
> - S019 Delusions: The patient expresses a firm belief that they are being physically followed and monitored, which is consistent with persecutory delusions.
> - S020 Hallucinations: The patient explicitly denies experiencing hallucinations, stating they do not hear voices or see things that are not there.

> Doctor's inference (final) — candidates: Delusional Disorder
> The patient denies mood symptoms, hallucinations, and impairment in daily functioning, which makes Schizophrenia less likely than Delusional Disorder. Given the absence of other psychotic symptoms (like hallucinations) and the preservation of daily functioning, the diagnostic focus narrows to Delusional Disorder.

> **Judge (inference scoring)** — predicted: D004
> reference (truth) set: D004
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
