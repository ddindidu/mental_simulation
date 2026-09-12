#!/usr/bin/env python3
"""
Flask 서버 없이 증상 프로필을 지정해 인터뷰 시뮬레이션을 실행하고
doctor_memory.json 과 transcript.json 을 저장한다.

예:
  python simulate.py --profile data/profiles/symptom_profile.json
  python simulate.py -p data/profiles/symptom_profile_2.json -o data/results --verbose
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 단건 실행 산출물은 saved/run_single_<날짜>/ 로 간다 (MS_RUN 지정 시 그쪽 우선).
os.environ.setdefault("MS_RUN_MODE", "single")

import doctor
import patient
from simulation_core import run_interview_simulation
from utils.config import CONFIG
import utils.llm as llm
from utils.paths import PROJECT_ROOT, RESULTS_DIR, ensure_run_root
from utils.llm import set_log_path
from utils.run_artifacts import persist_single_artifacts, single_case_id, single_run_paths
from utils.llm import get_doctor_model_name
from utils.llm import get_patient_model_name


def _apply_llm_model_overrides(
    patient_model: str | None,
    doctor_model: str | None,
) -> None:
    """이번 실행만 patient/doctor 모델명을 덮어쓴다 (config.json은 수정하지 않음)."""
    if patient_model and patient_model.strip():
        llm._patient_cfg["model"] = patient_model.strip()
    if doctor_model and doctor_model.strip():
        llm._doctor_cfg["model"] = doctor_model.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run patient–doctor interview simulation (no Flask).",
    )
    parser.add_argument(
        "--profile",
        "-p",
        type=Path,
        default=None,
        help=(
            "증상 프로필 JSON 경로 (예: data/profiles/symptom_profile.json). "
            "미지정 시 config.json의 patient.use_knowledge_graph 설정을 따름."
        ),
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=None,
        help=f"doctor_memory.json, transcript.json 저장 디렉터리 (기본: {RESULTS_DIR})",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="config.json simulation.max_turns 대신 사용할 최대 환자 턴 수",
    )
    parser.add_argument(
        "--style",
        default=None,
        choices=patient.conversation_style_names() + ["random"],
        help="대화 스타일 (미지정 시 config.json patient.conversation_style)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="LLM 메시지 로그 출력",
    )
    parser.add_argument(
        "--patient-model",
        default=None,
        help="Patient LLM 모델명 (미지정 시 config.json llm.patient.model)",
    )
    parser.add_argument(
        "--doctor-model",
        default=None,
        help="Doctor LLM 모델명 (미지정 시 config.json llm.doctor.model)",
    )
    args = parser.parse_args()

    _apply_llm_model_overrides(args.patient_model, args.doctor_model)

    if args.style:
        patient.set_conversation_style(args.style)

    use_kg = bool((CONFIG.get("patient") or {}).get("use_knowledge_graph", False))

    if args.profile is not None:
        profile_path = args.profile.resolve()
        if not profile_path.is_file():
            print(f"프로필 파일이 없습니다: {profile_path}", file=sys.stderr)
            return 1
    elif not use_kg:
        print(
            "--profile 미지정 + use_knowledge_graph=false: 프로필 경로를 지정해 주세요.",
            file=sys.stderr,
        )
        return 1
    else:
        profile_path = None

    if profile_path is not None:
        patient.set_symptom_profile_path(profile_path)

    # 웹 UI와 같은 산출물을 남긴다: logs/<case>.txt(프롬프트), logs/<case>.json(전사),
    # results/<case>_result.json. case 이름에 스타일이 붙어 있어 같은 프로필을 스타일만
    #바꿔 돌려도 서로 덮어쓰지 않는다.
    case_id = single_case_id(patient.current_config())
    txt_log_path, json_log_path, result_json_path = single_run_paths(case_id)
    set_log_path(txt_log_path)
    out_dir = args.output_dir.resolve() if args.output_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    max_turns = args.max_turns
    if max_turns is None:
        max_turns = int(CONFIG["simulation"]["max_turns"])
    if max_turns < 1:
        print("--max-turns 는 1 이상이어야 합니다.", file=sys.stderr)
        return 1

    print(
        "[simulate] "
        f"patient_model={get_patient_model_name()} | "
        f"doctor_model={get_doctor_model_name()} | "
        f"max_turns={max_turns}",
        flush=True,
    )

    # doctor.py의 저장 경로는 모듈 로드 시점에 고정돼 있다. None으로 두어 단건이
    # doctor_memory.json / transcript.json을 따로 남기지 않게 한다 — 두 정보 모두
    # logs/<case>.json 에 들어간다.
    doctor.DOCTOR_MEMORY_FILE = None
    doctor.TRANSCRIPT_FILE = None
    print(f"[simulate] case={case_id} | style={patient.current_conversation_style()} → {txt_log_path}", flush=True)

    patient_system = patient.SYSTEM_PROMPT

    try:
        result = run_interview_simulation(
            patient_system=patient_system,
            max_turns=max_turns,
            verbose=args.verbose,
        )
    except Exception as e:
        print(f"시뮬레이션 오류: {e}", file=sys.stderr)
        return 1

    dm = result["doctor_memory"]
    transcript = result["transcript"]
    closed_t = result["closed_at_patient_turn"]

    conversation_style = patient.current_conversation_style()
    dm["closed_at_patient_turn"] = closed_t
    persist_single_artifacts(
        case_id,
        json_log_path,
        txt_log_path,
        result_json_path,
        transcript,
        dm,
        conversation_style=conversation_style,
        profile_path=str(profile_path) if profile_path else "",
    )

    # --output-dir를 준 경우에만 예전 형식(doctor_memory.json / transcript.json)도 남긴다.
    if out_dir:
        doctor.persist_doctor_memory_json(dm, path=out_dir / "doctor_memory.json")
        tx_payload = doctor.build_interview_transcript_payload(
            transcript,
            max_turns_config=max_turns,
            closed_at_patient_turn=closed_t,
            patient_model=get_patient_model_name(),
            doctor_model=get_doctor_model_name(),
        )
        tx_payload["metadata"]["symptom_profile_path"] = str(profile_path) if profile_path else "kg_sampled"
        tx_payload["metadata"]["conversation_style"] = conversation_style
        tx_payload["metadata"]["working_dir"] = str(PROJECT_ROOT)
        doctor.persist_interview_transcript_json(tx_payload, path=out_dir / "transcript.json")
        print(f"       (추가) {out_dir}")

    print(f"완료: case={case_id} | style={conversation_style}")
    print(f"       prompts    → {txt_log_path}")
    print(f"       transcript → {json_log_path}")
    print(f"       result     → {result_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
