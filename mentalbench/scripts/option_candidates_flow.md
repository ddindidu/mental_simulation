# `option_candidates` 생성 흐름 분석

`MentalQA_v1-main/scripts/question_setter.py` 스크립트에서 `option_candidates` 변수는 주로 `list_options_for_question` 메서드에 의해 생성됩니다. 질병 특징(Sampled features)을 바탕으로 객관식(MCQ) 문제에 들어갈 오답 선지 후보군들을 **목표 질병과의 유사도(겹치는 증상군 및 증상)**에 따라 세 가지 범주로 분류 및 정렬하여 반환을 수행합니다.

## 1. 입력 데이터 준비 (Input)
`list_options_for_question(self, disease_features)` 함수는 `disease_features`(타겟 질병 정보 및 샘플링된 특징들)를 입력받아 다음 변수들을 추출합니다.
- **`target_disease_code` / `target_disease_name`**: 문제의 정답이 되는 타겟 질병 코드와 이름
- **`target_symptom_groups`**: 타겟 질병에 포함된 증상군 목록 (`set`)
- **`target_symptoms`**: 타겟 질병에 포함된 개별 증상 목록 (`set`)

## 2. 지식 그래프 기반의 질병 비교 및 분류 (Classification)
지식 그래프(`knowledge_graph_obj`)에서 전체 질병 노드 목록(`all_diseases`)을 가져온 뒤, 각 질병을 타겟 질병과 순차적으로 비교합니다. (※ 타겟 질병 본인은 무조건 건너뜀)

비교를 위해 각 질병 노드의 `symptom_groups`와 개별 증상(`full_symptom_pool`)을 추출하며, 타겟 질병과의 교집합(Intersection)을 구합니다.
- **`shared_groups`**: 겹치는 증상군
- **`shared_symptoms`**: 겹치는 개별 증상

교집합의 유무에 따라 질병(오답 후보)들을 다음 세 가지 리스트로 분류합니다.

1. **`Highly likely option` (매우 헷갈리는 오답 후보)**
   - **조건**: `shared_groups` 가 1개 이상 존재할 때 (겹치는 증상군이 있음)
   - **저장 정보**: 질병코드, 질병명, 겹치는 증상군 리스트, 겹치는 증상 리스트
2. **`Moderately likely option` (적당히 헷갈리는 오답 후보)**
   - **조건**: 증상군은 겹치지 않지만, `shared_symptoms` 가 1개 이상 존재할 때 (공통 개별 증상이 있음)
   - **저장 정보**: 질병코드, 질병명, 겹치는 증상 리스트
3. **`Less likely option` (연관성이 적은 오답 후보)**
   - **조건**: 겹치는 증상군 및 증상이 전혀 없을 때
   - **저장 정보**: 질병코드, 질병명

## 3. 후보군 내부 정렬 및 셔플 (Sorting & Shuffling)
유사도가 높은 순서대로 오답이 우선적으로 뽑힐 수 있도록 카테고리 내부에서 정렬을 수행합니다. 같은 조건을 가진 그룹화(Bucketing)와 무작위 셔플을 혼합하여 우선순위를 결정합니다.

- **`Highly likely option` 정렬**: 겹치는 증상군(`shared_symptom_groups`)의 개수가 같은 질병끼리 버킷(`_buckets`)으로 묶습니다. 버킷 내의 질병 순서는 무작위로 섞고(`random.shuffle`), 전체 순서는 **겹치는 증상군 개수가 많은 순서(내림차순)** 로 정렬합니다.
- **`Moderately likely option` 정렬**: 겹치는 개별 증상(`shared_symptoms`)의 개수가 같은 질병끼리 버킷으로 묶습니다. 마찬가지로 버킷 내에서 무작위로 섞은 후, 전체는 **겹치는 증상 개수가 많은 순서(내림차순)** 로 정렬합니다.
- **`Less likely option` 정렬**: 겹치는 기준이 없으므로 리스트 전체 순서를 완전히 무작위로 섞습니다.

## 4. 최종 반환 및 MCQ 옵션 샘플링 (Output)
분류 및 정렬된 결과들을 모아 다음과 같은 구조의 딕셔너리로 반환하며, 이 딕셔너리의 결과물이 `option_candidates` 변수로 할당되어 이후 객관식 보기 구성(`sample_options_for_mcq`) 단계의 입력으로 넘겨집니다.

```python
{
    'answer': [{
        'disease_code': ... ,
        'disease_name': ... ,
    }],
    'Highly likely option': [ ... ],     # 겹치는 증상군 수가 많은 순서 (내림차순)
    'Moderately likely option': [ ... ], # 겹치는 증상 수가 많은 순서 (내림차순)
    'Less likely option': [ ... ],       # 완전 무작위 배열
}
```
