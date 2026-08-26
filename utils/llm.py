from __future__ import annotations

import json
import os
import re
import threading
from typing import Any, Literal

from .config import CONFIG

_LLM = CONFIG.get("llm") or {}

# ── Logging ──────────────────────────────────────────────────────────────────
_current_log_path: "Path | None" = None
_warned_log_fallback = False


def rotate_log_file() -> "Path":
    """로그 파일 번호를 자동 증가시켜 새 파일 경로를 설정하고 반환한다."""
    global _current_log_path
    from .paths import PROJECT_ROOT
    n = 1
    while (PROJECT_ROOT / f"logging{n}.txt").exists():
        n += 1
    _current_log_path = PROJECT_ROOT / f"logging{n}.txt"
    print(f"[llm] Log file: {_current_log_path}", flush=True)
    return _current_log_path


def set_log_path(path: "Path | str | None", *, truncate: bool = True) -> None:
    """배치 평가 등에서 로그 파일 경로를 직접 지정한다.

    truncate=True(기본)면 새 시뮬레이션으로 보고 기존 파일을 지우고 빈 파일로
    시작한다. 이미 끝난 케이스의 로그에 후속 LLM 호출(증상추출 등)만 덧붙일
    때는 truncate=False 로 호출해 기존 내용을 보존한다.
    path=None 이면 로그 경로를 해제한다 (이후 호출은 logging.txt 로 폴백).
    """
    global _current_log_path
    if path is None:
        _current_log_path = None
        return
    from pathlib import Path as _Path
    _current_log_path = _Path(path)
    _current_log_path.parent.mkdir(parents=True, exist_ok=True)
    if truncate:
        _current_log_path.write_text("", encoding="utf-8")


def _log_meta_line(
    role: str,
    phase: str | None,
    turn: int | None,
    source: str | None,
    model: str,
) -> str | None:
    """로그 블록 앞에 붙일 한 줄 요약(턴/단계/생성 함수/모델)을 만든다."""
    if phase is None and turn is None and source is None:
        return None
    parts = [f"turn {turn}" if turn is not None else "turn -"]
    parts.append(f"{role}:{phase}" if phase else role)
    if source:
        parts.append(f"{source}()")
    if model:
        parts.append(f"model={model}")
    return "-" * 10 + " " + " | ".join(parts) + " " + "-" * 10


def _append_to_log(
    role: str,
    messages: list,
    result: str,
    *,
    phase: str | None = None,
    turn: int | None = None,
    source: str | None = None,
) -> None:
    """LLM 입출력을 현재 로그 파일에 추가한다."""
    global _warned_log_fallback
    from .paths import PROJECT_ROOT
    log_path = _current_log_path
    if log_path is None:
        # 로그 경로가 지정되지 않았으면 프로젝트 루트 logging.txt 로 폴백한다.
        log_path = PROJECT_ROOT / "logging.txt"
        if not _warned_log_fallback:
            _warned_log_fallback = True
            print(
                f"[llm] WARNING: set_log_path() 미설정 상태의 LLM 호출 → {log_path} 로 폴백",
                flush=True,
            )
    meta = _log_meta_line(role, phase, turn, source, str(_cfg_for_role(role)["model"]))
    with open(log_path, "a", encoding="utf-8") as f:
        if meta:
            f.write(meta + "\n")
        f.write(f"========== INPUT [{role}] ==========\n")
        f.write(json.dumps(messages, ensure_ascii=False, indent=2) + "\n")
        f.write(f"========== OUTPUT [{role}] ==========\n")
        f.write(result + "\n")
        f.write("=====================================\n\n")

# ─────────────────────────────────────────────────────────────────────────────
Role = Literal["patient", "doctor", "judge"]

# Per-role resolved config: { "provider", "model", "openai": {...}, "gemini": {...} }
_patient_cfg: dict[str, Any]
_doctor_cfg: dict[str, Any]
_judge_cfg: dict[str, Any]

_openai_client: Any | None = None
_openai_ready = threading.Event()
_openai_error: str | None = None

_gemini_ready = threading.Event()
_gemini_error: str | None = None

_openrouter_client: Any | None = None
_openrouter_ready = threading.Event()
_openrouter_error: str | None = None

# Local: one bundle per HuggingFace model id (supports patient/doctor different models)
_local_bundles: dict[str, dict[str, Any]] = {}
_local_events: dict[str, threading.Event] = {}
_model_lock = threading.Lock()


def _normalize_role_configs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Parse per-role configs. Returns (patient_cfg, doctor_cfg, judge_cfg)."""
    raw = _LLM
    shared_openai = raw.get("openai") if isinstance(raw.get("openai"), dict) else {}
    shared_gemini = raw.get("gemini") if isinstance(raw.get("gemini"), dict) else {}

    if any(isinstance(raw.get(r), dict) for r in ("patient", "doctor", "judge")):
        legacy_prov = (raw.get("provider") or "openai").lower().strip()
        legacy_model = raw.get("model") or "gpt-4o-mini"

        def one(role_key: str, default_model: str) -> dict[str, Any]:
            block = raw.get(role_key) if isinstance(raw.get(role_key), dict) else {}
            prov = (block.get("provider") or legacy_prov).lower().strip()
            model = block.get("model") or legacy_model or default_model
            o = {**shared_openai, **(block.get("openai") or {})}
            g = {**shared_gemini, **(block.get("gemini") or {})}
            return {"provider": prov, "model": str(model), "openai": o, "gemini": g}

        return (
            one("patient", "gpt-4o-mini"),
            one("doctor", "gpt-4o-mini"),
            one("judge", "gpt-4o-mini"),
        )

    prov = (raw.get("provider") or "openai").lower().strip()
    model = raw.get("model") or "gpt-4o-mini"
    cfg = {
        "provider": prov,
        "model": str(model),
        "openai": {**shared_openai},
        "gemini": {**shared_gemini},
    }
    return cfg, cfg, cfg


_patient_cfg, _doctor_cfg, _judge_cfg = _normalize_role_configs()


def _normalize_generation() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Returns (patient_gen, doctor_gen, judge_gen)."""
    raw = CONFIG.get("generation") or {}
    legacy_shared = {
        k: v
        for k, v in raw.items()
        if k not in ("patient", "doctor", "judge") and not isinstance(v, dict)
    }

    patient_defaults: dict[str, Any] = {
        "default_max_new_tokens": 300,
        "alignment_max_new_tokens": 500,
        "temperature": 0.7,
        "top_p": 0.9,
        "do_sample": True,
    }
    doctor_defaults: dict[str, Any] = {
        **patient_defaults,
        "inference_max_new_tokens": 400,
        "diagnosis_max_new_tokens": 600,
    }
    judge_defaults: dict[str, Any] = {
        "default_max_new_tokens": 3072,
        "temperature": 0.0,
        "top_p": 1.0,
        "do_sample": False,
    }

    if any(isinstance(raw.get(r), dict) for r in ("patient", "doctor", "judge")):
        pb = raw.get("patient") if isinstance(raw.get("patient"), dict) else {}
        db = raw.get("doctor") if isinstance(raw.get("doctor"), dict) else {}
        jb = raw.get("judge") if isinstance(raw.get("judge"), dict) else {}
        patient = {**patient_defaults, **legacy_shared, **pb}
        doctor = {**doctor_defaults, **legacy_shared, **db}
        judge = {**judge_defaults, **jb}
        return patient, doctor, judge

    flat = raw
    common = {
        "default_max_new_tokens": int(flat.get("default_max_new_tokens", 300)),
        "alignment_max_new_tokens": int(flat.get("alignment_max_new_tokens", 500)),
        "temperature": float(flat.get("temperature", 0.7)),
        "top_p": float(flat.get("top_p", 0.9)),
        "do_sample": bool(flat.get("do_sample", True)),
    }
    doctor_only = {
        **common,
        "inference_max_new_tokens": int(flat.get("inference_max_new_tokens", 400)),
        "diagnosis_max_new_tokens": int(flat.get("diagnosis_max_new_tokens", 600)),
    }
    return common, doctor_only, dict(judge_defaults)


_patient_gen, _doctor_gen, _judge_gen = _normalize_generation()


def _gen_for_role(role: Role) -> dict[str, Any]:
    if role == "patient":
        return _patient_gen
    if role == "doctor":
        return _doctor_gen
    return _judge_gen


def get_doctor_inference_max_tokens() -> int:
    return int(_doctor_gen.get("inference_max_new_tokens", 400))


def get_doctor_diagnosis_max_tokens() -> int:
    return int(_doctor_gen.get("diagnosis_max_new_tokens", 600))


def get_patient_alignment_max_tokens() -> int:
    return int(_patient_gen.get("alignment_max_new_tokens", 500))


def get_patient_model_name() -> str:
    return str(_patient_cfg.get("model") or "")


def get_doctor_model_name() -> str:
    return str(_doctor_cfg.get("model") or "")


def get_judge_model_name() -> str:
    return str(_judge_cfg.get("model") or "")


def _model_slug(model: str) -> str:
    """'org/name' → 'name', 경로에 안전하지 않은 문자는 '_' 로 치환."""
    name = model.rsplit("/", 1)[-1]
    return re.sub(r"[^\w.\-]", "_", name)


def get_run_dir() -> str:
    """{patient}/{judge}/{doctor} 3단계 경로를 반환한다.

    계층 설계 근거:
      - patient : 변종 적음 (조건 고정) → 최상위
      - judge   : 중간 변종              → 중간
      - doctor  : 평가 대상, 종류 최다   → 최하위 leaf
    """
    p = _model_slug(_patient_cfg["model"])
    j = _model_slug(_judge_cfg["model"])
    d = _model_slug(_doctor_cfg["model"])
    return f"{p}/{j}/{d}"


def _cfg_for_role(role: Role) -> dict[str, Any]:
    if role == "patient":
        return _patient_cfg
    if role == "doctor":
        return _doctor_cfg
    return _judge_cfg


def get_display_model_name() -> str:
    p, d, j = _patient_cfg, _doctor_cfg, _judge_cfg
    return (
        f"Patient: {p['model']} ({p['provider']}) · "
        f"Doctor: {d['model']} ({d['provider']}) · "
        f"Judge: {j['model']} ({j['provider']})"
    )


def get_provider() -> str:
    """호환용: patient 쪽 provider (구 API)."""
    return str(_patient_cfg["provider"])


def _unique_local_model_names() -> list[str]:
    names: list[str] = []
    for cfg in (_patient_cfg, _doctor_cfg, _judge_cfg):
        if cfg["provider"] == "local":
            m = str(cfg["model"])
            if m not in names:
                names.append(m)
    return names


def get_status() -> dict[str, Any]:
    p, d, j = _patient_cfg, _doctor_cfg, _judge_cfg
    all_cfgs = (p, d, j)
    needs_openai      = any(c["provider"] == "openai"      for c in all_cfgs)
    needs_vllm        = any(c["provider"] == "vllm"        for c in all_cfgs)
    needs_gemini      = any(c["provider"] == "gemini"      for c in all_cfgs)
    needs_openrouter  = any(c["provider"] == "openrouter"  for c in all_cfgs)
    loading = False
    err: str | None = None

    if needs_openai:
        if not _openai_ready.is_set():
            loading = True
        elif _openai_error:
            err = _openai_error

    if needs_vllm:
        if not _vllm_ready.is_set():
            loading = True
        elif _vllm_error:
            err = _vllm_error

    if needs_gemini:
        if not _gemini_ready.is_set():
            loading = True
        elif _gemini_error:
            err = _gemini_error

    if needs_openrouter:
        if not _openrouter_ready.is_set():
            loading = True
        elif _openrouter_error:
            err = _openrouter_error

    for name in _unique_local_model_names():
        ev = _local_events.get(name)
        if ev and not ev.is_set():
            loading = True
        b = _local_bundles.get(name) or {}
        if b.get("error"):
            err = f"{name}: {b['error']}" if err is None else f"{err}; {name}: {b['error']}"

    loaded = not loading and err is None

    return {
        "loaded": loaded,
        "loading": loading,
        "error": err,
        "patient": {"provider": p["provider"], "model": p["model"]},
        "doctor":  {"provider": d["provider"], "model": d["model"]},
        "judge":   {"provider": j["provider"], "model": j["model"]},
    }


def _init_openai() -> None:
    global _openai_error
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        _openai_error = "OPENAI_API_KEY is missing; add it to .env"
    else:
        _openai_error = None
    _openai_ready.set()


def _init_openrouter() -> None:
    global _openrouter_error, _openrouter_client
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        _openrouter_error = "OPENROUTER_API_KEY is missing; add it to .env"
        _openrouter_ready.set()
        return
    try:
        from openai import OpenAI
        or_cfg = (_LLM.get("openrouter") or {}) if isinstance(_LLM.get("openrouter"), dict) else {}
        base_url = or_cfg.get("base_url", "https://openrouter.ai/api/v1")
        timeout  = float(or_cfg.get("timeout_seconds", 600))
        _openrouter_client = OpenAI(
            api_key=key,
            base_url=base_url,
            timeout=timeout,
        )
        _openrouter_error = None
        print(f"[INFO] OpenRouter client ready → {base_url}", flush=True)
    except Exception as e:
        _openrouter_error = str(e)
        print(f"[ERROR] OpenRouter client init failed: {e}", flush=True)
    finally:
        _openrouter_ready.set()


def _init_gemini() -> None:
    global _gemini_error
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        _gemini_error = "GEMINI_API_KEY is missing; add it to .env"
        _gemini_ready.set()
        return
    try:
        import google.generativeai as genai  # type: ignore[import]
        genai.configure(api_key=key)
        _gemini_error = None
        print("[INFO] Gemini client ready", flush=True)
    except ImportError:
        _gemini_error = (
            "google-generativeai package not installed; "
            "run: pip install google-generativeai"
        )
    except Exception as e:
        _gemini_error = str(e)
    finally:
        _gemini_ready.set()


def _load_local_model_named(hf_name: str) -> None:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        print(f"[INFO] Loading local model {hf_name} ...")
        tokenizer = AutoTokenizer.from_pretrained(hf_name)
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        device_map = "cuda:0" if torch.cuda.is_available() else "cpu"
        model = AutoModelForCausalLM.from_pretrained(
            hf_name,
            torch_dtype=dtype,
            device_map=device_map,
        )
        print(f"[INFO] Model {hf_name!r} loaded on device: {device_map}")
        _local_bundles[hf_name] = {
            "model": model,
            "tokenizer": tokenizer,
            "error": None,
        }
    except Exception as e:
        print(f"[ERROR] Model loading failed ({hf_name}): {e}")
        _local_bundles[hf_name] = {
            "model": None,
            "tokenizer": None,
            "error": str(e),
        }
    finally:
        if hf_name in _local_events:
            _local_events[hf_name].set()


# ── vLLM (OpenAI-compatible local server) ────────────────────────────────────
_vllm_client: Any | None = None
_vllm_ready = threading.Event()
_vllm_error: str | None = None


def _init_vllm() -> None:
    global _vllm_error
    v_cfg = (_LLM.get("vllm") or {}) if isinstance(_LLM.get("vllm"), dict) else {}
    base_url = v_cfg.get("base_url", "http://localhost:8001/v1")
    try:
        from openai import OpenAI
        global _vllm_client
        _vllm_client = OpenAI(
            api_key="EMPTY",
            base_url=base_url,
            timeout=float(v_cfg.get("timeout_seconds", 600)),
        )
        _vllm_error = None
        print(f"[INFO] vLLM client ready → {base_url}", flush=True)
    except Exception as e:
        _vllm_error = str(e)
        print(f"[ERROR] vLLM client init failed: {e}", flush=True)
    finally:
        _vllm_ready.set()


def _chat_vllm(messages: list[dict], max_new_tokens: int, role: Role) -> str:
    _vllm_ready.wait()
    if _vllm_error:
        raise RuntimeError(f"vLLM not available: {_vllm_error}")
    cfg = _cfg_for_role(role)
    g = _gen_for_role(role)
    model = str(cfg["model"])

    resp = _vllm_client.chat.completions.create(  # type: ignore[union-attr]
        model=model,
        messages=messages,
        max_tokens=max_new_tokens,
        temperature=float(g["temperature"]),
        top_p=float(g["top_p"]),
        extra_body={
            "chat_template_kwargs": {"enable_thinking": False},
        },
    )

    result = _message_content_text(resp.choices[0].message) if getattr(resp, "choices", None) else ""
    result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
    return result


# ── OpenAI (cloud) ────────────────────────────────────────────────────────────

def _openai_timeout_seconds(o_cfg: dict) -> float:
    if os.environ.get("OPENAI_TIMEOUT", "").strip():
        return float(os.environ["OPENAI_TIMEOUT"])
    return float(o_cfg.get("timeout_seconds", 600))


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        o_cfg = (_LLM.get("openai") or {}) if isinstance(_LLM.get("openai"), dict) else {}
        kw: dict[str, Any] = {
            "api_key": os.environ["OPENAI_API_KEY"],
            "timeout": _openai_timeout_seconds(o_cfg),
        }
        base = os.environ.get("OPENAI_BASE_URL", "").strip()
        if base:
            kw["base_url"] = base
        _openai_client = OpenAI(**kw)
    return _openai_client


def _message_content_text(msg: Any) -> str:
    """Normalize message.content (str or list of parts)."""
    c = getattr(msg, "content", None)
    if c is None:
        return ""
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        parts: list[str] = []
        for p in c:
            if isinstance(p, dict):
                if p.get("type") == "text" and "text" in p:
                    parts.append(str(p["text"]))
                elif "text" in p:
                    parts.append(str(p["text"]))
            elif hasattr(p, "text"):
                parts.append(str(getattr(p, "text", "")))
        return "".join(parts).strip()
    return str(c).strip()


def _should_log_openai_response() -> bool:
    v = os.environ.get("SIM_LOG_OPENAI", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    return bool((CONFIG.get("debug") or {}).get("log_openai_response", False))


def _log_openai_response_object(resp: Any) -> None:
    if not _should_log_openai_response():
        return
    print("========== OpenAI response ==========", flush=True)
    try:
        data = resp.model_dump() if hasattr(resp, "model_dump") else resp
        print(json.dumps(data, ensure_ascii=False, default=str, indent=2), flush=True)
    except Exception as e:
        print(f"[OpenAI] could not serialize response: {e}\n{resp!r}", flush=True)
    print("========== /OpenAI response ==========", flush=True)


def _openai_uses_max_completion_tokens(model: str, o_cfg: dict) -> bool:
    mode = o_cfg.get("use_max_completion_tokens", "auto")
    if mode is True:
        return True
    if mode is False:
        return False
    m = model.lower()
    return (
        "gpt-5" in m
        or m.startswith("o1")
        or m.startswith("o3")
        or m.startswith("o4")
    )


def _openai_reasoning_style_model(model: str) -> bool:
    m = model.lower()
    return (
        "gpt-5" in m
        or m.startswith("o1")
        or m.startswith("o3")
        or m.startswith("o4")
    )


def _effective_openai_output_limit(model: str, requested: int, o_cfg: dict) -> int:
    if not _openai_reasoning_style_model(model):
        return requested
    floor = int(o_cfg.get("reasoning_completion_floor", 512))
    return max(requested, floor)


def _chat_openai(messages: list[dict], max_new_tokens: int, role: Role) -> str:
    cfg = _cfg_for_role(role)
    o_cfg = cfg.get("openai") or {}
    model = str(cfg["model"])
    client = _get_openai_client()
    use_mct = _openai_uses_max_completion_tokens(model, o_cfg)
    limit = _effective_openai_output_limit(model, max_new_tokens, o_cfg)

    g = _gen_for_role(role)

    def _call(use_completion_tokens: bool):
        kw: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": float(g["temperature"]),
            "top_p": float(g["top_p"]),
        }
        reff = o_cfg.get("reasoning_effort")
        if reff and _openai_reasoning_style_model(model):
            kw["reasoning_effort"] = reff
        if use_completion_tokens:
            kw["max_completion_tokens"] = limit
        else:
            kw["max_tokens"] = limit
        return client.chat.completions.create(**kw)

    try:
        resp = _call(use_mct)
    except Exception as e:
        err = str(e).lower()
        if "max_completion_tokens" in err and not use_mct:
            resp = _call(True)
        elif "max_tokens" in err and use_mct and "unsupported" in err:
            resp = _call(False)
        else:
            raise
    _log_openai_response_object(resp)
    if not getattr(resp, "choices", None):
        return ""
    return _message_content_text(resp.choices[0].message)


# ── OpenRouter (OpenAI-compatible proxy) ──────────────────────────────────────

def _chat_openrouter(messages: list[dict], max_new_tokens: int, role: Role) -> str:
    _openrouter_ready.wait()
    if _openrouter_error:
        raise RuntimeError(f"OpenRouter not available: {_openrouter_error}")

    cfg = _cfg_for_role(role)
    g   = _gen_for_role(role)
    model = str(cfg["model"])

    resp = _openrouter_client.chat.completions.create(  # type: ignore[union-attr]
        model=model,
        messages=messages,
        max_tokens=max_new_tokens,
        temperature=float(g["temperature"]),
        top_p=float(g["top_p"]),
    )
    _log_openai_response_object(resp)
    if not getattr(resp, "choices", None):
        return ""
    result = _message_content_text(resp.choices[0].message)
    # Strip <think>…</think> blocks emitted by reasoning models (e.g. Qwen3)
    return re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()


# ── Gemini ────────────────────────────────────────────────────────────────────

def _messages_to_gemini(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Convert OpenAI-format messages to Gemini contents + system_instruction."""
    system_parts: list[str] = []
    contents: list[dict] = []
    for msg in messages:
        msg_role = msg.get("role", "user")
        content = msg.get("content", "")
        if msg_role == "system":
            system_parts.append(content)
        elif msg_role == "user":
            contents.append({"role": "user", "parts": [{"text": content}]})
        elif msg_role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
    system_instruction = "\n\n".join(system_parts) if system_parts else None
    return system_instruction, contents


def _chat_gemini(messages: list[dict], max_new_tokens: int, role: Role) -> str:
    _gemini_ready.wait()
    if _gemini_error:
        raise RuntimeError(f"Gemini not available: {_gemini_error}")

    import google.generativeai as genai  # type: ignore[import]

    cfg = _cfg_for_role(role)
    g = _gen_for_role(role)
    model_name = str(cfg["model"])

    system_instruction, contents = _messages_to_gemini(messages)

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction,
    )
    generation_config = genai.types.GenerationConfig(
        max_output_tokens=max_new_tokens,
        temperature=float(g["temperature"]),
        top_p=float(g["top_p"]),
    )
    resp = model.generate_content(contents, generation_config=generation_config)

    try:
        finish_reason = resp.candidates[0].finish_reason if resp.candidates else None
        # finish_reason 2 == MAX_TOKENS (응답이 토큰 한도로 잘림)
        if finish_reason is not None and str(finish_reason) not in ("FinishReason.STOP", "STOP", "1"):
            print(
                f"[WARN] Gemini response truncated (finish_reason={finish_reason}, "
                f"max_output_tokens={max_new_tokens}, role={role})",
                flush=True,
            )
    except Exception:
        pass

    return resp.text.strip() if getattr(resp, "text", None) else ""


# ── Local (HuggingFace) ───────────────────────────────────────────────────────

def _chat_local(messages: list[dict], max_new_tokens: int, role: Role) -> str:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: F401

    cfg = _cfg_for_role(role)
    hf_name = str(cfg["model"])
    ev = _local_events.get(hf_name)
    if ev:
        ev.wait()
    bundle = _local_bundles.get(hf_name) or {}
    err = bundle.get("error")
    if err:
        raise RuntimeError(f"Model not available ({hf_name}): {err}")
    model = bundle.get("model")
    tokenizer = bundle.get("tokenizer")
    if model is None or tokenizer is None:
        raise RuntimeError(f"Model not available: {hf_name!r}")

    try:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    except TypeError:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    device = next(model.parameters()).device
    inputs = tokenizer(text, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    g = _gen_for_role(role)
    gen_kw = {
        "max_new_tokens": max_new_tokens,
        "do_sample": bool(g.get("do_sample", True)),
        "temperature": float(g["temperature"]),
        "top_p": float(g["top_p"]),
        "pad_token_id": (
            tokenizer.pad_token_id
            or tokenizer.eos_token_id
        ),
    }

    with _model_lock:
        with torch.no_grad():
            out = model.generate(**inputs, **gen_kw)

    new_tokens = out[0][inputs["input_ids"].shape[1]:]
    resp = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return re.sub(r"<think>.*?</think>", "", resp, flags=re.DOTALL).strip()


# ── Public chat entry point ───────────────────────────────────────────────────

def chat(
    messages: list[dict],
    max_new_tokens: int | None = None,
    *,
    role: Role = "patient",
    phase: str | None = None,
    turn: int | None = None,
    source: str | None = None,
) -> str:
    """phase/turn/source 는 로그 표시용 메타데이터로 호출 동작에는 영향이 없다."""
    if max_new_tokens is None:
        max_new_tokens = int(_gen_for_role(role)["default_max_new_tokens"])

    cfg = _cfg_for_role(role)
    prov = cfg["provider"]

    if prov == "vllm":
        _vllm_ready.wait()
        if _vllm_error:
            raise RuntimeError(_vllm_error)
        result = _chat_vllm(messages, max_new_tokens, role)
    elif prov == "openai":
        _openai_ready.wait()
        if _openai_error:
            raise RuntimeError(_openai_error)
        result = _chat_openai(messages, max_new_tokens, role)
    elif prov == "openrouter":
        _openrouter_ready.wait()
        if _openrouter_error:
            raise RuntimeError(_openrouter_error)
        result = _chat_openrouter(messages, max_new_tokens, role)
    elif prov == "gemini":
        _gemini_ready.wait()
        if _gemini_error:
            raise RuntimeError(_gemini_error)
        result = _chat_gemini(messages, max_new_tokens, role)
    elif prov == "local":
        hf_name = str(cfg["model"])
        ev = _local_events.get(hf_name)
        if ev:
            ev.wait()
        result = _chat_local(messages, max_new_tokens, role)
    else:
        raise ValueError(
            f"Unknown llm provider for role {role!r}: {prov!r}; "
            "use 'vllm', 'openai', 'openrouter', 'gemini', or 'local'"
        )

    _append_to_log(role, messages, result, phase=phase, turn=turn, source=source)
    return result


def _bootstrap() -> None:
    all_cfgs = (_patient_cfg, _doctor_cfg, _judge_cfg)
    need_openai     = any(c["provider"] == "openai"      for c in all_cfgs)
    need_local      = any(c["provider"] == "local"       for c in all_cfgs)
    need_vllm       = any(c["provider"] == "vllm"        for c in all_cfgs)
    need_gemini     = any(c["provider"] == "gemini"      for c in all_cfgs)
    need_openrouter = any(c["provider"] == "openrouter"  for c in all_cfgs)

    if need_openai:
        _init_openai()
    else:
        _openai_ready.set()

    if need_vllm:
        _init_vllm()
    else:
        _vllm_ready.set()

    if need_gemini:
        threading.Thread(target=_init_gemini, daemon=True).start()
    else:
        _gemini_ready.set()

    if need_openrouter:
        _init_openrouter()
    else:
        _openrouter_ready.set()

    if not any((need_openai, need_local, need_vllm, need_gemini, need_openrouter)):
        global _openai_error
        _openai_error = (
            'No llm role uses "openai", "vllm", "openrouter", "gemini", or "local"; '
            "check config.json"
        )

    for name in _unique_local_model_names():
        if name not in _local_events:
            _local_events[name] = threading.Event()
            threading.Thread(
                target=_load_local_model_named,
                args=(name,),
                daemon=True,
            ).start()


_bootstrap()
