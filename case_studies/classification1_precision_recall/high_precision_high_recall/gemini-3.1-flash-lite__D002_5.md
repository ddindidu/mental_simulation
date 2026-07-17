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

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Combined Presentation), Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient reports significant difficulties with sustained attention, listening, and organization, which are hallmark symptoms of ADHD. I have narrowed the candidates to the two most likely presentations of ADHD. I need to determine if hyperactive or impulsive symptoms are also present to differentiate between the two.

**Doctor**: Beyond the difficulty focusing, do you often find yourself feeling restless, fidgety, or struggling to remain seated when you are expected to?

**Patient**: No, I wouldn't say I struggle with feeling restless or staying seated. I haven't really noticed those kinds of physical issues, it's more just my mind drifting away.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient explicitly denied symptoms of physical restlessness or hyperactivity, which makes the Combined Presentation unlikely and strongly supports the Predominantly Inattentive Presentation.

**Doctor**: Have you noticed these difficulties with focus and organization since you were a child, or is this a more recent development in your life?

**Patient**: Looking back, I've definitely had these focus issues since I was a kid, well before I turned 12. However, it has become a really constant, major struggle for about the last year and three months.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient's clinical presentation of persistent inattention, lack of hyperactivity/impulsivity, and symptom onset prior to age 12 remains consistent with ADHD (Predominantly Inattentive Presentation). I need to rule out other potential causes for the recent worsening of symptoms, such as mood or anxiety disorders, before finalizing.

**Doctor**: Do these challenges with focus and organization cause significant problems for you in at least two different areas of your life, such as at work, at school, or in your personal relationships?

**Patient**: I'm not really sure, to be honest. I haven't thought much about how it specifically affects different areas of my life like work or my relationships. I just know it's been a constant struggle for me lately.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient's report of long-standing, childhood-onset difficulties with focus and organization, combined with a clear absence of hyperactivity or impulsivity, remains consistent with the Predominantly Inattentive presentation of ADHD. I need to further assess the functional impairment across different settings (e.g., work, home, social) to confirm the diagnostic criteria for clinical significance.

**Doctor**: Can you give me an example of a specific task at work or a situation in your personal life where this lack of focus has caused you to miss a deadline, make a mistake, or lead to a misunderstanding with someone?

**Patient**: Just last week, I kept putting off a big project report because organizing all that information required so much mental effort and I just couldn't face it. When I finally tried to do it, I realized I had completely missed the instructions my coworker had explained to me directly. It was a total mess and I ended up missing the deadline, which was really frustrating.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient confirms long-standing (childhood onset) symptoms of inattention without significant hyperactive or impulsive symptoms. The recent example of missing a work deadline due to organizational and attentional deficits further supports the diagnosis. I need to clarify if these difficulties persist across multiple settings (e.g., home/social life vs. just work) to confirm the diagnostic criteria.

**Doctor**: Besides the project report, have you experienced similar instances of forgetting appointments, losing important personal items, or failing to follow through on instructions in your home life or social activities?

**Patient**: I don't really experience those specific issues. I don't usually lose my things or forget appointments, so that hasn't been a problem for me.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The candidate remains the same as the patient consistently reports inattentive symptoms since childhood without hyperactive or impulsive behaviors. Further inquiry is needed to confirm if these symptoms meet the DSM-5 criteria for functional impairment across multiple settings.

**Doctor**: Do you often find that you make careless mistakes in your work because you have difficulty paying close attention to details, or do you struggle to sustain your attention during lengthy meetings or while reading documents?

**Patient**: I don't really think I have those specific issues with making careless mistakes or struggling to pay attention in meetings. I'm not really sure about that, as it hasn't stood out to me as a major problem.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The candidate remains the same as the patient reports long-standing (since childhood) inattentive symptoms that cause functional impairment (missed deadlines). However, the patient denies many of the other core diagnostic criteria (losing items, careless mistakes, sustaining attention in meetings), suggesting the symptoms may not meet the full threshold for an ADHD diagnosis. I need to continue to assess the breadth of the impairment and rule out other potential causes for the focus issues.

**Doctor**: Do you find that you frequently lose focus or your mind wanders when you are engaged in tasks that require sustained mental effort, even if you don't consider them 'meetings'?

**Patient**: Yes, I struggle with that a lot. Because my mind wanders so easily and I lose focus almost immediately, I find myself actively avoiding or procrastinating on any tasks that require prolonged mental effort. I just feel a really strong reluctance to even start them.

> Doctor's inference — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The patient confirms long-standing (since childhood) symptoms of inattention, specifically difficulty sustaining mental effort and avoidance of tasks requiring such effort. The patient denies hyperactive/impulsive symptoms. While the patient is unsure about impairment across multiple domains, the reported missed deadline and frustration indicate functional impairment. The candidate list remains unchanged as the symptoms consistently align with the inattentive presentation.

**Doctor**: Do you find that you have significant difficulty keeping your work materials, calendar, or workspace organized, often leading to a sense of being overwhelmed by clutter or a lack of structure?

**Patient**: Yes, absolutely. I struggle significantly with keeping my workspace, calendar, and daily tasks organized. This constant clutter and lack of structure leaves me feeling really overwhelmed and stressed out.

> Doctor's inference (final) — candidates: Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)
> The candidates remain the same. The patient's history of symptoms starting before age 12, the clear pattern of inattention and executive dysfunction (difficulty with sustained mental effort, procrastination, and poor organization), and the explicit denial of hyperactive/impulsive symptoms continue to strongly support the Predominantly Inattentive Presentation of ADHD. I have sufficient information to confirm the diagnostic criteria.
