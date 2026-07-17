# Case D008_8 — gemini-3.5-flash

**Category axis:** Classification 1: high_precision_high_recall

- Ground truth disease: `D008`
- Final diagnosis: Bipolar I Disorder
- Correct: True
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 1.000 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | During those times when you feel incredibly high or on top of the world, has this ever caused major disruptions in your daily life or work, or have you ever needed to be hospitalized because of it? | 0.00 | 0 | 0 | 0.10 |
| 2 | During these high periods, or even when your mood feels normal, have you ever heard voices, seen things others couldn't, or had strong beliefs that other people found highly unusual? | 0.00 | 0 | 0 | 0.10 |
| 3 | Have you ever experienced periods lasting two weeks or more where you felt consistently sad, down, or lost interest in almost all of your usual activities? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, welcome. What brings you in to see me today?

**Patient**: I'm here because for the last year and seven months, I've been dealing with this overwhelming surge of energy and extreme mood swings. I keep shifting between feeling incredibly high and on top of the world, to being intensely irritable and angry at the smallest things. It's just exhausting because my mood is constantly bouncing back and forth like this.

**Doctor**: During those times when you feel incredibly high or on top of the world, has this ever caused major disruptions in your daily life or work, or have you ever needed to be hospitalized because of it?

**Patient**: Yes, these high periods have caused major disruptions over the past year and seven months, especially since my reckless spending and foolish business investments have put me in severe financial distress. However, I have never been hospitalized because of it.

**Doctor**: During these high periods, or even when your mood feels normal, have you ever heard voices, seen things others couldn't, or had strong beliefs that other people found highly unusual?

**Patient**: No, I've never heard any voices or seen things that weren't really there. I also haven't held any unusual beliefs that other people found strange.

**Doctor**: Have you ever experienced periods lasting two weeks or more where you felt consistently sad, down, or lost interest in almost all of your usual activities?

**Patient**: No, I haven't really experienced anything like that. I don't recall ever feeling consistently sad or losing interest in my usual activities for weeks at a time.
