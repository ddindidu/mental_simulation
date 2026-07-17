# Case D001_4 — gemini-3.5-flash

**Category axis:** Classification 2: low_inference_high_question

- Ground truth disease: `D001`
- Final diagnosis: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
- Correct: False
- Closed at patient turn: 5

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.222 | 0.900 | low |
| Recall | 0.389 | 0.500 | low |
| Inference quality (jaccard) | 0.189 | 0.426 | low |
| Question reasonability (composite) | 0.325 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.250 | 0.000 | high |
|  ↳ Mandatory-first compliance | 0.250 | 0.000 | high |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Have you struggled with these focus and organization issues since you were a child, or is this a relatively new pattern for you? | 0.00 | 0 | 0 | 0.10 |
| 2 | Along with these focus issues, do you often feel physically restless, find it hard to sit still, or feel like you are constantly driven by a motor? | 1.00 | 1 | 0 | 1.00 |
| 3 | Have you been experiencing a consistently low or depressed mood, or a loss of interest or pleasure in activities you normally enjoy? | 0.00 | 0 | 0 | 0.10 |
| 4 | Do you find yourself struggling with excessive, constant worry or anxiety about a variety of everyday things, and is this worry difficult to control? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, I'm glad to meet you. What brings you into the clinic today?

**Patient**: I'm here because I've been struggling a lot with making careless mistakes and staying focused at work. It's also been really hard for me to organize my tasks and daily activities lately. I just feel like I can't keep on top of things.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Generalized Anxiety Disorder, Major Depressive Disorder
> The patient presents with prominent symptoms of inattention, including careless mistakes, difficulty focusing, and disorganization. This initially suggests ADHD (Inattentive or Combined presentation). However, because anxiety and depressive disorders can also impair concentration and executive functioning, Generalized Anxiety Disorder and Major Depressive Disorder are also included in the differential diagnosis.

**Doctor**: Have you struggled with these focus and organization issues since you were a child, or is this a relatively new pattern for you?

**Patient**: No, this isn't a new thing at all; I've actually struggled with this for as long as I can remember. Even back in elementary school, well before I was twelve, my teachers always complained about me making careless mistakes and losing my schoolwork. It's just gotten a lot harder to manage now that I have adult responsibilities.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Generalized Anxiety Disorder, Major Depressive Disorder
> The patient reports a long-standing history of inattention, organization difficulties, and careless mistakes dating back to childhood (before age 12). This strongly supports an ADHD diagnosis. We need to maintain the current candidates (ADHD Inattentive, ADHD Combined, GAD, and MDD) while we investigate whether there are hyperactive/impulsive symptoms and rule out or evaluate comorbid mood or anxiety disorders.

**Doctor**: Along with these focus issues, do you often feel physically restless, find it hard to sit still, or feel like you are constantly driven by a motor?

**Patient**: No, I wouldn't say I feel physically restless or like I'm constantly driven by a motor. I can usually sit still without much of an issue, so that's not really something I experience.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Generalized Anxiety Disorder, Major Depressive Disorder
> Previously, the candidates included both ADHD Inattentive and Combined presentations, along with GAD and MDD. Because the patient explicitly denied symptoms of hyperactivity and restlessness, the Combined Presentation of ADHD is now excluded, leaving ADHD (Predominantly Inattentive Presentation), GAD, and MDD as the active candidates.

**Doctor**: Have you been experiencing a consistently low or depressed mood, or a loss of interest or pleasure in activities you normally enjoy?

**Patient**: No, I haven't really been feeling depressed or losing interest in my usual activities. My mood is generally fine, so that hasn't been an issue for me.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Generalized Anxiety Disorder
> The patient denies any depressed mood or loss of interest in activities, which allows us to rule out Major Depressive Disorder. The lifelong history of inattention, organization difficulties, and careless mistakes starting before age 12 strongly supports ADHD (Predominantly Inattentive Presentation), as they also deny hyperactivity. We keep Generalized Anxiety Disorder on the differential to explore if excessive worry or anxiety is contributing to or co-occurring with these symptoms.

**Doctor**: Do you find yourself struggling with excessive, constant worry or anxiety about a variety of everyday things, and is this worry difficult to control?

**Patient**: No, I don't really experience constant or uncontrollable worry. Anxiety isn't really a primary issue for me, so I wouldn't say I struggle with that.

> Doctor's inference (final) — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> Previously the candidates were ['Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)', 'Generalized Anxiety Disorder']. Based on the patient's explicit denial of constant, uncontrollable worry or anxiety, Generalized Anxiety Disorder has been ruled out. The patient meets the criteria for ADHD (Predominantly Inattentive Presentation) with childhood onset (before age 12) and lack of hyperactive symptoms. Therefore, the candidate list is narrowed down to ADHD (Predominantly Inattentive Presentation) and the interview can be finalized.
