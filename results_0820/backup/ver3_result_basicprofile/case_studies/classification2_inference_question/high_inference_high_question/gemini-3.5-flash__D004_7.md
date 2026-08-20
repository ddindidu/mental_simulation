# Case D004_7 — gemini-3.5-flash

**Category axis:** Classification 2: high_inference_high_question

- Ground truth disease: `D004`
- Final diagnosis: Delusional Disorder
- Correct: True
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.667 | 0.900 | low |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 0.667 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Besides feeling watched and followed, have you heard any voices or seen things that other people don't seem to hear or see? | 0.00 | 0 | 0 | 0.10 |
| 2 | How has your mood been overall? Have you experienced any long periods of feeling very depressed, or times when you felt unusually energetic and didn't need much sleep? | 0.00 | 0 | 0 | 0.10 |
| 3 | How long has this monitoring been going on, and has it affected your ability to work, keep up with daily tasks, or maintain your relationships? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello. What brings you in to see me today?

**Patient**: I'm here because I need help dealing with the people who are constantly watching and following me. I know for a fact that a certain organization has been monitoring my daily movements and tapping my phone. I just don't know how to make them stop.

> **Judge (symptom extraction)** — confirmed: S019 Delusions
> denied: (none)
> - S019 Delusions: The patient expresses a fixed, ungrounded belief that they are being constantly watched, followed, and monitored by an organization, which is characteristic of persecutory delusions.

> Doctor's inference — candidates: Delusional Disorder, Schizophrenia, Schizoaffective Disorder (Bipolar Type), Schizoaffective Disorder (Depressive Type), Bipolar I Disorder with Psychotic Features, Major Depressive Disorder with Psychotic Features
> The patient presents with persecutory delusions of being monitored and followed by an organization. The differential diagnosis includes Delusional Disorder, Schizophrenia, Schizoaffective Disorder, and Mood Disorders with Psychotic Features. Further exploration of mood symptoms, hallucinations, and duration is needed.

> **Judge (inference scoring)** — predicted: D004, D005, D006, D007, D010, D015
> reference (truth) set: D004, D005, D006, D007, D010, D015
> TP=6 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Besides feeling watched and followed, have you heard any voices or seen things that other people don't seem to hear or see?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.7333 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, I don't hear any voices or see things that aren't there. My mind is completely clear, but I know for a fact that those people are physically tracking and watching me. It is actually happening in the real world, not in my head.

> **Judge (symptom extraction)** — confirmed: S019 Delusions
> denied: S020 Hallucinations
> - S019 Delusions: The patient expresses a fixed, unshakeable belief that they are being physically tracked and watched by others, which is characteristic of persecutory delusions.
> - S020 Hallucinations: The patient explicitly denies experiencing auditory or visual hallucinations by stating they do not hear voices or see things that are not there.

> Doctor's inference — candidates: Delusional Disorder, Schizophrenia, Schizoaffective Disorder (Bipolar Type), Schizoaffective Disorder (Depressive Type), Bipolar I Disorder with Psychotic Features, Major Depressive Disorder with Psychotic Features
> Previously the candidates were [Delusional Disorder, Schizophrenia, Schizoaffective Disorder (Bipolar Type), Schizoaffective Disorder (Depressive Type), Bipolar I Disorder with Psychotic Features, Major Depressive Disorder with Psychotic Features]. The patient denies auditory or visual hallucinations, which increases the likelihood of Delusional Disorder, but we must still rule out Schizophrenia (which can present with delusions and other symptoms like disorganization or negative symptoms without prominent hallucinations) and various mood disorders with psychotic features. Therefore, the candidate list remains the same while we investigate mood symptoms and other psychotic features.

> **Judge (inference scoring)** — predicted: D004, D005, D006, D007, D010, D015
> reference (truth) set: D004
> TP=1 FP=5 FN=0 | precision=0.17 recall=1.00 accuracy=0.00 jaccard=0.17 weighted_recall=1.00

**Doctor**: How has your mood been overall? Have you experienced any long periods of feeling very depressed, or times when you felt unusually energetic and didn't need much sleep?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.7333 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, my mood has been pretty normal and stable overall. I haven't experienced any deep depression or times where I felt unusually energetic and stopped sleeping. The only real stress I have is dealing with the people who are tracking me.

> **Judge (symptom extraction)** — confirmed: S019 Delusions
> denied: S024 Depressed_Mood, S033 Elevated_Irritable_Mood, S036 Decreased_Sleep
> - S019 Delusions: The patient expresses a belief that they are being tracked by people, which is indicative of persecutory delusions.
> - S024 Depressed_Mood: The patient explicitly denies experiencing 'any deep depression'.
> - S033 Elevated_Irritable_Mood: The patient denies having periods where they felt 'unusually energetic'.
> - S036 Decreased_Sleep: The patient denies experiencing times where they 'stopped sleeping' in association with high energy.

> Doctor's inference — candidates: Delusional Disorder, Schizophrenia
> The patient denies any significant mood symptoms (depressive or manic), which allows us to rule out Schizoaffective Disorder (Bipolar and Depressive types), Bipolar I Disorder with Psychotic Features, and Major Depressive Disorder with Psychotic Features. The primary symptoms are non-bizarre persecutory delusions without prominent auditory or visual hallucinations, making Delusional Disorder the primary suspect, though Schizophrenia remains a differential possibility pending further exploration of functioning and negative/disorganized symptoms.

> **Judge (inference scoring)** — predicted: D004, D005
> reference (truth) set: D004
> TP=1 FP=1 FN=0 | precision=0.50 recall=1.00 accuracy=0.00 jaccard=0.50 weighted_recall=1.00

**Doctor**: How long has this monitoring been going on, and has it affected your ability to work, keep up with daily tasks, or maintain your relationships?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: It has been going on for about 11 months now. Even though it's stressful and I have to take precautions, I'm still able to do my job, handle my chores, and keep up with my relationships without any major issues.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S004 Instruction_Follow through_Difficulty, S009 Daily_Activities_Forgetfulness, S075 Social_Detachment
> - S004 Instruction_Follow through_Difficulty: The patient explicitly denies having difficulty finishing duties or chores by stating they are still able to do their job and handle chores.
> - S009 Daily_Activities_Forgetfulness: The patient denies forgetfulness or difficulty in daily activities by stating they can handle their chores without any major issues.
> - S075 Social_Detachment: The patient denies social detachment or relationship issues by stating they are able to keep up with their relationships without any major issues.

> Doctor's inference (final) — candidates: Delusional Disorder
> Previously the candidates were ['Delusional Disorder', 'Schizophrenia']. Based on this conversation, Schizophrenia is unlikely because the patient does not report hallucinations, disorganized speech, or negative symptoms, and their global functioning remains relatively preserved and unimpaired apart from the impact of the delusion. This presentation fits the criteria for Delusional Disorder, which has been present for 11 months. Thus, the final diagnosis is Delusional Disorder.

> **Judge (inference scoring)** — predicted: D004
> reference (truth) set: D004
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
