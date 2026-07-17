# Case D021_5 — gemini-3.1-flash-lite

**Category axis:** Classification 1: high_precision_low_recall

- Ground truth disease: `D021`
- Final diagnosis: Anorexia Nervosa
- Correct: True
- Closed at patient turn: 6

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.126 | 0.500 | low |
| Inference quality (jaccard) | 0.126 | 0.426 | low |
| Question reasonability (composite) | 0.020 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | When you think about your current weight or the way your body looks, do you feel an intense fear of gaining weight or believe that you are heavier than you actually are? | 0.00 | 0 | 0 | 0.10 |
| 2 | Have you noticed any significant changes in your menstrual cycle, such as your periods becoming irregular or stopping altogether? | n/a (single candidate) | 0 | 0 | 0.00 |
| 3 | Do you ever engage in behaviors like making yourself vomit, using laxatives, or exercising excessively to try to control your weight? | n/a (single candidate) | 0 | 0 | 0.00 |
| 4 | Do you ever have episodes where you feel out of control and eat an unusually large amount of food in a short period of time? | n/a (single candidate) | 0 | 0 | 0.00 |
| 5 | Even though you are eating very little, do you still perceive your body as being overweight or feel that certain parts of your body are too large? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me a little bit about what has been bothering you lately and what brings you into the clinic today?

**Patient**: I'm visiting today because I've lost a lot of weight recently. I have been eating very little, sometimes just a bite or two a day, and my family wanted me to get checked out.

**Doctor**: When you think about your current weight or the way your body looks, do you feel an intense fear of gaining weight or believe that you are heavier than you actually are?

**Patient**: Yes, I am absolutely terrified of gaining any weight. Seeing even a tiny increase on the scale makes me extremely anxious, and I feel like I need to keep my weight as low as possible.

**Doctor**: Have you noticed any significant changes in your menstrual cycle, such as your periods becoming irregular or stopping altogether?

**Patient**: I'm not really sure, to be honest. I haven't noticed any significant changes to my cycle recently.

**Doctor**: Do you ever engage in behaviors like making yourself vomit, using laxatives, or exercising excessively to try to control your weight?

**Patient**: No, I don't do any of those things. I have never forced myself to vomit, used laxatives, or exercised excessively to control my weight.

**Doctor**: Do you ever have episodes where you feel out of control and eat an unusually large amount of food in a short period of time?

**Patient**: No, I never have episodes like that where I lose control and eat a lot. Actually, I do the exact opposite by strictly restricting my food intake and trying to eat as little as possible.

**Doctor**: Even though you are eating very little, do you still perceive your body as being overweight or feel that certain parts of your body are too large?

**Patient**: Yes, definitely. When I look in the mirror, I still feel like I am too big and need to lose more weight. The thought of gaining even a little bit of weight is absolutely terrifying to me.
