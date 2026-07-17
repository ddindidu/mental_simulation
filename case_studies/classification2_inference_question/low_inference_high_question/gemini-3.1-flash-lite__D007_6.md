# Case D007_6 — gemini-3.1-flash-lite

**Category axis:** Classification 2: low_inference_high_question

- Ground truth disease: `D007`
- Final diagnosis: Major Depressive Disorder
- Correct: False
- Closed at patient turn: 7

## Metrics (case mean vs. global median)

| Metric | Case mean | Global median | Level |
|---|---|---|---|
| Precision | 0.500 | 0.900 | low |
| Recall | 0.113 | 0.500 | low |
| Inference quality (jaccard) | 0.113 | 0.426 | low |
| Question reasonability (composite) | 0.100 | 0.100 | high |
|  ↳ DCS (discrimination coverage) | 0.000 | 0.000 | at median |
|  ↳ Mandatory-first compliance | 0.000 | 0.000 | at median |
|  ↳ Redundancy penalty (1=violation) | 0.000 | 0.000 | at median |
| Safety screening fully covered | False | | |

## Question reasonability — per-turn breakdown

| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |
|---|---|---|---|---|---|
| 1 | During these past nine months, have you ever experienced periods lasting a few days where you felt unusually energetic, talkative, or productive, to the point where you didn't need much sleep? | 0.00 | 0 | 0 | 0.10 |
| 2 | Have you felt this way every single day for the past nine months, or have there been any periods of a few weeks or months where your mood felt relatively normal or better? | 0.00 | 0 | 0 | 0.10 |
| 3 | Besides feeling sad and exhausted, have you noticed significant changes in your appetite, your sleep patterns, or your ability to concentrate during these past nine months? | 0.00 | 0 | 0 | 0.10 |
| 4 | Have these feelings of emptiness and difficulty concentrating been severe enough to cause you significant problems in your daily functioning, such as at work, school, or in your social relationships? | 0.00 | 0 | 0 | 0.10 |
| 5 | In addition to the sadness, loss of motivation, and concentration issues, have you been feeling unusually worthless, guilty, or experiencing thoughts that life is not worth living? | 0.00 | 0 | 0 | 0.10 |
| 6 | Before this nine-month period began, were you feeling relatively well, or have you experienced similar feelings of sadness and low motivation for two years or longer in the past? | 0.00 | 0 | 0 | 0.10 |

## Dialogue transcript

**Doctor**: Hello, I am Dr. Smith. Could you please tell me what brings you in to see me today?

**Patient**: I'm here because I've been feeling extremely depressed, sad, and completely empty inside for about nine months now. I feel constantly exhausted and have lost all my motivation to do anything. It has just become too hard to get through the day like this.

> Doctor's inference — candidates: Major Depressive Disorder, Persistent Depressive Disorder, Bipolar II Disorder
> The patient reports a 9-month history of depressed mood, exhaustion, and avolition. This duration meets the criteria for Major Depressive Disorder (if symptoms are severe) or Persistent Depressive Disorder. Bipolar II Disorder must be considered in the differential until a history of hypomania is ruled out.

**Doctor**: During these past nine months, have you ever experienced periods lasting a few days where you felt unusually energetic, talkative, or productive, to the point where you didn't need much sleep?

**Patient**: No, I haven't had any times like that at all. It's actually been the complete opposite—I feel constantly exhausted, down, and just completely drained of all my energy.

> Doctor's inference — candidates: Major Depressive Disorder, Persistent Depressive Disorder
> The patient explicitly denied any periods of elevated mood or energy, which significantly lowers the likelihood of Bipolar II Disorder. Given the nine-month duration, both Major Depressive Disorder and Persistent Depressive Disorder remain viable candidates, pending further clarification on the severity and consistency of symptoms.

**Doctor**: Have you felt this way every single day for the past nine months, or have there been any periods of a few weeks or months where your mood felt relatively normal or better?

**Patient**: No, there haven't been any breaks or better days at all. It has been like this every single day for the entire nine months. I just feel constantly heavy and sad without any relief.

> Doctor's inference — candidates: Major Depressive Disorder, Persistent Depressive Disorder
> The patient reports a continuous nine-month period of depressed mood, exhaustion, and lack of motivation without any symptom-free intervals. This duration meets the criteria for both Major Depressive Disorder (which requires at least 2 weeks) and Persistent Depressive Disorder (which requires at least 2 years in adults, though the current symptom profile aligns with both). I need to assess for the presence of specific neurovegetative symptoms (appetite, sleep, concentration, etc.) to determine the severity and specific diagnostic criteria fulfillment.

**Doctor**: Besides feeling sad and exhausted, have you noticed significant changes in your appetite, your sleep patterns, or your ability to concentrate during these past nine months?

**Patient**: Yes, my concentration has been really bad, and my mind often feels completely foggy and dazed, making it hard to even focus on watching TV. However, I haven't noticed any major changes in my appetite or my sleep patterns.

> Doctor's inference — candidates: Major Depressive Disorder, Persistent Depressive Disorder
> The patient reports a persistent low mood for nine months, which meets the duration criteria for both Major Depressive Disorder (if symptoms are severe enough) and Persistent Depressive Disorder (which requires two years, though the current symptoms are consistent with the presentation). I need to clarify the severity of the symptoms to determine if they meet the full criteria for a Major Depressive Episode.

**Doctor**: Have these feelings of emptiness and difficulty concentrating been severe enough to cause you significant problems in your daily functioning, such as at work, school, or in your social relationships?

**Patient**: Yes, they have completely disrupted my daily life. Because of the constant emptiness and lack of focus, I've withdrawn from my family and friends and can barely keep up with conversations. I also just don't have any motivation or energy left to handle basic daily tasks or my work responsibilities.

> Doctor's inference — candidates: Major Depressive Disorder, Persistent Depressive Disorder
> The patient reports a 9-month history of persistent low mood, exhaustion, and cognitive difficulties causing significant functional impairment. While the duration meets the criteria for Persistent Depressive Disorder (Dysthymia), the severity and the impact on daily functioning also align with Major Depressive Disorder. Both remain viable candidates as I need to clarify the intensity of symptoms to distinguish between a Major Depressive Episode and a chronic, lower-intensity depressive state.

**Doctor**: In addition to the sadness, loss of motivation, and concentration issues, have you been feeling unusually worthless, guilty, or experiencing thoughts that life is not worth living?

**Patient**: Yes, I feel completely worthless and carry this overwhelming sense of guilt all the time. I constantly replay past mistakes in my head and end up blaming myself for things that aren't even my fault. It makes me feel like I'm just a massive burden to everyone around me.

> Doctor's inference — candidates: Major Depressive Disorder, Persistent Depressive Disorder
> The patient meets the criteria for both Major Depressive Disorder and Persistent Depressive Disorder (Dysthymia) given the 9-month duration of symptoms including depressed mood, loss of motivation, concentration difficulties, feelings of worthlessness/guilt, and significant functional impairment. Since the symptoms have been constant for 9 months, both remain viable candidates; further questioning regarding the specific constellation of symptoms (e.g., number of depressive symptoms) is needed to differentiate between the two or determine if criteria for both are met.

**Doctor**: Before this nine-month period began, were you feeling relatively well, or have you experienced similar feelings of sadness and low motivation for two years or longer in the past?

**Patient**: No, I haven't experienced these feelings of sadness and low motivation for two years or longer in the past. The severe depression only started about nine months ago, and although my overall struggles began about a year and ten months ago, I felt relatively well before that.

> Doctor's inference (final) — candidates: Major Depressive Disorder
> Previously the candidates were [Major Depressive Disorder, Persistent Depressive Disorder]. I have removed Persistent Depressive Disorder because the patient confirmed that these symptoms have only been present for nine months and that they felt relatively well before that period, failing the two-year duration criteria for Persistent Depressive Disorder. Major Depressive Disorder remains the primary candidate as the patient meets the criteria for a current major depressive episode.
