# Case D002_5 — gemini-3.1-flash-lite

**Category axis:** Classification 1: high_precision_high_recall

- Ground truth disease: `D002`
- Final diagnosis: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
- Correct: True
- Closed at patient turn: 9

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.967 | 0.500 | high |
| Inference quality (jaccard) | 0.967 | 0.426 | high |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.125 | 0.000 | high |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Beyond the difficulty focusing, do you often find yourself feeling restless, fidgety, or struggling to remain seated when you are expected to? | 0.00 | 0 | 0 | 0.00 |
| 2 | Have you noticed these difficulties with focus and organization since you were a child, or is this a more recent development in your life? | n/a (single candidate) | 0 | 0 | 0.00 |
| 3 | Do these challenges with focus and organization cause significant problems for you in at least two different areas of your life, such as at work, at school, or in your personal relationships? | n/a (single candidate) | 0 | 0 | 0.00 |
| 4 | Can you give me an example of a specific task at work or a situation in your personal life where this lack of focus has caused you to miss a deadline, make a mistake, or lead to a misunderstanding with someone? | n/a (single candidate) | 0 | 0 | 0.00 |
| 5 | Besides the project report, have you experienced similar instances of forgetting appointments, losing important personal items, or failing to follow through on instructions in your home life or social activities? | n/a (single candidate) | 0 | 0 | 0.00 |
| 6 | Do you often find that you make careless mistakes in your work because you have difficulty paying close attention to details, or do you struggle to sustain your attention during lengthy meetings or while reading documents? | n/a (single candidate) | 0 | 0 | 0.00 |
| 7 | Do you find that you frequently lose focus or your mind wanders when you are engaged in tasks that require sustained mental effort, even if you don't consider them 'meetings'? | n/a (single candidate) | 0 | 0 | 0.00 |
| 8 | Do you find that you have significant difficulty keeping your work materials, calendar, or workspace organized, often leading to a sense of being overwhelmed by clutter or a lack of structure? | n/a (single candidate) | 1 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: Honestly, I've been struggling a lot lately with listening to people when they talk directly to me. It feels like my mind just wanders off, and I'm having a really hard time focusing and staying organized because of it.

> **Judge (symptom extraction)** — confirmed: S002 Sustained_Attention_Difficulty, S003 Listening_Difficulty, S005 Organization_Difficulty, S008 Distractibility
> denied: (none)
> - S002 Sustained_Attention_Difficulty: The patient reports having a really hard time focusing, which indicates difficulty sustaining attention.
> - S003 Listening_Difficulty: The patient explicitly states they struggle with listening to people when they talk directly to them.
> - S005 Organization_Difficulty: The patient mentions having a hard time staying organized.
> - S008 Distractibility: The patient describes their mind wandering off, which corresponds to distractibility by unrelated thoughts.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient reports significant difficulties with sustained attention, listening, and organization, which are hallmark symptoms of ADHD. I have narrowed the candidates to the two most likely presentations of ADHD. I need to determine if hyperactive or impulsive symptoms are also present to differentiate between the two.

> **Judge (inference scoring)** — predicted: D001, D002
> reference (truth) set: D001, D002, D003
> TP=2 FP=0 FN=1 | precision=1.00 recall=0.67 accuracy=0.00 jaccard=0.67 weighted_recall=0.67

**Doctor**: Beyond the difficulty focusing, do you often find yourself feeling restless, fidgety, or struggling to remain seated when you are expected to?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: No, I wouldn't say I struggle with feeling restless or staying seated. I haven't really noticed those kinds of physical issues, it's more just my mind drifting away.

> **Judge (symptom extraction)** — confirmed: S008 Distractibility
> denied: S011 Leaving_Seat, S012 Feeling_Restless
> - S008 Distractibility: The patient's description of their 'mind drifting away' indicates distractibility, particularly through unrelated thoughts.
> - S011 Leaving_Seat: The patient explicitly denies having any trouble with staying seated.
> - S012 Feeling_Restless: The patient explicitly denies struggling with feeling restless.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient explicitly denied symptoms of physical restlessness or hyperactivity, which makes the Combined Presentation unlikely and strongly supports the Predominantly Inattentive Presentation.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Have you noticed these difficulties with focus and organization since you were a child, or is this a more recent development in your life?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Looking back, I've definitely had these focus issues since I was a kid, well before I turned 12. However, it has become a really constant, major struggle for about the last year and three months.

> **Judge (symptom extraction)** — confirmed: S002 Sustained_Attention_Difficulty
> denied: (none)
> - S002 Sustained_Attention_Difficulty: The patient's self-reported history of 'focus issues' since childhood directly maps to sustained attention difficulties.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient's clinical presentation of persistent inattention, lack of hyperactivity/impulsivity, and symptom onset prior to age 12 remains consistent with ADHD (Predominantly Inattentive Presentation). I need to rule out other potential causes for the recent worsening of symptoms, such as mood or anxiety disorders, before finalizing.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Do these challenges with focus and organization cause significant problems for you in at least two different areas of your life, such as at work, at school, or in your personal relationships?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: I'm not really sure, to be honest. I haven't thought much about how it specifically affects different areas of my life like work or my relationships. I just know it's been a constant struggle for me lately.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: (none)

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient's report of long-standing, childhood-onset difficulties with focus and organization, combined with a clear absence of hyperactivity or impulsivity, remains consistent with the Predominantly Inattentive presentation of ADHD. I need to further assess the functional impairment across different settings (e.g., work, home, social) to confirm the diagnostic criteria for clinical significance.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Can you give me an example of a specific task at work or a situation in your personal life where this lack of focus has caused you to miss a deadline, make a mistake, or lead to a misunderstanding with someone?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Just last week, I kept putting off a big project report because organizing all that information required so much mental effort and I just couldn't face it. When I finally tried to do it, I realized I had completely missed the instructions my coworker had explained to me directly. It was a total mess and I ended up missing the deadline, which was really frustrating.

> **Judge (symptom extraction)** — confirmed: S003 Listening_Difficulty, S005 Organization_Difficulty, S006 Sustained_Mental_Effort_Avoidance
> denied: (none)
> - S003 Listening_Difficulty: The utterance explicitly mentions missing key instructions due to not listening directly to a colleague.
> - S005 Organization_Difficulty: The utterance explicitly notes a struggle with organizing a project at work.
> - S006 Sustained_Mental_Effort_Avoidance: The utterance explicitly describes putting off a report because it required too much mental effort.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient confirms long-standing (childhood onset) symptoms of inattention without significant hyperactive or impulsive symptoms. The recent example of missing a work deadline due to organizational and attentional deficits further supports the diagnosis. I need to clarify if these difficulties persist across multiple settings (e.g., home/social life vs. just work) to confirm the diagnostic criteria.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Besides the project report, have you experienced similar instances of forgetting appointments, losing important personal items, or failing to follow through on instructions in your home life or social activities?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: I don't really experience those specific issues. I don't usually lose my things or forget appointments, so that hasn't been a problem for me.

> **Judge (symptom extraction)** — confirmed: S003 Listening_Difficulty, S004 Instruction_Follow through_Difficulty, S006 Sustained_Mental_Effort_Avoidance
> denied: (none)
> - S003 Listening_Difficulty: The patient admitted to completely missing instructions that a coworker had explained to them directly.
> - S004 Instruction_Follow through_Difficulty: The patient failed to finish a workplace duty, resulting in missing the deadline for a big project report.
> - S006 Sustained_Mental_Effort_Avoidance: The patient avoided and put off a project report because they felt organizing the information required too much mental effort.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The candidate remains the same as the patient consistently reports inattentive symptoms since childhood without hyperactive or impulsive behaviors. Further inquiry is needed to confirm if these symptoms meet the DSM-5 criteria for functional impairment across multiple settings.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Do you often find that you make careless mistakes in your work because you have difficulty paying close attention to details, or do you struggle to sustain your attention during lengthy meetings or while reading documents?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: I don't really think I have those specific issues with making careless mistakes or struggling to pay attention in meetings. I'm not really sure about that, as it hasn't stood out to me as a major problem.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S007 Losing_Items, S009 Daily_Activities_Forgetfulness
> - S007 Losing_Items: The patient explicitly states that they do not usually lose their things.
> - S009 Daily_Activities_Forgetfulness: The patient explicitly denies forgetting appointments, which is a key component of daily activities forgetfulness.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The candidate remains the same as the patient reports long-standing (since childhood) inattentive symptoms that cause functional impairment (missed deadlines). However, the patient denies many of the other core diagnostic criteria (losing items, careless mistakes, sustaining attention in meetings), suggesting the symptoms may not meet the full threshold for an ADHD diagnosis. I need to continue to assess the breadth of the impairment and rule out other potential causes for the focus issues.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Do you find that you frequently lose focus or your mind wanders when you are engaged in tasks that require sustained mental effort, even if you don't consider them 'meetings'?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, I struggle with that a lot. Because my mind wanders so easily and I lose focus almost immediately, I find myself actively avoiding or procrastinating on any tasks that require prolonged mental effort. I just feel a really strong reluctance to even start them.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: S001 Detail_Inattention_Errors, S002 Sustained_Attention_Difficulty
> - S001 Detail_Inattention_Errors: The patient explicitly denies having issues with making careless mistakes.
> - S002 Sustained_Attention_Difficulty: The patient explicitly denies having difficulty sustaining attention in meetings.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient confirms long-standing (since childhood) symptoms of inattention, specifically difficulty sustaining mental effort and avoidance of tasks requiring such effort. The patient denies hyperactive/impulsive symptoms. While the patient is unsure about impairment across multiple domains, the reported missed deadline and frustration indicate functional impairment. The candidate list remains unchanged as the symptoms consistently align with the inattentive presentation.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Do you find that you have significant difficulty keeping your work materials, calendar, or workspace organized, often leading to a sense of being overwhelmed by clutter or a lack of structure?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=1 redundancy_penalty=0 composite=0.00

**Patient**: Yes, absolutely. I struggle significantly with keeping my workspace, calendar, and daily tasks organized. This constant clutter and lack of structure leaves me feeling really overwhelmed and stressed out.

> **Judge (symptom extraction)** — confirmed: S002 Sustained_Attention_Difficulty, S006 Sustained_Mental_Effort_Avoidance, S008 Distractibility
> denied: (none)
> - S002 Sustained_Attention_Difficulty: The patient reports losing focus almost immediately, which indicates difficulty sustaining attention in tasks.
> - S006 Sustained_Mental_Effort_Avoidance: The patient explicitly states they actively avoid, procrastinate on, and feel a strong reluctance to start tasks requiring prolonged mental effort.
> - S008 Distractibility: The patient mentions that their mind wanders easily, which aligns with being easily distracted by unrelated thoughts.

> Doctor's inference (final) — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The candidates remain the same. The patient's history of symptoms starting before age 12, the clear pattern of inattention and executive dysfunction (difficulty with sustained mental effort, procrastination, and poor organization), and the explicit denial of hyperactive/impulsive symptoms continue to strongly support the Predominantly Inattentive Presentation of ADHD. I have sufficient information to confirm the diagnostic criteria.

> **Judge (inference scoring)** — predicted: D002
> reference (truth) set: D002
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
