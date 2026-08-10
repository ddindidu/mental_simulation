# Case D005_7 — gemini-3.1-flash-lite

**Category axis:** Classification 2: high_inference_high_question

- Ground truth disease: `D005`
- Final diagnosis: Schizophrenia
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
| 1 | Besides the voices and visions, have you experienced any periods where your mood was unusually high, energetic, or irritable, or conversely, periods where you felt persistently sad, hopeless, or lacked energy? | 0.00 | 0 | 0 | 0.10 |
| 2 | Beyond the voices and visions, have you noticed a decrease in your motivation to do things, a tendency to withdraw from friends and family, or a feeling that you have less interest in your usual hobbies? | 0.00 | 0 | 0 | 0.10 |
| 3 | Are the voices and visions you experience related to a specific, singular belief—such as the idea that someone is following you or that you have a special identity—or are your experiences more disorganized and varied in nature? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: I'm here because I've been hearing voices and seeing things that other people tell me aren't actually there. This has been happening to me for about a year and three months now. I just really need some help figuring out why this is happening to me.

> **Judge (symptom extraction)** — confirmed: S020 Hallucinations
> denied: (none)
> - S020 Hallucinations: The patient explicitly reports hearing voices and seeing things that others tell them are not there, which corresponds to auditory and visual hallucinations.

> Doctor's inference — candidates: Schizophrenia, Schizoaffective Disorder (Bipolar Type), Schizoaffective Disorder (Depressive Type), Bipolar I Disorder with Psychotic Features, Major Depressive Disorder with Psychotic Features
> The patient reports persistent hallucinations (auditory and visual) for over 15 months. This necessitates a differential diagnosis that includes primary psychotic disorders, as well as mood disorders with psychotic features. I have narrowed the list to these candidates to begin exploring the presence of mood symptoms and the temporal relationship between those symptoms and the psychosis.

> **Judge (inference scoring)** — predicted: D005, D006, D007, D010, D015
> reference (truth) set: D005, D006, D007, D010, D015
> TP=5 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Besides the voices and visions, have you experienced any periods where your mood was unusually high, energetic, or irritable, or conversely, periods where you felt persistently sad, hopeless, or lacked energy?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.6 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, I haven't really experienced anything like that. I don't get those kinds of extreme highs or feel persistently sad and hopeless. My mood has been pretty much the same, it's just the things I'm seeing and hearing that trouble me.

> **Judge (symptom extraction)** — confirmed: S020 Hallucinations
> denied: S024 Depressed_Mood, S033 Elevated_Irritable_Mood, S083 Hopelessness
> - S020 Hallucinations: The patient reports being troubled by 'things I'm seeing and hearing', which indicates the presence of visual and auditory hallucinations.
> - S024 Depressed_Mood: The patient explicitly denies feeling 'persistently sad', which corresponds to depressed mood.
> - S033 Elevated_Irritable_Mood: The patient explicitly denies experiencing 'extreme highs', which corresponds to an elevated mood.
> - S083 Hopelessness: The patient explicitly denies feeling 'hopeless', which corresponds to hopelessness.

> Doctor's inference — candidates: Schizophrenia, Major Depressive Disorder with Psychotic Features
> The patient explicitly denies symptoms of mania or hypomania, which makes Schizoaffective Disorder (Bipolar Type) and Bipolar I Disorder with Psychotic Features unlikely. They also deny persistent depressive symptoms, which makes Schizoaffective Disorder (Depressive Type) less likely. The persistent presence of hallucinations and delusions without significant mood episodes points towards Schizophrenia, though Major Depressive Disorder with Psychotic Features remains a consideration if depressive symptoms were perhaps underreported or masked.

> **Judge (inference scoring)** — predicted: D005, D015
> reference (truth) set: D005
> TP=1 FP=1 FN=0 | precision=0.50 recall=1.00 accuracy=0.00 jaccard=0.50 weighted_recall=1.00

**Doctor**: Beyond the voices and visions, have you noticed a decrease in your motivation to do things, a tendency to withdraw from friends and family, or a feeling that you have less interest in your usual hobbies?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, I haven't really noticed any issues with that. My motivation and interest in my hobbies seem about the same as usual, and I haven't been withdrawing from my family or friends.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S025 Loss_of_Interest
> - S025 Loss_of_Interest: The patient explicitly denies experiencing a loss of motivation, loss of interest in hobbies, or social withdrawal from family and friends.

> Doctor's inference — candidates: Schizophrenia, Delusional Disorder
> The patient denies significant mood symptoms (ruling out mood disorders with psychotic features) and denies negative symptoms like avolition or social withdrawal, which makes Schizophrenia less definitive but still possible. Delusional Disorder is now included as a candidate because the patient reports hallucinations but lacks the full symptom cluster typically associated with a chronic schizophrenic decline.

> **Judge (inference scoring)** — predicted: D004, D005
> reference (truth) set: D005
> TP=1 FP=1 FN=0 | precision=0.50 recall=1.00 accuracy=0.00 jaccard=0.50 weighted_recall=1.00

**Doctor**: Are the voices and visions you experience related to a specific, singular belief—such as the idea that someone is following you or that you have a special identity—or are your experiences more disorganized and varied in nature?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, they aren't tied to any specific belief like someone following me or me being someone special. It's much more jumbled and disconnected than that, and my thoughts feel really disorganized. Sometimes it is just really hard to keep my thoughts or my speech on track because everything feels so scattered.

> **Judge (symptom extraction)** — confirmed: S020 Hallucinations, S021 Disorganized_Thinking_Speech
> denied: S019 Delusions
> - S020 Hallucinations: The patient confirms experiencing voices and visions, which represent auditory and visual hallucinations.
> - S021 Disorganized_Thinking_Speech: The patient describes their thoughts and speech as jumbled, disconnected, and disorganized, indicating disorganized thinking and speech.
> - S019 Delusions: The patient explicitly denies that their experiences are tied to specific beliefs like being followed or having a special identity, ruling out persecutory or grandiose delusions.

> Doctor's inference (final) — candidates: Schizophrenia
> The patient reports persistent auditory and visual hallucinations for over a year, along with disorganized thoughts and speech. They explicitly denied mood symptoms that would suggest Bipolar or Depressive disorders, and denied the fixed, singular, non-bizarre beliefs associated with Delusional Disorder. Given the duration (exceeding 6 months) and the presence of disorganized symptoms without mood disturbance, Schizophrenia is the most appropriate remaining candidate.

> **Judge (inference scoring)** — predicted: D005
> reference (truth) set: D005
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
