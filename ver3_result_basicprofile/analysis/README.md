# `analysis/` 디렉토리 안내

`analysis/`에는 시뮬레이션 로그(`logs/`)와 원시 결과(`results/`)를 가공한
**리포트/시각화 산출물**이 모입니다. 원시 캐시(예: LLM denial 캐시, `efficiency_eval.json`)는
계속 `results/<run_dir>/`에 남고, 사람이 보는 지표 JSON과 그래프(PNG)는 여기에 저장됩니다.

## 경로 구조

```
analysis/<patient>/<judge>/<doctor>/...
```

`utils/llm.py`의 `get_run_dir()`이 만드는 `{patient}/{judge}/{doctor}` 3단계 경로입니다
(환자 역할 모델 / LLM judge 모델 / 평가 대상 doctor 모델). 예:
`analysis/gemini-3.5-flash/gemini-3.5-flash/gemini-3.1-flash-lite/`

각 leaf 디렉토리(`.../<doctor>/`) 안에 아래 파일·폴더들이 생성됩니다.

## 파일·폴더별 의미

| 경로 | 생성 스크립트 | 내용 |
|---|---|---|
| `turn_eval.json` | `evaluate_turns.py` | 턴별 doctor 추론 지표(accuracy/precision/recall/jaccard/weighted_recall)의 **원본 데이터**. 로그에서 doctor가 각 턴마다 제시한 후보 진단과, 정답/후보군(disease_matches)을 비교해 계산 |
| `turn_eval_strict.json` | `evaluate_turns_strict.py` | 동일 지표를 **Method B(규칙 기반 constraint propagation)** 방식으로 계산한 버전. 부정된(denied) 증상까지 누적 반영해 더 엄격하게 후보군을 좁힘 |
| `turn_eval/` | `evaluate_turns.py` | 위 `turn_eval.json`을 절대 턴 번호(1,2,3…) 기준, 질환별+전체 평균으로 그린 그래프 (`turn_eval_plot*.png`) |
| `turn_eval/turn_eval_plot_strict*.png` | `evaluate_turns_strict.py` | 위와 동일하지만 `turn_eval_strict.json` 기준 |
| `question_eval_semantic.json` | `plot_question_eval.py` | 턴별 doctor **질문 품질** 지표(DCS, composite, mandatory-first, redundancy, information gain)의 원본 데이터. 의미 유사도 기반(LLM 미사용)으로 계산 |
| `question_eval/` | `plot_question_eval.py` | 위 데이터를 절대 턴 번호 기준으로 그린 그래프 |
| `turn_abs/` | `plot_turn_abs.py` | `turn_eval.json`(추론 지표) + `question_eval_semantic.json`(질문 지표)을 **함께**, 절대 턴 번호(1,2,…,max_turns) 기준으로 시각화. "N번째 턴에서 평균적으로 얼마나 정확하고 질문이 좋은가" |
| `turn_rel/` | `plot_turn_rel.py` | 같은 두 데이터를 **상대 진행률**(0%/25%/50%/75%/100%) 기준으로 시각화. 케이스마다 총 턴 수가 다르므로 절대 턴 대신 "진단 진행 정도"로 정규화해 공정 비교 |
| `confusion/` | `plot_confusion.py` | `turn_eval.json`의 오답(FP)을 분석. 정답 질환 X일 때 doctor가 실제로 어떤 다른 질환을 후보로 잘못 제시하는지 heatmap/trajectory로 시각화 |
| `efficiency/` | `plot_efficiency_eval.py`, `summarize_efficiency.py` | `results/<run_dir>/efficiency_eval.json`(원본은 `evaluate_efficiency.py`가 생성)을 읽어 진단 효율성 지표(CSSR, 턴 수, 첫 정답 turn, monotonicity, redundancy, overcommit 등)를 질환별로 그래프/표(`efficiency_summary.txt`)로 정리 |
| `summary_doctor_models.xlsx` (최상위) | (수동/별도 스크립트) | 여러 doctor 모델을 가로질러 비교하는 요약 엑셀 |

## 요약: 데이터 흐름

1. **원본 지표 계산** — `evaluate_turns.py` / `evaluate_turns_strict.py` / `plot_question_eval.py` /
   `evaluate_efficiency.py`가 로그·결과를 읽어 `turn_eval*.json`, `question_eval_semantic.json`,
   (`results/`의) `efficiency_eval.json`을 만듭니다.
2. **1차 시각화** — 각 스크립트가 자기 데이터를 바로 그래프로도 저장합니다
   (`turn_eval/`, `question_eval/`, `efficiency/`).
3. **교차 분석** — `plot_turn_abs.py`(절대 턴 기준), `plot_turn_rel.py`(상대 진행률 기준),
   `plot_confusion.py`(오답 분석)가 위 JSON들을 다시 읽어 더 상위 관점의 그래프를 만듭니다.

`case_studies/`(저장소 루트)는 `script/build_case_studies.py`가 이 `analysis/` 데이터를 읽어
케이스별 마크다운 리포트를 생성하는 별도 산출물이며, `analysis/` 안에는 포함되지 않습니다.
