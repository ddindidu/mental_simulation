# Case D005_7 — gemini-3.1-flash-lite

**Category axis:** Classification 2: high_inference_high_question

- Ground truth disease: `D005`
- Final diagnosis: Schizophrenia
- Correct: True
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.667 | 0.900 | low |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 0.667 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Besides the voices and visions, have you experienced any periods where your mood was unusually high, energetic, or irritable, or conversely, periods where you felt persistently sad, hopeless, or lacked energy? | 0.00 | 0 | 0 | 0.10 |
| 2 | Beyond the voices and visions, have you noticed a decrease in your motivation to do things, a tendency to withdraw from friends and family, or a feeling that you have less interest in your usual hobbies? | 0.00 | 0 | 0 | 0.10 |
| 3 | Are the voices and visions you experience related to a specific, singular belief—such as the idea that someone is following you or that you have a special identity—or are your experiences more disorganized and varied in nature? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: I'm here because I've been hearing voices and seeing things that other people tell me aren't actually there. This has been happening to me for about a year and three months now. I just really need some help figuring out why this is happening to me.

**Doctor**: Besides the voices and visions, have you experienced any periods where your mood was unusually high, energetic, or irritable, or conversely, periods where you felt persistently sad, hopeless, or lacked energy?

**Patient**: No, I haven't really experienced anything like that. I don't get those kinds of extreme highs or feel persistently sad and hopeless. My mood has been pretty much the same, it's just the things I'm seeing and hearing that trouble me.

**Doctor**: Beyond the voices and visions, have you noticed a decrease in your motivation to do things, a tendency to withdraw from friends and family, or a feeling that you have less interest in your usual hobbies?

**Patient**: No, I haven't really noticed any issues with that. My motivation and interest in my hobbies seem about the same as usual, and I haven't been withdrawing from my family or friends.

**Doctor**: Are the voices and visions you experience related to a specific, singular belief—such as the idea that someone is following you or that you have a special identity—or are your experiences more disorganized and varied in nature?

**Patient**: No, they aren't tied to any specific belief like someone following me or me being someone special. It's much more jumbled and disconnected than that, and my thoughts feel really disorganized. Sometimes it is just really hard to keep my thoughts or my speech on track because everything feels so scattered.
