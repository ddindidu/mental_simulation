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

> Doctor's inference — candidates: Posttraumatic Stress Disorder, Adjustment Disorder
> The patient reports intrusive memories and nightmares related to a specific distressing event lasting for 10 months. This clinical presentation strongly aligns with Posttraumatic Stress Disorder. Adjustment Disorder remains a differential as we need to further assess the full range of diagnostic criteria (avoidance, negative alterations in cognition/mood, and hyperarousal) to confirm the diagnosis.

**Doctor**: Besides the nightmares and memories, have you been avoiding people or places that remind you of the event, or have you noticed a persistent negative change in your mood or how you view the world since then?

**Patient**: Yes, I do everything I can to avoid places, people, or conversations that remind me of what happened. Since then, my mood has completely changed; I'm constantly living in fear and anger. I also feel totally detached from everyone, so I've just been isolating myself.

> Doctor's inference (final) — candidates: Posttraumatic Stress Disorder
> The patient reports symptoms including intrusive memories, nightmares, avoidance behavior, negative alterations in mood/cognition (fear, anger, detachment), and social isolation lasting for 10 months. These criteria strongly align with Posttraumatic Stress Disorder and exceed the typical duration or scope of an Adjustment Disorder. Therefore, Adjustment Disorder has been removed from the candidates.
