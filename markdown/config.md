# config.json 설정 가이드

## llm

역할별(patient / doctor / judge) LLM 모델을 지정한다.

```json
"llm": {
    "patient": { "provider": "gemini", "model": "gemini-3.5-flash" },
    "doctor":  { "provider": "openai", "model": "gpt-4o" },
    "judge":   { "provider": "vllm",   "model": "Qwen/Qwen2.5-72B-Instruct" }
}
```

지원 provider:

| provider | 설명 |
|----------|------|
| `gemini` | Google Gemini API |
| `openai` | OpenAI API |
| `vllm`   | 로컬 vLLM 서버 (OpenAI-compatible endpoint) |
| `local`  | 로컬 HuggingFace 모델 직접 로드 |

### provider별 공통 설정

**vllm**
```json
"vllm": {
    "base_url": "http://localhost:8001/v1",
    "timeout_seconds": 600
}
```

**openai**
```json
"openai": {
    "use_max_completion_tokens": "auto",   // "auto" | true | false
    "timeout_seconds": 600,
    "reasoning_completion_floor": 512      // reasoning 모델용 최소 토큰
}
```

**gemini**
```json
"gemini": {
    "timeout_seconds": 600
}
```

---

## simulation

단일 시뮬레이션 설정.

```json
"simulation": {
    "max_turns": 10   // 의사-환자 대화 최대 턴 수
}
```

---

## batch

배치 평가 시 실행할 disease code를 지정한다.

```json
"batch": {
    "disease_codes": []        // 빈 리스트 = 전체 disease 실행
}
```

```json
"batch": {
    "disease_codes": [1, 3, 9] // D001, D003, D009 만 실행
}
```

- 정수 리스트로 입력하면 `D{n:03d}` 형식으로 변환됨 (예: `9` → `D009`)
- 존재하지 않는 코드만 입력하면 즉시 에러 반환

---

## patient

단일 시뮬레이션용 환자 설정. 배치 평가에서는 disorder.json 전체(또는 `batch.disease_codes`)를 사용하므로 `disease_code`는 무시된다.

```json
"patient": {
    "use_knowledge_graph": true,      // KG 기반 환자 생성 여부
    "disease_code": "D009",           // 단일 시뮬레이션 대상 disease
    "difficulty_level": "medium",     // "easy" | "medium" | "hard"
    "kg_base_dir": "./mentalbench"    // knowledge graph 루트 경로
}
```

---

## generation

LLM 생성 파라미터. 역할별(patient / doctor)로 분리.

```json
"generation": {
    "patient": {
        "default_max_new_tokens": 1024,
        "alignment_max_new_tokens": 1024,
        "temperature": 0.7,
        "top_p": 0.9,
        "do_sample": true
    },
    "doctor": {
        "default_max_new_tokens": 1024,
        "inference_max_new_tokens": 1024,
        "diagnosis_max_new_tokens": 1500,  // 최종 진단 시 더 긴 출력 허용
        "temperature": 0.7,
        "top_p": 0.9,
        "do_sample": true
    }
}
```

---

## server

Flask 서버 설정.

```json
"server": {
    "host": "0.0.0.0",
    "port": 5080,
    "debug": false,
    "threaded": true
}
```

---

## debug

```json
"debug": {
    "log_llm_messages": true,      // LLM 입출력 전체를 터미널에 출력
    "log_openai_response": false   // OpenAI raw response 출력 (상세 디버깅용)
}
```
