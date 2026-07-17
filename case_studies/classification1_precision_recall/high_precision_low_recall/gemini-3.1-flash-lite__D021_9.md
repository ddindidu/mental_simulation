# Case D021_9 — gemini-3.1-flash-lite

**Category axis:** Classification 1: high_precision_low_recall

- Ground truth disease: `D021`
- Final diagnosis: Anorexia Nervosa
- Correct: True
- Closed at patient turn: 3

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.141 | 0.500 | low |
| Inference quality (jaccard) | 0.141 | 0.426 | low |
| Question reasonability (composite) | 0.050 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | How do you feel about your current body shape or weight, and does the thought of gaining weight cause you significant distress? | 0.00 | 0 | 0 | 0.10 |
| 2 | To better understand the physical impact of this weight loss, have you noticed any changes in your menstrual cycle, such as your periods becoming irregular or stopping entirely? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: I'm coming in today because I've been losing a lot of weight recently. I've also been eating very small amounts of food lately, sometimes barely anything during the day.

**Doctor**: How do you feel about your current body shape or weight, and does the thought of gaining weight cause you significant distress?

**Patient**: Honestly, I feel extremely uncomfortable with my body because whenever I look in the mirror, I still see myself as too fat. The thought of gaining any weight at all absolutely terrifies me and makes me feel completely worthless. My entire self-esteem is basically tied to keeping the number on the scale as low as possible.

**Doctor**: To better understand the physical impact of this weight loss, have you noticed any changes in your menstrual cycle, such as your periods becoming irregular or stopping entirely?

**Patient**: Honestly, I'm not really sure about that. I haven't noticed any major changes with my period recently.
