# Case D011_6 — gpt-5.4-mini-2026-03-17

**Category axis:** Classification 2: high_inference_low_question

- Ground truth disease: `D011`
- Final diagnosis: Generalized Anxiety Disorder
- Correct: True
- Closed at patient turn: 3

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 1.000 | 0.426 | high |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | When you feel this worry, do you also get symptoms like restlessness, feeling on edge, muscle tension, fatigue, trouble concentrating, irritability, or sleep problems? | n/a (single candidate) | 0 | 0 | 0.00 |
| 2 | Have these worries been difficult to control most days, and have they been causing problems in your work, relationships, or daily life? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I’m glad you came in today. What brings you in today?

**Patient**: I'm here because I've been dealing with constant, uncontrollable worry about almost everything in my life, like my work, family, and finances. This has been going on for about a year and eight months now, and I just can't seem to turn my mind off.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously there were no candidates provided. The patient describes excessive, uncontrollable worry about multiple domains (work, family, finances) occurring for about 1 year and 8 months, which strongly supports Generalized Anxiety Disorder. No evidence yet for panic, trauma, mood episodes, psychosis, compulsions, or an eating disorder, so those diagnoses are not currently supported.

**Doctor**: When you feel this worry, do you also get symptoms like restlessness, feeling on edge, muscle tension, fatigue, trouble concentrating, irritability, or sleep problems?

**Patient**: Yes, my neck, shoulders, and jaw are constantly tense and aching, and I've become incredibly irritable and snappy over minor things. The worries constantly intrude on my mind, making it very hard to focus on daily tasks, though I'm not quite sure if my sleep is directly affected.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the new information strongly supports it: the patient reports excessive, hard-to-control worry about multiple domains for about 1 year and 8 months, along with associated muscle tension, irritability, and difficulty concentrating. No evidence has emerged for another diagnosis, so the candidate list remains unchanged.

**Doctor**: Have these worries been difficult to control most days, and have they been causing problems in your work, relationships, or daily life?

**Patient**: Yes, it is incredibly difficult to stop these worries once they start, and it happens almost every single day. It has definitely taken a toll on my daily life, making it hard to focus at work because the thoughts constantly intrude, and straining my relationships because I've become so snappy and impatient.

> Doctor's inference (final) — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the interview has further supported it rather than introducing alternatives. The patient describes excessive, uncontrollable worry about multiple areas of life for about 1 year and 8 months, occurring כמעט daily, with associated muscle tension, irritability, and impaired concentration, causing functional impairment. No evidence has emerged for panic, trauma-related symptoms, obsessions/compulsions, mood episodes, psychosis, or other conditions on the allowed list, so GAD remains the sole candidate.
