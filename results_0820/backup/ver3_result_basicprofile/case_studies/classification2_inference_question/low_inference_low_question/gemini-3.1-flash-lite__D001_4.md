# Case D001_4 — gemini-3.1-flash-lite

**Category axis:** Classification 2: low_inference_low_question

- Ground truth disease: `D001`
- Final diagnosis: Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
- Correct: False
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.267 | 0.900 | low |
| Recall | 0.400 | 0.500 | low |
| Inference quality (jaccard) | 0.267 | 0.426 | low |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | When you feel this restlessness, do you find it difficult to control impulsive actions or interrupting others, or is the difficulty primarily limited to the physical need to move? | 0.00 | 0 | 0 | 0.00 |
| 2 | Regarding the focus issues you mentioned, do you frequently lose things necessary for tasks or find that you are easily distracted by external stimuli or unrelated thoughts? | 0.00 | 0 | 0 | 0.00 |
| 3 | Have you experienced these challenges with physical restlessness and difficulty sitting still since you were a child, or is this a more recent development in your life? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: I'm seeking help because I've been struggling a lot with focusing and making careless mistakes. I also feel very restless and find it really hard to just sit still. It's starting to make daily life pretty difficult for me.

> **Judge (symptom extraction)** — confirmed: S001 Detail_Inattention_Errors, S002 Sustained_Attention_Difficulty, S012 Feeling_Restless
> denied: (none)
> - S001 Detail_Inattention_Errors: The patient explicitly reports struggling with 'making careless mistakes'.
> - S002 Sustained_Attention_Difficulty: The patient states they are 'struggling a lot with focusing', which indicates difficulty sustaining attention.
> - S012 Feeling_Restless: The patient reports feeling 'very restless' and finding it 'really hard to just sit still'.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient reports symptoms of both inattention (focusing, careless mistakes) and hyperactivity/impulsivity (restlessness, inability to sit still), which warrants keeping all three ADHD presentations as initial differential candidates.

> **Judge (inference scoring)** — predicted: D001, D002, D003
> reference (truth) set: D001, D002, D003
> TP=3 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: When you feel this restlessness, do you find it difficult to control impulsive actions or interrupting others, or is the difficulty primarily limited to the physical need to move?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: It's definitely more of a physical need to move. I have a really hard time staying in my seat when I'm expected to, and even during my free time, I find it difficult to do things quietly. I don't really struggle with interrupting others or other impulsive behaviors.

> **Judge (symptom extraction)** — confirmed: S011 Leaving_Seat, S013 Quiet_Activity_Difficulty
> denied: S018 Interrupting_Intruding
> - S011 Leaving_Seat: The patient explicitly states they have a hard time staying in their seat when expected to.
> - S013 Quiet_Activity_Difficulty: The patient notes that they find it difficult to do things quietly, even during their free time.
> - S018 Interrupting_Intruding: The patient explicitly denies struggling with interrupting others.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient reports both significant inattentive symptoms (focus, careless mistakes) and hyperactive symptoms (physical restlessness, difficulty sitting still), but explicitly denies impulsive behaviors such as interrupting others. I am retaining the three ADHD presentations to further clarify the symptom profile and frequency/duration criteria before narrowing it down.

> **Judge (inference scoring)** — predicted: D001, D002, D003
> reference (truth) set: D001
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00

**Doctor**: Regarding the focus issues you mentioned, do you frequently lose things necessary for tasks or find that you are easily distracted by external stimuli or unrelated thoughts?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: To be honest, I don't really lose my things very often, as I usually keep them in the same spots. As for being easily distracted by outside noises or random thoughts, I'm not really sure if that's a big issue for me.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S007 Losing_Items
> - S007 Losing_Items: The patient explicitly denies losing things often, stating that this symptom is not part of their profile.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient reports significant physical restlessness and difficulty sitting still, which aligns with the hyperactive/impulsive presentation. However, they explicitly denied common inattentive symptoms like losing items or being easily distracted, making the Combined and Predominantly Inattentive presentations less likely. I am narrowing the focus to the Predominantly Hyperactive/Impulsive Presentation.

> **Judge (inference scoring)** — predicted: D003
> reference (truth) set: D001
> TP=0 FP=1 FN=1 | precision=0.00 recall=0.00 accuracy=0.00 jaccard=0.00 weighted_recall=0.00

**Doctor**: Have you experienced these challenges with physical restlessness and difficulty sitting still since you were a child, or is this a more recent development in your life?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, I've actually struggled with this physical restlessness and needing to get up since I was a young kid, definitely before the age of 12. It's not a recent development at all, as I remember constantly getting in trouble in elementary school for not staying in my seat.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S007 Losing_Items
> - S007 Losing_Items: The patient explicitly denies losing things often, stating they usually keep them in the same spots.

> Doctor's inference (final) — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient confirms a long-standing history of physical restlessness and difficulty sitting still since childhood, meeting the criteria for hyperactivity. The lack of significant inattentive symptoms (not losing items, not easily distracted) suggests the Predominantly Hyperactive/Impulsive presentation remains the most appropriate candidate.

> **Judge (inference scoring)** — predicted: D003
> reference (truth) set: D001
> TP=0 FP=1 FN=1 | precision=0.00 recall=0.00 accuracy=0.00 jaccard=0.00 weighted_recall=0.00
