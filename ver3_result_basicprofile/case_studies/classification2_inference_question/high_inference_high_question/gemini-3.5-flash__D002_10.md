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

> **Judge (symptom extraction)** — confirmed: S007 Losing_Items
> denied: (none)
> - S007 Losing_Items: The patient explicitly states they are constantly losing important items needed for daily life, such as keys, a wallet, and work documents.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Generalized Anxiety Disorder, Major Depressive Disorder
> The patient presents with chronic forgetfulness and losing important items, which is a classic symptom of inattention. The initial differential diagnosis includes ADHD (Inattentive or Combined Presentations), as well as Generalized Anxiety Disorder and Major Depressive Disorder, which can both impair concentration and memory.

> **Judge (inference scoring)** — predicted: D001, D002, D011, D013
> reference (truth) set: D001, D002, D003
> TP=2 FP=2 FN=1 | precision=0.50 recall=0.67 accuracy=0.00 jaccard=0.40 weighted_recall=0.67

**Doctor**: How long have you been struggling with losing things like this, and did you experience similar difficulties when you were a child or in school?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.6667 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: It’s been a really consistent struggle for about two years and one month now. I also definitely remember having these same issues back in elementary school, well before I turned 12, when I would constantly lose my homework and school supplies.

> **Judge (symptom extraction)** — confirmed: S007 Losing_Items
> denied: (none)
> - S007 Losing_Items: The patient explicitly reports a persistent history of constantly losing school-related items.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Generalized Anxiety Disorder, Major Depressive Disorder
> The patient reports a long-standing history of losing daily items (keys, wallet, work documents) starting before age 12, which strongly aligns with ADHD. The candidates remain the same as we need to investigate other symptoms of inattention, hyperactivity/impulsivity, and rule out or identify comorbid anxiety or depressive symptoms.

> **Judge (inference scoring)** — predicted: D001, D002, D011, D013
> reference (truth) set: D001, D002, D003
> TP=2 FP=2 FN=1 | precision=0.50 recall=0.67 accuracy=0.00 jaccard=0.40 weighted_recall=0.67

**Doctor**: Besides losing things, do you often feel restless, fidgety, or have a hard time sitting still, both now and when you were growing up?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.6667 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, I don't really struggle with feeling restless or fidgety, and I've never had a hard time sitting still. Even when I was growing up, I was always pretty quiet and able to stay seated without any issues.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S010 Fidgeting, S011 Leaving_Seat, S012 Feeling_Restless
> - S010 Fidgeting: The patient explicitly denies struggling with feeling fidgety.
> - S011 Leaving_Seat: The patient states they have never had a hard time sitting still and were always able to stay seated without issues.
> - S012 Feeling_Restless: The patient explicitly denies struggling with feeling restless.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Generalized Anxiety Disorder, Major Depressive Disorder
> Previously the candidates were [Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Generalized Anxiety Disorder, Major Depressive Disorder]. Based on the patient's report of having no history of restlessness, fidgetiness, or difficulty sitting still either now or in childhood, we can rule out the Combined Presentation of ADHD. The remaining candidates are ADHD (Predominantly Inattentive Presentation), Generalized Anxiety Disorder, and Major Depressive Disorder.

> **Judge (inference scoring)** — predicted: D002, D011, D013
> reference (truth) set: D002
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00

**Doctor**: Apart from losing things, have you been experiencing constant, excessive worry about various aspects of your life, or persistent feelings of sadness and low mood?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.6667 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, I haven't been experiencing constant worry or persistent feelings of sadness. My mood is generally okay, and I don't feel anxious or depressed.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S024 Depressed_Mood, S056 Excessive_Anxiety_Worry
> - S024 Depressed_Mood: The patient explicitly denies experiencing persistent feelings of sadness or feeling depressed.
> - S056 Excessive_Anxiety_Worry: The patient explicitly denies experiencing constant worry or feeling anxious.

> Doctor's inference (final) — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> Previously, the candidates were Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Generalized Anxiety Disorder, and Major Depressive Disorder. Based on the patient's explicit denial of excessive worry, anxiety, sadness, and low mood, Generalized Anxiety Disorder and Major Depressive Disorder have been ruled out. The patient meets the criteria for ADHD (Predominantly Inattentive Presentation) with childhood onset of inattentive symptoms (losing things) and no hyperactive/impulsive symptoms.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
