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

**Doctor**: Do you also often interrupt others, blurt out answers before questions are finished, or have trouble waiting your turn?

**Patient**: I definitely struggle a lot with waiting my turn. It is really hard for me to wait in lines, and I find it very difficult to wait for my turn to speak during conversations or activities.

**Doctor**: Do you also often lose things, forget appointments or daily tasks, or have trouble staying organized and finishing tasks?

**Patient**: Yes, I'm constantly losing important items like my keys, wallet, and work documents, which makes staying organized incredibly difficult. It is so frustrating because this happens almost daily and leads to so many careless mistakes on my tasks. I feel like I'm always wasting time searching for things I've misplaced.

**Doctor**: Have these attention and restlessness symptoms been present since childhood, before age 12, and have they been causing problems in more than one setting like home, work, or school?

**Patient**: Yes, these issues definitely started during childhood, well before I was 12, and they've been actively causing me major problems for at least the last two years and two months. It affects almost every part of my life, especially at home with my family and at my job.
