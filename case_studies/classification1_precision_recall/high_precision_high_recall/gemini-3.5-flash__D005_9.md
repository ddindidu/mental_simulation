# Case D005_9 — gemini-3.5-flash

**Category axis:** Classification 1: high_precision_high_recall

- Ground truth disease: `D005`
- Final diagnosis: Schizophrenia
- Correct: True
- Closed at patient turn: 3

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.833 | 0.500 | high |
| Inference quality (jaccard) | 0.833 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Along with these voices and feelings of being watched, have you experienced any periods where you felt extremely depressed or, on the other hand, unusually high, energetic, or irritable? | 0.00 | 0 | 0 | 0.10 |
| 2 | Could you tell me more about the voices you hear? For example, do they speak in clear words, talk to each other, or comment on what you are doing? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, welcome. What brings you in to see me today?

**Patient**: I'm here because I finally decided I need help with something that's been happening for about a year and seven months. I constantly feel like I'm being watched and monitored, and I keep hearing these voices that no one else can hear. It's just getting to be too much to handle.

**Doctor**: Along with these voices and feelings of being watched, have you experienced any periods where you felt extremely depressed or, on the other hand, unusually high, energetic, or irritable?

**Patient**: No, I haven't really felt that way at all. My mood has been pretty much the same, without those kinds of extreme highs or lows. It's really just the voices and the constant monitoring that are the problem.

**Doctor**: Could you tell me more about the voices you hear? For example, do they speak in clear words, talk to each other, or comment on what you are doing?

**Patient**: Yes, they speak very clearly, and it's usually a couple of voices talking about me and commenting on everything I'm doing. It's been happening almost every day for a year and seven months now, and it's really scary because I can't make them stop.
