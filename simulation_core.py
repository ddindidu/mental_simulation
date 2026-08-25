"""
Flask 없이 인터뷰 시뮬레이션 한 번 실행 (simulate.py에서 사용).
"""
from __future__ import annotations

import json
from typing import Any

import doctor
import patient
from utils.llm import chat as llm_chat
from utils.llm import get_doctor_diagnosis_max_tokens
from utils.llm import get_doctor_inference_max_tokens
from utils.llm import get_doctor_model_name
from utils.llm import get_patient_alignment_max_tokens


def _log(verbose: bool, which: str, step: str, messages: list) -> None:
    if not verbose:
        return
    print(
        f"\n========== {which} | {step} | {len(messages)} messages ==========",
        flush=True,
    )
    print(json.dumps(messages, ensure_ascii=False, indent=2), flush=True)


def run_interview_simulation(
    *,
    patient_system: str,
    max_turns: int,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    인터뷰를 끝까지 돌린 뒤 완료된 doctor_memory를 반환한다.
    transcript는 doctor_memory와 함께 재구성하려면 별도로 반환해야 하므로
    (finalize 전에 필요) dict에 넣어 반환한다.

    Returns:
        {"doctor_memory": dict, "transcript": list[tuple[str,str]], "closed_at_patient_turn": int}
    """
    if max_turns < 1:
        raise ValueError("max_turns must be >= 1")

    doctor_model = get_doctor_model_name()
    inference_system = doctor.get_inference_system_prompt(doctor_model)
    final_system = doctor.get_final_diagnosis_system_prompt(doctor_model)
    diag_tokens = get_doctor_diagnosis_max_tokens()
    inf_tokens = get_doctor_inference_max_tokens()
    align_tokens = get_patient_alignment_max_tokens()

    doctor_memory: dict[str, Any] = doctor.new_doctor_memory()
    patient_hist: list[dict] = [{"role": "system", "content": patient_system}]
    transcript: list[tuple[str, str]] = []

    opening_messages = [
        {
            "role": "system",
            "content": doctor.get_questioning_system_prompt(max_turns, [], doctor_model),
        },
        {"role": "user", "content": doctor.opening_user_message()},
    ]
    _log(verbose, "Doctor LLM (questioning)", "opening", opening_messages)
    doctor_raw = llm_chat(
        opening_messages,
        role="doctor",
        phase="opening",
        turn=0,
        source="doctor.opening_user_message",
    )
    q_open = doctor.parse_questioning_result(doctor_raw)
    question_text = q_open["question"]
    doctor_memory["opening_question"] = {
        "category": q_open["category"],
        "subcategory": q_open["subcategory"],
        "question": question_text,
    }

    transcript.append(("doctor", question_text))
    if verbose:
        print(f"[opening] doctor question: {question_text[:200]}...", flush=True)

    patient_hist.append({"role": "user", "content": question_text})

    for t in range(1, max_turns + 1):
        doctor_last = patient_hist[-1]["content"]
        align_messages = patient.build_alignment_messages(doctor_last, t)
        _log(verbose, "Patient LLM (alignment)", f"turn {t}", align_messages)
        align_raw = llm_chat(
            align_messages,
            max_new_tokens=align_tokens,
            role="patient",
            phase="alignment",
            turn=t,
            source="patient.build_alignment_messages",
        )
        parsed_align = patient.parse_alignment_result(align_raw)
        strategy_text = patient.format_alignment_for_response(parsed_align)

        resp_messages = patient.build_response_messages(patient_hist, strategy_text)
        _log(verbose, "Patient LLM (response)", f"turn {t}", resp_messages)
        patient_msg = llm_chat(
            resp_messages,
            role="patient",
            phase="response",
            turn=t,
            source="patient.build_response_messages",
        )
        patient_hist.append({"role": "assistant", "content": patient_msg})
        transcript.append(("patient", patient_msg))
        if verbose:
            print(f"[turn {t}] patient: {patient_msg[:200]}...", flush=True)

        tr_text = doctor.format_interview_transcript(transcript)

        inf_messages = [
            {"role": "system", "content": inference_system},
            {"role": "user", "content": doctor.inference_user_payload(
                tr_text,
                previous_candidates=(
                    doctor_memory["inference_history"][-1]["candidates"]
                    if doctor_memory["inference_history"]
                    else []
                ),
            )},
        ]
        _log(verbose, "Doctor LLM (inference)", f"turn {t}", inf_messages)
        inf_raw = llm_chat(
            inf_messages,
            max_new_tokens=inf_tokens,
            role="doctor",
            phase="inference",
            turn=t,
            source="doctor.inference_user_payload",
        )
        candidates, inf_note, is_final = doctor.parse_inference_result(inf_raw)
        if verbose:
            print(f"[turn {t}] inference candidates: {candidates}, is_final={is_final}", flush=True)

        doctor.update_doctor_memory_after_inference(
            doctor_memory,
            turn=t,
            candidates=candidates,
            note=inf_note,
            raw_model=inf_raw,
            is_final=is_final,
        )

        if doctor.should_finish_interview(is_final, t, max_turns):
            fin_messages = [
                {"role": "system", "content": final_system},
                {
                    "role": "user",
                    "content": doctor.final_diagnosis_user_payload(tr_text, candidates),
                },
            ]
            _log(verbose, "Doctor LLM (final)", f"turn {t}", fin_messages)
            diagnosis_raw = llm_chat(
                fin_messages,
                max_new_tokens=diag_tokens,
                role="doctor",
                phase="final",
                turn=t,
                source="doctor.final_diagnosis_user_payload",
            )
            fd = doctor.parse_final_diagnosis_result(diagnosis_raw)
            doctor.finalize_doctor_memory(
                doctor_memory,
                closed_at_patient_turn=t,
                final_diagnosis=fd,
                final_candidates_used=candidates,
            )
            if verbose:
                print(f"[done] final diagnosis: {fd.get('diagnosis', '')}", flush=True)
            return {
                "doctor_memory": doctor_memory,
                "transcript": transcript,
                "closed_at_patient_turn": t,
            }

        questioning_messages = [
            {
                "role": "system",
                "content": doctor.get_questioning_system_prompt(max_turns, candidates, doctor_model),
            },
            {
                "role": "user",
                "content": doctor.questioning_followup_user_payload(tr_text, candidates),
            },
        ]
        _log(
            verbose,
            "Doctor LLM (questioning)",
            f"follow-up after turn {t}",
            questioning_messages,
        )
        doctor_raw = llm_chat(
            questioning_messages,
            role="doctor",
            phase="followup",
            turn=t,
            source="doctor.questioning_followup_user_payload",
        )
        q_follow = doctor.parse_questioning_result(doctor_raw)
        question_text = q_follow["question"]

        transcript.append(("doctor", question_text))
        if verbose:
            print(f"[turn {t}] doctor follow-up: {question_text[:200]}...", flush=True)

        patient_hist.append({"role": "user", "content": question_text})

    raise RuntimeError(
        "시뮬레이션이 finalize 없이 종료되었습니다 (내부 오류 가능)."
    )
