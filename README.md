# Patient–Doctor Psychiatric Interview Simulation



두 개의 LLM(**환자**와 **정신과 의사**)이 다중 턴으로 진단 인터뷰를 진행하는 시뮬레이터입니다.
환자 LLM은 [MentalBench](mentalbench/) 지식 그래프(KG)에서 특정 정신질환의 증상 프로필을 동적으로
생성해 연기하고, 의사 LLM은 매 턴 감별진단 후보를 좁혀가며 최종 진단을 내립니다.
생성된 대화 로그는 별도의 평가 파이프라인으로 **턴 단위 정밀도/재현율**과 **최종 진단 정확도**를 측정합니다.

---

## 핵심 구성

| 영역 | 파일 | 설명 |
|------|------|------|
| **환자 LLM** | `patient.py` | KG 또는 JSON 프로필 기반 환자 페르소나 생성, 답변 정렬(alignment) + 응답(response) 2단계 |
| **의사 LLM** | `doctor.py` | 질문(questioning) / 추론(inference) / 최종 진단(final) 프롬프트, doctor_memory 관리 |
| **시뮬레이션 루프** | `simulation_core.py` | Flask 없이 인터뷰 1회 실행 (CLI·배치 공용) |
| **웹 서버** | `app.py` | Flask UI + SSE 스트리밍 + 배치 평가 엔드포인트 |
| **CLI 실행** | `simulate.py` | JSON 프로필로 인터뷰 1회 실행 → `doctor_memory.json`, `transcript.json` 저장 |
| **LLM 백엔드** | `utils/llm.py` | `vllm` / `openai` / `local` 제공자, 역할별(patient·doctor) 모델 분리 |
| **설정** | `config.json` | 모델·생성 파라미터·환자 KG 설정·서버 설정 |

---

## 인터뷰 흐름

```
        ┌──────────────────────────── Doctor LLM ────────────────────────────┐
opening │ questioning : 인사 + 주호소(chief complaint) 질문                     │
        └─────────────────────────────────────────────────────────────────────┘
                                       │ question
                                       ▼
   ┌──────────── 매 턴 (t = 1 … max_turns) ─────────────────────────────────┐
   │  Patient LLM                                                           │
   │   ① alignment : 의사 질문 ↔ 증상 프로필 매칭 → 답변 전략(JSON)         │
   │   ② response  : 전략에 따라 환자처럼 2~3문장 자연어 답변                │
   │                                                                        │
   │  Doctor LLM                                                            │
   │   ③ inference : 대화 전체 + 이전 후보 → 감별진단 후보 갱신(+변경 사유)  │
   │                                                                        │
   │   ▸ 후보가 1개로 좁혀지거나 t == max_turns →                            │
   │       ④ final : 최종 진단 리포트(diagnosis / candidates / reason) 후 종료 │
   │   ▸ 그렇지 않으면 →                                                     │
   │       ⑤ questioning : 후보를 가장 잘 변별하는 후속 질문 1개             │
   └────────────────────────────────────────────────────────────────────────┘
```

- 의사의 추론·최종 진단은 **23개 허용 질환 리스트**(`doctor.py` / `disorder.json`의 D001–D023) 안에서만 선택됩니다.
- 종료 조건은 `doctor.should_finish_interview()` — 후보 1개 수렴 또는 최대 턴(`config.json`의 `simulation.max_turns`, 기본 10) 도달.
- 모든 LLM 입출력은 `loggingN.txt`(웹) 또는 `logs/D###_N.txt`(배치)에 `INPUT/OUTPUT [role]` 블록으로 기록됩니다.

---

## 디렉터리 구조

```
simulation_new/
├── app.py                       # Flask 서버 (웹 UI · SSE · 배치 평가)
├── simulate.py                  # CLI 단일 인터뷰 실행
├── simulation_core.py           # 인터뷰 1회 실행 코어
├── patient.py                   # 환자 프롬프트/응답 빌더 (KG·JSON)
├── doctor.py                    # 의사 프롬프트/메모리/파서
├── config.json                  # 전체 설정
├── requirements.txt
│
├── utils/
│   ├── config.py                # config.json + .env 로드
│   ├── llm.py                   # vllm/openai/local 백엔드, 역할별 모델
│   ├── paths.py                 # 프로젝트 경로 상수
│   └── prompt_display.py        # 프롬프트 → HTML (웹 UI용)
│
├── templates/index.html         # 웹 UI
├── script/run_simulate.sh       # 모델×프로필 배치 CLI
│
├── data/
│   ├── profiles/                # JSON 증상 프로필 (KG 미사용 시 폴백)
│   └── results/                 # CLI 결과 (doctor_memory.json, transcript.json)
│
├── mentalbench/                 # MentalBench 지식 그래프 + 데이터셋
│   ├── scripts/                 # knowledge_graph.py, question_setter.py 등
│   └── resources/knowledge_graph/EN/
│       ├── disorder.json            # D001–D023 코드 ↔ 질환명
│       ├── diagnostic_criteria.json # 질환별 진단 기준(증상 풀)
│       └── symptom/                 # 증상 정의(S###)
│
├── logs/                        # 시뮬레이션 로그 (loggingN.txt, D###_N.txt)
├── logs_fixed/                  # test.ipynb로 정제한 로그 변형본
│
├── symptom_diagnosis.py         # [평가1] 턴별 증상 추출 + 질환 매칭
├── evaluate_turns.py            # [평가2-구] 턴별 acc/prec/recall (legacy)
├── evaluate_turns_strict.py     # [평가2-신] Method B: +/−증상 제약 전파
├── evaluate_final_diagnosis.py  # [평가3] 최종 진단 정확도
│
├── results/                     # 평가 산출물 (*_result.json, summary.json, *.png, ...)
├── acc.txt                      # 배치 평가 최종 진단 정확도 요약
├── changed.md                   # evaluate_turns → strict 변경 배경
└── evaluate_turns_strict.md     # Method B TP/FP/FN/TN 산식 설명
```

---

## 설치

```bash
pip install -r requirements.txt
```

주요 의존성: `flask`, `openai`, `transformers`, `torch`, `accelerate`, `vllm`, `python-dotenv`
(평가 스크립트는 추가로 `matplotlib`, `numpy` 필요)

### LLM 백엔드 준비

`config.json`의 `llm.patient.provider` / `llm.doctor.provider`에 따라 백엔드가 달라집니다.

- **`vllm`** (기본값): OpenAI 호환 로컬 서버를 별도로 띄워야 합니다.
  ```bash
  vllm serve Qwen/Qwen3.5-35B-A3B --port 8001
  ```
  → `config.json`의 `llm.vllm.base_url`(`http://localhost:8001/v1`)과 맞춰야 합니다.
- **`openai`**: `.env`에 `OPENAI_API_KEY`를 넣습니다. (필요 시 `OPENAI_BASE_URL`)
- **`local`**: HuggingFace 모델을 `transformers`로 직접 로드(GPU면 float16, 아니면 CPU float32).

> 평가 스크립트(`symptom_diagnosis.py`, `evaluate_turns_strict.py`)는 LLM을 호출해
> 증상/부정 증상을 추출하므로 동일한 vLLM 서버(`localhost:8001`)가 필요합니다.

---

## 실행 방법

### 1) 웹 UI

```bash
python app.py          # http://localhost:5000
```

- 환자/의사 시스템 프롬프트가 화면에 표시되고, **Start**로 단일 인터뷰를 SSE로 스트리밍합니다.
- 환자 설정(질환 코드·난이도·KG 사용 여부)을 UI에서 바꾸면 프롬프트가 재생성됩니다.
- **배치 평가**: `POST /api/batch_eval` (`{ "runs_per_disorder": 10, "difficulty": "medium" }`)
  → 23개 질환 × N회 인터뷰를 백그라운드로 돌려 `logs/D###_N.txt`와 `acc.txt`를 생성합니다.
  진행 상황은 `GET /api/batch_status`로 조회합니다.

| 엔드포인트 | 용도 |
|-----------|------|
| `GET /` | 프롬프트 표시 UI |
| `GET /simulate` | 단일 인터뷰 SSE 스트림 |
| `GET /api/status` | 모델 로딩 상태 |
| `GET /api/diseases` | KG 질환 목록(disorder.json) |
| `GET/POST /api/patient_config` | 환자 설정 조회/변경 |
| `POST /api/batch_eval` · `GET /api/batch_status` | 배치 평가 실행/진행 |

### 2) CLI 단일 실행

```bash
python simulate.py --profile data/profiles/symptom_profile.json
python simulate.py -p data/profiles/symptom_profile_2.json -o data/results --verbose \
    --patient-model gpt-4o-mini --doctor-model gpt-4o-mini --max-turns 10
```

→ `data/results/doctor_memory.json`, `transcript.json` 저장. (CLI는 JSON 프로필 기반으로 환자를 구성)

### 3) 배치 CLI

```bash
bash script/run_simulate.sh    # PATIENT_MODELS × DOCTOR_MODELS × SYMPTOM_PROFILES 반복
```

---

## 환자 프로필: KG vs JSON

`config.json`의 `patient.use_knowledge_graph`로 결정됩니다 (`patient.build_system_prompt()`).

- **`true`** — `mentalbench`의 `KnowledgeGraph` + `QuestionSetter`로 `disease_code`(예: `D009`)와
  `difficulty_level`(`low`/`medium`/`high`)에 맞춰 증상 그룹·진단 기준을 **매번 샘플링**해 프로필을 생성합니다.
  (배치 평가는 이 경로로 같은 질환을 매번 다른 증상 조합으로 생성)
- **`false`** — `data/profiles/symptom_profile.json`의 정적 프로필을 사용합니다(폴백). KG 생성 실패 시에도 폴백.

환자는 첫 턴엔 주호소만 말하고, 의사가 묻지 않은 증상은 먼저 드러내지 않으며, 프로필에 없는 증상은
"잘 모르겠다"고 답하도록 프롬프트가 통제합니다.

---

## 평가 파이프라인

로그(`logs/*.txt`)가 준비된 뒤 순서대로 실행합니다.

```
logs/D###_N.txt
   │
   ├─(1) python symptom_diagnosis.py
   │        턴별 환자 발화 → LLM 증상 추출(S###) → diagnostic_criteria.json 질환 매칭
   │        → results/{log}_result.json, results/summary.json
   │
   ├─(2) python evaluate_turns_strict.py        # Method B (현행)
   │        +증상(confirmed) / −증상(denied) 누적 → 제약 전파로 truth_set 산정
   │        → results/turn_eval_strict.json, turn_eval_plot_strict.png, results/denials/*.json
   │        (구버전: evaluate_turns.py → turn_eval.json / turn_eval_plot.png)
   │
   └─(3) python evaluate_final_diagnosis.py
            마지막 의사 블록의 diagnosis ↔ disorder.json 매핑으로 질환별 정확도
            → results/final_diagnosis_eval.txt
```

### Method B (`evaluate_turns_strict.py`)

기존 평가는 *n*번째 턴의 단일 답변만 보고 TP를 판정해, 누적 맥락으로 후보를 좁히는 의사와 평가 기준이
비대칭이라 precision이 떨어졌습니다. Method B는 환자가 **확인한 증상(+)** 과 **명시적으로 부정한 증상(−)** 을
모두 누적해 다음과 같이 truth_set을 정의합니다 (자세한 산식은 [`evaluate_turns_strict.md`](evaluate_turns_strict.md), 배경은 [`changed.md`](changed.md)).

```
질환 D ∈ truth_set  ⟺  feasible(D) ∧ supported(D)
  feasible(D)  : 모든 must_include 그룹 G에서  |G.pool − denied| ≥ min_count   (부정으로 불가능해지지 않음)
  supported(D) : 적어도 한 그룹 G에서  G.pool ∩ confirmed ≠ ∅                  (양성 증거 존재)
  (ground truth 질환은 항상 포함)

TP=|pred∩truth|  FP=|pred−truth|  FN=|truth−pred|  TN=N − |pred∪truth|   (N=23)
```

→ 턴이 진행될수록 denial·confirmed가 쌓여 truth_set이 정제되고, 의사도 후보를 좁히며 **precision이 상승**합니다.

---

## 결과 (예시 — `acc.txt`)

`difficulty=medium`, 질환당 10회, 총 230회 인터뷰의 최종 진단 정확도:

```
TOTAL        74.78%  172/230
```

질환별로는 Delusional Disorder·Specific Phobia·OCD·PTSD·Eating Disorders 등이 100%인 반면,
Bipolar II Disorder(20%)·MDD with Psychotic Features(0%) 등 인접 질환과 변별이 어려운 항목은 낮게 나옵니다.
(전체 표는 `acc.txt` 참고)

---

## 설정 요약 (`config.json`)

```jsonc
{
  "llm": {
    "patient": { "provider": "vllm", "model": "Qwen/Qwen3.5-35B-A3B" },
    "doctor":  { "provider": "vllm", "model": "Qwen/Qwen3.5-35B-A3B" },
    "vllm":    { "base_url": "http://localhost:8001/v1", "timeout_seconds": 600 }
  },
  "simulation": { "max_turns": 10 },
  "patient": {
    "use_knowledge_graph": true,
    "disease_code": "D009",
    "difficulty_level": "medium",
    "kg_base_dir": ".../mentalbench"
  },
  "generation": {
    "patient": { "default_max_new_tokens": 300, "alignment_max_new_tokens": 500, "temperature": 0.7 },
    "doctor":  { "inference_max_new_tokens": 400, "diagnosis_max_new_tokens": 600, "temperature": 0.7 }
  },
  "server": { "host": "0.0.0.0", "port": 5000 }
}
```

- 환자/의사에 **서로 다른 모델·제공자**를 지정할 수 있습니다 (역할별 블록).
- `generation`은 역할별로 토큰 한도·온도를 분리합니다. (구버전 평면 형식도 자동 호환)
- 프롬프트는 `doctor.py`의 `get_*_system_prompt()`, `patient.py`의 `PROMPT`/`ALIGNMENT_PROMPT`에서 수정합니다.
