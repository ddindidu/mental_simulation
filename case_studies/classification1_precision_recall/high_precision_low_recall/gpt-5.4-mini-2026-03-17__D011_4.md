# Case D011_4 — gpt-5.4-mini-2026-03-17

**Category axis:** Classification 1: high_precision_low_recall

- Ground truth disease: `D011`
- Final diagnosis: Generalized Anxiety Disorder
- Correct: True
- Closed at patient turn: 6

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.091 | 0.500 | low |
| Inference quality (jaccard) | 0.091 | 0.426 | low |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | When you feel worried, do you also get symptoms like restlessness, muscle tension, fatigue, trouble concentrating, or irritability? | n/a (single candidate) | 0 | 0 | 0.00 |
| 2 | Do you worry about many different areas of your life, such as work, finances, health, or family, most days? | n/a (single candidate) | 0 | 0 | 0.00 |
| 3 | Has this worry made it hard for you to work, manage daily tasks, or enjoy your life? | n/a (single candidate) | 0 | 0 | 0.00 |
| 4 | You mentioned this has been going on for over two years—has the worry been present more days than not during that whole time? | n/a (single candidate) | 0 | 0 | 0.00 |
| 5 | Have you had this anxiety and worry for at least 6 months, with difficulty controlling it and symptoms like sleep problems or trouble concentrating? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I’m glad you came in today. What brings you in today?

**Patient**: I'm visiting today because I've been struggling with severe sleep issues and constant, uncontrollable worry for over two years now. It has been going on for so long, and I've really been finding it hard to get any rest.

> **Judge (symptom extraction)** — confirmed: S027 Sleep_Disturbance, S056 Excessive_Anxiety_Worry, S057 Uncontrollable_Worry
> denied: (none)
> - S027 Sleep_Disturbance: The patient reports struggling with severe sleep issues and finding it hard to get any rest.
> - S056 Excessive_Anxiety_Worry: The patient reports experiencing constant worry for over two years.
> - S057 Uncontrollable_Worry: The patient explicitly describes their worry as uncontrollable.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously there were no candidates provided. Based on the initial interview, the patient describes more than two years of excessive, uncontrollable worry with significant sleep disturbance, which strongly supports Generalized Anxiety Disorder. No evidence yet suggests mood episodes, psychosis, trauma-related symptoms, obsessive-compulsive symptoms, or an eating disorder, so those are not currently favored.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=0 FN=10 | precision=1.00 recall=0.09 accuracy=0.00 jaccard=0.09 weighted_recall=0.17

**Doctor**: When you feel worried, do you also get symptoms like restlessness, muscle tension, fatigue, trouble concentrating, or irritability?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: I don't really experience those physical symptoms like muscle tension, and I wouldn't say I get particularly irritable when I'm anxious. For me, it is much more about my mind constantly racing with worries that I just can't seem to shut off.

> **Judge (symptom extraction)** — confirmed: S056 Excessive_Anxiety_Worry, S057 Uncontrollable_Worry
> denied: S060 Irritability, S061 Muscle_Tension
> - S056 Excessive_Anxiety_Worry: The patient describes their mind as 'constantly racing with worries', which indicates persistent and excessive worry.
> - S057 Uncontrollable_Worry: The patient states they 'just can't seem to shut off' their worries, reflecting an inability to control or stop the worry.
> - S060 Irritability: The patient explicitly denies becoming particularly irritable when anxious.
> - S061 Muscle_Tension: The patient explicitly denies experiencing physical symptoms such as muscle tension.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the new information supports it rather than ruling it out. The patient reports more than two years of excessive, hard-to-control worry with prominent insomnia, which is consistent with GAD. Lack of some associated physical symptoms (muscle tension, irritability) does not exclude GAD because not all associated symptoms are required if the core criteria are met.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=0 FN=10 | precision=1.00 recall=0.09 accuracy=0.00 jaccard=0.09 weighted_recall=0.17

**Doctor**: Do you worry about many different areas of your life, such as work, finances, health, or family, most days?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, absolutely. My worries aren't just about one thing; they seem to spread to almost every area of my life, including my job, our finances, and my family. I feel this way almost every single day, and it feels like there is always something to worry about.

> **Judge (symptom extraction)** — confirmed: S056 Excessive_Anxiety_Worry
> denied: (none)
> - S056 Excessive_Anxiety_Worry: The patient describes persistent, daily worries that spread across multiple areas of life, including work, finances, and family, which aligns with excessive and generalized worry.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the interview continues to support it: the patient reports excessive, hard-to-control worry for over two years, occurring almost every day and spanning multiple domains (work, finances, family). The absence of prominent muscle tension or irritability does not rule it out, and there is no evidence here for another disorder from the allowed list. So the candidate list remains unchanged.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=0 FN=10 | precision=1.00 recall=0.09 accuracy=0.00 jaccard=0.09 weighted_recall=0.17

**Doctor**: Has this worry made it hard for you to work, manage daily tasks, or enjoy your life?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: I'm not entirely sure, and I haven't really thought about it in those terms before. But I do know that the constant worrying makes it quite hard to focus on my tasks during the day.

> **Judge (symptom extraction)** — confirmed: S056 Excessive_Anxiety_Worry, S059 Concentration_Difficulty
> denied: (none)
> - S056 Excessive_Anxiety_Worry: The patient's mention of 'constant worrying' indicates the presence of persistent, excessive worry.
> - S059 Concentration_Difficulty: The patient reports that worrying makes it 'quite hard to focus on my tasks', directly showing concentration difficulty interfered with by worry.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the new information continues to support it: the patient has excessive, hard-to-control worry across multiple domains for more than two years, occurring nearly every day, with associated sleep disturbance and concentration difficulty. No new evidence suggests another diagnosis, and the absence of prominent panic, trauma, obsessive-compulsive symptoms, mood episodes, or psychosis keeps the differential unchanged.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=0 FN=10 | precision=1.00 recall=0.09 accuracy=0.00 jaccard=0.09 weighted_recall=0.17

**Doctor**: You mentioned this has been going on for over two years—has the worry been present more days than not during that whole time?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, absolutely. For the entire two years and three months, the worry has been there almost every single day. It really feels like a constant background presence that I just can't escape.

> **Judge (symptom extraction)** — confirmed: S056 Excessive_Anxiety_Worry, S057 Uncontrollable_Worry
> denied: (none)
> - S056 Excessive_Anxiety_Worry: The patient confirms experiencing persistent worry almost every day for over two years.
> - S057 Uncontrollable_Worry: The patient describes the worry as a constant presence that they cannot escape, indicating it is uncontrollable.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the interview continues to support it: the patient reports excessive, uncontrollable worry across multiple domains (work, finances, family) occurring nearly every day for over two years, with associated sleep disturbance and difficulty concentrating. No new evidence suggests an alternative diagnosis, and the absence of prominent irritability or muscle tension does not rule out GAD because not all associated symptoms are required. The candidate list therefore remains unchanged.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=0 FN=10 | precision=1.00 recall=0.09 accuracy=0.00 jaccard=0.09 weighted_recall=0.17

**Doctor**: Have you had this anxiety and worry for at least 6 months, with difficulty controlling it and symptoms like sleep problems or trouble concentrating?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, it has been much longer than six months—about two years and three months now, and I find it incredibly difficult to control or stop the worrying once it starts. It completely ruins my sleep by making it hard to fall asleep and waking me up throughout the night, and the constant intrusive thoughts make it really difficult to concentrate during the day.

> **Judge (symptom extraction)** — confirmed: S027 Sleep_Disturbance, S057 Uncontrollable_Worry, S059 Concentration_Difficulty
> denied: (none)
> - S027 Sleep_Disturbance: The patient reports that worrying ruins their sleep by making it hard to fall asleep and causing them to wake up throughout the night.
> - S057 Uncontrollable_Worry: The patient explicitly states that they find it incredibly difficult to control or stop the worrying once it starts.
> - S059 Concentration_Difficulty: The patient notes that constant intrusive thoughts make it really difficult to concentrate during the day.

> Doctor's inference (final) — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the interview continues to strongly support it: excessive worry across multiple domains, occurring most days for over 2 years, difficult to control, with associated sleep disturbance and impaired concentration. There is no evidence presented for panic, trauma, obsessions/compulsions, mood episodes, psychosis, or an alternative primary disorder, so the candidate list remains unchanged.

> **Judge (inference scoring)** — predicted: D011
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=0 FN=10 | precision=1.00 recall=0.09 accuracy=0.00 jaccard=0.09 weighted_recall=0.17
