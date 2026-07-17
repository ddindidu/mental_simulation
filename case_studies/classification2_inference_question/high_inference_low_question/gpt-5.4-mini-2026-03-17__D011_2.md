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

**Doctor**: When you feel this anxiety, do you also get physical symptoms like restlessness, muscle tension, fatigue, trouble concentrating, irritability, or sleep problems?

**Patient**: I don't really experience those physical symptoms like muscle tension or sleep problems. However, my mind gets extremely cluttered, and it becomes really hard to focus on anything when I start worrying.

**Doctor**: Do you find that this worrying happens on most days and is hard to control, even when there is no specific problem in front of you?

**Patient**: Yes, it happens almost every single day, and I find it incredibly hard to stop once it starts. Even when there is no immediate problem, the worry just creeps into every part of my life, from work to family. It feels completely out of my control.

**Doctor**: How much has this worry been affecting your daily life, such as your work, relationships, or ability to get things done?

**Patient**: It heavily impacts my daily life because my worries aren't limited to one thing; they constantly spread across my work, family, and finances. These thoughts constantly intrude into my mind all day long, making it almost impossible to focus and get my daily tasks done.

**Doctor**: Have you ever had periods of intense fear or panic that come on suddenly and peak within minutes, rather than the worry being constant?

**Patient**: No, I don't really get those sudden, intense surges of panic that peak quickly. My anxiety is much more of a constant, ongoing worry that just lingers with me all day long.

**Doctor**: Based on what you’ve described, your symptoms are most consistent with generalized anxiety disorder. Would you like me to explain the diagnosis and discuss treatment options?

**Patient**: Yes, please, I would really appreciate you explaining it to me and discussing how we can treat it. It is actually a huge relief to finally have a name for what I've been struggling with for over two years. I am very open to finding any ways to help manage this constant worry.
