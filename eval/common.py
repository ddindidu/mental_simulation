"""Shared helpers for the eval/*.py scripts: ICD-10 → disease-id mapping and
final-diagnosis parsing. Side-effect free on import (no argv parsing), so any
eval/reporting script can use it."""
from __future__ import annotations

import json
import re
from pathlib import Path

KG_DIR = Path(__file__).resolve().parent.parent / "mentalbench" / "resources" / "knowledge_graph" / "EN"
DISORDER_ICD10_FILE = KG_DIR / "disorder_icd10.json"

_DIAGNOSIS_KEY_RE = re.compile(r'"diagnosis"\s*:\s*"([^"]+)"', re.IGNORECASE)


def load_code2id() -> dict[str, str]:
    """{ICD-10 code: disease_id}. Every code in a disorder's
    icd10_accepted_codes maps to it (falls back to its single icd10_code)."""
    data = json.loads(DISORDER_ICD10_FILE.read_text(encoding="utf-8"))
    code2id: dict[str, str] = {}
    for k, v in data.items():
        for code in v.get("icd10_accepted_codes") or [v["icd10_code"]]:
            code2id[code.strip().upper()] = k
    return code2id


def unwrap_json_diagnosis(raw: str) -> str:
    """Some doctor models (observed: claude-sonnet-5, occasionally
    gemini-3.8-flash) return the final-diagnosis step as a raw JSON object
    string (e.g. '{"diagnosis": "F90.0", "candidates": [...], ...}') that gets
    stored verbatim. Return the inner "diagnosis" value in that case; return
    `raw` unchanged otherwise."""
    stripped = raw.strip()
    if not stripped.startswith("{"):
        return raw
    try:
        parsed = json.loads(stripped)
        for key in ("diagnosis", "DIAGNOSIS", "Diagnosis"):
            if isinstance(parsed, dict) and key in parsed:
                return str(parsed[key]).strip()
    except json.JSONDecodeError:
        pass
    m = _DIAGNOSIS_KEY_RE.search(stripped)
    return m.group(1).strip() if m else raw


def read_final_diagnosis(log_file: Path) -> str:
    """The doctor's final diagnosis string (unwrapped) from the .json
    simulation log's top-level `final_diagnosis`; "" if missing/unreadable."""
    try:
        data = json.loads(log_file.with_suffix(".json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    return unwrap_json_diagnosis(str(data.get("final_diagnosis") or "").strip())


def resolve_disease_id(raw_diagnosis: str, code2id: dict[str, str]) -> str | None:
    """Doctor's diagnosis string (ICD-10, possibly JSON-wrapped) → disease id."""
    if not raw_diagnosis:
        return None
    return code2id.get(unwrap_json_diagnosis(raw_diagnosis).strip().upper())
