"""Per-profile simulation worker for the fixed-profile batch (see
script/run_profile_batch.py). Unlike batch_worker.py's run_disorder() — which
samples an ad-hoc patient on the fly from the KnowledgeGraph for each run — this
module runs exactly one simulation per pre-generated profile JSON (e.g. under
data/profiles/add_requirements/<difficulty>/<disease>/<disease>_S<NNN>_P<NNN>.json),
one profile = one simulation.

Must run in its own spawned process (ProcessPoolExecutor with mp_context="spawn"):
patient.py / utils.llm.py hold mutable module-global state (current log path,
SYSTEM_PROMPT) that is not safe to share across concurrently-running profiles in
the same process — same constraint documented in batch_worker.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def run_profile(
    profile_path: str,
    logs_dir: str,
    results_dir: str,
    max_turns: int,
    style: str | None = None,
) -> dict[str, Any]:
    """Run one simulation for a single profile JSON. Returns a status dict.

    `style` overrides the conversation style for this run only; with it the same profile
    can be run once per style, each landing in its own <profile>_<style> files.

    Skips (status="skipped") if both the json log and result JSON already exist,
    so a batch can be safely re-run to pick up where it left off.
    """
    profile_p = Path(profile_path)
    profile_id = profile_p.stem
    logs_path = Path(logs_dir)
    results_path = Path(results_dir)

    # KG 모드 차단. patient 는 import 시점에 프로필을 빌드하므로 그 전에 검사한다.
    from utils.config import CONFIG
    if bool((CONFIG.get("patient") or {}).get("use_knowledge_graph", False)):
        raise RuntimeError(
            "profile batch cannot run with patient.use_knowledge_graph=true "
            "(KG builder pollutes sys.path and breaks eval.symptom_diagnosis); "
            "set it to false in config/config.json"
        )

    import patient
    from simulation_core import run_interview_simulation
    from utils.llm import set_log_path

    # 스타일을 파일명에 붙여 같은 프로필을 스타일만 바꿔 돌려도 덮어쓰지 않게 한다.
    # (eval 은 파일명 앞머리의 D코드만 보므로 접미사는 안전하다.)
    if style:
        patient.set_conversation_style(style)
    style = patient.current_conversation_style()
    case_id = f"{profile_id}_{style}" if style else profile_id

    txt_log_path = logs_path / f"{case_id}.txt"
    json_log_path = logs_path / f"{case_id}.json"
    result_json_path = results_path / f"{case_id}_result.json"

    if json_log_path.exists() and result_json_path.exists():
        return {"profile_id": profile_id, "style": style, "status": "skipped"}

    set_log_path(txt_log_path)

    try:
        patient.set_symptom_profile_path(profile_p)
        patient_system = patient.SYSTEM_PROMPT
    except Exception as e:
        return {"profile_id": profile_id, "status": "error", "error": f"profile load failed: {e}"}

    try:
        result = run_interview_simulation(
            patient_system=patient_system,
            max_turns=max_turns,
            verbose=False,
        )
    except Exception as e:
        return {"profile_id": profile_id, "status": "error", "error": f"simulation failed: {e}"}

    mem = result["doctor_memory"]
    fd = mem.get("final_diagnosis") or {}
    json_log_data = {
        "profile_id": profile_id,
        "profile_path": str(profile_p),
        "conversation_style": style,
        "closed_at_patient_turn": result.get("closed_at_patient_turn"),
        "final_diagnosis": fd.get("diagnosis", ""),
        "transcript": [
            {"role": r, "content": c} for r, c in result.get("transcript", [])
        ],
        "doctor_memory": mem,
    }
    json_log_path.write_text(
        json.dumps(json_log_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Symptom extraction + KG-deterministic candidate_set — required by the
    # downstream eval/evaluate_*.py scripts (they read results/<run_dir>/*_result.json).
    try:
        import eval.symptom_diagnosis as sd
        all_symptoms = sd.load_all_symptoms()
        criteria = sd.load_diagnostic_criteria()
        sd_result = sd.process_log(txt_log_path, all_symptoms, criteria)
        if sd_result is not None:
            results_path.mkdir(parents=True, exist_ok=True)
            result_json_path.write_text(
                json.dumps(sd_result, indent=2, ensure_ascii=False), encoding="utf-8"
            )
    except Exception as e:
        return {
            "profile_id": profile_id,
            "style": style,
            "status": "sim_ok_sd_failed",
            "final_diagnosis": fd.get("diagnosis", ""),
            "error": f"symptom_diagnosis failed: {e}",
        }

    return {
        "profile_id": profile_id,
        "style": style,
        "status": "done",
        "final_diagnosis": fd.get("diagnosis", ""),
    }
