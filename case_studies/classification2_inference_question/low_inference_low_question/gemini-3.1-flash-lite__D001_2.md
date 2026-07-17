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

**Doctor**: Beyond difficulty focusing, do you also frequently find yourself feeling restless, fidgeting often, or acting without thinking before others have finished speaking?

**Patient**: Yes, I definitely feel very restless, almost like I am constantly "on the go" or driven by a motor. I also tend to talk excessively quite a bit. As for fidgeting or acting without thinking, I'm not really sure about those.

**Doctor**: Since you mentioned having trouble listening, do you also frequently make careless mistakes in your work or struggle to keep track of your belongings and daily tasks?

**Patient**: To be honest, I don't really experience making careless mistakes in my work. Losing track of my belongings or daily tasks hasn't really been a major issue for me either.

**Doctor**: Do you often find yourself interrupting others during conversations or having significant difficulty waiting your turn in social or professional situations?

**Patient**: To be honest, I don't think I do that very often. I haven't really noticed interrupting others or having trouble waiting my turn being much of an issue for me.

**Doctor**: Have you experienced these symptoms of restlessness and difficulty with sustained attention consistently since you were a child, or did they only begin recently?

**Patient**: They actually started back when I was a kid, definitely before I was 12 years old. While I've had these struggles for a long time, they've been particularly noticeable and constant for the last year and three months.

**Doctor**: Regarding the difficulty with sustained attention you mentioned, does this occur in multiple settings, such as both at home and at work or school, rather than just in one specific environment?

**Patient**: I'm not entirely sure, to be honest. I haven't really thought about whether it happens in all of those different places or if it's just in specific situations.

**Doctor**: When you are in a situation that requires intense focus, like a meeting or a long lecture, do you find that your mind wanders frequently or that you struggle to stay engaged even when you are trying your hardest?

**Patient**: Yes, definitely. My mind constantly wanders during those times, and I find it incredibly hard to stay engaged in long meetings or lectures. Because of that, I often dread and try to avoid tasks that require that kind of sustained mental effort.

**Doctor**: Besides feeling restless and talking excessively, do you often find yourself unable to remain seated in situations where it is expected, such as during a meal or at your desk?

**Patient**: No, I don't really experience difficulty staying seated, even during meals or at my desk. I haven't noticed that being a significant issue for me.
