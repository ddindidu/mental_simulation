from __future__ import annotations

import json
import os
import re
import threading
from typing import Any, Literal

from .config import CONFIG

_LLM = CONFIG.get("llm") or {}

# ── Logging ──────────────────────────────────────────────────────────────────
# 시뮬레이션 시작(rotate_log_file 호출)마다 logging1.txt, logging2.txt ... 순으로 증가
_current_log_path: "Path | None" = None


def rotate_log_file() -> "Path":
    """로그 파일 번호를 자동 증가시켜 새 파일 경로를 설정하고 반환한다.
    logging1.txt 이 없으면 logging1.txt 를 사용하고,
    이미 있으면 logging(n+1).txt 를 사용한다.
    """
    global _current_log_path
    from .paths import PROJECT_ROOT
    n = 1
    while (PROJECT_ROOT / f"logging{n}.txt").exists():
        n += 1
    _current_log_path = PROJECT_ROOT / f"logging{n}.txt"
    print(f"[llm] Log file: {_current_log_path}", flush=True)
    return _current_log_path


def set_log_path(path: "Path | str") -> None:
    """배치 평가 등에서 로그 파일 경로를 직접 지정한다."""
    global _current_log_path
    from pathlib import Path as _Path
    _current_log_path = _Path(path)
    _current_log_path.parent.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
Role = Literal["patient", "doctor"]

# Per-role resolved config: { "provider", "model", "openai": {...} }
_patient_cfg: dict[str, Any]
_doctor_cfg: dict[str, Any]

_openai_client: Any | None = None
_openai_ready = threading.Event()
_openai_error: str | None = None

# Local: one bundle per HuggingFace model id (supports patient/doctor different models)
_local_bundles: dict[str, dict[str, Any]] = {}
_local_events: dict[str, threading.Event] = {}
_model_lock = threading.Lock()


def _merge_openai(role_partial: dict) -> dict[str, Any]:
    shared = (_LLM.get("openai") or {}) if isinstance(_LLM.get("openai"), dict) else {}
    extra = role_partial.get("openai") if isinstance(role_partial.get("openai"), dict) else {}
    return {**shared, **extra}


def _normalize_role_configs() -> tuple[dict[str, Any], dict[str, Any]]:
    """Legacy: top-level provider/model only → both roles share. New: patient + doctor blocks."""
    raw = _LLM
    shared_openai = raw.get("openai") if isinstance(raw.get("openai"), dict) else {}

    if isinstance(raw.get("patient"), dict) or isinstance(raw.get("doctor"), dict):
        legacy_prov = (raw.get("provider") or "openai").lower().strip()
        legacy_model = raw.get("model") or "gpt-4o-mini"

        def one(role_key: str, default_model: str) -> dict[str, Any]:
            block = raw.get(role_key) if isinstance(raw.get(role_key), dict) else {}
            prov = (block.get("provider") or legacy_prov).lower().strip()
            model = block.get("model") or legacy_model or default_model
            o = {**shared_openai, **(block.get("openai") or {})}
            return {"provider": prov, "model": str(model), "openai": o}

        return one("patient", "gpt-4o-mini"), one("doctor", "gpt-4o-mini")

    prov = (raw.get("provider") or "openai").lower().strip()
    model = raw.get("model") or "gpt-4o-mini"
    cfg = {
        "provider": prov,
        "model": str(model),
        "openai": {**shared_openai},
    }
    return cfg, cfg


_patient_cfg, _doctor_cfg = _normalize_role_configs()


def _normalize_generation() -> tuple[dict[str, Any], dict[str, Any]]:
    """Legacy: flat generation dict → patient/doctor에 동일 값 복제. 새 형식: patient / doctor 블록."""
    raw = CONFIG.get("generation") or {}
    legacy_shared = {
        k: v
        for k, v in raw.items()
        if k not in ("patient", "doctor") and not isinstance(v, dict)
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

    if isinstance(raw.get("patient"), dict) or isinstance(raw.get("doctor"), dict):
        pb = raw.get("patient") if isinstance(raw.get("patient"), dict) else {}
        db = raw.get("doctor") if isinstance(raw.get("doctor"), dict) else {}
        patient = {**patient_defaults, **legacy_shared, **pb}
        doctor = {**doctor_defaults, **legacy_shared, **db}
        return patient, doctor

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
    return common, doctor_only


_patient_gen, _doctor_gen = _normalize_generation()


def _gen_for_role(role: Role) -> dict[str, Any]:
    return _patient_gen if role == "patient" else _doctor_gen


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


def _cfg_for_role(role: Role) -> dict[str, Any]:
    return _patient_cfg if role == "patient" else _doctor_cfg


def get_display_model_name() -> str:
    """헤더 등에 표시: 두 역할 모델을 한 줄로."""
    p, d = _patient_cfg, _doctor_cfg
    return (
        f"Patient: {p['model']} ({p['provider']}) · "
        f"Doctor: {d['model']} ({d['provider']})"
    )


def get_provider() -> str:
    """호환용: patient 쪽 provider (구 API)."""
    return str(_patient_cfg["provider"])


def get_status() -> dict[str, Any]:
    p, d = _patient_cfg, _doctor_cfg
    needs_openai = p["provider"] == "openai" or d["provider"] == "openai"
    needs_vllm = p["provider"] == "vllm" or d["provider"] == "vllm"
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
        "doctor": {"provider": d["provider"], "model": d["model"]},
    }


def _unique_local_model_names() -> list[str]:
    names: list[str] = []
    for cfg in (_patient_cfg, _doctor_cfg):
        if cfg["provider"] == "local":
            m = str(cfg["model"])
            if m not in names:
                names.append(m)
    return names


def _init_openai() -> None:
    global _openai_error
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        _openai_error = "OPENAI_API_KEY is missing; add it to .env"
    else:
        _openai_error = None
    _openai_ready.set()


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
            api_key="EMPTY",  # vLLM은 인증 불필요
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
        max_tokens=16384,
        temperature=float(g["temperature"]),
        top_p=float(g["top_p"]),
        extra_body={
            "chat_template_kwargs": {"enable_thinking": False},
        }, 
    )

    result = _message_content_text(resp.choices[0].message) if getattr(resp, "choices", None) else ""
    # <think>...</think> 태그 제거 (Qwen3 reasoning 모드)
    result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()

    from .paths import PROJECT_ROOT
    log_path = _current_log_path if _current_log_path is not None else (PROJECT_ROOT / "logging.txt")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"========== INPUT [{role}] ==========\n")
        f.write(json.dumps(messages, ensure_ascii=False, indent=2) + "\n")
        f.write(f"========== OUTPUT [{role}] ==========\n")
        f.write(result + "\n")
        f.write("=====================================\n\n")

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
    """Normalize message.content (str or list of parts for some models)."""
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
    """Print full API response to stdout when logging is enabled."""
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
    resp = re.sub(r"<think>.*?</think>", "", resp, flags=re.DOTALL).strip()

    from .paths import PROJECT_ROOT
    log_path = _current_log_path if _current_log_path is not None else (PROJECT_ROOT / "logging.txt")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"========== INPUT [{role}] ==========\n")
        f.write(text + "\n")
        f.write(f"========== OUTPUT [{role}] ==========\n")
        f.write(resp + "\n")
        f.write("=====================================\n\n")

    return resp


def chat(
    messages: list[dict],
    max_new_tokens: int | None = None,
    *,
    role: Role = "patient",
) -> str:
    if max_new_tokens is None:
        max_new_tokens = int(_gen_for_role(role)["default_max_new_tokens"])

    cfg = _cfg_for_role(role)
    prov = cfg["provider"]

    if prov == "vllm":
        _vllm_ready.wait()
        if _vllm_error:
            raise RuntimeError(_vllm_error)
        return _chat_vllm(messages, max_new_tokens, role)

    if prov == "openai":
        _openai_ready.wait()
        if _openai_error:
            raise RuntimeError(_openai_error)
        return _chat_openai(messages, max_new_tokens, role)

    if prov == "local":
        hf_name = str(cfg["model"])
        ev = _local_events.get(hf_name)
        if ev:
            ev.wait()
        return _chat_local(messages, max_new_tokens, role)

    raise ValueError(f"Unknown llm provider for role {role!r}: {prov!r}; use 'vllm', 'local', or 'openai'")


def _bootstrap() -> None:
    need_openai = _patient_cfg["provider"] == "openai" or _doctor_cfg["provider"] == "openai"
    need_local = _patient_cfg["provider"] == "local" or _doctor_cfg["provider"] == "local"
    need_vllm = _patient_cfg["provider"] == "vllm" or _doctor_cfg["provider"] == "vllm"

    if need_openai:
        _init_openai()
    else:
        _openai_ready.set()

    if need_vllm:
        _init_vllm()
    else:
        _vllm_ready.set()

    if not need_openai and not need_local and not need_vllm:
        global _openai_error
        _openai_error = 'No llm role uses "openai", "vllm", or "local"; check config.json'

    for name in _unique_local_model_names():
        if name not in _local_events:
            _local_events[name] = threading.Event()
            threading.Thread(
                target=_load_local_model_named,
                args=(name,),
                daemon=True,
            ).start()


_bootstrap()
