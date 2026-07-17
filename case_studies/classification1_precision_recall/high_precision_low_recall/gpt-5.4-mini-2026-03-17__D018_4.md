# Case D018_4 — gpt-5.4-mini-2026-03-17

**Category axis:** Classification 1: high_precision_low_recall

- Ground truth disease: `D018`
- Final diagnosis: Posttraumatic Stress Disorder
- Correct: True
- Closed at patient turn: 4

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 1.000 | 0.900 | high |
| Recall | 0.091 | 0.500 | low |
| Inference quality (jaccard) | 0.091 | 0.426 | low |
| Question reasonability (composite) | 0.000 | 0.100 | low |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | Do you find yourself avoiding places, people, or situations that remind you of the traumatic event? | n/a (single candidate) | 0 | 0 | 0.00 |
| 2 | Have you also been feeling constantly on edge, jumpy, or having trouble sleeping because of this? | n/a (single candidate) | 0 | 0 | 0.00 |
| 3 | Have these symptoms been going on for more than one month? | n/a (single candidate) | 0 | 0 | 0.00 |

## Dialogue transcript

**Doctor**: Hello, I’m glad you came in today. What brings you in?

**Patient**: I'm here because I can't stop having these awful, intrusive memories and nightmares about a traumatic event from almost two years ago. It feels like I'm constantly re-living it, and I'm just so exhausted. I really need some help to make them stop.

**Doctor**: Do you find yourself avoiding places, people, or situations that remind you of the traumatic event?

**Patient**: Yes, absolutely. I go completely out of my way to avoid the area where it happened, and I've distanced myself from anyone who reminds me of that time. Just encountering anything related to it triggers intense distress and brings the memories flooding right back.

**Doctor**: Have you also been feeling constantly on edge, jumpy, or having trouble sleeping because of this?

**Patient**: Yes, I'm constantly on edge and jump at the slightest noise or sudden movement. Sleeping has also been a nightmare; I struggle to fall asleep, wake up constantly, and am always plagued by terrible dreams about what happened.

**Doctor**: Have these symptoms been going on for more than one month?

**Patient**: Yes, absolutely. It's been going on for much longer than a month—actually, it's been about one year and eleven months now, almost two years. It has been a constant struggle every single day since it happened.
