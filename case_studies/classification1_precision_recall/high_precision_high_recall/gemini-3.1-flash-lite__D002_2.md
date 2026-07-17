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

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient reports significant difficulty with focus and memory related to daily tasks, which points toward ADHD. I am currently considering both the Combined and Predominantly Inattentive presentations, as we have not yet explored potential hyperactive or impulsive symptoms.

**Doctor**: Do you also find yourself feeling restless, having trouble sitting still for long periods, or often interrupting others when they are speaking?

**Patient**: No, I don't really experience those specific symptoms. I don't usually feel restless or have trouble sitting still, and I don't think I have a habit of interrupting others when they are talking.

> Doctor's inference (final) — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient explicitly denied symptoms of hyperactivity and impulsivity (restlessness, inability to sit still, interrupting others), which makes the Combined Presentation unlikely. Therefore, the diagnosis is narrowed to the Predominantly Inattentive Presentation.
