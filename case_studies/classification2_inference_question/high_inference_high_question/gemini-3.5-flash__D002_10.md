# Case D002_10 — gemini-3.5-flash

**Category axis:** Classification 2: high_inference_high_question

- Ground truth disease: `D002`
- Final diagnosis: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
- Correct: True
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.583 | 0.900 | low |
| Recall | 0.833 | 0.500 | high |
| Inference quality (jaccard) | 0.533 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | How long have you been struggling with losing things like this, and did you experience similar difficulties when you were a child or in school? | 0.00 | 0 | 0 | 0.10 |
| 2 | Besides losing things, do you often feel restless, fidgety, or have a hard time sitting still, both now and when you were growing up? | 0.00 | 0 | 0 | 0.10 |
| 3 | Apart from losing things, have you been experiencing constant, excessive worry about various aspects of your life, or persistent feelings of sadness and low mood? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello. What brings you in to see me today?

**Patient**: I'm here because I've been constantly losing important things that I need for my daily life, like my keys, wallet, and work documents. It's gotten to the point where it's happening almost every day, and it's becoming a really big problem for me.

**Doctor**: How long have you been struggling with losing things like this, and did you experience similar difficulties when you were a child or in school?

**Patient**: It’s been a really consistent struggle for about two years and one month now. I also definitely remember having these same issues back in elementary school, well before I turned 12, when I would constantly lose my homework and school supplies.

**Doctor**: Besides losing things, do you often feel restless, fidgety, or have a hard time sitting still, both now and when you were growing up?

**Patient**: No, I don't really struggle with feeling restless or fidgety, and I've never had a hard time sitting still. Even when I was growing up, I was always pretty quiet and able to stay seated without any issues.

**Doctor**: Apart from losing things, have you been experiencing constant, excessive worry about various aspects of your life, or persistent feelings of sadness and low mood?

**Patient**: No, I haven't been experiencing constant worry or persistent feelings of sadness. My mood is generally okay, and I don't feel anxious or depressed.
