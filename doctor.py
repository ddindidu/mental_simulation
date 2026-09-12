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


INFERENCE_PROMPT = """You are a board-certified psychiatrist interviewing a patient to reach a diagnosis.
Your goal is to reach the correct diagnosis within {max_turns} turns of talking with the patient. From the dialogue so far and your candidates from the previous turn, list the disorders this patient could have.

[Current Turn]
{current_turn}

[Previous Candidates]
{previous_candidates}

[Dialogue History]
{dialogue_history}

[Instruction]
- Give candidates as ICD-10 codes, not disease names.
- If the list changed from the previous candidates, say in "note" what this turn added or ruled out. If it did not change, leave "note" empty.
- If the candidates have narrowed to one and you are confident enough that no further questioning is needed, return true for is_final.

[Output Format — JSON only, no other text]
{"candidates": ["<ICD-10 code>", "..."], "note": "<why the list changed, or empty>", "is_final": <true or false>}
"""


def build_inference_prompt(
    transcript: str,
    previous_candidates: list[str] | None = None,
    turn_index: int | None = None,
    max_turns: int = 10,
    doctor_model: str = "",
) -> str:
    """Fill the inference prompt for this turn."""
    return (
        _no_think_prefix(doctor_model)
        + INFERENCE_PROMPT
        .replace("{current_turn}", str(turn_index) if turn_index else "1")
        .replace("{previous_candidates}",
                 ", ".join(previous_candidates) if previous_candidates else "(none — this is your first inference)")
        .replace("{dialogue_history}", transcript)
        .replace("{max_turns}", str(max_turns))
    )


def get_inference_system_prompt(doctor_model: str = "", max_turns: int = 10) -> str:
    """The prompt with its per-turn slots left visible — what the UI shows."""
    return (
        build_inference_prompt("{dialogue_history}", None, None, max_turns, doctor_model)
        .replace("[Current Turn]\n1", "[Current Turn]\n{current_turn}")
        .replace("(none — this is your first inference)", "{previous_candidates}")
    )


QUESTIONING_PROMPT = """You are a board-certified psychiatrist interviewing a patient to reach a diagnosis.
Your goal is to reach the correct diagnosis within {max_turns} turns of talking with the patient. From the dialogue so far and your current candidates, ask the one follow-up question that best separates them.

[Current Turn]
{current_turn}

[Current Candidates]
{current_candidates}

[Dialogue History]
{dialogue_history}

[Instruction]
- Ask about exactly ONE thing. Never bundle several symptoms, or several attributes of one symptom, into a single question — e.g. asking whether a symptom is present and how long it has lasted at the same time.
- If you need to ask about more than one thing, ask the one that tells you the most now and come back to the rest later.
- Keep the question clear enough for the patient to understand.
- Respond in English.

[Output Format — JSON only, no other text]
{"intent": "<what you want to find out with this question>", "question": "<how you actually ask it in the interview>"}
"""


def build_questioning_prompt(
    transcript: str = "",
    candidates: list[str] | None = None,
    turn_index: int | None = None,
    max_turns: int = 10,
    doctor_model: str = "",
) -> str:
    """Fill the questioning prompt for this turn."""
    return (
        _no_think_prefix(doctor_model)
        + QUESTIONING_PROMPT
        .replace("{current_turn}", str(turn_index) if turn_index else "1")
        .replace("{current_candidates}",
                 ", ".join(candidates) if candidates else "(none yet — this is your opening question)")
        .replace("{dialogue_history}",
                 transcript or "(none yet — the interview has not started)")
        .replace("{max_turns}", str(max_turns))
    )


def get_questioning_system_prompt(
    max_turns: int,
    candidates: list[str] | None = None,
    doctor_model: str = "",
) -> str:
    """The prompt with its per-turn slots left visible — what the UI shows."""
    return (
        build_questioning_prompt("", candidates, None, max_turns, doctor_model)
        .replace("[Current Turn]\n1", "[Current Turn]\n{current_turn}")
        .replace("(none yet — this is your opening question)", "{current_candidates}")
        .replace("(none yet — the interview has not started)", "{dialogue_history}")
    )


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


def final_diagnosis_user_payload(transcript: str, candidates: list[str]) -> str:  # constructing scripts for final diagnosis
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
    """Parse questioning phase LLM output (JSON) → intent, question.

    Older runs wrote "category"/"subcategory" instead of "intent"; both are read so a log
    from either version parses the same way.
    """
    text = (raw or "").strip()
    if not text:
        return {"intent": "", "question": ""}
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {"intent": "", "question": text}
    try:
        data: Any = json.loads(m.group())
    except json.JSONDecodeError:
        return {"intent": "", "question": text}
    if not isinstance(data, dict):
        return {"intent": "", "question": text}
    q = str(data.get("question") or "").strip()
    intent = str(data.get("intent") or data.get("category") or data.get("type") or "").strip()
    return {"intent": intent, "question": q or text}


def new_doctor_memory() -> dict[str, Any]:  # initializing doctor memory (json)
    return {
        "schema": "doctor_memory/v6",
        "status": "running",
        "latest_inference": None,
        "inference_history": [],  # 매 턴 후보 질환 이력 누적
        "turns": [],              # 턴별로 doctor/patient 산출물을 한 칸에 모아둔 것
    }


def _turn_slot(state: dict[str, Any], turn: int) -> dict[str, Any]:
    """turns 안에서 해당 턴 칸을 찾고, 없으면 만들어 돌려준다.

    한 턴은 의사의 질문 → 환자의 응답 → 의사의 후보 추론 순으로 세 번에 걸쳐 채워지므로
    먼저 도착한 쪽이 칸을 만들고 나머지가 같은 칸에 덧붙인다.
    """
    turns: list[dict[str, Any]] = state.setdefault("turns", [])
    for slot in turns:
        if slot.get("turn") == turn:
            return slot
    slot = {"turn": turn, "doctor": None, "patient": None, "inference": None}
    turns.append(slot)
    turns.sort(key=lambda s: s.get("turn", 0))
    return slot


def record_doctor_question(
    state: dict[str, Any],
    *,
    turn: int,
    intent: str,
    question: str,
) -> dict[str, Any]:
    """Keep what the doctor meant to ask, next to what they actually asked.

    The transcript only carries the question as the patient heard it; the intent is the
    doctor's own account of what that turn was for, and it is what makes a turn readable
    afterwards — the note in inference_history says what the answer changed, this says
    what was being sought.
    """
    entry = {"intent": intent, "question": question}
    _turn_slot(state, turn)["doctor"] = entry
    return entry


def record_patient_turn(
    state: dict[str, Any],
    *,
    turn: int,
    target_item: dict[str, Any] | None,
    answer: str,
) -> dict[str, Any]:
    """Keep the profile item the patient aligned on, next to what they said about it.

    target_item is the alignment stage's own output ({key, name, description, reason});
    answer is the utterance the doctor actually heard. Together with the doctor half of
    the same turn slot, one turn can be read end to end without re-opening the prompt log.
    """
    entry = {"target_item": target_item, "answer": answer}
    _turn_slot(state, turn)["patient"] = entry
    return entry


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
    _turn_slot(state, turn)["inference"] = {
        "candidates": list(candidates),
        "note": note,
        "is_final": is_final,
    }
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
    if p is None:
        return  # 경로 없음 = 별도 파일로 남기지 않음 (전사 로그에 이미 포함)
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
    if p is None:
        return  # 경로 없음 = 별도 파일로 남기지 않음 (전사 로그에 이미 포함)
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
