# Case D002_2 — gemini-3.1-flash-lite

**Category axis:** Classification 1: high_precision_high_recall

- Ground truth disease: `D002`
- Final diagnosis: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
- Correct: True
- Closed at patient turn: 2

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.833 | 0.500 | high |
| Inference quality (jaccard) | 0.833 | 0.426 | high |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Do you also find yourself feeling restless, having trouble sitting still for long periods, or often interrupting others when they are speaking? | 0.00 | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: I'm here today because I've been struggling a lot with staying focused and keeping my attention on tasks. I also find myself constantly forgetting to do daily chores and errands, which is making things really difficult for me.

> **Judge (symptom extraction)** — confirmed: S002 Sustained_Attention_Difficulty, S009 Daily_Activities_Forgetfulness
> denied: (none)
> - S002 Sustained_Attention_Difficulty: The patient explicitly states they struggle with staying focused and keeping attention on tasks.
> - S009 Daily_Activities_Forgetfulness: The patient mentions constantly forgetting to do daily chores and errands.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient reports significant difficulty with focus and memory related to daily tasks, which points toward ADHD. I am currently considering both the Combined and Predominantly Inattentive presentations, as we have not yet explored potential hyperactive or impulsive symptoms.

> **Judge (inference scoring)** — predicted: D001, D002
> reference (truth) set: D001, D002, D003
> TP=2 FP=0 FN=1 | precision=1.00 recall=0.67 accuracy=0.00 jaccard=0.67 weighted_recall=0.67

**Doctor**: Do you also find yourself feeling restless, having trouble sitting still for long periods, or often interrupting others when they are speaking?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: No, I don't really experience those specific symptoms. I don't usually feel restless or have trouble sitting still, and I don't think I have a habit of interrupting others when they are talking.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S011 Leaving_Seat, S012 Feeling_Restless, S018 Interrupting_Intruding
> - S011 Leaving_Seat: The patient denies having difficulty remaining seated or sitting still.
> - S012 Feeling_Restless: The patient denies experiencing feelings of restlessness.
> - S018 Interrupting_Intruding: The patient denies interrupting others during conversations.

> Doctor's inference (final) — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient explicitly denied symptoms of hyperactivity and impulsivity (restlessness, inability to sit still, interrupting others), which makes the Combined Presentation unlikely. Therefore, the diagnosis is narrowed to the Predominantly Inattentive Presentation.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
