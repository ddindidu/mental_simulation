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

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously there were no candidates provided. Based on the initial interview, the patient describes more than two years of excessive, uncontrollable worry with significant sleep disturbance, which strongly supports Generalized Anxiety Disorder. No evidence yet suggests mood episodes, psychosis, trauma-related symptoms, obsessive-compulsive symptoms, or an eating disorder, so those are not currently favored.

**Doctor**: When you feel worried, do you also get symptoms like restlessness, muscle tension, fatigue, trouble concentrating, or irritability?

**Patient**: I don't really experience those physical symptoms like muscle tension, and I wouldn't say I get particularly irritable when I'm anxious. For me, it is much more about my mind constantly racing with worries that I just can't seem to shut off.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the new information supports it rather than ruling it out. The patient reports more than two years of excessive, hard-to-control worry with prominent insomnia, which is consistent with GAD. Lack of some associated physical symptoms (muscle tension, irritability) does not exclude GAD because not all associated symptoms are required if the core criteria are met.

**Doctor**: Do you worry about many different areas of your life, such as work, finances, health, or family, most days?

**Patient**: Yes, absolutely. My worries aren't just about one thing; they seem to spread to almost every area of my life, including my job, our finances, and my family. I feel this way almost every single day, and it feels like there is always something to worry about.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the interview continues to support it: the patient reports excessive, hard-to-control worry for over two years, occurring almost every day and spanning multiple domains (work, finances, family). The absence of prominent muscle tension or irritability does not rule it out, and there is no evidence here for another disorder from the allowed list. So the candidate list remains unchanged.

**Doctor**: Has this worry made it hard for you to work, manage daily tasks, or enjoy your life?

**Patient**: I'm not entirely sure, and I haven't really thought about it in those terms before. But I do know that the constant worrying makes it quite hard to focus on my tasks during the day.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the new information continues to support it: the patient has excessive, hard-to-control worry across multiple domains for more than two years, occurring nearly every day, with associated sleep disturbance and concentration difficulty. No new evidence suggests another diagnosis, and the absence of prominent panic, trauma, obsessive-compulsive symptoms, mood episodes, or psychosis keeps the differential unchanged.

**Doctor**: You mentioned this has been going on for over two years—has the worry been present more days than not during that whole time?

**Patient**: Yes, absolutely. For the entire two years and three months, the worry has been there almost every single day. It really feels like a constant background presence that I just can't escape.

> Doctor's inference — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the interview continues to support it: the patient reports excessive, uncontrollable worry across multiple domains (work, finances, family) occurring nearly every day for over two years, with associated sleep disturbance and difficulty concentrating. No new evidence suggests an alternative diagnosis, and the absence of prominent irritability or muscle tension does not rule out GAD because not all associated symptoms are required. The candidate list therefore remains unchanged.

**Doctor**: Have you had this anxiety and worry for at least 6 months, with difficulty controlling it and symptoms like sleep problems or trouble concentrating?

**Patient**: Yes, it has been much longer than six months—about two years and three months now, and I find it incredibly difficult to control or stop the worrying once it starts. It completely ruins my sleep by making it hard to fall asleep and waking me up throughout the night, and the constant intrusive thoughts make it really difficult to concentrate during the day.

> Doctor's inference (final) — candidates: Generalized Anxiety Disorder
> Previously the only candidate was Generalized Anxiety Disorder, and the interview continues to strongly support it: excessive worry across multiple domains, occurring most days for over 2 years, difficult to control, with associated sleep disturbance and impaired concentration. There is no evidence presented for panic, trauma, obsessions/compulsions, mood episodes, psychosis, or an alternative primary disorder, so the candidate list remains unchanged.
