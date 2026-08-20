# Case D018_2 — gemini-3.1-flash-lite

**Category axis:** Classification 2: low_inference_high_question

- Ground truth disease: `D018`
- Final diagnosis: Posttraumatic Stress Disorder
- Correct: True
- Closed at patient turn: 2

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.750 | 0.900 | low |
| Recall | 0.091 | 0.500 | low |
| Inference quality (jaccard) | 0.087 | 0.426 | low |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Besides the nightmares and memories, have you been avoiding people or places that remind you of the event, or have you noticed a persistent negative change in your mood or how you view the world since then? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: I'm hoping to get some help because I keep having these really distressing, vivid memories of a terrible event that happened to me. I've also been struggling with awful nightmares about it almost every night, and it's been going on like this for about 10 months now.

> **Judge (symptom extraction)** — confirmed: S027 Sleep_Disturbance, S069 Intrusive_Symptoms
> denied: (none)
> - S027 Sleep_Disturbance: The patient reports struggling with awful nightmares almost every night, which indicates a sleep disturbance.
> - S069 Intrusive_Symptoms: The patient describes having distressing, vivid memories and nightmares of a terrible event that happened to them.

> Doctor's inference — candidates: Posttraumatic Stress Disorder, Adjustment Disorder
> The patient reports intrusive memories and nightmares related to a specific distressing event lasting for 10 months. This clinical presentation strongly aligns with Posttraumatic Stress Disorder. Adjustment Disorder remains a differential as we need to further assess the full range of diagnostic criteria (avoidance, negative alterations in cognition/mood, and hyperarousal) to confirm the diagnosis.

> **Judge (inference scoring)** — predicted: D018, D020
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=1 FN=10 | precision=0.50 recall=0.09 accuracy=0.00 jaccard=0.08 weighted_recall=0.15

**Doctor**: Besides the nightmares and memories, have you been avoiding people or places that remind you of the event, or have you noticed a persistent negative change in your mood or how you view the world since then?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: Yes, I do everything I can to avoid places, people, or conversations that remind me of what happened. Since then, my mood has completely changed; I'm constantly living in fear and anger. I also feel totally detached from everyone, so I've just been isolating myself.

> **Judge (symptom extraction)** — confirmed: S070 Trauma_Avoidance, S074 Persistent_Negative_Emotional_State, S075 Social_Detachment
> denied: (none)
> - S070 Trauma_Avoidance: The patient explicitly states they do everything they can to avoid places, people, or conversations that remind them of what happened.
> - S074 Persistent_Negative_Emotional_State: The patient describes constantly living in a state of fear and anger since the event occurred.
> - S075 Social_Detachment: The patient reports feeling totally detached from everyone and actively isolating themselves.

> Doctor's inference (final) — candidates: Posttraumatic Stress Disorder
> The patient reports symptoms including intrusive memories, nightmares, avoidance behavior, negative alterations in mood/cognition (fear, anger, detachment), and social isolation lasting for 10 months. These criteria strongly align with Posttraumatic Stress Disorder and exceed the typical duration or scope of an Adjustment Disorder. Therefore, Adjustment Disorder has been removed from the candidates.

> **Judge (inference scoring)** — predicted: D018
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=0 FN=10 | precision=1.00 recall=0.09 accuracy=0.00 jaccard=0.09 weighted_recall=0.17
