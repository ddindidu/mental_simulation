# Case D004_3 — gemini-3.1-flash-lite

**Category axis:** Classification 2: high_inference_high_question

- Ground truth disease: `D004`
- Final diagnosis: Delusional Disorder
- Correct: True
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.750 | 0.500 | high |
| Inference quality (jaccard) | 0.750 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Besides these feelings of being followed, have you experienced any significant periods where your mood felt unusually high, energetic, or conversely, very low and hopeless? | 0.00 | 0 | 0 | 0.10 |
| 2 | Beyond the feeling of being followed, have you noticed any changes in your ability to keep up with daily tasks, or have you found yourself becoming more withdrawn from friends and social activities? | 0.00 | 0 | 0 | 0.10 |
| 3 | Have you ever heard voices or seen things that others around you do not seem to hear or see, or have you had any other unusual sensory experiences? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: I'm here because I'm being constantly monitored and followed by a specific group of people. I can't shake the feeling that they are tracking my every move, and I just don't feel safe anymore.

**Doctor**: Besides these feelings of being followed, have you experienced any significant periods where your mood felt unusually high, energetic, or conversely, very low and hopeless?

**Patient**: I haven't really experienced those kinds of extreme mood swings. My mood generally stays pretty level, and I don't have periods of feeling unusually high or very hopeless. I'm mostly just stressed about the constant monitoring.

**Doctor**: Beyond the feeling of being followed, have you noticed any changes in your ability to keep up with daily tasks, or have you found yourself becoming more withdrawn from friends and social activities?

**Patient**: My ability to handle my daily chores and tasks is generally fine, and I can take care of myself. However, I have been staying inside much more and avoiding social activities lately. I'm only doing that to stay safe and avoid the people who are constantly tracking and monitoring me.

**Doctor**: Have you ever heard voices or seen things that others around you do not seem to hear or see, or have you had any other unusual sensory experiences?

**Patient**: No, I have never experienced anything like that. I don't hear voices or see things that aren't there, and my senses are completely normal. My concern is strictly about the very real people who are physically following and monitoring me.
