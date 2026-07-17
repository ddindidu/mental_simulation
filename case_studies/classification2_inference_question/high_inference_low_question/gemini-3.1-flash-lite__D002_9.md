# Case D002_9 — gemini-3.1-flash-lite

**Category axis:** Classification 2: high_inference_low_question

- Ground truth disease: `D002`
- Final diagnosis: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
- Correct: True
- Closed at patient turn: 5

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
| 1 | Beyond your difficulty with focus, do you also frequently find yourself feeling restless, fidgety, or acting impulsively without thinking things through? | 0.00 | 0 | 0 | 0.00 |
| 2 | To better understand your history, have these difficulties with focus been present since you were a child, or is this a more recent change in your life? | n/a (single candidate) | 0 | 0 | 0.00 |
| 3 | Besides difficulty focusing, do you frequently lose things necessary for tasks, find yourself easily distracted by external stimuli, or struggle to organize your daily activities? | n/a (single candidate) | 0 | 0 | 0.00 |
| 4 | Do you often make careless mistakes in your work, struggle to follow through on instructions, or find yourself avoiding tasks that require sustained mental effort? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. I'm here to help. Could you please tell me what brings you in to see me today?

**Patient**: Hi, Dr. Smith. I'm here today because I've been struggling a lot with paying attention and staying focused on my tasks and activities. It just feels really hard for me to keep my mind on one thing for very long.

**Doctor**: Beyond your difficulty with focus, do you also frequently find yourself feeling restless, fidgety, or acting impulsively without thinking things through?

**Patient**: No, I don't really experience restlessness or fidgeting, and I wouldn't say I act impulsively. My main struggles are really just with focusing and sustaining my attention on my tasks.

**Doctor**: To better understand your history, have these difficulties with focus been present since you were a child, or is this a more recent change in your life?

**Patient**: These focus issues aren't new; I've actually struggled with them since I was a kid, definitely before I turned 12. However, they have been consistently troublesome and really hard to manage for the last two years and five months.

**Doctor**: Besides difficulty focusing, do you frequently lose things necessary for tasks, find yourself easily distracted by external stimuli, or struggle to organize your daily activities?

**Patient**: I don't really experience those specific problems. I don't tend to lose things, get easily distracted, or have much trouble organizing, as those aren't my main issues. It's really just the struggle of keeping my mind on a task once I've started.

**Doctor**: Do you often make careless mistakes in your work, struggle to follow through on instructions, or find yourself avoiding tasks that require sustained mental effort?

**Patient**: I wouldn't say careless mistakes are my main issue, but I definitely struggle with avoiding tasks that require deep, prolonged concentration. I often procrastinate or feel a really strong reluctance to even start projects that need a lot of sustained mental effort.
