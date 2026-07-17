# Case D005_1 — gpt-5.4-mini-2026-03-17

**Category axis:** Classification 2: high_inference_high_question

- Ground truth disease: `D005`
- Final diagnosis: Schizophrenia
- Correct: True
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.631 | 0.500 | high |
| Inference quality (jaccard) | 0.631 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Have you also had periods of depression or mania during this time, such as feeling very down or hopeless, or feeling unusually energetic, needing little sleep, and having racing thoughts? | 0.00 | 0 | 0 | 0.10 |
| 2 | Have these beliefs and voices significantly affected your work, school, relationships, or daily functioning? | 0.00 | 0 | 0 | 0.10 |
| 3 | Have you noticed any other unusual experiences, like disorganized thoughts or speech, trouble keeping track of your thoughts, or behaving in a very odd or confused way? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, I’m glad you came in. What brings you in today?

**Patient**: I've been feeling really anxious because I constantly feel like I'm being watched and monitored by people. This has been going on for about a year and four months now, and sometimes I even hear voices that others can't hear. It's just getting really hard to handle.

**Doctor**: Have you also had periods of depression or mania during this time, such as feeling very down or hopeless, or feeling unusually energetic, needing little sleep, and having racing thoughts?

**Patient**: No, I haven't really experienced those kinds of extreme emotional highs or lows. I don't feel unusually energetic or deeply hopeless. It's mostly just the constant anxiety from feeling watched and hearing those things.

**Doctor**: Have these beliefs and voices significantly affected your work, school, relationships, or daily functioning?

**Patient**: I'm not really sure, to be honest. I haven't really thought about how much it has affected my work or daily life. I've just been trying to get by.

**Doctor**: Have you noticed any other unusual experiences, like disorganized thoughts or speech, trouble keeping track of your thoughts, or behaving in a very odd or confused way?

**Patient**: Yes, my mind feels really jumbled lately and it's hard to keep track of my thoughts. I often find myself jumping quickly from one topic to another, and people sometimes tell me that my speech doesn't make sense. It's really frustrating because it just happens without me realizing it.
