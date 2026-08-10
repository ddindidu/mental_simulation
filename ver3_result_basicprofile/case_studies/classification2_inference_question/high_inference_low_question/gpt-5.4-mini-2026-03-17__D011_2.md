# Case D011_2 — gpt-5.4-mini-2026-03-17

**Category axis:** Classification 2: high_inference_low_question

- Ground truth disease: `D011`
- Final diagnosis: Generalized Anxiety Disorder
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
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | When you feel this anxiety, do you also get physical symptoms like restlessness, muscle tension, fatigue, trouble concentrating, irritability, or sleep problems? | n/a (single candidate) | 0 | 0 | 0.00 |
| 2 | Do you find that this worrying happens on most days and is hard to control, even when there is no specific problem in front of you? | n/a (single candidate) | 0 | 0 | 0.00 |
| 3 | How much has this worry been affecting your daily life, such as your work, relationships, or ability to get things done? | n/a (single candidate) | 0 | 0 | 0.00 |
| 4 | Have you ever had periods of intense fear or panic that come on suddenly and peak within minutes, rather than the worry being constant? | n/a (single candidate) | 0 | 0 | 0.00 |
| 5 | Based on what you’ve described, your symptoms are most consistent with generalized anxiety disorder. Would you like me to explain the diagnosis and discuss treatment options? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I’m glad you came in. What brings you in today?

**Patient**: I'm here because I just can't stop worrying about almost everything in my life, and it's completely overwhelming. It feels like this constant, non-stop anxiety has been going on for over two years now. I just really need help figuring out how to make it stop.

> **Judge (symptom extraction)** — confirmed: S056 Excessive_Anxiety_Worry, S057 Uncontrollable_Worry
> denied: (none)
> - S056 Excessive_Anxiety_Worry: The patient describes persistent, overwhelming worry about almost everything in their life.
> - S057 Uncontrollable_Worry: The patient states they cannot stop worrying, showing an inability to control it.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously no candidates were provided. Based on the transcript, the patient describes excessive worry about multiple areas of life, occurring nearly nonstop for over two years and causing significant distress/impairment, which most strongly fits Generalized Anxiety Disorder. Other listed diagnoses are not supported by the current information.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D011
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: When you feel this anxiety, do you also get physical symptoms like restlessness, muscle tension, fatigue, trouble concentrating, irritability, or sleep problems?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: I don't really experience those physical symptoms like muscle tension or sleep problems. However, my mind gets extremely cluttered, and it becomes really hard to focus on anything when I start worrying.

> **Judge (symptom extraction)** — confirmed: S059 Concentration_Difficulty
> denied: S027 Sleep_Disturbance, S061 Muscle_Tension
> - S027 Sleep_Disturbance: The patient explicitly denies experiencing sleep problems.
> - S059 Concentration_Difficulty: The patient reports that it becomes very hard to focus when they start worrying, indicating concentration difficulty interfered with by worry.
> - S061 Muscle_Tension: The patient explicitly denies experiencing muscle tension.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the new information supports it rather than replacing it: the patient reports excessive, hard-to-control worry about many areas of life for over two years, with associated impaired concentration. The absence of some somatic symptoms does not rule out GAD, since only one associated symptom is needed and cognitive symptoms like difficulty concentrating are consistent with the diagnosis. No evidence has emerged for a different disorder, so the candidate list remains unchanged.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D011
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Do you find that this worrying happens on most days and is hard to control, even when there is no specific problem in front of you?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, it happens almost every single day, and I find it incredibly hard to stop once it starts. Even when there is no immediate problem, the worry just creeps into every part of my life, from work to family. It feels completely out of my control.

> **Judge (symptom extraction)** — confirmed: S056 Excessive_Anxiety_Worry, S057 Uncontrollable_Worry
> denied: (none)
> - S056 Excessive_Anxiety_Worry: The patient describes worry creeping into every part of their life, including work and family, which indicates excessive and generalized worry.
> - S057 Uncontrollable_Worry: The patient explicitly states that they find it incredibly hard to stop the worry once it starts and that it feels completely out of their control.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the interview continues to support it: the patient reports excessive, difficult-to-control worry occurring כמעט daily for over two years, with impairment in concentration. Other listed diagnoses are not suggested by the current history because there is no evidence of panic, trauma, obsessions/compulsions, mood episodes, psychosis, eating disturbance, or a specific phobia. The candidate list remains the same.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D011
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: How much has this worry been affecting your daily life, such as your work, relationships, or ability to get things done?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: It heavily impacts my daily life because my worries aren't limited to one thing; they constantly spread across my work, family, and finances. These thoughts constantly intrude into my mind all day long, making it almost impossible to focus and get my daily tasks done.

> **Judge (symptom extraction)** — confirmed: S056 Excessive_Anxiety_Worry, S057 Uncontrollable_Worry, S059 Concentration_Difficulty
> denied: (none)
> - S056 Excessive_Anxiety_Worry: The patient states that their worries are not limited to one thing and constantly spread across work, family, and finances, indicating excessive and generalized worry.
> - S057 Uncontrollable_Worry: The patient describes their worrisome thoughts as constantly intruding into their mind all day long, showing that the worry is uncontrollable and intrusive.
> - S059 Concentration_Difficulty: The patient mentions that these intrusive thoughts make it almost impossible to focus, indicating significant concentration difficulty.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the new information continues to strongly support it: the patient reports excessive worry about multiple domains (work, family, finances), occurring nearly every day for over two years, difficult to control, and causing clear functional impairment. Although classic associated physical symptoms are not prominent, the patient does endorse impaired concentration due to worry, which still fits the diagnosis. No evidence has emerged for a more specific anxiety disorder, mood disorder, or psychotic disorder, so the candidate list remains unchanged.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D011
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Have you ever had periods of intense fear or panic that come on suddenly and peak within minutes, rather than the worry being constant?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: No, I don't really get those sudden, intense surges of panic that peak quickly. My anxiety is much more of a constant, ongoing worry that just lingers with me all day long.

> **Judge (symptom extraction)** — confirmed: S056 Excessive_Anxiety_Worry
> denied: (none)
> - S056 Excessive_Anxiety_Worry: The patient describes their anxiety as a 'constant, ongoing worry that just lingers with me all day long,' which directly corresponds to chronic and persistent worry.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the interview continues to support it. The patient describes excessive, hard-to-control worry occurring כמעט every day for over two years, across multiple domains (work, family, finances), with significant functional impairment. Panic attacks are denied, making panic disorder less likely, and there is no evidence provided for another disorder on the allowed list that better explains the presentation. The candidate list therefore remains unchanged.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D011
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: Based on what you’ve described, your symptoms are most consistent with generalized anxiety disorder. Would you like me to explain the diagnosis and discuss treatment options?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, please, I would really appreciate you explaining it to me and discussing how we can treat it. It is actually a huge relief to finally have a name for what I've been struggling with for over two years. I am very open to finding any ways to help manage this constant worry.

> **Judge (symptom extraction)** — confirmed: S056 Excessive_Anxiety_Worry
> denied: (none)
> - S056 Excessive_Anxiety_Worry: The patient explicitly mentions struggling with 'constant worry' for over two years.

> Doctor's inference (final) — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the interview continues to strongly support it: the patient reports excessive worry about multiple domains, occurring nearly every day for over two years, difficult to control, and causing significant impairment. Panic disorder is less likely because there are no sudden, discrete panic surges. No new evidence suggests an alternative diagnosis, so the candidate list remains unchanged.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D011
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
