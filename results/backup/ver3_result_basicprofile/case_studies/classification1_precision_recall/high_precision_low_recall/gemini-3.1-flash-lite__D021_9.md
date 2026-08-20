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

> **Judge (symptom extraction)** — confirmed: S026 Weight_Appetite_Change, S043 Restrictive_Intake, S044 Low_Weight
> denied: (none)
> - S026 Weight_Appetite_Change: The patient reports losing a lot of weight recently, which corresponds to the significant weight loss subtype of weight and appetite change.
> - S043 Restrictive_Intake: The patient states they have been eating very small amounts of food lately, which directly indicates restrictive intake.
> - S044 Low_Weight: The patient's statement about losing a lot of weight recently indicates continuous weight loss, which is a subtype of low weight.

> Doctor's inference — candidates: Anorexia Nervosa, Major Depressive Disorder
> The patient's presentation of significant weight loss and restricted food intake necessitates the consideration of eating disorders. Anorexia Nervosa is a primary candidate to investigate, while Major Depressive Disorder is included as it is a common comorbidity that can lead to appetite changes and weight loss.

> **Judge (inference scoring)** — predicted: D013, D021
> reference (truth) set: D006, D007, D008, D009, D010, D013, D014, D015, D021
> TP=2 FP=0 FN=7 | precision=1.00 recall=0.22 accuracy=0.00 jaccard=0.22 weighted_recall=0.30

**Doctor**: How do you feel about your current body shape or weight, and does the thought of gaining weight cause you significant distress?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: Honestly, I feel extremely uncomfortable with my body because whenever I look in the mirror, I still see myself as too fat. The thought of gaining any weight at all absolutely terrifies me and makes me feel completely worthless. My entire self-esteem is basically tied to keeping the number on the scale as low as possible.

> **Judge (symptom extraction)** — confirmed: S042 Low_Self_Esteem, S045 Fear_of_Weight_Gain, S046 Body_Image_Weight_Shape_Disturbance
> denied: (none)
> - S042 Low_Self_Esteem: The patient expresses feeling completely worthless and indicates that their self-esteem is entirely dependent on their weight.
> - S045 Fear_of_Weight_Gain: The patient explicitly states that the thought of gaining any weight at all absolutely terrifies them.
> - S046 Body_Image_Weight_Shape_Disturbance: The patient describes seeing themselves as too fat in the mirror and explains that their self-esteem is tied to keeping their weight as low as possible.

> Doctor's inference — candidates: Anorexia Nervosa
> The patient's report of a distorted body image (seeing themselves as 'too fat' despite weight loss), an intense fear of weight gain, and self-esteem being tethered to low weight strongly points toward Anorexia Nervosa. Major Depressive Disorder was previously considered due to the potential for comorbid mood symptoms, but the clinical picture is now dominated by the diagnostic criteria for Anorexia Nervosa. I have narrowed the list to this single candidate.

> **Judge (inference scoring)** — predicted: D021
> reference (truth) set: D006, D007, D008, D009, D010, D013, D014, D015, D021, D022
> TP=1 FP=0 FN=9 | precision=1.00 recall=0.10 accuracy=0.00 jaccard=0.10 weighted_recall=0.18

**Doctor**: To better understand the physical impact of this weight loss, have you noticed any changes in your menstrual cycle, such as your periods becoming irregular or stopping entirely?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Honestly, I'm not really sure about that. I haven't noticed any major changes with my period recently.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: (none)

> Doctor's inference (final) — candidates: Anorexia Nervosa
> The patient's clinical presentation, including significant weight loss, restricted caloric intake, intense fear of weight gain, and body image distortion, strongly aligns with the diagnostic criteria for Anorexia Nervosa. While the absence of amenorrhea is noted, it is not a required diagnostic criterion in the DSM-5. I have sufficient information to conclude the assessment.

> **Judge (inference scoring)** — predicted: D021
> reference (truth) set: D006, D007, D008, D009, D010, D013, D014, D015, D021, D022
> TP=1 FP=0 FN=9 | precision=1.00 recall=0.10 accuracy=0.00 jaccard=0.10 weighted_recall=0.18
