# Case D017_3 — gemini-3.5-flash

**Category axis:** Classification 1: low_precision_high_recall

- Ground truth disease: `D017`
- Final diagnosis: Body Dysmorphic Disorder
- Correct: True
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.500 | 0.900 | low |
| Recall | 1.000 | 0.500 | high |
| Inference quality (jaccard) | 0.500 | 0.426 | high |
| Question reasonability (composite) | 0.067 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.333 | 0.000 | high |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Do you find yourself spending a lot of time doing things like checking your appearance in the mirror, grooming, picking at your skin, or asking others for reassurance about how you look? | 0.00 | 0 | 0 | 0.10 |
| 2 | Aside from your concerns about your appearance, do you experience other repetitive thoughts or behaviors, such as a need to constantly wash your hands, check locks, or arrange objects in a specific order? | 0.00 | 0 | 0 | 0.10 |
| 3 | How convinced are you that these flaws on your face are as bad as you see them? Do you feel absolutely certain they are real, or is there a part of you that thinks your mind might be exaggerating them? | n/a (single candidate) | 1 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello. What brings you in to see me today?

**Patient**: I'm here because I'm just so incredibly distressed about how my face looks. I can't stop obsessing over the terrible acne and scars on my skin, and my nose feels completely asymmetrical and ugly. Everyone else keeps telling me it looks totally normal, but I just can't see it that way.

**Doctor**: Do you find yourself spending a lot of time doing things like checking your appearance in the mirror, grooming, picking at your skin, or asking others for reassurance about how you look?

**Patient**: Yes, I spend hours every day doing those exact things. I constantly check my reflection in mirrors or any shiny surface I pass, and I often pick at my skin for hours trying to 'fix' the flaws. I also constantly ask my family if my face looks okay because I feel so insecure, but I can never bring myself to believe them.

**Doctor**: Aside from your concerns about your appearance, do you experience other repetitive thoughts or behaviors, such as a need to constantly wash your hands, check locks, or arrange objects in a specific order?

**Patient**: No, I don't experience anything like that. I don't feel any need to constantly wash my hands or check locks; all of my anxiety and habits are strictly focused on my face and how I look.

**Doctor**: How convinced are you that these flaws on your face are as bad as you see them? Do you feel absolutely certain they are real, or is there a part of you that thinks your mind might be exaggerating them?

**Patient**: I am absolutely certain they are real and exactly as bad as I see them. It is incredibly frustrating when people suggest I'm exaggerating, because my skin and nose look absolutely terrible to me and I can't see them any other way. There is no doubt in my mind that these flaws are completely real.
