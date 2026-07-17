# Case D017_4 — gemini-3.5-flash

**Category axis:** Classification 1: low_precision_high_recall

- Ground truth disease: `D017`
- Final diagnosis: Body Dysmorphic Disorder
- Correct: True
- Closed at patient turn: 5

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.500 | 0.900 | low |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 0.500 | 0.426 | high |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.250 | 0.000 | high |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Have friends, family, or doctors told you that they don't really notice these scars, or that they seem very minor to them? | 0.00 | 0 | 0 | 0.10 |
| 2 | Do you find yourself spending a lot of time each day checking your face in the mirror, trying to hide these scars, or picking at your skin? | 0.00 | 0 | 0 | 0.10 |
| 3 | Aside from your concerns about your skin and appearance, do you experience other repetitive thoughts or urges to perform rituals, like excessive cleaning, checking locks, or needing things to be in a perfect order? | 0.00 | 0 | 0 | 0.10 |
| 4 | Is there any part of you that thinks your view of your face might be exaggerated, or are you absolutely certain that your face is deformed and everyone else is wrong? | 0.00 | 1 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello. I'm glad you're here today. What brings you in to see me?

**Patient**: I'm here because I'm really distressed about how terrible my skin and face look. I have these awful acne scars and flaws all over my face that make me look hideous, and I really need to find a way to fix them.

**Doctor**: Have friends, family, or doctors told you that they don't really notice these scars, or that they seem very minor to them?

**Patient**: Yes, my family and even some doctors keep telling me they can barely see anything and that my skin looks fine. It's incredibly frustrating because to me, these scars are so obvious and completely ruin my face. I don't understand how they can just dismiss them like that.

**Doctor**: Do you find yourself spending a lot of time each day checking your face in the mirror, trying to hide these scars, or picking at your skin?

**Patient**: Yes, I spend hours in front of the mirror every day obsessing over them, and I have to use layers of heavy makeup just to try and hide how awful I look. I also constantly pick at my skin to try and smooth out the scars, but it just makes me feel even more distressed and self-conscious.

**Doctor**: Aside from your concerns about your skin and appearance, do you experience other repetitive thoughts or urges to perform rituals, like excessive cleaning, checking locks, or needing things to be in a perfect order?

**Patient**: No, I don't experience anything like that. I don't have any urges to constantly clean things or check locks. My worries and habits are really just focused on my face and trying to fix how I look.

**Doctor**: Is there any part of you that thinks your view of your face might be exaggerated, or are you absolutely certain that your face is deformed and everyone else is wrong?

**Patient**: I'm really not sure, and I feel very conflicted about it. When I look in the mirror, the flaws look so real and terrible to me, but everyone else keeps telling me my skin is fine. Part of me wonders if I'm exaggerating, but it's just so hard to believe they are right when I see it so clearly.
