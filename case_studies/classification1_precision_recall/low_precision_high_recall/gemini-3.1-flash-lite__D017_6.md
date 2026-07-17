# Case D017_6 — gemini-3.1-flash-lite

**Category axis:** Classification 1: low_precision_high_recall

- Ground truth disease: `D017`
- Final diagnosis: Body Dysmorphic Disorder
- Correct: True
- Closed at patient turn: 3

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.556 | 0.900 | low |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 0.556 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Do you find yourself frequently checking your reflection in mirrors or seeking reassurance from others about how your skin looks? | 0.00 | 0 | 0 | 0.10 |
| 2 | Beyond your concerns about your skin, have you been feeling persistently sad, hopeless, or have you lost interest in activities you usually enjoy over the past few weeks? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: I'm here today because I'm feeling incredibly anxious about my skin. I have these horrible scars and acne all over my face that look absolutely terrible, and it's getting to the point where I can barely focus on anything else. I really need help finding a way to fix how awful it looks.

> Doctor's inference — candidates: Body Dysmorphic Disorder, Generalized Anxiety Disorder, Major Depressive Disorder
> The patient's primary complaint centers on intense preoccupation with perceived flaws in their physical appearance (skin/acne), which is causing significant distress and impairment. This strongly suggests Body Dysmorphic Disorder. Generalized Anxiety Disorder and Major Depressive Disorder remain as potential comorbid conditions given the impact on focus and overall emotional state.

**Doctor**: Do you find yourself frequently checking your reflection in mirrors or seeking reassurance from others about how your skin looks?

**Patient**: Yes, to be honest, I'm constantly checking my reflection in any mirror or window I pass just to inspect my skin. I also frequently ask my family and friends if it looks terrible, even though it's really embarrassing to admit how much I need their reassurance.

> Doctor's inference — candidates: Body Dysmorphic Disorder, Generalized Anxiety Disorder, Major Depressive Disorder
> The patient's report of constant mirror-checking and excessive reassurance-seeking specifically regarding perceived skin flaws strongly aligns with the diagnostic criteria for Body Dysmorphic Disorder. Generalized Anxiety Disorder and Major Depressive Disorder remain in the differential as comorbid conditions, as the patient reports difficulty focusing and significant distress related to these thoughts. No changes were made to the candidate list at this time.

**Doctor**: Beyond your concerns about your skin, have you been feeling persistently sad, hopeless, or have you lost interest in activities you usually enjoy over the past few weeks?

**Patient**: No, I haven't really been feeling persistently sad or hopeless. My main distress and anxiety are really just focused on my skin and how awful my appearance looks.

> Doctor's inference (final) — candidates: Body Dysmorphic Disorder
> The patient's clinical presentation is characterized by a preoccupation with a perceived defect in their appearance (skin/acne) that is causing significant distress and impairment. The patient explicitly denies persistent feelings of sadness or hopelessness, which makes Major Depressive Disorder less likely. While they report anxiety, it is specific to their appearance, making Generalized Anxiety Disorder less likely than a primary diagnosis of Body Dysmorphic Disorder.
