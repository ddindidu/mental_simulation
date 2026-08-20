# Case D003_6 — gemini-3.1-flash-lite

**Category axis:** Classification 2: high_inference_low_question

- Ground truth disease: `D003`
- Final diagnosis: Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
- Correct: True
- Closed at patient turn: 6

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 1.000 | 0.426 | high |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.400 | 0.000 | high |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | In addition to that restlessness, do you also find yourself frequently struggling to focus on tasks, making careless mistakes, or feeling like you are often 'zoning out'? | 0.00 | 0 | 0 | 0.00 |
| 2 | Do you often find yourself interrupting others while they are speaking or having difficulty waiting your turn in conversations or group settings? | n/a (single candidate) | 1 | 0 | 0.00 |
| 3 | Since you mentioned feeling restless and having trouble staying seated, do you often feel like you are 'driven by a motor' or find it difficult to engage in leisure activities quietly? | n/a (single candidate) | 1 | 0 | 0.00 |
| 4 | Have you experienced these difficulties with remaining seated and engaging in quiet activities since you were a child, or is this a more recent development? | n/a (single candidate) | 0 | 0 | 0.00 |
| 5 | Do you also find yourself talking excessively or feeling the need to fidget with your hands or feet when you are forced to sit for extended periods? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: Well, I've been struggling a lot with restlessness lately, specifically finding it really difficult to remain seated when I'm expected to. It's gotten to the point where I'

> **Judge (symptom extraction)** — confirmed: S011 Leaving_Seat, S012 Feeling_Restless
> denied: (none)
> - S011 Leaving_Seat: The patient explicitly mentions finding it really difficult to remain seated when expected to.
> - S012 Feeling_Restless: The patient reports struggling a lot with restlessness lately, which represents the adolescent/adult manifestation of this symptom.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient's initial report of restlessness and difficulty remaining seated suggests symptoms consistent with ADHD. As this is the first interaction, I am including all three ADHD presentations to evaluate the full spectrum of symptoms.

> **Judge (inference scoring)** — predicted: D001, D002, D003
> reference (truth) set: D001, D002, D003
> TP=3 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: In addition to that restlessness, do you also find yourself frequently struggling to focus on tasks, making careless mistakes, or feeling like you are often 'zoning out'?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: No, I don't really have trouble focusing or zoning out. I can usually pay attention just fine, and I don't make many careless mistakes.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S001 Detail_Inattention_Errors, S002 Sustained_Attention_Difficulty
> - S001 Detail_Inattention_Errors: The patient explicitly denies making many careless mistakes, stating 'I don't make many careless mistakes.'
> - S002 Sustained_Attention_Difficulty: The patient denies having trouble focusing or paying attention, stating 'I don't really have trouble focusing or zoning out. I can usually pay attention just fine.'

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient explicitly denied symptoms of inattention (difficulty focusing, zoning out, or making careless mistakes), which makes the Combined and Predominantly Inattentive presentations unlikely. The patient's primary complaints of restlessness and difficulty remaining seated align with the Predominantly Hyperactive/Impulsive presentation.

> **Judge (inference scoring)** — predicted: D003
> reference (truth) set: D003
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Do you often find yourself interrupting others while they are speaking or having difficulty waiting your turn in conversations or group settings?

> **Judge (question scoring)** — targeted symptoms: S017 Waiting_Turn_Difficulty
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=1 redundancy_penalty=0 composite=0.00

**Patient**: No, I haven't really noticed myself doing that. I don't think I have much trouble waiting my turn or interrupting people when they are talking.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S017 Waiting_Turn_Difficulty, S018 Interrupting_Intruding
> - S017 Waiting_Turn_Difficulty: The patient explicitly denies having difficulty waiting their turn, stating they do not think they have much trouble with it.
> - S018 Interrupting_Intruding: The patient explicitly denies interrupting others when they are talking.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient reports significant restlessness and difficulty remaining seated, but explicitly denies the inattentive symptoms required for the Combined or Inattentive presentations. Since the patient denies impulsivity (interrupting/waiting turns), the current candidate remains the Hyperactive/Impulsive presentation, though further questioning is required to determine if these symptoms are pervasive and meet the diagnostic criteria for ADHD as a whole.

> **Judge (inference scoring)** — predicted: D003
> reference (truth) set: D003
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Since you mentioned feeling restless and having trouble staying seated, do you often feel like you are 'driven by a motor' or find it difficult to engage in leisure activities quietly?

> **Judge (question scoring)** — targeted symptoms: S013 Quiet_Activity_Difficulty, S014 Constant_Activity
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=1 redundancy_penalty=0 composite=0.00

**Patient**: I wouldn't say I feel like I'm "driven by a motor," but I definitely find it really hard to engage in leisure activities quietly. Even during my downtime or when I'm trying to enjoy a hobby, I feel this constant need to be active or make noise rather than just relaxing quietly.

> **Judge (symptom extraction)** — confirmed: S013 Quiet_Activity_Difficulty
> denied: S014 Constant_Activity
> - S013 Quiet_Activity_Difficulty: The patient explicitly states that they find it really hard to engage in leisure activities quietly, even during downtime or when trying to enjoy a hobby.
> - S014 Constant_Activity: The patient explicitly denies feeling like they are 'driven by a motor'.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient denies inattentive symptoms, confirming the focus remains on the hyperactive/impulsive presentation. However, the patient also denies impulsive symptoms like interrupting others, which is atypical for the full diagnostic criteria of ADHD (Predominantly Hyperactive/Impulsive Presentation). I need to determine if the restlessness is truly ADHD-related or if it stems from another source like anxiety.

> **Judge (inference scoring)** — predicted: D003
> reference (truth) set: D003
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Have you experienced these difficulties with remaining seated and engaging in quiet activities since you were a child, or is this a more recent development?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: I've actually struggled with staying seated and being quiet since I was a kid, definitely before I turned 12. However, it has become a much more consistent and noticeable problem for about the last year and five months.

> **Judge (symptom extraction)** — confirmed: S011 Leaving_Seat, S013 Quiet_Activity_Difficulty
> denied: (none)
> - S011 Leaving_Seat: The patient explicitly states they have struggled with staying seated since childhood.
> - S013 Quiet_Activity_Difficulty: The patient explicitly states they have struggled with being quiet since childhood.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient confirms lifelong symptoms of restlessness and difficulty engaging in quiet activities, consistent with the hyperactive/impulsive subtype. Since the patient explicitly denies inattentive symptoms, the diagnosis remains focused on the hyperactive/impulsive presentation.

> **Judge (inference scoring)** — predicted: D003
> reference (truth) set: D003
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Do you also find yourself talking excessively or feeling the need to fidget with your hands or feet when you are forced to sit for extended periods?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, I definitely find myself talking excessively quite a lot. And instead of just fidgeting with my hands or feet, I usually end up actually getting up and leaving my seat entirely when I'm expected to stay put.

> **Judge (symptom extraction)** — confirmed: S011 Leaving_Seat, S015 Excessive_Talking
> denied: S010 Fidgeting
> - S011 Leaving_Seat: The patient states that they usually end up getting up and leaving their seat entirely when they are expected to stay put.
> - S015 Excessive_Talking: The patient explicitly confirms that they find themselves talking excessively quite a lot.
> - S010 Fidgeting: The patient denies fidgeting with their hands or feet, stating that they leave their seat instead.

> Doctor's inference (final) — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient confirms symptoms of hyperactive/impulsive behavior (difficulty staying seated, difficulty engaging in quiet leisure activities, excessive talking) that have been present since childhood, meeting the core criteria for ADHD (Predominantly Hyperactive/Impulsive Presentation). The patient explicitly denied significant inattentive symptoms, making the Combined Presentation less likely.

> **Judge (inference scoring)** — predicted: D003
> reference (truth) set: D003
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
