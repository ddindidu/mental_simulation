# Case D001_2 — gemini-3.1-flash-lite

**Category axis:** Classification 2: low_inference_low_question

- Ground truth disease: `D001`
- Final diagnosis: Attention-Deficit/Hyperactivity Disorder (Combined Presentation)
- Correct: True
- Closed at patient turn: 8

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.333 | 0.900 | low |
| Recall | 0.458 | 0.500 | low |
| Inference quality (jaccard) | 0.292 | 0.426 | low |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.143 | 0.000 | high |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Beyond difficulty focusing, do you also frequently find yourself feeling restless, fidgeting often, or acting without thinking before others have finished speaking? | 0.00 | 0 | 0 | 0.00 |
| 2 | Since you mentioned having trouble listening, do you also frequently make careless mistakes in your work or struggle to keep track of your belongings and daily tasks? | 0.00 | 0 | 0 | 0.00 |
| 3 | Do you often find yourself interrupting others during conversations or having significant difficulty waiting your turn in social or professional situations? | n/a (single candidate) | 1 | 0 | 0.00 |
| 4 | Have you experienced these symptoms of restlessness and difficulty with sustained attention consistently since you were a child, or did they only begin recently? | n/a (single candidate) | 0 | 0 | 0.00 |
| 5 | Regarding the difficulty with sustained attention you mentioned, does this occur in multiple settings, such as both at home and at work or school, rather than just in one specific environment? | 0.00 | 0 | 0 | 0.00 |
| 6 | When you are in a situation that requires intense focus, like a meeting or a long lecture, do you find that your mind wanders frequently or that you struggle to stay engaged even when you are trying your hardest? | 0.00 | 0 | 0 | 0.00 |
| 7 | Besides feeling restless and talking excessively, do you often find yourself unable to remain seated in situations where it is expected, such as during a meal or at your desk? | 0.00 | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: Hi Dr. Smith. I'm here today because I've been having a really hard time listening when people are talking directly to me. It often feels like I just can't focus on what they are saying, even when they are looking right at me.

> **Judge (symptom extraction)** — confirmed: S003 Listening_Difficulty
> denied: (none)
> - S003 Listening_Difficulty: The patient explicitly describes having a hard time listening and focusing when people are talking directly to them, even when making eye contact.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient's initial complaint of difficulty focusing and listening, even during direct conversation, is highly suggestive of inattentive symptoms. I have initiated the differential with ADHD presentations to explore this further.

> **Judge (inference scoring)** — predicted: D001, D002, D003
> reference (truth) set: D001, D002, D003
> TP=3 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Beyond difficulty focusing, do you also frequently find yourself feeling restless, fidgeting often, or acting without thinking before others have finished speaking?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, I definitely feel very restless, almost like I am constantly "on the go" or driven by a motor. I also tend to talk excessively quite a bit. As for fidgeting or acting without thinking, I'm not really sure about those.

> **Judge (symptom extraction)** — confirmed: S012 Feeling_Restless, S014 Constant_Activity, S015 Excessive_Talking
> denied: (none)
> - S012 Feeling_Restless: The patient explicitly confirms feeling very restless.
> - S014 Constant_Activity: The patient describes feeling constantly on the go or driven by a motor.
> - S015 Excessive_Talking: The patient states that they tend to talk excessively.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient confirmed symptoms of inattention, restlessness, and excessive talking. Given the presence of both inattentive and hyperactive symptoms, the 'Predominantly Inattentive Presentation' is now less likely, while 'Combined Presentation' and 'Predominantly Hyperactive/Impulsive Presentation' remain the primary considerations.

> **Judge (inference scoring)** — predicted: D001, D003
> reference (truth) set: D001, D002, D003
> TP=2 FP=0 FN=1 | precision=1.00 recall=0.67 accuracy=0.00 jaccard=0.67 weighted_recall=0.67

**Doctor**: Since you mentioned having trouble listening, do you also frequently make careless mistakes in your work or struggle to keep track of your belongings and daily tasks?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: To be honest, I don't really experience making careless mistakes in my work. Losing track of my belongings or daily tasks hasn't really been a major issue for me either.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S001 Detail_Inattention_Errors, S007 Losing_Items, S009 Daily_Activities_Forgetfulness
> - S001 Detail_Inattention_Errors: The patient explicitly denies experiencing making careless mistakes in their work.
> - S007 Losing_Items: The patient states that losing track of their belongings has not been a major issue.
> - S009 Daily_Activities_Forgetfulness: The patient states that losing track of daily tasks has not been a major issue.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> Previously the candidates were [Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)]. The patient denied key inattentive symptoms such as making careless mistakes and struggling to keep track of tasks or belongings, which makes the Combined Presentation less likely. Therefore, the list has been narrowed to the Predominantly Hyperactive/Impulsive Presentation.

> **Judge (inference scoring)** — predicted: D003
> reference (truth) set: D001
> TP=0 FP=1 FN=1 | precision=0.00 recall=0.00 accuracy=0.00 jaccard=0.00 weighted_recall=0.00

**Doctor**: Do you often find yourself interrupting others during conversations or having significant difficulty waiting your turn in social or professional situations?

> **Judge (question scoring)** — targeted symptoms: S017 Waiting_Turn_Difficulty
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=1 redundancy_penalty=0 composite=0.00

**Patient**: To be honest, I don't think I do that very often. I haven't really noticed interrupting others or having trouble waiting my turn being much of an issue for me.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S017 Waiting_Turn_Difficulty, S018 Interrupting_Intruding
> - S017 Waiting_Turn_Difficulty: The patient explicitly states that having trouble waiting their turn has not been much of an issue for them.
> - S018 Interrupting_Intruding: The patient explicitly denies interrupting others as being a notable issue for them.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient reports significant restlessness and feeling 'on the go,' which aligns with the hyperactive presentation. However, they explicitly deny the inattentive symptoms (careless mistakes, losing items) and the impulsive symptoms (interrupting others, difficulty waiting turns) typically associated with the Combined or Inattentive presentations. Therefore, the focus remains on the Predominantly Hyperactive/Impulsive Presentation, though the lack of impulsive behaviors suggests I need to clarify the duration and onset of these symptoms to confirm if they meet the full diagnostic criteria.

> **Judge (inference scoring)** — predicted: D003
> reference (truth) set: D001
> TP=0 FP=1 FN=1 | precision=0.00 recall=0.00 accuracy=0.00 jaccard=0.00 weighted_recall=0.00

**Doctor**: Have you experienced these symptoms of restlessness and difficulty with sustained attention consistently since you were a child, or did they only begin recently?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: They actually started back when I was a kid, definitely before I was 12 years old. While I've had these struggles for a long time, they've been particularly noticeable and constant for the last year and three months.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: (none)

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> Previously the candidate was only ADHD (Predominantly Hyperactive/Impulsive), but the patient reports significant, long-standing difficulties with sustained attention alongside restlessness. Given that the patient does not clearly meet all criteria for either inattentive or hyperactive presentations exclusively, I have broadened the candidates to include all three presentations to better evaluate the symptom cluster.

> **Judge (inference scoring)** — predicted: D001, D002, D003
> reference (truth) set: D001
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00

**Doctor**: Regarding the difficulty with sustained attention you mentioned, does this occur in multiple settings, such as both at home and at work or school, rather than just in one specific environment?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: I'm not entirely sure, to be honest. I haven't really thought about whether it happens in all of those different places or if it's just in specific situations.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: (none)

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient reports significant restlessness and 'on the go' behavior, but explicitly denies the core inattentive symptoms of making careless mistakes and losing track of belongings, as well as denying impulsive behaviors like interrupting others. Given the mixed report of symptoms (some inattentive, some hyperactive, but lacking the full criteria for Combined Presentation), I have narrowed the candidates to the specific presentations to further investigate symptom clusters across settings.

> **Judge (inference scoring)** — predicted: D002, D003
> reference (truth) set: D001
> TP=0 FP=2 FN=1 | precision=0.00 recall=0.00 accuracy=0.00 jaccard=0.00 weighted_recall=0.00

**Doctor**: When you are in a situation that requires intense focus, like a meeting or a long lecture, do you find that your mind wanders frequently or that you struggle to stay engaged even when you are trying your hardest?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, definitely. My mind constantly wanders during those times, and I find it incredibly hard to stay engaged in long meetings or lectures. Because of that, I often dread and try to avoid tasks that require that kind of sustained mental effort.

> **Judge (symptom extraction)** — confirmed: S002 Sustained_Attention_Difficulty, S006 Sustained_Mental_Effort_Avoidance, S008 Distractibility
> denied: (none)
> - S002 Sustained_Attention_Difficulty: The patient states they find it incredibly hard to stay engaged in long meetings or lectures, indicating difficulty sustaining attention.
> - S006 Sustained_Mental_Effort_Avoidance: The patient explicitly mentions that they dread and try to avoid tasks that require sustained mental effort.
> - S008 Distractibility: The patient reports that their mind constantly wanders, which is characteristic of distractibility and unrelated thoughts.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> The patient reports significant symptoms of both inattention (mind wandering, avoiding tasks requiring sustained effort) and hyperactivity (feeling 'on the go' or driven by a motor, talking excessively). While they deny some classic symptoms like careless mistakes, losing belongings, or interrupting others, the presence of both inattentive and hyperactive symptoms suggests that the Combined Presentation must remain a candidate alongside the individual presentations. The list remains broad as I need to clarify the cross-situational nature of the symptoms to confirm the diagnosis.

> **Judge (inference scoring)** — predicted: D001, D002, D003
> reference (truth) set: D001
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00

**Doctor**: Besides feeling restless and talking excessively, do you often find yourself unable to remain seated in situations where it is expected, such as during a meal or at your desk?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: No, I don't really experience difficulty staying seated, even during meals or at my desk. I haven't noticed that being a significant issue for me.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S011 Leaving_Seat
> - S011 Leaving_Seat: The patient explicitly denies having difficulty staying seated, even during meals or at their desk.

> Doctor's inference (final) — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> Previously the candidates included all ADHD presentations. However, the patient explicitly denied significant hyperactive/impulsive behaviors such as interrupting others, trouble waiting their turn, or difficulty remaining seated, while confirming symptoms of inattention and restlessness. Given the lack of sufficient hyperactive/impulsive criteria to meet the Combined or Predominantly Hyperactive/Impulsive presentations, the diagnosis is narrowed to the Predominantly Inattentive Presentation.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D001
> TP=0 FP=1 FN=1 | precision=0.00 recall=0.00 accuracy=0.00 jaccard=0.00 weighted_recall=0.00
