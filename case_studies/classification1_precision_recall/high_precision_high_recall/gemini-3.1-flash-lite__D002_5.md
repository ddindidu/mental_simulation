# Case D002_5 — gemini-3.1-flash-lite

**Category axis:** Classification 1: high_precision_high_recall

- Ground truth disease: `D002`
- Final diagnosis: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
- Correct: True
- Closed at patient turn: 9

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.967 | 0.500 | high |
| Inference quality (jaccard) | 0.967 | 0.426 | high |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.125 | 0.000 | high |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Beyond the difficulty focusing, do you often find yourself feeling restless, fidgety, or struggling to remain seated when you are expected to? | 0.00 | 0 | 0 | 0.00 |
| 2 | Have you noticed these difficulties with focus and organization since you were a child, or is this a more recent development in your life? | n/a (single candidate) | 0 | 0 | 0.00 |
| 3 | Do these challenges with focus and organization cause significant problems for you in at least two different areas of your life, such as at work, at school, or in your personal relationships? | n/a (single candidate) | 0 | 0 | 0.00 |
| 4 | Can you give me an example of a specific task at work or a situation in your personal life where this lack of focus has caused you to miss a deadline, make a mistake, or lead to a misunderstanding with someone? | n/a (single candidate) | 0 | 0 | 0.00 |
| 5 | Besides the project report, have you experienced similar instances of forgetting appointments, losing important personal items, or failing to follow through on instructions in your home life or social activities? | n/a (single candidate) | 0 | 0 | 0.00 |
| 6 | Do you often find that you make careless mistakes in your work because you have difficulty paying close attention to details, or do you struggle to sustain your attention during lengthy meetings or while reading documents? | n/a (single candidate) | 0 | 0 | 0.00 |
| 7 | Do you find that you frequently lose focus or your mind wanders when you are engaged in tasks that require sustained mental effort, even if you don't consider them 'meetings'? | n/a (single candidate) | 0 | 0 | 0.00 |
| 8 | Do you find that you have significant difficulty keeping your work materials, calendar, or workspace organized, often leading to a sense of being overwhelmed by clutter or a lack of structure? | n/a (single candidate) | 1 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: Honestly, I've been struggling a lot lately with listening to people when they talk directly to me. It feels like my mind just wanders off, and I'm having a really hard time focusing and staying organized because of it.

**Doctor**: Beyond the difficulty focusing, do you often find yourself feeling restless, fidgety, or struggling to remain seated when you are expected to?

**Patient**: No, I wouldn't say I struggle with feeling restless or staying seated. I haven't really noticed those kinds of physical issues, it's more just my mind drifting away.

**Doctor**: Have you noticed these difficulties with focus and organization since you were a child, or is this a more recent development in your life?

**Patient**: Looking back, I've definitely had these focus issues since I was a kid, well before I turned 12. However, it has become a really constant, major struggle for about the last year and three months.

**Doctor**: Do these challenges with focus and organization cause significant problems for you in at least two different areas of your life, such as at work, at school, or in your personal relationships?

**Patient**: I'm not really sure, to be honest. I haven't thought much about how it specifically affects different areas of my life like work or my relationships. I just know it's been a constant struggle for me lately.

**Doctor**: Can you give me an example of a specific task at work or a situation in your personal life where this lack of focus has caused you to miss a deadline, make a mistake, or lead to a misunderstanding with someone?

**Patient**: Just last week, I kept putting off a big project report because organizing all that information required so much mental effort and I just couldn't face it. When I finally tried to do it, I realized I had completely missed the instructions my coworker had explained to me directly. It was a total mess and I ended up missing the deadline, which was really frustrating.

**Doctor**: Besides the project report, have you experienced similar instances of forgetting appointments, losing important personal items, or failing to follow through on instructions in your home life or social activities?

**Patient**: I don't really experience those specific issues. I don't usually lose my things or forget appointments, so that hasn't been a problem for me.

**Doctor**: Do you often find that you make careless mistakes in your work because you have difficulty paying close attention to details, or do you struggle to sustain your attention during lengthy meetings or while reading documents?

**Patient**: I don't really think I have those specific issues with making careless mistakes or struggling to pay attention in meetings. I'm not really sure about that, as it hasn't stood out to me as a major problem.

**Doctor**: Do you find that you frequently lose focus or your mind wanders when you are engaged in tasks that require sustained mental effort, even if you don't consider them 'meetings'?

**Patient**: Yes, I struggle with that a lot. Because my mind wanders so easily and I lose focus almost immediately, I find myself actively avoiding or procrastinating on any tasks that require prolonged mental effort. I just feel a really strong reluctance to even start them.

**Doctor**: Do you find that you have significant difficulty keeping your work materials, calendar, or workspace organized, often leading to a sense of being overwhelmed by clutter or a lack of structure?

**Patient**: Yes, absolutely. I struggle significantly with keeping my workspace, calendar, and daily tasks organized. This constant clutter and lack of structure leaves me feeling really overwhelmed and stressed out.
