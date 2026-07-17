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

> **Judge (symptom extraction)** — confirmed: S026 Weight_Appetite_Change, S043 Restrictive_Intake
> denied: (none)
> - S026 Weight_Appetite_Change: The patient explicitly states that they have 'lost a lot of weight recently,' which indicates a significant change in weight.
> - S043 Restrictive_Intake: The patient reports 'eating very little, sometimes just a bite or two a day,' which matches the criteria for restrictive food intake.

> Doctor's inference — candidates: Anorexia Nervosa, Major Depressive Disorder
> The patient presents with significant weight loss and restricted caloric intake. Anorexia Nervosa is a primary consideration given the reported behavior. Major Depressive Disorder is also included as it can present with appetite changes and weight loss.

> **Judge (inference scoring)** — predicted: D013, D021
> reference (truth) set: D006, D007, D008, D009, D010, D013, D014, D015, D021
> TP=2 FP=0 FN=7 | precision=1.00 recall=0.22 accuracy=0.00 jaccard=0.22 weighted_recall=0.30

**Doctor**: When you think about your current weight or the way your body looks, do you feel an intense fear of gaining weight or believe that you are heavier than you actually are?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: Yes, I am absolutely terrified of gaining any weight. Seeing even a tiny increase on the scale makes me extremely anxious, and I feel like I need to keep my weight as low as possible.

> **Judge (symptom extraction)** — confirmed: S044 Low_Weight, S045 Fear_of_Weight_Gain
> denied: (none)
> - S044 Low_Weight: The patient expresses a strong need to keep their weight as low as possible, which aligns with the 'Insistence on Low Weight' subtype.
> - S045 Fear_of_Weight_Gain: The patient explicitly states they are 'absolutely terrified of gaining any weight' and experience extreme anxiety at any scale increase, matching the 'Fear of Weight Gain' subtype.

> Doctor's inference — candidates: Anorexia Nervosa
> The patient's report of intense fear of weight gain, restrictive eating behavior, and significant weight loss strongly aligns with the diagnostic criteria for Anorexia Nervosa. Major Depressive Disorder is removed as the primary diagnostic concern at this stage, as the clinical picture is currently dominated by the specific symptoms of an eating disorder.

> **Judge (inference scoring)** — predicted: D021
> reference (truth) set: D006, D007, D008, D009, D010, D013, D014, D015, D021, D022
> TP=1 FP=0 FN=9 | precision=1.00 recall=0.10 accuracy=0.00 jaccard=0.10 weighted_recall=0.18

**Doctor**: Have you noticed any significant changes in your menstrual cycle, such as your periods becoming irregular or stopping altogether?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: I'm not really sure, to be honest. I haven't noticed any significant changes to my cycle recently.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: (none)

> Doctor's inference — candidates: Anorexia Nervosa
> The patient's report of severe food restriction, an intense fear of weight gain, and distress regarding the scale strongly aligns with Anorexia Nervosa. While the absence of reported amenorrhea is noted, it does not rule out the diagnosis. I will continue to explore the patient's body image perception and potential compensatory behaviors to confirm the diagnosis.

> **Judge (inference scoring)** — predicted: D021
> reference (truth) set: D006, D007, D008, D009, D010, D013, D014, D015, D021, D022
> TP=1 FP=0 FN=9 | precision=1.00 recall=0.10 accuracy=0.00 jaccard=0.10 weighted_recall=0.18

**Doctor**: Do you ever engage in behaviors like making yourself vomit, using laxatives, or exercising excessively to try to control your weight?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: No, I don't do any of those things. I have never forced myself to vomit, used laxatives, or exercised excessively to control my weight.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S047 Compensatory_Behavior_NonPurging, S048 Compensatory_Behavior_Purging
> - S047 Compensatory_Behavior_NonPurging: The patient explicitly denies ever exercising excessively to control their weight, which corresponds to non-purging compensatory behavior.
> - S048 Compensatory_Behavior_Purging: The patient explicitly denies ever forcing themselves to vomit or using laxatives, which corresponds to purging compensatory behavior.

> Doctor's inference — candidates: Anorexia Nervosa
> The patient's clinical presentation—significant weight loss, severe restriction of food intake, and an intense fear of weight gain—strongly aligns with the diagnostic criteria for Anorexia Nervosa, even in the absence of compensatory behaviors (purging) or reported amenorrhea at this time. The candidate list remains unchanged.

> **Judge (inference scoring)** — predicted: D021
> reference (truth) set: D006, D007, D008, D009, D010, D013, D014, D015, D021
> TP=1 FP=0 FN=8 | precision=1.00 recall=0.11 accuracy=0.00 jaccard=0.11 weighted_recall=0.20

**Doctor**: Do you ever have episodes where you feel out of control and eat an unusually large amount of food in a short period of time?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: No, I never have episodes like that where I lose control and eat a lot. Actually, I do the exact opposite by strictly restricting my food intake and trying to eat as little as possible.

> **Judge (symptom extraction)** — confirmed: S043 Restrictive_Intake
> denied: S049 Eating_Large_Amount, S050 Loss_of_Control
> - S043 Restrictive_Intake: The patient explicitly states that they strictly restrict their food intake and try to eat as little as possible.
> - S049 Eating_Large_Amount: The patient denies having episodes where they eat a lot.
> - S050 Loss_of_Control: The patient denies having episodes where they lose control while eating.

> Doctor's inference — candidates: Anorexia Nervosa
> The patient's clinical presentation of significant weight loss through extreme caloric restriction, combined with an intense fear of weight gain and body image disturbance, remains highly consistent with Anorexia Nervosa. The absence of bingeing, purging, or excessive exercise supports the Restricting Type presentation of Anorexia Nervosa. The lack of menstrual changes does not rule out the diagnosis, as it is not a required criterion for males or in all female presentations.

> **Judge (inference scoring)** — predicted: D021
> reference (truth) set: D006, D007, D008, D009, D010, D013, D014, D015, D021
> TP=1 FP=0 FN=8 | precision=1.00 recall=0.11 accuracy=0.00 jaccard=0.11 weighted_recall=0.20

**Doctor**: Even though you are eating very little, do you still perceive your body as being overweight or feel that certain parts of your body are too large?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, definitely. When I look in the mirror, I still feel like I am too big and need to lose more weight. The thought of gaining even a little bit of weight is absolutely terrifying to me.

> **Judge (symptom extraction)** — confirmed: S045 Fear_of_Weight_Gain, S046 Body_Image_Weight_Shape_Disturbance
> denied: (none)
> - S045 Fear_of_Weight_Gain: The patient states that the thought of gaining even a little bit of weight is 'absolutely terrifying' to them, indicating an intense fear of weight gain.
> - S046 Body_Image_Weight_Shape_Disturbance: The patient describes looking in the mirror and feeling like they are 'too big' and need to lose more weight, which reflects a distorted body image.

> Doctor's inference (final) — candidates: Anorexia Nervosa
> The patient's clinical presentation, including restricted caloric intake leading to significant weight loss, an intense fear of weight gain, and a distorted body image (feeling too big despite evidence to the contrary), strongly supports a diagnosis of Anorexia Nervosa. She specifically denies bingeing, purging, or excessive exercise, which is consistent with the restricting subtype.

> **Judge (inference scoring)** — predicted: D021
> reference (truth) set: D006, D007, D008, D009, D010, D013, D014, D015, D021
> TP=1 FP=0 FN=8 | precision=1.00 recall=0.11 accuracy=0.00 jaccard=0.11 weighted_recall=0.20
