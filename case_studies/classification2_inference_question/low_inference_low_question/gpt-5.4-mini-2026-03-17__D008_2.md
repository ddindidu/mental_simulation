# Case D008_2 — gpt-5.4-mini-2026-03-17

**Category axis:** Classification 2: low_inference_low_question

- Ground truth disease: `D008`
- Final diagnosis: Bipolar I Disorder
- Correct: True
- Closed at patient turn: 2

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.778 | 0.900 | low |
| Recall | 0.311 | 0.500 | low |
| Inference quality (jaccard) | 0.267 | 0.426 | low |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | During this time, have you had any hallucinations, such as hearing or seeing things that others do not, or beliefs that others said were clearly untrue? | 0.00 | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I’m Dr. AI. What brings you in today?

**Patient**: For the past 10 months, I've been experiencing this incredibly high, euphoric mood and just overflowing energy, like I'm completely unstoppable! But at the same time, I've been getting extremely irritable and furious over the smallest little things. It's this weird mix of feeling absolutely amazing but also snapping at everyone.

**Doctor**: During this time, have you had any hallucinations, such as hearing or seeing things that others do not, or beliefs that others said were clearly untrue?

**Patient**: No, I haven't experienced anything like that at all. I haven't seen or heard things that aren't actually there, nor have I held any beliefs that others found untrue.
