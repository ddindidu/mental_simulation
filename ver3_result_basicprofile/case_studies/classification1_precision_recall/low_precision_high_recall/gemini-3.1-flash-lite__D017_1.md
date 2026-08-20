# Case D017_1 — gemini-3.1-flash-lite

**Category axis:** Classification 1: low_precision_high_recall

- Ground truth disease: `D017`
- Final diagnosis: Body Dysmorphic Disorder
- Correct: True
- Closed at patient turn: 3

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.556 | 0.900 | low |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 0.556 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Do you find yourself spending a significant amount of time each day checking your appearance in mirrors or attempting to hide or fix these features, and does this interfere with your daily routine or social life? | 0.00 | 0 | 0 | 0.10 |
| 2 | Beyond your concerns about your appearance, have you been feeling persistently sad, hopeless, or lost interest in activities you usually enjoy for most of the day? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: Honestly, I'm just incredibly distressed about how my face looks, especially my skin and my nose. I have these horrible scars and acne, and my nose just looks so crooked and deformed. It's so ugly and noticeable, and I feel like everyone is constantly staring at me because of it.

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance
> denied: (none)
> - S067 Preoccupation_with_Appearance: The patient expresses intense distress and preoccupation with perceived flaws in their physical appearance, specifically mentioning their skin (scars and acne) and nose (crooked and deformed).

> Doctor's inference — candidates: Body Dysmorphic Disorder, Major Depressive Disorder, Generalized Anxiety Disorder
> The patient's primary complaint focuses on a preoccupation with perceived flaws in their physical appearance (skin and nose) and the belief that others are staring at them, which is highly characteristic of Body Dysmorphic Disorder. Major Depressive Disorder and Generalized Anxiety Disorder are included as potential comorbidities given the patient's reported distress.

> **Judge (inference scoring)** — predicted: D011, D013, D017
> reference (truth) set: D017
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00

**Doctor**: Do you find yourself spending a significant amount of time each day checking your appearance in mirrors or attempting to hide or fix these features, and does this interfere with your daily routine or social life?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.6667 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: Yes, I spend hours in front of the mirror every day picking at my skin and applying heavy makeup to try and hide my nose. This routine takes up so much time that I'm constantly late for work, and I've started avoiding social situations entirely because I'm terrified of people judging me.

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance, S068 Appearance_Related_Repetitive_Behaviors
> denied: (none)
> - S067 Preoccupation_with_Appearance: The patient describes spending hours trying to hide their nose, indicating a preoccupation with a perceived physical flaw.
> - S068 Appearance_Related_Repetitive_Behaviors: The patient engages in repetitive behaviors such as mirror checking, skin picking, and applying heavy makeup in response to appearance concerns.

> Doctor's inference — candidates: Body Dysmorphic Disorder, Major Depressive Disorder, Generalized Anxiety Disorder
> The candidates remain the same. The patient's description of excessive mirror checking, skin picking, and social avoidance strongly aligns with Body Dysmorphic Disorder. However, the severity of the distress and social withdrawal warrants keeping Major Depressive Disorder and Generalized Anxiety Disorder in the differential as potential comorbidities.

> **Judge (inference scoring)** — predicted: D011, D013, D017
> reference (truth) set: D017
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00

**Doctor**: Beyond your concerns about your appearance, have you been feeling persistently sad, hopeless, or lost interest in activities you usually enjoy for most of the day?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.6667 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: I haven't really thought about feeling hopeless or losing interest in things. Honestly, I'm just so overwhelmed and completely focused on my appearance concerns right now.

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance
> denied: S025 Loss_of_Interest, S083 Hopelessness
> - S067 Preoccupation_with_Appearance: The patient explicitly states that they are completely focused on their appearance concerns.
> - S025 Loss_of_Interest: The patient denies having thought about losing interest in things.
> - S083 Hopelessness: The patient denies having thought about feeling hopeless.

> Doctor's inference (final) — candidates: Body Dysmorphic Disorder
> The patient's clinical presentation is highly specific to Body Dysmorphic Disorder, characterized by excessive preoccupation with perceived flaws in physical appearance, repetitive behaviors (mirror checking, skin picking, makeup application), and significant functional impairment (lateness for work, social withdrawal). Given the patient explicitly stated that their distress is focused entirely on these physical concerns and denied symptoms of depression or generalized anxiety, Major Depressive Disorder and Generalized Anxiety Disorder are now less likely primary explanations for the current distress.

> **Judge (inference scoring)** — predicted: D017
> reference (truth) set: D017
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
