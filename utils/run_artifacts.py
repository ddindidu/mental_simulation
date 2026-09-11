"""Where a single run's artifacts go, and what they are called.

The web UI and simulate.py both run one interview at a time, and both should leave the
same files behind — otherwise a run started from the CLI cannot be opened in review_app,
and repeated runs quietly overwrite one another. Both call in here so the naming rule
lives in one place.
"""

from __future__ import annotations

import json
from pathlib import Path

from .llm import get_run_dir
from .paths import artifact_dirs, ensure_run_root


def single_case_id(patient_cfg: dict) -> str:
    """The case name for a single run — the batch's D001_S001_P001 slot.

    Profile mode uses the profile's filename, KG mode "<disease>_kg". The conversation
    style is appended so the same profile run under a different style does not overwrite
    the first; eval matches on the leading D-code only, so the suffix is safe.
    """
    style = patient_cfg.get("conversation_style") or ""
    suffix = f"_{style}" if style else ""
    if patient_cfg.get("use_knowledge_graph"):
        return f"{patient_cfg.get('disease_code') or 'unknown'}_kg{suffix}"
    return (Path(patient_cfg.get("symptom_profile_path") or "").stem or "single") + suffix


def single_run_paths(case_id: str) -> tuple[Path, Path, Path]:
    """(txt_log, json_log, result_json) under saved/run_single_<date>/."""
    ensure_run_root("single")
    results_dir, logs_dir, _ = artifact_dirs(get_run_dir(), mode="single")
    logs_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    return (
        logs_dir / f"{case_id}.txt",
        logs_dir / f"{case_id}.json",
        results_dir / f"{case_id}_result.json",
    )


def persist_single_artifacts(
    case_id: str,
    json_log_path: Path,
    txt_log_path: Path,
    result_json_path: Path,
    transcript: list,
    doctor_memory: dict,
    conversation_style: str = "",
    profile_path: str = "",
) -> None:
    """Write a single run's artifacts in the same form the batch writes them.

    Failures are swallowed: a run that finished should not be lost because a follow-up
    extraction failed.
    """
    fd = (doctor_memory.get("final_diagnosis") or {})
    try:
        json_log_path.write_text(
            json.dumps({
                "case_id": case_id,
                "profile_path": profile_path,
                "conversation_style": conversation_style,
                "closed_at_patient_turn": doctor_memory.get("closed_at_patient_turn"),
                "final_diagnosis": fd.get("diagnosis", ""),
                "transcript": [{"role": r, "content": c} for r, c in transcript],
                "doctor_memory": doctor_memory,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[simulate] log saved → {json_log_path}", flush=True)
    except Exception as e:
        print(f"[simulate] json log save failed: {e}", flush=True)

    try:
        from batch_worker import _make_symptom_diagnosis_runner
        _make_symptom_diagnosis_runner(case_id)(txt_log_path, result_json_path)
    except Exception as e:
        print(f"[simulate] symptom_diagnosis failed: {e}", flush=True)
