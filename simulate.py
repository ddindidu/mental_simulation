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
import sys
from pathlib import Path

import doctor
import patient
from simulation_core import run_interview_simulation
from utils.config import CONFIG
import utils.llm as llm
from utils.paths import PROJECT_ROOT, RESULTS_DIR
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
        required=True,
        help="증상 프로필 JSON 경로 (예: data/profiles/symptom_profile.json)",
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

    profile_path = args.profile.resolve()
    if not profile_path.is_file():
        print(f"프로필 파일이 없습니다: {profile_path}", file=sys.stderr)
        return 1

    out_dir = (args.output_dir or RESULTS_DIR).resolve()
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

    patient.set_symptom_profile_path(profile_path)
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

    memory_path = out_dir / "doctor_memory.json"
    transcript_path = out_dir / "transcript.json"

    doctor.persist_doctor_memory_json(dm, path=memory_path)

    tx_payload = doctor.build_interview_transcript_payload(
        transcript,
        max_turns_config=max_turns,
        closed_at_patient_turn=closed_t,
        patient_model=get_patient_model_name(),
        doctor_model=get_doctor_model_name(),
    )
    tx_payload["metadata"]["symptom_profile_path"] = str(profile_path)
    tx_payload["metadata"]["working_dir"] = str(PROJECT_ROOT)
    doctor.persist_interview_transcript_json(tx_payload, path=transcript_path)

    print(f"완료: doctor_memory → {memory_path}")
    print(f"       transcript   → {transcript_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
