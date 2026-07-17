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

> Doctor's inference — candidates: Bipolar I Disorder, Bipolar I Disorder with Psychotic Features
> The presentation has shifted away from a broad mood/anxiety differential to a clear manic syndrome: elevated/expansive mood, markedly increased energy/activity, decreased need for sleep, and feeling unstoppable for five months. This makes depressive, anxiety, trauma-related, and ADHD diagnoses unlikely. The remaining question is whether there are any psychotic symptoms during the mood episode; since none have been reported yet, Bipolar I Disorder is most likely, with Bipolar I Disorder with Psychotic Features still possible if psychosis emerges on further questioning.

**Doctor**: During this time, have you had any experiences like hearing or seeing things other people don’t, or feeling especially certain that you have special powers or a unique mission?

**Patient**: No, I don't see or hear things that aren't there. But I absolutely know I have a highly special mission in life! I feel like I am destined for a grand purpose that will completely change the world, and I'm ready to achieve it.

> Doctor's inference — candidates: Bipolar I Disorder with Psychotic Features
> Previously the candidates were [Bipolar I Disorder, Bipolar I Disorder with Psychotic Features]. The patient has had a sustained 5-month period of markedly elevated mood, increased energy, decreased need for sleep, and grandiosity, which supports a manic episode consistent with Bipolar I Disorder. Although he denies hallucinations, his fixed belief in a highly special mission and destiny suggests a grandiose delusion, so Bipolar I Disorder with Psychotic Features is now more likely than Bipolar I Disorder alone.

**Doctor**: Do you believe this special mission is definitely true even if other people disagree, or could it be part of feeling unusually energized and confident?

**Patient**: This mission is absolutely real and true, and it has nothing to do with just feeling energetic. Other people might not understand it yet because they can't see the bigger picture, but I have been chosen for this specific purpose. My confidence and energy are just natural results of knowing what I am destined to achieve.

> Doctor's inference (final) — candidates: Bipolar I Disorder with Psychotic Features
> Previously the only candidate was Bipolar I Disorder with Psychotic Features, and the new information continues to support it: there is a sustained 5-month period of markedly elevated mood, decreased need for sleep, increased energy, and grandiose delusional belief in a special mission. No hallucinations are reported, but the fixed, bizarre grandiose belief indicates psychotic features. Other mood or psychotic disorders remain less likely because the presentation is dominated by a manic syndrome with psychosis rather than isolated psychosis or depression.
