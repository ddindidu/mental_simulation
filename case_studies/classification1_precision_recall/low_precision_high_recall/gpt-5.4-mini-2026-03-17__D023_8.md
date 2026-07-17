# Case D023_8 — gpt-5.4-mini-2026-03-17

**Category axis:** Classification 1: low_precision_high_recall

- Ground truth disease: `D023`
- Final diagnosis: Binge-Eating Disorder
- Correct: True
- Closed at patient turn: 3

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.611 | 0.900 | low |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 0.611 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | After these episodes of overeating, do you ever try to make up for it by vomiting, using laxatives, fasting, or exercising excessively? | 0.00 | 0 | 0 | 0.10 |
| 2 | Over the past two weeks, have you been feeling depressed, down, or lost interest or pleasure in things you usually enjoy? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, I’m glad you came in. What brings you in today?

**Patient**: I've been really struggling with my eating habits lately. I keep eating unusually large amounts of food, and it feels like I just can't control it once I start.

> Doctor's inference — candidates: Binge-Eating Disorder, Bulimia Nervosa, Major Depressive Disorder, Generalized Anxiety Disorder
> Previously there were no candidates. The patient reports recurrent episodes of eating unusually large amounts of food with loss of control, which strongly raises Binge-Eating Disorder. Bulimia Nervosa remains possible because binge eating can also occur there, but we do not yet know whether there are compensatory behaviors (vomiting, laxative use, excessive exercise). Major Depressive Disorder and Generalized Anxiety Disorder are still possible contributors or comorbidities to assess because overeating can sometimes be associated with mood or anxiety symptoms, but there is not enough information yet to confirm or exclude them.

**Doctor**: After these episodes of overeating, do you ever try to make up for it by vomiting, using laxatives, fasting, or exercising excessively?

**Patient**: No, I don't do any of those things. I've never tried to make myself throw up, use laxatives, or fast to make up for what I've eaten.

> Doctor's inference — candidates: Binge-Eating Disorder, Major Depressive Disorder, Generalized Anxiety Disorder
> Previously the candidates were [Binge-Eating Disorder, Bulimia Nervosa, Major Depressive Disorder, Generalized Anxiety Disorder], but the patient denies compensatory behaviors such as vomiting, laxatives, fasting, or excessive exercise, making Bulimia Nervosa unlikely. The remaining eating-pattern concern is most consistent with Binge-Eating Disorder, while Major Depressive Disorder and Generalized Anxiety Disorder remain possible comorbid or alternative explanations pending more history about mood, anxiety, and associated symptoms.

**Doctor**: Over the past two weeks, have you been feeling depressed, down, or lost interest or pleasure in things you usually enjoy?

**Patient**: I wouldn't say I've lost interest in my normal activities, but I do feel deeply depressed, guilty, and disgusted with myself right after I overeat. Those feelings are incredibly intense, but they specifically happen right after one of those episodes rather than being a constant state.

> Doctor's inference (final) — candidates: Binge-Eating Disorder
> Previously the candidates were [Binge-Eating Disorder, Major Depressive Disorder, Generalized Anxiety Disorder]. The patient describes recurrent episodes of eating unusually large amounts with loss of control and denies compensatory behaviors, which strongly supports Binge-Eating Disorder. Major Depressive Disorder is less likely because the depressed/guilty/disgusted feelings are brief and specifically occur after overeating rather than representing a persistent two-week depressive syndrome. Generalized Anxiety Disorder is also less likely because the interview does not describe pervasive, excessive worry across multiple domains; the distress appears tied to eating episodes.
