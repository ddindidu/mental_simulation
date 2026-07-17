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

> Doctor's inference — candidates: Body Dysmorphic Disorder, Major Depressive Disorder, Generalized Anxiety Disorder
> The patient's primary complaint focuses on a preoccupation with perceived flaws in their physical appearance (skin and nose) and the belief that others are staring at them, which is highly characteristic of Body Dysmorphic Disorder. Major Depressive Disorder and Generalized Anxiety Disorder are included as potential comorbidities given the patient's reported distress.

**Doctor**: Do you find yourself spending a significant amount of time each day checking your appearance in mirrors or attempting to hide or fix these features, and does this interfere with your daily routine or social life?

**Patient**: Yes, I spend hours in front of the mirror every day picking at my skin and applying heavy makeup to try and hide my nose. This routine takes up so much time that I'm constantly late for work, and I've started avoiding social situations entirely because I'm terrified of people judging me.

> Doctor's inference — candidates: Body Dysmorphic Disorder, Major Depressive Disorder, Generalized Anxiety Disorder
> The candidates remain the same. The patient's description of excessive mirror checking, skin picking, and social avoidance strongly aligns with Body Dysmorphic Disorder. However, the severity of the distress and social withdrawal warrants keeping Major Depressive Disorder and Generalized Anxiety Disorder in the differential as potential comorbidities.

**Doctor**: Beyond your concerns about your appearance, have you been feeling persistently sad, hopeless, or lost interest in activities you usually enjoy for most of the day?

**Patient**: I haven't really thought about feeling hopeless or losing interest in things. Honestly, I'm just so overwhelmed and completely focused on my appearance concerns right now.

> Doctor's inference (final) — candidates: Body Dysmorphic Disorder
> The patient's clinical presentation is highly specific to Body Dysmorphic Disorder, characterized by excessive preoccupation with perceived flaws in physical appearance, repetitive behaviors (mirror checking, skin picking, makeup application), and significant functional impairment (lateness for work, social withdrawal). Given the patient explicitly stated that their distress is focused entirely on these physical concerns and denied symptoms of depression or generalized anxiety, Major Depressive Disorder and Generalized Anxiety Disorder are now less likely primary explanations for the current distress.
