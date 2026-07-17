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

**Doctor**: Besides feeling watched and followed, have you heard any voices or seen things that other people don't seem to hear or see?

**Patient**: No, I don't hear any voices or see things that aren't there. My mind is completely clear, but I know for a fact that those people are physically tracking and watching me. It is actually happening in the real world, not in my head.

**Doctor**: How has your mood been overall? Have you experienced any long periods of feeling very depressed, or times when you felt unusually energetic and didn't need much sleep?

**Patient**: No, my mood has been pretty normal and stable overall. I haven't experienced any deep depression or times where I felt unusually energetic and stopped sleeping. The only real stress I have is dealing with the people who are tracking me.

**Doctor**: How long has this monitoring been going on, and has it affected your ability to work, keep up with daily tasks, or maintain your relationships?

**Patient**: It has been going on for about 11 months now. Even though it's stressful and I have to take precautions, I'm still able to do my job, handle my chores, and keep up with my relationships without any major issues.
