# Case D001_10 — gpt-5.4-mini-2026-03-17

**Category axis:** Classification 1: high_precision_high_recall

- Ground truth disease: `D001`
- Final diagnosis: Attention-Deficit/Hyperactivity Disorder (Combined Presentation)
- Correct: True
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.667 | 0.500 | high |
| Inference quality (jaccard) | 0.667 | 0.426 | high |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.333 | 0.000 | high |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Do you also often interrupt others, blurt out answers before questions are finished, or have trouble waiting your turn? | 0.00 | 1 | 0 | 0.00 |
| 2 | Do you also often lose things, forget appointments or daily tasks, or have trouble staying organized and finishing tasks? | 0.00 | 0 | 0 | 0.00 |
| 3 | Have these attention and restlessness symptoms been present since childhood, before age 12, and have they been causing problems in more than one setting like home, work, or school? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I’m glad you came in today. What brings you in?

**Patient**: I’ve been having a lot of trouble focusing lately and keep making careless mistakes because I miss small details. I also feel constantly restless, like I’m always on the go and can't seem to slow down.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> No previous candidates were provided. Based on the initial report of poor focus, careless mistakes from missing details, and constant restlessness/being 'always on the go,' the ADHD spectrum is most likely. Combined presentation is favored because both inattentive symptoms and hyperactive/restless symptoms are present, but inattentive-only and hyperactive/impulsive-only remain possible until more history clarifies the full symptom pattern, onset, and impairment.

**Doctor**: Do you also often interrupt others, blurt out answers before questions are finished, or have trouble waiting your turn?

**Patient**: I definitely struggle a lot with waiting my turn. It is really hard for me to wait in lines, and I find it very difficult to wait for my turn to speak during conversations or activities.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)
> Previously the candidates were the three ADHD presentations, and the new information supports continuing that same differential. The patient reports inattention (difficulty focusing, careless mistakes, missing details), hyperactivity/restlessness (constantly on the go), and impulsivity (difficulty waiting in lines and turn-taking), which keeps Combined Presentation most likely while still leaving the inattentive and hyperactive/impulsive presentations as alternatives pending fuller symptom count, duration, and functional impairment history.

**Doctor**: Do you also often lose things, forget appointments or daily tasks, or have trouble staying organized and finishing tasks?

**Patient**: Yes, I'm constantly losing important items like my keys, wallet, and work documents, which makes staying organized incredibly difficult. It is so frustrating because this happens almost daily and leads to so many careless mistakes on my tasks. I feel like I'm always wasting time searching for things I've misplaced.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation)
> Previously the candidates were all three ADHD presentations. The new information supports both inattentive symptoms (careless mistakes, losing items, disorganization, trouble focusing) and hyperactive/impulsive symptoms (constant restlessness, difficulty waiting in lines and turn-taking). Because symptoms from both domains are clearly present, the inattentive-only and hyperactive/impulsive-only presentations are less likely, leaving ADHD Combined Presentation as the best current candidate.

**Doctor**: Have these attention and restlessness symptoms been present since childhood, before age 12, and have they been causing problems in more than one setting like home, work, or school?

**Patient**: Yes, these issues definitely started during childhood, well before I was 12, and they've been actively causing me major problems for at least the last two years and two months. It affects almost every part of my life, especially at home with my family and at my job.

> Doctor's inference (final) — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation)
> Previously the only candidate was Attention-Deficit/Hyperactivity Disorder (Combined Presentation), and the interview further supports it rather than ruling it out. The patient endorses inattention (careless mistakes, losing items, disorganization, difficulty sustaining focus) and hyperactive/impulsive symptoms (restlessness, difficulty waiting turn), with onset in childhood and impairment in multiple settings. No evidence emerged for an alternative diagnosis from the allowed list, so the candidate list remains unchanged.
