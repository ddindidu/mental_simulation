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

> **Judge (symptom extraction)** — confirmed: S029 Fatigue, S069 Intrusive_Symptoms
> denied: (none)
> - S029 Fatigue: The patient explicitly states that they are 'just so exhausted' due to their ongoing symptoms.
> - S069 Intrusive_Symptoms: The patient reports experiencing awful, intrusive memories and nightmares about a traumatic event, describing it as constantly re-living the experience.

> Doctor's inference — candidates: Posttraumatic Stress Disorder
> Previously no candidate list was provided. The patient describes persistent intrusive memories and nightmares about a traumatic event nearly two years ago, with re-experiencing that is characteristic of PTSD. At this point, PTSD is the leading and only supported candidate from the allowed list, though more history about avoidance, hyperarousal, mood, and functional impairment would help confirm it.

> **Judge (inference scoring)** — predicted: D018
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=0 FN=10 | precision=1.00 recall=0.09 accuracy=0.00 jaccard=0.09 weighted_recall=0.17

**Doctor**: Do you find yourself avoiding places, people, or situations that remind you of the traumatic event?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, absolutely. I go completely out of my way to avoid the area where it happened, and I've distanced myself from anyone who reminds me of that time. Just encountering anything related to it triggers intense distress and brings the memories flooding right back.

> **Judge (symptom extraction)** — confirmed: S069 Intrusive_Symptoms, S070 Trauma_Avoidance
> denied: (none)
> - S069 Intrusive_Symptoms: The patient reports that encountering reminders triggers intense distress and brings memories flooding back, which aligns with intrusive symptoms and psychological distress at cues.
> - S070 Trauma_Avoidance: The patient explicitly states they go out of their way to avoid the area where the event occurred and distance themselves from people who remind them of it, indicating trauma avoidance.

> Doctor's inference — candidates: Posttraumatic Stress Disorder
> Previously the only candidate was Posttraumatic Stress Disorder, and the new information strongly supports it rather than shifting the differential. The patient describes intrusive memories, nightmares, re-experiencing, avoidance of reminders, and marked distress triggered by cues related to the trauma, all occurring nearly two years after the event. No evidence has emerged for mood episodes, psychosis, OCD, or an anxiety disorder unrelated to trauma, so the candidate list remains unchanged.

> **Judge (inference scoring)** — predicted: D018
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=0 FN=10 | precision=1.00 recall=0.09 accuracy=0.00 jaccard=0.09 weighted_recall=0.17

**Doctor**: Have you also been feeling constantly on edge, jumpy, or having trouble sleeping because of this?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, I'm constantly on edge and jump at the slightest noise or sudden movement. Sleeping has also been a nightmare; I struggle to fall asleep, wake up constantly, and am always plagued by terrible dreams about what happened.

> **Judge (symptom extraction)** — confirmed: S027 Sleep_Disturbance, S058 Restlessness_Tension, S069 Intrusive_Symptoms, S080 Exaggerated_Startle_Response
> denied: (none)
> - S027 Sleep_Disturbance: The patient reports struggling to fall asleep and waking up constantly, which indicates sleep disturbance.
> - S058 Restlessness_Tension: The patient states they are 'constantly on edge,' which directly corresponds to feeling keyed up or on edge.
> - S069 Intrusive_Symptoms: The patient describes being plagued by terrible dreams about what happened, which represents intrusive distressing dreams of a past event.
> - S080 Exaggerated_Startle_Response: The patient reports jumping at the slightest noise or sudden movement, which is a clear description of an exaggerated startle response.

> Doctor's inference — candidates: Posttraumatic Stress Disorder
> Previously the only candidate was Posttraumatic Stress Disorder, and the conversation continues to strongly support it: the patient has a qualifying traumatic event, intrusive memories and nightmares, avoidance of reminders, and hyperarousal with exaggerated startle and sleep disturbance lasting almost two years. No new evidence suggests an alternative diagnosis, so the candidate list remains unchanged.

> **Judge (inference scoring)** — predicted: D018
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=0 FN=10 | precision=1.00 recall=0.09 accuracy=0.00 jaccard=0.09 weighted_recall=0.17

**Doctor**: Have these symptoms been going on for more than one month?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=0 redundancy_penalty=0 composite=0.00

**Patient**: Yes, absolutely. It's been going on for much longer than a month—actually, it's been about one year and eleven months now, almost two years. It has been a constant struggle every single day since it happened.

> **Judge (symptom extraction)** — confirmed: (none)
> denied: (none)

> Doctor's inference (final) — candidates: Posttraumatic Stress Disorder
> Previously the only candidate was Posttraumatic Stress Disorder, and the interview strongly supports keeping it as the sole diagnosis. The patient describes a trauma exposure followed by persistent intrusive memories, nightmares, avoidance of reminders, hyperarousal/startle, sleep disturbance, and duration of nearly two years, which fits PTSD well. No new information suggests an alternative diagnosis, so the candidate list remains unchanged.

> **Judge (inference scoring)** — predicted: D018
> reference (truth) set: D006, D007, D008, D009, D010, D011, D013, D014, D015, D018, D019
> TP=1 FP=0 FN=10 | precision=1.00 recall=0.09 accuracy=0.00 jaccard=0.09 weighted_recall=0.17
