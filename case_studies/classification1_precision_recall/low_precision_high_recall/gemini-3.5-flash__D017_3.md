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

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance
> denied: (none)
> - S067 Preoccupation_with_Appearance: The patient expresses extreme distress and preoccupation with perceived flaws in their face (acne, scars, and an asymmetrical nose) that others assure them look completely normal.

> Doctor's inference — candidates: Body Dysmorphic Disorder, Delusional Disorder, Obsessive-Compulsive Disorder
> The patient presents with a preoccupation with perceived defects or flaws in their physical appearance (acne, scars, nose asymmetry) that are not observable or appear slight to others. This strongly suggests Body Dysmorphic Disorder. Delusional Disorder (somatic type) is a differential if these beliefs are held with delusional intensity. Obsessive-Compulsive Disorder is also in the differential due to the obsessive nature of the thoughts.

> **Judge (inference scoring)** — predicted: D004, D016, D017
> reference (truth) set: D017
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00

**Doctor**: Do you find yourself spending a lot of time doing things like checking your appearance in the mirror, grooming, picking at your skin, or asking others for reassurance about how you look?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: Yes, I spend hours every day doing those exact things. I constantly check my reflection in mirrors or any shiny surface I pass, and I often pick at my skin for hours trying to 'fix' the flaws. I also constantly ask my family if my face looks okay because I feel so insecure, but I can never bring myself to believe them.

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance, S068 Appearance_Related_Repetitive_Behaviors
> denied: (none)
> - S067 Preoccupation_with_Appearance: The patient expresses deep insecurity about their face and refers to trying to 'fix' perceived flaws, indicating a preoccupation with their physical appearance.
> - S068 Appearance_Related_Repetitive_Behaviors: The patient describes repetitive behaviors in response to appearance concerns, including constantly checking their reflection, picking at their skin for hours, and repeatedly seeking reassurance from family.

> Doctor's inference — candidates: Body Dysmorphic Disorder, Delusional Disorder, Obsessive-Compulsive Disorder
> The patient's symptoms of preoccupation with perceived defects in physical appearance, repetitive mirror checking, skin picking, and reassurance-seeking are highly characteristic of Body Dysmorphic Disorder (BDD). However, we must keep Delusional Disorder (somatic type) and Obsessive-Compulsive Disorder (OCD) in the differential to explore the degree of conviction in these beliefs and whether there are other non-appearance-related obsessions and compulsions.

> **Judge (inference scoring)** — predicted: D004, D016, D017
> reference (truth) set: D017
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00

**Doctor**: Aside from your concerns about your appearance, do you experience other repetitive thoughts or behaviors, such as a need to constantly wash your hands, check locks, or arrange objects in a specific order?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, I don't experience anything like that. I don't feel any need to constantly wash my hands or check locks; all of my anxiety and habits are strictly focused on my face and how I look.

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance, S068 Appearance_Related_Repetitive_Behaviors
> denied: S066 Compulsions
> - S067 Preoccupation_with_Appearance: The patient states that their anxiety is strictly focused on their face and how they look, indicating a preoccupation with physical appearance.
> - S068 Appearance_Related_Repetitive_Behaviors: The patient mentions having habits strictly focused on their face and appearance, which points to appearance-related repetitive behaviors.
> - S066 Compulsions: The patient explicitly denies having a need to constantly wash their hands or check locks, which are common compulsions.

> Doctor's inference — candidates: 

> **Judge (inference scoring)** — predicted: D017
> reference (truth) set: D017
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00

**Doctor**: How convinced are you that these flaws on your face are as bad as you see them? Do you feel absolutely certain they are real, or is there a part of you that thinks your mind might be exaggerating them?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=n/a (single candidate) kg_edge_fraction=0.0 edge_alignment=None mandatory_first_compliance=1 redundancy_penalty=0 composite=0.00

**Patient**: I am absolutely certain they are real and exactly as bad as I see them. It is incredibly frustrating when people suggest I'm exaggerating, because my skin and nose look absolutely terrible to me and I can't see them any other way. There is no doubt in my mind that these flaws are completely real.

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance
> denied: (none)
> - S067 Preoccupation_with_Appearance: The patient describes a strong, unshakeable preoccupation with perceived flaws in their skin and nose, which others suggest are exaggerated, indicating a preoccupation with physical appearance defects that are not observable or appear slight to others.

> Doctor's inference (final) — candidates: Body Dysmorphic Disorder
> The patient presents with a severe preoccupation with perceived physical flaws (acne, scars, and nose asymmetry) that are not observable or appear slight to others. They engage in repetitive behaviors (mirror checking, skin picking, reassurance seeking) causing significant distress, and have delusional intensity beliefs (absent insight). This presentation meets all DSM-5 criteria for Body Dysmorphic Disorder.

> **Judge (inference scoring)** — predicted: D004, D016, D017
> reference (truth) set: D017
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00
