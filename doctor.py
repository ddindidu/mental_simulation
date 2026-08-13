from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from utils.paths import DEFAULT_DOCTOR_MEMORY_PATH, DEFAULT_TRANSCRIPT_PATH

DOCTOR_MEMORY_FILE = DEFAULT_DOCTOR_MEMORY_PATH
TRANSCRIPT_FILE = DEFAULT_TRANSCRIPT_PATH


def _no_think_prefix(doctor_model: str = "") -> str:
    """'/no_think' is a Qwen3 control token that disables its thinking phase.
    It's meaningless (and shows up as literal text) for non-Qwen models, so
    only prepend it when the doctor model is actually a Qwen3 model."""
    if "qwen" in doctor_model.lower():
        return "/no_think\n"
    return ""


def get_inference_system_prompt(doctor_model: str = "") -> str:  # inference system prompt
    # 허용된 질환 리스트 정의
    allowed_candidates = [
        "Attention-Deficit/Hyperactivity Disorder (Combined Presentation)",
        "Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)",
        "Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)",
        "Delusional Disorder",
        "Schizophrenia",
        "Schizoaffective Disorder (Bipolar Type)",
        "Schizoaffective Disorder (Depressive Type)",
        "Bipolar I Disorder",
        "Bipolar II Disorder",
        "Bipolar I Disorder with Psychotic Features",
        "Generalized Anxiety Disorder",
        "Specific Phobia",
        "Major Depressive Disorder",
        "Persistent Depressive Disorder",
        "Major Depressive Disorder with Psychotic Features",
        "Obsessive-Compulsive Disorder",
        "Body Dysmorphic Disorder",
        "Posttraumatic Stress Disorder",
        "Acute Stress Disorder",
        "Adjustment Disorder",
        "Anorexia Nervosa",
        "Bulimia Nervosa",
        "Binge-Eating Disorder"
    ]
    
    candidates_bullet = "\n".join([f"- {c}" for c in allowed_candidates])
    
    # ver.1
#     return f"""/no_think
# You are a board-certified psychiatrist.
# Your goal is to identify the patient's accurate diagnosis through an interview.

# Based on the interview conversation so far and the Previous Candidates (if provided),
# infer the current differential diagnosis candidates.

# [Constraint: Allowed Candidate List]
# You MUST ONLY select candidates from the following list. Do not use any diagnosis names outside of this list:
# {candidates_bullet}

# [Important — Note Field Formatting]
# In the "note" field, you MUST explain WHY the candidate list has changed or remained the same
# compared to the previous candidates.
# For example: "Previously the candidates were [A, B, C], but based on this conversation,
# C seems unlikely because [reason], so the current candidates are [A, B]."

# [When to End the Interview]
# Set "is_final": true ONLY when you have gathered sufficient evidence to make a confident
# final diagnosis and no further questioning is needed. You may set is_final=true with one
# OR multiple candidates still listed (the final diagnosis call will select among them).
# Continue the interview (is_final: false) if uncertainty remains, even if only one candidate
# is currently listed.

# Output Format (JSON only, no other text):
# {{"candidates": ["Disease1", "Disease2"], "note": "Explanation of changes from previous candidates", "is_final": false}}
# """

    # ver.2 (260730 updated)
    # - Remove the constraint on allowed candidates in the prompt.
    return f"""{_no_think_prefix(doctor_model)}You are a board-certified psychiatrist. Your goal is to identify the patient's accurate diagnosis through an interview.

Based on the interview conversation so far and the Previous Candidates (if provided), infer the current differential diagnosis candidates based on International Classification of Diseases Version 10 (ICD-10). Do not use any diagnosis names.

[Important — Note Field Formatting]
In the "note" field, you MUST explain WHY the candidate list has changed or remained the same compared to the previous candidates.
For example: "Previously the candidates were [A, B, C], but based on this conversation, C seems unlikely because [reason], so the current candidates are [A, B]."

[When to End the Interview]
Set "is_final": true ONLY when you have gathered sufficient evidence to make a confident final diagnosis and no further questioning is needed. You may set is_final=true with one OR multiple candidates still listed (the final diagnosis call will select among them). Continue the interview (is_final: false) if uncertainty remains, even if only one candidate is currently listed.

Output Format (JSON only, no other text):
{{"candidates": ["Disease Code1", "Disease Code2"], "note": "Explanation of changes from previous candidates", "is_final": false}}
"""


def get_questioning_system_prompt(  # questioning system prompt
    max_turns: int,
    candidates: list[str] | None = None,
    doctor_model: str = "",
) -> str:
    cand_list = list(candidates or [])
    # asked_list = list(asked_questions or [])

    if cand_list:
        candidate_block = (
            "\n[Current Candidate Diagnoses]\n" + "\n".join(f"- {c}" for c in cand_list)
        )
    else:
        candidate_block = ""

    # asked_block = ""
    # if asked_list:
    #     asked_block = "\n[Already Asked Questions]\n" + "\n".join(f"- {q}" for q in asked_list)

    # ver.1
#     return f"""{_no_think_prefix(doctor_model)}You are a board-certified psychiatrist. 
# Your goal is to identify the patient's accurate diagnosis through an interview.

# Based on the interview so far and the current differential diagnosis candidates,
# ask one follow-up question to narrow down the diagnosis.

# [Candidate Diseases]
# {candidate_block}

# [Already Asked Questions]
# {asked_block}

# [Interview Strategy]
# - Review the conversation and the candidate disease list.
# - Ask exactly one follow-up question that best differentiates among the candidates.
# - Keep the question clear and easy for the patient to understand. Two sentences at most.
# - Respond in English.

# [Output Format — JSON only, no other text]
# {{
#   "category": "Type of question (e.g., symptom presence, duration, intensity, aggravating factors, medical history, social history, differential point)",
#   "subcategory": "Specific symptom/area if applicable (e.g., sleep, anhedonia, appetite, guilt). null if not applicable.",
#   "question": "The actual question to say to the patient (only this field is delivered to the patient)"
# }}
# """

    # ver.2 (260730 updated)
    # 
    return f"""{_no_think_prefix(doctor_model)}You are a board-certified psychiatrist. Your goal is to identify the patient's accurate diagnosis through an interview.

Based on the interview so far and the current differential diagnosis candidates, ask one follow-up question to narrow down the diagnosis.

[Candidate Diseases]
{candidate_block}

[Interview Strategy]
- Review the conversation and ask one follow-up question that best differentiates among the candidates.
- Keep the question clear and easy for the patient to understand. Two sentences at most.
- Respond in English.

[Output Format — JSON only, no other text]
{{
  "category": "Type of question (e.g., symptom presence, duration, intensity, aggravating factors, medical history, social history, differential point)",
  "subcategory": "Specific symptom/area if applicable (e.g., sleep, anhedonia, appetite, guilt). null if not applicable.",
  "question": "The actual question to say to the patient (only this field is delivered to the patient)"
}}
"""


def get_final_diagnosis_system_prompt(doctor_model: str = "") -> str:  # final diagnosis system prompt
    # 허용된 질환 리스트 정의
    allowed_candidates = [
        "Attention-Deficit/Hyperactivity Disorder (Combined Presentation)",
        "Attention-Deficit/Hyperactivity Disorder (Predominantly Inattentive Presentation)",
        "Attention-Deficit/Hyperactivity Disorder (Predominantly Hyperactive/Impulsive Presentation)",
        "Delusional Disorder",
        "Schizophrenia",
        "Schizoaffective Disorder (Bipolar Type)",
        "Schizoaffective Disorder (Depressive Type)",
        "Bipolar I Disorder",
        "Bipolar II Disorder",
        "Bipolar I Disorder with Psychotic Features",
        "Generalized Anxiety Disorder",
        "Specific Phobia",
        "Major Depressive Disorder",
        "Persistent Depressive Disorder",
        "Major Depressive Disorder with Psychotic Features",
        "Obsessive-Compulsive Disorder",
        "Body Dysmorphic Disorder",
        "Posttraumatic Stress Disorder",
        "Acute Stress Disorder",
        "Adjustment Disorder",
        "Anorexia Nervosa",
        "Bulimia Nervosa",
        "Binge-Eating Disorder"
    ]
    
    candidates_bullet = "\n".join([f"- {c}" for c in allowed_candidates])

    # ver.1
#     return f"""{_no_think_prefix(doctor_model)}You are a board-certified psychiatrist.
# Your goal is to identify the patient's accurate diagnosis through an interview.

# Based on the full interview transcript and the differential diagnosis candidates,
# write the final diagnosis report.

# [Constraint: Allowed Candidate List]
# Both the "diagnosis" and "candidates" fields MUST ONLY contain items from the following list:
# {candidates_bullet}

# Output Format (JSON only, no other text):
# {{
#   "diagnosis": "Final Diagnosis Name",
#   "candidates": ["Candidate1", "Candidate2"],
#   "reason": "Brief diagnostic rationale.",
#   "diagnostic_checklist": {{
#     "symptom_groups": [
#       {{
#         "group": "clinical group name (e.g., inattention, manic_episode, psychotic_symptoms)",
#         "confirmed_symptoms": ["natural language description of each confirmed symptom in this group"],
#         "count": <integer>
#       }}
#     ],
#     "duration_verified": "Description of how the duration criterion was established (e.g., 'symptoms present for over 6 months since childhood'), or null if not assessed.",
#     "functional_impairment": <true if functional impairment was confirmed, false if denied, null if not assessed>,
#     "traumatic_stressor": <true if a qualifying traumatic stressor was confirmed, null if not applicable or not assessed>,
#     "psychosocial_stressor": <true if a qualifying psychosocial stressor was confirmed, null if not applicable or not assessed>,
#     "additional_requirements": ["Each additional criterion that was explicitly verified during the interview (e.g., 'Onset prior to age 12 confirmed')"]
#   }}
# }}

# [Field Instructions]
# - diagnosis: The single diagnosis name from the allowed list you are most confident about.
# - candidates: Top 2–3 differential candidates from the allowed list considered until the end.
# - reason: Brief diagnostic rationale.
# - diagnostic_checklist: Structured evidence summary organized by diagnostic criterion type.
#   List only symptom groups that are relevant to your diagnosis, with the symptoms the patient actually confirmed.
# """

    # ver.2 (260730 updated)
    # - Remove the constraint on allowed candidates in the prompt.
    return f"""{_no_think_prefix(doctor_model)}You are a board-certified psychiatrist. Your goal is to identify the patient's accurate diagnosis through an interview.

Based on the full interview transcript and the differential diagnosis candidates, write the final diagnosis report.

Both the "diagnosis" and "candidates" MUST be ICD-10 codes.

[Field Instructions]
- diagnosis: The single diagnosis code of ICD-10.
- candidates: Top 2–3 differential candidates of ICD-10 codes considered until the end.
- reason: Brief diagnostic rationale.
- diagnostic_checklist: Structured evidence summary organized by diagnostic criterion type.
  List only symptom groups that are relevant to your diagnosis, with the symptoms the patient actually confirmed.

Output Format (JSON only, no other text):
{{
  "diagnosis": "Final Diagnosis ICD-10 code",
  "candidates": ["Disease Code1", "Disease Code2"],
  "reason": "Brief diagnostic rationale.",
  "diagnostic_checklist": {{
    "symptom_groups": [
      {{
        "group": "clinical group name (e.g., inattention, manic_episode, psychotic_symptoms)",
        "confirmed_symptoms": ["natural language description of each confirmed symptom in this group"],
        "count": <integer>
      }}
    ],
    "duration_verified": "Description of how the duration criterion was established (e.g., 'symptoms present for over 6 months since childhood'), or null if not assessed.",
    "functional_impairment": <true if functional impairment was confirmed, false if denied, null if not assessed>,
    "traumatic_stressor": <true if a qualifying traumatic stressor was confirmed, null if not applicable or not assessed>,
    "psychosocial_stressor": <true if a qualifying psychosocial stressor was confirmed, null if not applicable or not assessed>,
    "additional_requirements": ["Each additional criterion that was explicitly verified during the interview (e.g., 'Onset prior to age 12 confirmed')"]
  }}
}}
"""



def opening_user_message() -> str:  # opening user message
    return (
        "The patient has entered the clinic. "
        "Greet them briefly, then ask what brings them in today. "
        "Follow the [Output Format] JSON rules strictly."
    )


def format_interview_transcript(entries: list[tuple[str, str]]) -> str:  # conversation transcript formatting
    lines: list[str] = []
    for role, text in entries:
        label = "Doctor" if role == "doctor" else "Patient"
        lines.append(f"{label}: {text.strip()}")
    return "\n\n".join(lines)


def inference_user_payload(transcript: str, previous_candidates: list[str] | None = None) -> str:
    """Build user payload for inference phase, including previous candidates if available."""
    if previous_candidates:
        cand_str = json.dumps(previous_candidates, ensure_ascii=False)
        return f"Previous Candidates:\n{cand_str}\n\nInterview Transcript:\n\n{transcript}"
    return f"Interview Transcript:\n\n{transcript}"


def final_diagnosis_user_payload(transcript: str, candidates: list[str]) -> str:  # constructing scripts for final diagnosis
    cand_json = json.dumps(candidates, ensure_ascii=False)
    return (
        f"Candidate Diseases: \n{cand_json}\n\n"
        f"Interview Transcript: \n{transcript}"
    )


def questioning_followup_user_payload(  # constructing scripts for questioning phase
    transcript: str,
    candidates: list[str],
) -> str:
    cand_json = json.dumps(candidates, ensure_ascii=False)
    return (
        f"Candidate Diseases: \n{cand_json}\n\n"
        f"Interview Transcript: \n{transcript}"
    )


def parse_inference_result(raw: str) -> tuple[list[str], str | None, bool]:
    """Return (candidates, note, is_final)."""
    text = (raw or "").strip()
    if not text:
        return [], None, False
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return [], None, False
    try:
        data: Any = json.loads(m.group())
    except json.JSONDecodeError:
        return [], None, False

    out: list[str] = []
    note: str | None = None
    is_final: bool = False
    if isinstance(data, dict):
        c = data.get("candidates")
        if isinstance(c, list):
            for x in c:
                s = str(x).strip()
                if s:
                    out.append(s)
        n = data.get("note")
        if isinstance(n, str) and n.strip():
            note = n.strip()
        is_final = bool(data.get("is_final", False))

    return out, note, is_final


def parse_final_diagnosis_result(raw: str) -> dict[str, Any]:
    """Parse final diagnosis LLM output (JSON) → diagnosis / candidates / reason."""
    text = (raw or "").strip()
    if not text:
        return {"diagnosis": "", "candidates": [], "reason": ""}
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {"diagnosis": text, "candidates": [], "reason": ""}
    try:
        data: Any = json.loads(m.group())
    except json.JSONDecodeError:
        return {"diagnosis": text, "candidates": [], "reason": ""}
    if not isinstance(data, dict):
        return {"diagnosis": str(data), "candidates": [], "reason": ""}
    diagnosis = str(data.get("diagnosis") or "").strip()
    cand = data.get("candidates")
    candidates: list[str] = []
    if isinstance(cand, list):
        candidates = [str(x).strip() for x in cand if str(x).strip()]
    reason = str(
        data.get("reason")
        or data.get("diagnosis_basis")
        or data.get("basis")
        or ""
    ).strip()
    if not diagnosis:
        diagnosis = text
    checklist = data.get("diagnostic_checklist")
    if not isinstance(checklist, dict):
        checklist = None
    return {"diagnosis": diagnosis, "candidates": candidates, "reason": reason, "diagnostic_checklist": checklist}


def parse_questioning_result(raw: str) -> dict[str, Any]:
    """Parse questioning phase LLM output (JSON) → category, subcategory, question."""
    text = (raw or "").strip()
    if not text:
        return {"category": "", "subcategory": None, "question": ""}
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {"category": "", "subcategory": None, "question": text}
    try:
        data: Any = json.loads(m.group())
    except json.JSONDecodeError:
        return {"category": "", "subcategory": None, "question": text}
    if not isinstance(data, dict):
        return {"category": "", "subcategory": None, "question": text}
    q = str(data.get("question") or "").strip()
    cat = str(data.get("category") or data.get("type") or "").strip()
    sub = data.get("subcategory")
    if sub is None or (isinstance(sub, str) and not sub.strip()):
        sub_norm: str | None = None
    else:
        sub_norm = str(sub).strip()
    if not q:
        q = text
    return {"category": cat, "subcategory": sub_norm, "question": q}


def new_doctor_memory() -> dict[str, Any]:  # initializing doctor memory (json)
    return {
        "schema": "doctor_memory/v4",
        "status": "running",
        "latest_inference": None,
        "inference_history": [],  # 매 턴 후보 질환 이력 누적
    }


def update_doctor_memory_after_inference(  # updating doctor memory with inference result
    state: dict[str, Any],
    *,
    turn: int,
    candidates: list[str],
    note: str | None,
    raw_model: str,
    is_final: bool = False,
) -> dict[str, Any]:
    """Append inference result to history and update latest_inference."""
    preview = (raw_model or "").strip()
    if len(preview) > 1200:
        preview = preview[:1200] + "…"

    entry: dict[str, Any] = {
        "turn": turn,
        "candidates": list(candidates),
        "note": note,
        "is_final": is_final,
        "raw_preview": preview,
    }
    state["inference_history"].append(entry)
    state["latest_inference"] = entry
    return state


def finalize_doctor_memory(  # store doctor memory when interview is finished
    state: dict[str, Any],
    *,
    closed_at_patient_turn: int,
    final_diagnosis: dict[str, Any],
    final_candidates_used: list[str] | None = None,
) -> dict[str, Any]:
    state["status"] = "completed"
    state["closed_at_patient_turn"] = closed_at_patient_turn
    state["final_candidates_used"] = list(final_candidates_used or [])
    state["final_diagnosis"] = {
        "diagnosis": str(final_diagnosis.get("diagnosis") or ""),
        "candidates": list(final_diagnosis.get("candidates") or []),
        "reason": str(final_diagnosis.get("reason") or ""),
    }
    return state


def persist_doctor_memory_json(
    state: dict[str, Any],
    *,
    path: Path | None = None,
) -> None:
    p = path or DOCTOR_MEMORY_FILE
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def build_interview_transcript_payload(
    entries: list[tuple[str, str]],
    *,
    max_turns_config: int,
    closed_at_patient_turn: int,
    patient_model: str,
    doctor_model: str,
) -> dict[str, Any]:
    """Build transcript payload for saving: metadata + turn-by-turn doctor/patient utterances."""
    turns: list[dict[str, Any]] = []
    for i, (role, text) in enumerate(entries):
        turns.append(
            {
                "turn_id": i,
                "role": role,
                "content": (text or "").strip(),
            }
        )
    return {
        "metadata": {
            "schema": "interview_transcript/v1",
            "simulation_max_turns": max_turns_config,
            "closed_at_patient_turn": closed_at_patient_turn,
            "patient_model": patient_model,
            "doctor_model": doctor_model,
        },
        "turns": turns,
    }


def persist_interview_transcript_json(
    payload: dict[str, Any],
    *,
    path: Path | None = None,
) -> None:
    p = path or TRANSCRIPT_FILE
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def should_finish_interview(
    is_final: bool,
    patient_turn_index: int,
    max_turns: int,
) -> bool:
    """End the interview when the doctor signals is_final=True or max_turns is reached.
    No longer ends automatically when candidate list narrows to one."""
    if patient_turn_index >= max_turns:
        return True
    return is_final
