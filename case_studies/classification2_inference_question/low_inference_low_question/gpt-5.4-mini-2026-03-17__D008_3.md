# Case D008_3 — gpt-5.4-mini-2026-03-17

**Category axis:** Classification 2: low_inference_low_question

- Ground truth disease: `D008`
- Final diagnosis: Bipolar I Disorder with Psychotic Features
- Correct: True
- Closed at patient turn: 3

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.333 | 0.900 | low |
| Recall | 0.167 | 0.500 | low |
| Inference quality (jaccard) | 0.167 | 0.426 | low |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | During this time, have you had any experiences like hearing or seeing things other people don’t, or feeling especially certain that you have special powers or a unique mission? | 0.00 | 0 | 0 | 0.00 |
| 2 | Do you believe this special mission is definitely true even if other people disagree, or could it be part of feeling unusually energized and confident? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I’m glad you came in. What brings you in today?

**Patient**: For the past five months, I’ve been feeling this incredible surge of energy, feeling extremely happy and active all the time. I barely need any sleep at night but still wake up feeling completely refreshed and on top of the world. I just feel absolutely unstoppable lately.

**Doctor**: During this time, have you had any experiences like hearing or seeing things other people don’t, or feeling especially certain that you have special powers or a unique mission?

**Patient**: No, I don't see or hear things that aren't there. But I absolutely know I have a highly special mission in life! I feel like I am destined for a grand purpose that will completely change the world, and I'm ready to achieve it.

**Doctor**: Do you believe this special mission is definitely true even if other people disagree, or could it be part of feeling unusually energized and confident?

**Patient**: This mission is absolutely real and true, and it has nothing to do with just feeling energetic. Other people might not understand it yet because they can't see the bigger picture, but I have been chosen for this specific purpose. My confidence and energy are just natural results of knowing what I am destined to achieve.
