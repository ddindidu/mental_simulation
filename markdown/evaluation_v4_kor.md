# Evaluation v4 — 핵심 지표(Headline Metric) 참조 문서

4개의 리포팅 축(dimension)이며, 각각 KG 기반의 결정론적 ground truth
(`mentalbench/resources/knowledge_graph/EN/diagnostic_criteria.json`)를
근거로 계산됩니다. 이 문서는 구현 코드와 대조 확인을 마친 짧은 참조용
문서입니다 — 전체 공식/edge case는 `evaluation_v3.md`(이 문서가 반복하지
않는 세부 로직의 canonical spec)와 아래 링크된 각 모듈의 docstring을
참고하세요.

네 축 모두 턴마다 계산되는 하나의 ground-truth 객체를 공유합니다:

```
compute_candidate_set(confirmed, denied, diagnostic_criteria)
  -> (high_likely, moderate_likely, low_likely, excluded)
```
— `eval/symptom_diagnosis.py:compute_candidate_set()`. 어떤 질병은 모든
`must_include` 그룹이 `min_count`를 충족하면 `high_likely`, mandatory
증거가 일부만 있으면 `moderate_likely`, optional 증거만 있으면
`low_likely`, mandatory 증상 하나라도 denied되면 `excluded`로 분류됩니다.
**아래에서 말하는 `truth_set` / "reference candidate set"은 전부
`high_likely ∪ moderate_likely ∪ low_likely`를 의미합니다.**

---

## 1. Inference Quality (추론 정확도)

턴마다: 의사가 말한 candidate list가 reference set과 얼마나 일치하는가?
`eval/evaluate_turns.py`에 구현되어 있고, 모든 리포팅 스크립트가 읽는
`analysis/<run>/turn_eval.json`을 이 파일이 생성합니다.

```
TP = |predicted ∩ truth_set|,  FP = |predicted − truth_set|,  FN = |truth_set − predicted|
precision = TP / |predicted|
recall    = TP / |truth_set|
jaccard   = TP / |predicted ∪ truth_set|
```

| | 지표 | 상태 |
|---|---|---|
| **main** | **Jaccard Index** | ✅ 구현됨 |
| sub | Precision | ✅ 구현됨 |
| sub | Recall | ✅ 구현됨 |

(`accuracy`/`weighted_recall`도 함께 계산되어 JSON에 저장되지만, 이번
headline 지표 집합에는 포함되지 않습니다 — ablation용으로만 유지.)

---

## 2. Information Acquisition Quality (정보 수집 능력)

턴마다: 의사의 질문이 relevant하면서 non-redundant한가, 그리고 candidate
set을 narrowing하는가? `eval/informative_question_score.py`에 구현되어
있고(설계 근거와 확정된 결정 사항은 모듈 docstring 참고),
`eval/evaluate_question.py`가 에피소드 단위로 오케스트레이션합니다.

Evidence state는 3-state(`CONFIRMED / DENIED / UNKNOWN`)를 그대로
유지합니다 — symptom extraction judge(`eval/symptom_diagnosis.py`)가
애매한 환자 답변에 대해 이미 `UNKNOWN`으로 처리하도록 설계되어 있어서,
명확화(clarification) 재질문이 redundant 질문으로 잘못 분류될 일이
없습니다.

### (main) Information Acquisition Score (IAS)

```
I_t  = discriminative_symptoms(C_t) ∪ required_symptoms(C_t)
DRS  = |S(q_t) ∩ I_t| / |S(q_t)|                       — 진단적 관련성(diagnostic relevance)
RP   = |S(q_t) ∩ resolved| / |S(q_t)|                  — 중복 패널티(redundancy penalty)
IAS  = DRS × (1 − RP)
```
- `discriminative_symptoms(C_t)`: 현재 candidate 중 *일부*에만 연결되고
  *전체*에는 연결되지 않는 symptom (`0 < |D_t(s)| < |C_t|`).
- `required_symptoms(C_t)`: 현재 candidate들의 `must_include` mandatory
  pool symptom ID를 전부 합친 것 — **symptom 단위**이며 **`min_count`
  그룹 게이팅을 하지 않음**(한 그룹이 "이미 충족됐다"고 취급해서 나머지
  member를 required에서 빼지 않음; mandatory symptom을 한 번에 하나씩
  물어보는 게 자연스러운 대화 단위이기 때문). 비-symptom 요건(duration,
  functional impairment, additional requirements)은 **범위 밖**입니다 —
  이 요건들에 대한 evidence extraction이 파이프라인에 아직 없습니다(미해결
  갭으로 4번 항목에서 추적).
- `mandatory_first_compliance`(question_score.py)는 이 축에서 **더 이상
  쓰이지 않습니다** — required 여부가 이제 `I_t`에 직접 녹아 있습니다.

### (sub) Information Gain — Expected Candidate Reduction (ECR)

```
ECR(s) = 1 − [P(+)·|C_t| + P(−)·(|C_t| − k)] / |C_t|      k = |{d ∈ C_t : s가 d의 mandatory symptom}|
ECR(q_t) = UNRESOLVED 타겟 symptom들에 대한 ECR(s)의 평균   (per_target_mean)
```
필터링은 presence(존재 여부) 기반이지만 **mandatory pool 소속 여부로
제한**합니다: `compute_candidate_set`에서는 오직 *mandatory* symptom의
denial만 candidate를 제외시키므로, symptom을 confirm하는 것은 절대로
`C_t`를 줄이지 않습니다("positive" branch는 항상 전체 집합) — 이렇게
해야 ECR이 Inference Quality가 쓰는 candidate set 정의와 일관되게
유지됩니다. `P(+)`의 기본값은 `candidate_frequency`(`k / |C_t|`)이며,
`config.json → evaluation.information_acquisition.probability_mode`로
설정 가능합니다 (`uniform_answer` / `candidate_frequency` / `provided`).

| | 지표 | 상태 |
|---|---|---|
| **main** | **Information Acquisition Score (IAS)** | ✅ 구현됨 |
| sub | Information Gain (ECR) | ✅ 구현됨 |

이 점수들을 계산하는 데 쓰인 모든 중간 집합(`discriminative_symptoms`,
`required_symptoms`, `candidate_symptoms`, `resolved_symptoms`,
`unresolved_symptoms`, symptom별 ECR 상세 내역)은 디버깅/케이스 스터디를
위해 `question_eval.json`에 점수와 함께 저장됩니다.

---

## 3. Efficiency (효율성)

에피소드 단위, 턴별 candidate-set 크기로부터 계산.
`eval/evaluate_efficiency.py`(`results/<run>/efficiency_eval.json` 생성).

| | 지표 | 정의 | 상태 |
|---|---|---|---|
| main | **Turn count** | 의사가 `is_final=true`를 선언할 때까지의 총 patient turn 수 | ✅ 구현됨 (`turn_count`) |
| sub | **Turn to 1st correct** | reference candidate set이 정확히 `{ground_truth}`로 수렴하는 첫 턴(`high∣moderate∣low` 합집합 `== {gt}`); 도달 못 하면 sentinel값 `turn_count + 1` | ✅ 구현됨 (`time_to_first_correct_narrowing`) |
| sub | **Overcommitment Turns** | `(turn_count − 1) − 최초로 \|C_t\|==1이 된 턴`; (정답 여부와 무관하게) candidate set이 이미 1개로 수렴한 후에도 종료 전까지 계속 이어간 턴 수 | ✅ 구현됨 (`overcommitment_turns`) |

**이번 작업에서 수정한 버그:** `time_to_first_correct_narrowing`이 기존에는
`high_likely` tier만 확인했지만, `overcommitment_turns`는
`high∣moderate∣low` 전체 합집합을 기준으로 하고 있어서, spec이 의도한
"두 지표가 서로 complement 관계"가 실제로는 성립하지 않았습니다. 이제 두
지표 모두 같은 "candidate set 크기 == 1" 조건을 사용하도록
(`eval/evaluate_efficiency.py:score_efficiency_episode`) 수정했고, 정답
질병이 실제로 candidate set이 수렴한 그 질병일 때는
`turn_to_1st_correct + overcommitment_turns ≤ turn_count`가 항상
성립합니다.

(`cssr`, `monotonicity_violations`, `redundant_turn_ratio`도 함께
계산되어 JSON에 남아있지만, headline 지표 집합에는 포함되지 않고
ablation 참고용입니다.)

---

## 4. Reliable Diagnosis (신뢰할 수 있는 진단)

에피소드 단위, 마지막 턴에서만 계산.

| | 지표 | 정의 | 상태 |
|---|---|---|---|
| — | **Final Accuracy** | 의사가 말한 최종 진단의 disease ID가 ground truth와 일치하면 1.0 | ✅ 구현됨 (`eval/evaluate_efficiency.py:final_accuracy`) |
| — | **Diagnostic Reasoning Ability** | 인터뷰에서 실제로 GT 질병의 required criteria — mandatory symptom 그룹(`min_count` 포함), `functional_impairment_required`, `min_duration`, `additional_requirements` — 를 충족할 만큼 정보를 **수집**했는가 | ✅ 구현됨 (`eval/score_diagnostic_reasoning.py`, `eval/evaluate_diagnostic_reasoning.py`가 오케스트레이션) |

`score_diagnostic_reasoning.py`의 `compute_score()`는 이 네 requirement
유형(mandatory 그룹 가중치 ×2, duration, functional impairment,
additional requirements — 전체 가중치 표는 모듈 docstring 참고)에 대한
macro-mean이지만, 채점 방식은 이제 **하이브리드**입니다 (LLM 전용이
아님):
- **Symptom 그룹(×2 가중치로 점수의 대부분 차지): algorithmic.**
  `compute_symptom_criterion_evaluations()`가 인터뷰의 실제
  `cumulative_confirmed`/`cumulative_denied` evidence(Inference
  Quality/IAS가 쓰는 것과 동일하게 symptom extraction judge가 만든 것)를
  각 `must_include`/`include` 그룹의 `min_count`와 비교합니다 — 새 LLM
  호출 없음, 의사 자기보고 checklist 문구에서 오는 bias 없음.
- **비-symptom scalar 항목**(duration, functional impairment, stressor,
  additional requirements)은 여전히 의사의 자기보고 checklist 텍스트를
  LLM이 채점합니다 — 이 항목들에 대한 턴 단위 구조화 evidence 추출이
  파이프라인에 아직 없기 때문입니다(2번 항목에서 언급한 것과 같은 갭).

`diagnostic_criteria.json`의 GT criteria 스키마와 1:1로 대응합니다. 출력
필드: `results/<run>/diagnostic_reasoning_eval.json`의 `overall_score`,
디버깅용 component별 점수(`duration_score`,
`functional_impairment_score`, `additional_requirements_score`), 그리고
algorithmic 채점 상세를 담은 `symptom_criterion_evaluations`.

---

## 요약

| 축(Dimension) | Main | Sub |
|---|---|---|
| Inference Quality | Jaccard Index | Precision, Recall |
| Information Acquisition Quality | Information Acquisition Score (IAS) | Information Gain (ECR) |
| Efficiency | Turn count | Turn to 1st correct, Overcommitment Turns |
| Reliable Diagnosis | Final Accuracy | Diagnostic Reasoning Ability |

8개 지표 전부 현재 코드베이스와 대조하여 구현 확인을 마쳤습니다. 이번
작업에서 실제로 변경한 항목은 두 가지입니다:
1. **Turn to 1st correct / Overcommitment Turns**가 이제 동일한
   candidate-set-size 조건으로 계산되어 진짜 complement 관계가 되도록
   고쳤습니다.
2. **Diagnostic Reasoning Ability**의 symptom 그룹 채점을
   LLM-judge(의사 자기보고 checklist 채점) 방식에서 algorithmic(실제
   누적 인터뷰 evidence 확인) 방식으로 전환했습니다 — 4번 항목 참고.
