# Case D002_9 — gemini-3.1-flash-lite

**Category axis:** Classification 2: high_inference_low_question

- Ground truth disease: `D002`
- Final diagnosis: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
- Correct: True
- Closed at patient turn: 5

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 1.000 | 0.426 | high |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Beyond your difficulty with focus, do you also frequently find yourself feeling restless, fidgety, or acting impulsively without thinking things through? | 0.00 | 0 | 0 | 0.00 |
| 2 | To better understand your history, have these difficulties with focus been present since you were a child, or is this a more recent change in your life? | n/a (single candidate) | 0 | 0 | 0.00 |
| 3 | Besides difficulty focusing, do you frequently lose things necessary for tasks, find yourself easily distracted by external stimuli, or struggle to organize your daily activities? | n/a (single candidate) | 0 | 0 | 0.00 |
| 4 | Do you often make careless mistakes in your work, struggle to follow through on instructions, or find yourself avoiding tasks that require sustained mental effort? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. I'm here to help. Could you please tell me what brings you in to see me today?

**Patient**: Hi, Dr. Smith. I'm here today because I've been struggling a lot with paying attention and staying focused on my tasks and activities. It just feels really hard for me to keep my mind on one thing for very long.

> **Judge (symptom extraction)** — confirmed: S002 Sustained_Attention_Difficulty
> denied: (none)
> - S002 Sustained_Attention_Difficulty: The patient explicitly states they struggle with paying attention, staying focused on tasks and activities, and keeping their mind on one thing for very long.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient's initial presentation involves significant difficulty with attention and focus, which warrants screening for ADHD. At this early stage, I need to determine if hyperactivity or impulsivity symptoms are also present to distinguish between the three ADHD presentations.

> **Judge (inference scoring)** — predicted: D001, D002, D003
> reference (truth) set: D001, D002, D003
> TP=3 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Beyond your difficulty with focus, do you also frequently find yourself feeling restless, fidgety, or acting impulsively without thinking things through?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: No, I don't really experience restlessness or fidgeting, and I wouldn't say I act impulsively. My main struggles are really just with focusing and sustaining my attention on my tasks.

> **Judge (symptom extraction)** — confirmed: S002 Sustained_Attention_Difficulty
> denied: S010 Fidgeting, S012 Feeling_Restless
> - S002 Sustained_Attention_Difficulty: The patient explicitly states that their main struggles are with focusing and sustaining attention on tasks.
> - S010 Fidgeting: The patient explicitly denies experiencing fidgeting.
> - S012 Feeling_Restless: The patient explicitly denies experiencing restlessness.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient explicitly denied symptoms of hyperactivity and impulsivity, which makes the Combined and Predominantly Hyperactive/Impulsive presentations of ADHD unlikely. Therefore, I have narrowed the candidates to the Predominantly Inattentive Presentation.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: To better understand your history, have these difficulties with focus been present since you were a child, or is this a more recent change in your life?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: These focus issues aren't new; I've actually struggled with them since I was a kid, definitely before I turned 12. However, they have been consistently troublesome and really hard to manage for the last two years and five months.

> **Judge (symptom extraction)** — confirmed: S002 Sustained_Attention_Difficulty
> denied: (none)
> - S002 Sustained_Attention_Difficulty: The patient explicitly describes long-standing 'focus issues' persisting since childhood (before age 12), which directly corresponds to difficulty sustaining attention.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient's report of chronic inattention symptoms dating back to childhood, combined with the explicit denial of hyperactive or impulsive symptoms, continues to strongly support a diagnosis of ADHD (Predominantly Inattentive Presentation). No other candidates are currently indicated.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Besides difficulty focusing, do you frequently lose things necessary for tasks, find yourself easily distracted by external stimuli, or struggle to organize your daily activities?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: I don't really experience those specific problems. I don't tend to lose things, get easily distracted, or have much trouble organizing, as those aren't my main issues. It's really just the struggle of keeping my mind on a task once I've started.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S005 Organization_Difficulty, S007 Losing_Items, S008 Distractibility
> - S005 Organization_Difficulty: The patient explicitly denies having trouble organizing, stating it is not one of their main issues.
> - S007 Losing_Items: The patient explicitly denies experiencing the problem of losing things.
> - S008 Distractibility: The patient explicitly denies being easily distracted, stating they do not really experience this problem.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient confirms long-standing difficulties with sustaining attention since childhood (before age 12) while explicitly denying hyperactive or impulsive symptoms. Although they do not report common associated symptoms like losing things or organization issues, the core diagnostic criteria for inattentive presentation are centered on the inability to sustain attention, which remains the primary focus. I will ask about other specific DSM-5 inattentive criteria in the next turn to ensure diagnostic threshold requirements are met.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Do you often make careless mistakes in your work, struggle to follow through on instructions, or find yourself avoiding tasks that require sustained mental effort?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: I wouldn't say careless mistakes are my main issue, but I definitely struggle with avoiding tasks that require deep, prolonged concentration. I often procrastinate or feel a really strong reluctance to even start projects that need a lot of sustained mental effort.

> **Judge (symptom extraction)** — confirmed: S002 Sustained_Attention_Difficulty
> denied: S005 Organization_Difficulty, S007 Losing_Items, S008 Distractibility
> - S002 Sustained_Attention_Difficulty: The patient explicitly describes a struggle with 'keeping my mind on a task once I've started,' which indicates difficulty sustaining attention.
> - S005 Organization_Difficulty: The patient explicitly denies having 'much trouble organizing.'
> - S007 Losing_Items: The patient explicitly states 'I don't tend to lose things.'
> - S008 Distractibility: The patient explicitly denies that they 'get easily distracted.'

> Doctor's inference (final) — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient confirms long-standing difficulties with sustained mental effort dating back to childhood, fitting the criteria for the Inattentive presentation. Although they denied several other classic symptoms like losing items or distractibility, the persistent struggle with sustained attention remains the primary clinical feature. No other conditions are currently suspected.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
