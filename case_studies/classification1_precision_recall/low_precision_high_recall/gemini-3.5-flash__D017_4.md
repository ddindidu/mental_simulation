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

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance
> denied: (none)
> - S067 Preoccupation_with_Appearance: The patient expresses significant distress and preoccupation with perceived flaws on their face and skin (acne scars), describing them as making them look 'hideous'.

> Doctor's inference — candidates: Body Dysmorphic Disorder, Obsessive-Compulsive Disorder, Delusional Disorder
> The patient presents with severe distress regarding perceived flaws in their physical appearance (acne scars and facial flaws) which they describe as making them look 'hideous'. This presentation is highly characteristic of Body Dysmorphic Disorder (BDD). Obsessive-Compulsive Disorder is included in the differential due to the repetitive, obsessive nature of these thoughts, and Delusional Disorder (somatic type) is considered depending on the level of insight the patient has regarding these perceived flaws.

> **Judge (inference scoring)** — predicted: D004, D016, D017
> reference (truth) set: D017
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00

**Doctor**: Have friends, family, or doctors told you that they don't really notice these scars, or that they seem very minor to them?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: Yes, my family and even some doctors keep telling me they can barely see anything and that my skin looks fine. It's incredibly frustrating because to me, these scars are so obvious and completely ruin my face. I don't understand how they can just dismiss them like that.

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance
> denied: (none)
> - S067 Preoccupation_with_Appearance: The patient describes a strong preoccupation with facial scars that they perceive as obvious and ruining their face, despite family and doctors stating they can barely see anything and that the skin looks fine.

> Doctor's inference — candidates: Body Dysmorphic Disorder, Obsessive-Compulsive Disorder, Delusional Disorder
> The patient describes a preoccupation with perceived physical flaws (acne scars) that others do not see or see as minor, which is highly characteristic of Body Dysmorphic Disorder. Delusional Disorder (Somatic Type) and OCD remain in the differential as we need to explore the degree of insight, repetitive behaviors (like mirror checking or skin picking), and the overall impact on functioning.

> **Judge (inference scoring)** — predicted: D004, D016, D017
> reference (truth) set: D017
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00

**Doctor**: Do you find yourself spending a lot of time each day checking your face in the mirror, trying to hide these scars, or picking at your skin?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: Yes, I spend hours in front of the mirror every day obsessing over them, and I have to use layers of heavy makeup just to try and hide how awful I look. I also constantly pick at my skin to try and smooth out the scars, but it just makes me feel even more distressed and self-conscious.

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance, S068 Appearance_Related_Repetitive_Behaviors
> denied: (none)
> - S067 Preoccupation_with_Appearance: The patient describes obsessing over perceived physical flaws and feeling that they look 'awful' and 'self-conscious.'
> - S068 Appearance_Related_Repetitive_Behaviors: The patient engages in multiple repetitive behaviors in response to appearance concerns, including mirror checking ('spend hours in front of the mirror'), excessive camouflaging ('use layers of heavy makeup'), and skin picking ('constantly pick at my skin').

> Doctor's inference — candidates: Body Dysmorphic Disorder, Obsessive-Compulsive Disorder, Delusional Disorder
> The patient describes a severe preoccupation with perceived physical flaws (acne scars) that others do not notice, accompanied by repetitive behaviors (mirror checking, skin picking, heavy makeup). This strongly aligns with Body Dysmorphic Disorder (BDD). However, we need to rule out Obsessive-Compulsive Disorder (by checking for non-appearance-related obsessions/compulsions) and Delusional Disorder (by assessing the degree of insight and presence of other delusions) before making a final diagnosis.

> **Judge (inference scoring)** — predicted: D004, D016, D017
> reference (truth) set: D017
> TP=1 FP=2 FN=0 | precision=0.33 recall=1.00 accuracy=0.00 jaccard=0.33 weighted_recall=1.00

**Doctor**: Aside from your concerns about your skin and appearance, do you experience other repetitive thoughts or urges to perform rituals, like excessive cleaning, checking locks, or needing things to be in a perfect order?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=0 redundancy_penalty=0 composite=0.10

**Patient**: No, I don't experience anything like that. I don't have any urges to constantly clean things or check locks. My worries and habits are really just focused on my face and trying to fix how I look.

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance, S068 Appearance_Related_Repetitive_Behaviors
> denied: S065 Obsessions, S066 Compulsions
> - S065 Obsessions: The patient explicitly denies having urges to constantly clean things, which are characteristic of obsessions.
> - S066 Compulsions: The patient explicitly denies having compulsive behaviors such as checking locks.
> - S067 Preoccupation_with_Appearance: The patient confirms that their worries are focused on their face, indicating a preoccupation with their appearance.
> - S068 Appearance_Related_Repetitive_Behaviors: The patient mentions habits focused on 'trying to fix how I look,' which represents appearance-related repetitive behaviors.

> Doctor's inference — candidates: Body Dysmorphic Disorder, Delusional Disorder
> Previously, the candidates included Obsessive-Compulsive Disorder, but the patient denied having any other repetitive rituals or obsessive thoughts unrelated to their appearance, making OCD unlikely. The remaining candidates are Body Dysmorphic Disorder and Delusional Disorder (somatic type), as the patient exhibits a strong, potentially delusional conviction regarding minor or unnoticeable physical flaws.

> **Judge (inference scoring)** — predicted: D004, D017
> reference (truth) set: D017
> TP=1 FP=1 FN=0 | precision=0.50 recall=1.00 accuracy=0.00 jaccard=0.50 weighted_recall=1.00

**Doctor**: Is there any part of you that thinks your view of your face might be exaggerated, or are you absolutely certain that your face is deformed and everyone else is wrong?

> **Judge (question scoring)** — targeted symptoms: (none)
> DCS=0.00 kg_edge_fraction=1.0 edge_alignment=1.0 mandatory_first_compliance=1 redundancy_penalty=0 composite=0.10

**Patient**: I'm really not sure, and I feel very conflicted about it. When I look in the mirror, the flaws look so real and terrible to me, but everyone else keeps telling me my skin is fine. Part of me wonders if I'm exaggerating, but it's just so hard to believe they are right when I see it so clearly.

> **Judge (symptom extraction)** — confirmed: S067 Preoccupation_with_Appearance, S068 Appearance_Related_Repetitive_Behaviors
> denied: (none)
> - S067 Preoccupation_with_Appearance: The patient describes seeing 'flaws' on her skin that look 'real and terrible' to her, despite others telling her that her skin is fine, which aligns with preoccupation with unnoticeable physical flaws.
> - S068 Appearance_Related_Repetitive_Behaviors: The patient mentions looking in the mirror to examine these perceived flaws, which represents mirror-checking behavior.

> Doctor's inference (final) — candidates: Body Dysmorphic Disorder
> Previously, the candidates were Body Dysmorphic Disorder and Delusional Disorder. The patient has now clarified that they have some insight and conflict about their appearance beliefs ('Part of me wonders if I'm exaggerating'), which rules out the fixed, unshakeable beliefs of Delusional Disorder. The patient's symptoms—excessive preoccupation with perceived physical flaws, repetitive mirror checking, skin picking, camouflaging, and distress—strongly align with Body Dysmorphic Disorder. Therefore, Delusional Disorder is removed, leaving Body Dysmorphic Disorder as the final diagnosis.

> **Judge (inference scoring)** — predicted: D017
> reference (truth) set: D017
> TP=1 FP=0 FN=0 | precision=1.00 recall=1.00 accuracy=1.00 jaccard=1.00 weighted_recall=1.00
