# Case D008_3 — gpt-5.4-mini-2026-03-17

**Category axis:** Classification 2: low_inference_low_question

- Ground truth disease: `D008`
- Final diagnosis: Bipolar I Disorder with Psychotic Features
- Correct: True
- Closed at patient turn: 3

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.333 | 0.900 | low |
| Recall | 0.167 | 0.500 | low |
| Inference quality (jaccard) | 0.167 | 0.426 | low |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | During this time, have you had any experiences like hearing or seeing things other people don’t, or feeling especially certain that you have special powers or a unique mission? | 0.00 | 0 | 0 | 0.00 |
| 2 | Do you believe this special mission is definitely true even if other people disagree, or could it be part of feeling unusually energized and confident? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I’m glad you came in. What brings you in today?

**Patient**: For the past five months, I’ve been feeling this incredible surge of energy, feeling extremely happy and active all the time. I barely need any sleep at night but still wake up feeling completely refreshed and on top of the world. I just feel absolutely unstoppable lately.

> **Judge (symptom extraction)** — confirmed: S033 Elevated_Irritable_Mood, S034 Increased_Activity, S035 Inflated_Self_Esteem, S036 Decreased_Sleep
> denied: (none)
> - S033 Elevated_Irritable_Mood: The patient reports feeling 'extremely happy' all the time, which indicates an elevated mood.
> - S034 Increased_Activity: The patient describes experiencing an 'incredible surge of energy' and feeling 'active all the time.'
> - S035 Inflated_Self_Esteem: The patient expresses feeling 'on top of the world' and 'absolutely unstoppable,' reflecting inflated self-esteem and confidence.
> - S036 Decreased_Sleep: The patient states they 'barely need any sleep at night but still wake up feeling completely refreshed,' demonstrating a decreased need for sleep.

> Doctor's inference — candidates: Bipolar I Disorder, Bipolar I Disorder with Psychotic Features
> The presentation has shifted away from a broad mood/anxiety differential to a clear manic syndrome: elevated/expansive mood, markedly increased energy/activity, decreased need for sleep, and feeling unstoppable for five months. This makes depressive, anxiety, trauma-related, and ADHD diagnoses unlikely. The remaining question is whether there are any psychotic symptoms during the mood episode; since none have been reported yet, Bipolar I Disorder is most likely, with Bipolar I Disorder with Psychotic Features still possible if psychosis emerges on further questioning.

> **Judge (inference scoring)** — predicted: D008, D010
> reference (truth) set: D006, D008, D009, D010
> TP=2 FP=0 FN=2 | precision=1.00 recall=0.50 accuracy=0.00 jaccard=0.50 weighted_recall=0.50

**Doctor**: During this time, have you had any experiences like hearing or seeing things other people don’t, or feeling especially certain that you have special powers or a unique mission?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: No, I don't see or hear things that aren't there. But I absolutely know I have a highly special mission in life! I feel like I am destined for a grand purpose that will completely change the world, and I'm ready to achieve it.

> **Judge (symptom extraction)** — confirmed: S019 Delusions, S035 Inflated_Self_Esteem
> denied: S020 Hallucinations
> - S019 Delusions: The patient expresses a fixed, ungrounded belief about having a highly special mission and being destined for a grand purpose to change the world, which is characteristic of grandiose delusions.
> - S035 Inflated_Self_Esteem: The patient exhibits inflated self-esteem and grandiosity, stating they are destined for a grand purpose that will completely change the world.
> - S020 Hallucinations: The patient explicitly denies experiencing hallucinations by stating they do not see or hear things that are not there.

> Doctor's inference — candidates: Bipolar I Disorder with Psychotic Features
> Previously the candidates were [Bipolar I Disorder, Bipolar I Disorder with Psychotic Features]. The patient has had a sustained 5-month period of markedly elevated mood, increased energy, decreased need for sleep, and grandiosity, which supports a manic episode consistent with Bipolar I Disorder. Although he denies hallucinations, his fixed belief in a highly special mission and destiny suggests a grandiose delusion, so Bipolar I Disorder with Psychotic Features is now more likely than Bipolar I Disorder alone.

> **Judge (inference scoring)** — predicted: D010
> reference (truth) set: D004, D008, D009
> TP=0 FP=1 FN=3 | precision=0.00 recall=0.00 accuracy=0.00 jaccard=0.00 weighted_recall=0.00

**Doctor**: Do you believe this special mission is definitely true even if other people disagree, or could it be part of feeling unusually energized and confident?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: This mission is absolutely real and true, and it has nothing to do with just feeling energetic. Other people might not understand it yet because they can't see the bigger picture, but I have been chosen for this specific purpose. My confidence and energy are just natural results of knowing what I am destined to achieve.

> **Judge (symptom extraction)** — confirmed: S019 Delusions, S035 Inflated_Self_Esteem
> denied: (none)
> - S019 Delusions: The patient expresses a fixed, ungrounded belief of being chosen for a specific mission that others cannot understand, indicating delusional grandiosity.
> - S035 Inflated_Self_Esteem: The patient exhibits inflated self-esteem and grandiosity, claiming absolute confidence and being destined to achieve a unique purpose.

> Doctor's inference (final) — candidates: Bipolar I Disorder with Psychotic Features
> Previously the only candidate was Bipolar I Disorder with Psychotic Features, and the new information continues to support it: there is a sustained 5-month period of markedly elevated mood, decreased need for sleep, increased energy, and grandiose delusional belief in a special mission. No hallucinations are reported, but the fixed, bizarre grandiose belief indicates psychotic features. Other mood or psychotic disorders remain less likely because the presentation is dominated by a manic syndrome with psychosis rather than isolated psychosis or depression.

> **Judge (inference scoring)** — predicted: D010
> reference (truth) set: D004, D008, D009
> TP=0 FP=1 FN=3 | precision=0.00 recall=0.00 accuracy=0.00 jaccard=0.00 weighted_recall=0.00
