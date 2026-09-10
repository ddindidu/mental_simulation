from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any

from utils.paths import DEFAULT_SYMPTOM_PROFILE_PATH, PROJECT_ROOT
from utils.config import CONFIG

# ─── config 로드 ───────────────────────────────────────────────────────────────
_PATIENT_CFG: dict = CONFIG.get("patient", {})
_USE_KG: bool = bool(_PATIENT_CFG.get("use_knowledge_graph", False))
_DISEASE_CODE: str = str(_PATIENT_CFG.get("disease_code", "D013"))
_DIFFICULTY: str = str(_PATIENT_CFG.get("difficulty_level", "low"))
_KG_BASE_DIR: str = str(
    _PATIENT_CFG.get("kg_base_dir", "/home/mlp/hgyoo/mentals/simulation_new/mentalbench")
)

# 두 프롬프트가 되돌아보는 대화 길이 — 의사-환자 교환 쌍의 수. 3이면 지난 세 번의
# 주고받음을 보고 이번 질문에 답한다. 0 이하면 전체 대화를 넘긴다.
DEFAULT_CONTEXT_WINDOW = 3
_CONTEXT_WINDOW: int = int(_PATIENT_CFG.get("context_window", DEFAULT_CONTEXT_WINDOW))


def _resolve_profile_path(path: str | Path) -> Path:
    """Resolve a configured profile path relative to the project root."""
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    return resolved.resolve()


_PROFILE_PATH = _resolve_profile_path(
    _PATIENT_CFG.get("symptom_profile_path", DEFAULT_SYMPTOM_PROFILE_PATH)
)


# ─── 레거시 JSON-파일 기반 함수들 (폴백용) ────────────────────────────────────

def _load_profile() -> dict:
    if not _PROFILE_PATH.is_file():
        raise FileNotFoundError(
            f"symptom profile JSON not found: {_PROFILE_PATH}"
        )
    with open(_PROFILE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(
            f"symptom profile JSON must contain an object: {_PROFILE_PATH}"
        )
    return data


def _skip_value(val: object) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip() in ("", "-"):
        return True
    return False


_SUB_MARK = "▸"


def _section_lines(pairs: list[tuple[str, str | None]]) -> list[str]:
    lines: list[str] = []
    for label, val in pairs:
        if val is None or _skip_value(val) or isinstance(val, (dict, list)):
            continue
        lines.append(f"- {label}: {val}")
    return lines


def _append_sub(out: list[str], title: str, lines: list[str]) -> None:
    if not lines:
        return
    out.append(f"{_SUB_MARK} {title}")
    out.extend(lines)


def _format_generated_profile(data: dict) -> str:
    """Format the new symptom/patient/manifestation/add_requirements schema."""
    symptom = data.get("symptom")
    patient = data.get("patient")
    if not isinstance(symptom, dict) or not isinstance(patient, dict):
        return ""

    sampled = symptom.get("sampled_features")
    if not isinstance(sampled, dict):
        sampled = {}

    disease_code = symptom.get("disease_code") or sampled.get("disease_code")
    disease_name = symptom.get("disease_name") or sampled.get("disease_name")

    out: list[str] = []
    clinical_lines = _section_lines(
        [
            ("Disease Code", disease_code),
            ("Diagnosis", disease_name),
        ]
    )
    _append_sub(out, "Clinical Context", clinical_lines)

    patient_lines = _section_lines(
        [
            ("Demographics", patient.get("demographics")),
            ("Stressor Event", patient.get("stressor_event")),
            ("Severity", patient.get("severity")),
            ("Stressor / Background", patient.get("stressor")),
        ]
    )
    _append_sub(out, "Patient Background and Presenting Concern", patient_lines)

    # Prefer patient-specific manifestations. During a partial pipeline run they
    # may not exist yet, so fall back to sampled symptom descriptions without
    # inventing patient-specific details.
    manifestations = data.get("manifestation")
    if isinstance(manifestations, dict) and manifestations:
        manifestation_lines: list[str] = []
        for code, entry in manifestations.items():
            if not isinstance(entry, dict):
                if not _skip_value(entry):
                    manifestation_lines.append(f"- {code}: {entry}")
                continue
            name = entry.get("name") or code
            text = entry.get("manifestation")
            if not _skip_value(text):
                manifestation_lines.append(f"- {code} ({name}): {text}")
        _append_sub(out, "Patient-specific Symptom Manifestations", manifestation_lines)
    else:
        descriptions = sampled.get("sampled_symptoms_descriptions")
        sampled_codes = sampled.get("sampled_symptoms")
        if isinstance(descriptions, dict):
            if not isinstance(sampled_codes, list):
                sampled_codes = list(descriptions)
            symptom_lines: list[str] = []
            for code in sampled_codes:
                entry = descriptions.get(code)
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name") or code
                description = entry.get("description")
                if not _skip_value(description):
                    symptom_lines.append(f"- {code} ({name}): {description}")
            _append_sub(out, "Sampled Symptoms", symptom_lines)

    requirements = data.get("add_requirements")
    if isinstance(requirements, dict):
        requirement_lines = [
            f"- {key}: {value}"
            for key, value in requirements.items()
            if not _skip_value(value) and not isinstance(value, (dict, list))
        ]
        _append_sub(out, "Additional Diagnostic Requirements", requirement_lines)

    return "\n".join(out).strip()


def format_symptom_profile(data: dict) -> str:
    """Render the patient prompt's [Symptom Profile] block from a pipeline profile."""
    return _format_generated_profile(data) or "(No symptom profile)"


# ── 1) Profile alignment: doctor question ↔ symptom profile mapping ─────────
#
# alignment 단계는 "이번 질문에 가장 가까운 프로필 항목 하나"만 고른다. 항목 본문은
# LLM이 다시 쓰지 않고 프로필에서 그대로(verbatim) 꺼내 response 단계에 넘긴다.
# 예전처럼 LLM이 답변 전략을 서술하면 항목 나열형 지시가 되어 발화가 길어지고,
# 프로필에 없는 내용까지 지어내는 문제가 있었다.

# key -> (label, verbatim text). 프로필을 빌드할 때마다 갱신된다.
_SECTION_INDEX: dict[str, tuple[str, str]] = {}


def _add_section(index: dict, key: str, label: str, text: object) -> None:
    if _skip_value(text) or isinstance(text, (dict, list)):
        return
    key = str(key).strip()
    if not key or key in index:
        return
    index[key] = (label, str(text).strip())


# ── Alignment input: the `symptom` block only ────────────────────────────────
#
# alignment 단계에는 환자 개인 정보(patient / manifestation / add_requirements)를
# 넣지 않는다. 질병 수준의 `symptom` 블록 — 진단 기준(additional_requirements,
# functional_impairment_required, duration)과 샘플링된 증상 — 만 보여주고 그중
# 의사 질문에 가장 가까운 항목 하나를 고르게 한다. 고른 항목의 실제 발화 재료
# (환자별 manifestation / add_requirements 원문)는 LLM이 아니라 _SECTION_INDEX에서
# 꺼내 response 단계로 넘긴다.

_REQ_KEY_PREFIX = "additional_requirement_"

# patient.chief_complaint_symptom_code에서 채운다. 첫 턴에 alignment가 돌려주는
# "chief_complaint"를 실제 증상 코드로 풀기 위한 별칭.
_CHIEF_COMPLAINT_KEY = ""


def _symptom_block(data: dict) -> dict:
    symptom = data.get("symptom")
    return symptom if isinstance(symptom, dict) else {}


def _sampled_features(data: dict) -> dict:
    sampled = _symptom_block(data).get("sampled_features")
    return sampled if isinstance(sampled, dict) else {}


def _sampled_criteria(data: dict) -> dict:
    criteria = _sampled_features(data).get("sampled_diagnostic_criteria")
    return criteria if isinstance(criteria, dict) else {}


def _criterion_text(value: object) -> str:
    """A diagnostic-criterion value: a plain string, a bool, or {required, event}."""
    if isinstance(value, dict):
        if not value.get("required"):
            return ""
        return str(value.get("event") or "required").strip()
    if isinstance(value, bool):
        return "required" if value else ""
    if _skip_value(value):
        return ""
    return str(value).strip()


def _slug_tokens(text: object) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", str(text).lower()) if t}


def _pick_requirement_key(req_text: str, candidates: list[str]) -> str | None:
    """Map one additional_requirements entry to its add_requirements key.

    "Onset prior to age 12 years" ↔ "onset_prior_to_12_years" — matched on shared
    tokens, since the two are written independently and never match exactly.
    """
    tokens = _slug_tokens(req_text)
    best: str | None = None
    best_score = 0
    for key in candidates:
        score = len(tokens & _slug_tokens(key))
        if score > best_score:
            best, best_score = key, score
    return best


def format_symptom_block_for_alignment(data: dict) -> str:
    """Render ONLY the `symptom` block — all the alignment stage is allowed to see."""
    symptom = _symptom_block(data)
    sampled = _sampled_features(data)
    if not symptom or not sampled:
        # 레거시 평면 스키마: 떼어낼 patient 블록 자체가 없다
        return format_symptom_profile(data)

    criteria = _sampled_criteria(data)
    descriptions = sampled.get("sampled_symptoms_descriptions")
    descriptions = descriptions if isinstance(descriptions, dict) else {}

    out: list[str] = []
    _append_sub(
        out,
        "Clinical Context",
        _section_lines(
            [
                ("Disease Code", symptom.get("disease_code") or sampled.get("disease_code")),
                ("Diagnosis", symptom.get("disease_name") or sampled.get("disease_name")),
            ]
        ),
    )

    crit_lines: list[str] = []
    reqs = criteria.get("additional_requirements")
    if isinstance(reqs, list):
        for i, req in enumerate(reqs, start=1):
            req_text = _criterion_text(req)
            if req_text:
                crit_lines.append(f"- {_REQ_KEY_PREFIX}{i}: {req_text}")
    fi_text = _criterion_text(criteria.get("functional_impairment_required"))
    if fi_text:
        crit_lines.append(f"- functional_impairment: {fi_text}")
    duration_text = _criterion_text(criteria.get("duration"))
    if duration_text:
        crit_lines.append(f"- duration: {duration_text}")
    _append_sub(out, "Diagnostic Criteria", crit_lines)

    def _symptom_line(code: str) -> str | None:
        entry = descriptions.get(code)
        if not isinstance(entry, dict):
            return None
        name = entry.get("name") or code
        description = entry.get("description")
        if _skip_value(description):
            return f"- {code} ({name})"
        return f"- {code} ({name}): {description}"

    grouped: set[str] = set()
    groups = sampled.get("sampled_symptom_groups")
    if isinstance(groups, dict):
        for gkey, ginfo in groups.items():
            if not isinstance(ginfo, dict):
                continue
            codes = ginfo.get("symptoms")
            if not isinstance(codes, list):
                continue
            lines = []
            for code in codes:
                line = _symptom_line(code)
                if line:
                    lines.append(line)
                    grouped.add(code)
            _append_sub(out, f"Symptoms — {ginfo.get('name') or gkey}", lines)

    sampled_codes = sampled.get("sampled_symptoms")
    if not isinstance(sampled_codes, list):
        sampled_codes = list(descriptions)
    ungrouped = []
    for code in sampled_codes:
        if code in grouped:
            continue
        line = _symptom_line(code)
        if line:
            ungrouped.append(line)
    _append_sub(out, "Symptoms", ungrouped)

    _append_sub(
        out,
        "Disease Overview",
        _section_lines([("Disease Info", symptom.get("disease_info"))]),
    )

    return "\n".join(out).strip() or "(No symptom profile)"


def _build_alignment_index(data: dict) -> dict[str, tuple[str, str]]:
    """Selectable items for alignment: {key: (label, verbatim text for the reply)}.

    Keys come from the `symptom` block only — the sampled symptom codes plus the
    diagnostic-criteria items (additional_requirement_N / functional_impairment /
    duration). The stored text is the patient-specific wording (manifestation /
    add_requirements) so the response stage still speaks in the patient's words.
    """
    global _CHIEF_COMPLAINT_KEY
    _CHIEF_COMPLAINT_KEY = ""

    sampled = _sampled_features(data)
    if not sampled:
        return {}

    criteria = _sampled_criteria(data)
    descriptions = sampled.get("sampled_symptoms_descriptions")
    descriptions = descriptions if isinstance(descriptions, dict) else {}
    manifestations = data.get("manifestation")
    manifestations = manifestations if isinstance(manifestations, dict) else {}
    requirements = data.get("add_requirements")
    requirements = requirements if isinstance(requirements, dict) else {}

    index: dict[str, tuple[str, str]] = {}

    codes = sampled.get("sampled_symptoms")
    if not isinstance(codes, list) or not codes:
        codes = list(descriptions)
    for code in codes:
        entry = descriptions.get(code)
        entry = entry if isinstance(entry, dict) else {}
        name = entry.get("name") or code
        mani = manifestations.get(code)
        text = mani.get("manifestation") if isinstance(mani, dict) else mani
        if _skip_value(text):
            text = entry.get("description")
        _add_section(index, code, f"{code} ({name})", text)

    used: set[str] = set()

    fi_text = _criterion_text(criteria.get("functional_impairment_required"))
    if fi_text:
        patient_text = requirements.get("functional_impairment")
        if _skip_value(patient_text):
            patient_text = fi_text
        else:
            used.add("functional_impairment")
        _add_section(index, "functional_impairment", "Functional Impairment", patient_text)

    duration_text = _criterion_text(criteria.get("duration"))
    if duration_text:
        patient_text = requirements.get("duration")
        if _skip_value(patient_text):
            patient_text = duration_text
        else:
            used.add("duration")
        _add_section(index, "duration", "Duration", patient_text)

    reqs = criteria.get("additional_requirements")
    if isinstance(reqs, list):
        spare = [k for k in requirements if k not in ("functional_impairment", "duration")]
        for i, req in enumerate(reqs, start=1):
            req_text = _criterion_text(req)
            if not req_text:
                continue
            remaining = [k for k in spare if k not in used]
            match = _pick_requirement_key(req_text, remaining)
            if match is None and remaining:
                match = remaining[0]
            patient_text = requirements.get(match) if match else None
            if _skip_value(patient_text):
                patient_text = req_text
            elif match:
                used.add(match)
            _add_section(index, f"{_REQ_KEY_PREFIX}{i}", req_text, patient_text)

    patient_block = data.get("patient")
    if isinstance(patient_block, dict):
        cc_code = str(patient_block.get("chief_complaint_symptom_code") or "").strip()
        if cc_code in index:
            _CHIEF_COMPLAINT_KEY = cc_code
    if not _CHIEF_COMPLAINT_KEY:
        for code in codes:
            if str(code) in index:
                _CHIEF_COMPLAINT_KEY = str(code)
                break

    return index


def format_selectable_items(index: dict[str, tuple[str, str]] | None = None) -> str:
    idx = _SECTION_INDEX if index is None else index
    if not idx:
        return "(No selectable items)"
    return "\n".join(f"- {key}  ({label})" for key, (label, _) in idx.items())


ALIGNMENT_PROMPT = """/no_think
You are an assistant analyst. Looking at the recent dialogue and the patient's symptom
profile, pick the ONE item to answer the doctor's **last utterance** with.

[Symptom Profile]
{symptom_profile}

[Selectable Items]
{selectable_items}

Rules:
- Choose exactly ONE key from [Selectable Items] — the single item closest to what the doctor
  just asked. Never choose more than one, even if the question touches several topics; pick the
  one the question is most directly about.
- Copy the key exactly as written in [Selectable Items].
- If the profile does not cover what the doctor asked, set matched=false and leave
  matched_section empty. Do NOT force an unrelated item.
- If patient_turn_index is 1 (patient's first reply), always choose chief_complaint.
- Do not write an answer, a strategy, or any other text.

[Output Format — JSON only, no other text]
{"matched": true|false, "matched_section": "<one key from the list, or empty>"}
"""


def build_alignment_system_prompt() -> str:
    # 프로필의 `symptom` 블록만 넣는다 — patient / manifestation / add_requirements는
    # 환자 개인 정보라 alignment 단계에 노출하지 않는다.
    symptom_block = _kg_symptom_block_cache.get("alignment_block", "")
    if not symptom_block:
        symptom_block = format_symptom_block_for_alignment(_load_profile())
    return (
        ALIGNMENT_PROMPT
        .replace("{symptom_profile}", symptom_block)
        .replace("{selectable_items}", format_selectable_items())
    )


def build_alignment_messages(
    doctor_last_message: str,
    patient_turn_index: int,
    patient_hist: list[dict[str, Any]] | None = None,
    context_window: int | None = None,
) -> list[dict[str, str]]:
    """Profile alignment only: system(profile) + user(recent dialogue + last question).

    The recent turns are there so a follow-up question resolves — "how long has that been
    going on?" only names an item once you can see what was just said.
    """
    parts = [
        f"patient_turn_index: {patient_turn_index}",
        "(If 1, this is the patient's first reply — choose chief_complaint.)",
    ]
    recent = _recent_messages(patient_hist or [], context_window)
    if len(recent) > 1:
        dialogue = format_full_dialogue_for_response(recent[:-1], context_window=0)
        parts.append(f"\n[Recent dialogue]\n{dialogue}")
    parts.append(f"\nDoctor's last question:\n{doctor_last_message.strip()}")
    return [
        {"role": "system", "content": build_alignment_system_prompt()},
        {"role": "user", "content": "\n".join(parts)},
    ]


_SYMPTOM_CODE_RE = re.compile(r"\bS\d+\b", re.IGNORECASE)


def _lookup_section(key: str) -> tuple[str, str, str] | None:
    """Resolve an LLM-returned key to (key, label, verbatim text)."""
    raw = str(key or "").strip()
    if not raw:
        return None
    # 첫 턴 지시("chief_complaint")는 실제 주호소 증상 코드로 푼다
    if raw.lower().replace(" ", "_") == "chief_complaint" and _CHIEF_COMPLAINT_KEY:
        raw = _CHIEF_COMPLAINT_KEY
    if raw in _SECTION_INDEX:
        label, text = _SECTION_INDEX[raw]
        return raw, label, text
    lowered = {k.lower(): k for k in _SECTION_INDEX}
    hit = lowered.get(raw.lower())
    if hit is None:
        # "S027 (Sleep_Disturbance)" 처럼 라벨째로 돌려주는 경우 코드만 뽑아 재시도
        m = _SYMPTOM_CODE_RE.search(raw)
        if m:
            hit = lowered.get(m.group().lower())
    if hit is None:
        # 키 대신 라벨(요건 원문 등)을 돌려주는 경우
        for k, (label, _) in _SECTION_INDEX.items():
            if label.strip().lower() == raw.lower():
                hit = k
                break
    if hit is None:
        return None
    label, text = _SECTION_INDEX[hit]
    return hit, label, text


def _no_match(reason: str = "") -> dict[str, Any]:
    return {
        "matched": False,
        "matched_section": "",
        "section_label": "",
        "section_text": "",
        "note": reason,
    }


def parse_alignment_result(raw: str) -> dict[str, Any]:
    """Parse alignment output and attach the profile text verbatim.

    Returns {matched, matched_section, section_label, section_text}. The text is
    read from the profile index, never from the LLM output, so nothing can be
    paraphrased or invented at this stage.
    """
    text = (raw or "").strip()
    if not text:
        return _no_match("empty alignment output")
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return _no_match("no JSON in alignment output")
    try:
        data: Any = json.loads(m.group())
    except json.JSONDecodeError:
        return _no_match("alignment output is not valid JSON")
    if not isinstance(data, dict):
        return _no_match("alignment output is not an object")

    key = data.get("matched_section")
    if isinstance(key, list):  # 여러 개를 돌려주면 첫 번째만 쓴다
        key = key[0] if key else ""
    resolved = _lookup_section(key)
    if resolved is None:
        return _no_match("no selectable item matched")
    if not bool(data.get("matched", True)):
        return _no_match("analyst reported no match")

    resolved_key, label, section_text = resolved
    return {
        "matched": True,
        "matched_section": resolved_key,
        "section_label": label,
        "section_text": section_text,
        "note": "",
    }


def format_alignment_for_response(parsed: dict[str, Any]) -> str:
    """Content handed to the response stage: the profile item for this turn.

    Data only — how the patient says it is decided by the behavioral guidelines and
    the [Conversation Style] block of the system prompt.
    """
    if parsed.get("matched"):
        return (
            f"{parsed.get('section_label', '')}:\n"
            f"\"{parsed.get('section_text', '')}\""
        )
    return "(none — your profile has nothing about what the doctor just asked)"


# ── 2) Response generation ────────────────────────────────────────────────────

def _recent_messages(
    patient_hist: list[dict[str, Any]],
    context_window: int | None = None,
) -> list[dict[str, Any]]:
    """The last `context_window` doctor-patient exchanges, oldest first.

    A patient recalls the last few exchanges, not the whole consultation, and a shorter
    window also keeps the two prompts from growing with every turn. Counted in exchanges
    rather than messages so a window never starts mid-way through one.
    """
    window = _CONTEXT_WINDOW if context_window is None else int(context_window)
    messages = [m for m in patient_hist if m.get("role") != "system"]
    if window > 0:
        # 마지막 메시지는 이번 의사 질문이므로 그것을 뺀 나머지에서 쌍 단위로 센다.
        messages = messages[-(2 * window + 1):]
    return messages


def format_full_dialogue_for_response(
    patient_hist: list[dict[str, Any]],
    context_window: int | None = None,
) -> str:
    """Convert the recent part of patient_hist to Doctor / Patient labeled text."""
    lines: list[str] = []
    for msg in _recent_messages(patient_hist, context_window):
        role = msg.get("role")
        if role == "system":
            continue
        c = (msg.get("content") or "").strip()
        if role == "user":
            lines.append(f"Doctor: {c}")
        elif role == "assistant":
            lines.append(f"Patient: {c}")
    return "\n\n".join(lines)


def build_response_messages(
    patient_hist: list[dict[str, Any]],
    alignment_strategy_text: str,
    context_window: int | None = None,
) -> list[dict[str, str]]:
    """
    Response generation: system(patient guidelines + alignment result) + user(full dialogue).
    patient_hist includes the doctor's user turn; patient assistant turn not yet appended.
    """
    dialogue = format_full_dialogue_for_response(patient_hist, context_window)
    system = (
        SYSTEM_PROMPT
        + "\n\n[This Turn: Profile Item to Talk About]\n"
        + alignment_strategy_text
    )
    user = (
        "Below is the recent part of the consultation dialogue. "
        "Reply in English as the Patient to the last Doctor utterance.\n"
        "Say what [This Turn: Profile Item to Talk About] holds, told in your "
        "[Conversation Style].\n\n"
        f"[Dialogue]\n{dialogue}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ─── 프롬프트 템플릿 ──────────────────────────────────────────────────────────

# ─── Conversation style ──────────────────────────────────────────────────────
# Definitions go into the [Conversation Style] block of the patient prompt
# verbatim. Keys are what config / CLI refer to.
CONVERSATION_STYLES: dict[str, str] = {
    "plain": (
        "A plain patient describes their symptoms and experiences in a direct and "
        "straightforward manner, providing clear and relevant answers to the doctor's "
        "questions."
    ),
    "verbose": (
        "A verbose patient may\n"
        "1) provide excessively detailed responses when describing their symptoms and "
        "experiences, even when the details are directly relevant,\n"
        "2) elaborate extensively on the background, events, thoughts, feelings, and "
        "personal experiences surrounding their symptoms, and\n"
        "3) demonstrate difficulty allowing the doctor to guide the interview or move on "
        "to another clinical topic."
    ),
    "reserved": (
        "A reserved patient may\n"
        "1) provide brief, vague, or evasive answers to questions about their symptoms and "
        "experiences,\n"
        "2) be reluctant to answer questions about personal information, emotions, or "
        "sensitive clinical experiences, and\n"
        "3) refrain from voluntarily providing information beyond what the doctor "
        "specifically asks."
    ),
    "tangent": (
        "A patient who goes off on tangents may\n"
        "1) begin answering the doctor's question but quickly shift to an unrelated "
        "topic,\n"
        "2) frequently add irrelevant personal anecdotes or experiences while answering "
        "the question, and\n"
        "3) have difficulty remaining focused on the doctor's question, potentially "
        "requiring the doctor to repeat the question or redirect the conversation to "
        "obtain clear clinical information."
    ),
    "pleasing": (
        "A pleasing patient may\n"
        "1) minimize, downplay, or describe in more favorable terms symptoms and behaviors "
        "that they believe could create a negative impression,\n"
        "2) initially withhold or delay disclosing sensitive clinical information due to "
        "shame or fear of being judged, and\n"
        "3) seek confirmation that their descriptions or answers are appropriate and "
        "demonstrate a tendency to seek the doctor's approval."
    ),
}

DEFAULT_CONVERSATION_STYLE = "plain"
RANDOM_CONVERSATION_STYLE = "random"


def conversation_style_names() -> list[str]:
    """Available style keys, in a fixed order (random picks depend on this order)."""
    return list(CONVERSATION_STYLES)


def build_conversation_style_block(style: str) -> str:
    """Render the [Conversation Style] section body for one style."""
    key = str(style or "").strip().lower()
    if key not in CONVERSATION_STYLES:
        raise ValueError(
            f"unknown conversation style: {style!r} "
            f"(available: {', '.join(conversation_style_names())})"
        )
    return (
        f"You are a {key.capitalize()} patient.\n"
        f"{CONVERSATION_STYLES[key]}\n"
        "Speak this way in every reply, whatever the doctor asks."
    )


def pick_conversation_style(seed: Any = None) -> str:
    """Pick a style uniformly at random.

    Pass a stable seed (e.g. the profile path or persona_uuid) to make the
    assignment reproducible per patient instead of per process.
    """
    rng = random.Random(seed) if seed is not None else random
    return rng.choice(conversation_style_names())


def _resolve_conversation_style(style: str | None, seed: Any = None) -> str:
    """Map a config/CLI value ("plain", "random", None) to a concrete style key."""
    key = str(style or DEFAULT_CONVERSATION_STYLE).strip().lower()
    if key == RANDOM_CONVERSATION_STYLE:
        return pick_conversation_style(seed)
    if key not in CONVERSATION_STYLES:
        raise ValueError(
            f"unknown conversation style: {style!r} "
            f"(available: {', '.join(conversation_style_names())}, {RANDOM_CONVERSATION_STYLE})"
        )
    return key


_CONVERSATION_STYLE: str = _resolve_conversation_style(
    _PATIENT_CFG.get("conversation_style", DEFAULT_CONVERSATION_STYLE),
    _PATIENT_CFG.get("conversation_style_seed"),
)
CONVERSATION_STYLE: str = build_conversation_style_block(_CONVERSATION_STYLE)


PROMPT = """/no_think
You are a patient experiencing {most_likely_diagnosis}.
Respond to the doctor's questions based on the symptom profile provided below.

[Symptom Profile]
{symptom_profile}

[Behavioral Guidelines]
- In the very first turn, only talk about the item you are given. Do NOT reveal any other symptoms.
- Each turn you are given [This Turn: Profile Item to Talk About] — the one profile item the
  doctor's question is about. Answer from that item only; do not bring in other symptoms or
  profile items the doctor has not asked about.
- If that item is "(none ...)", tell the doctor you are not sure or that it has not been an
  issue for you.
- Never state a clinical fact that is not in your profile — no other symptoms, substances,
  medications, test results, dates, or events. Your style shapes how you tell it, never what
  happened to you.
- Respond in English.
- The guidelines above decide WHAT you say. The [Conversation Style] below decides HOW you say
  it — tone, wording, and length. Follow both.

[Conversation Style]
{conversation_style}
"""


# ─── KG symptom block cache (alignment prompt 재사용 위해) ───────────────────
_kg_symptom_block_cache: dict = {}


# ─── KnowledgeGraph 기반 프롬프트 빌더 ───────────────────────────────────────

def _build_system_prompt_from_kg() -> str:
    """Dynamically generate patient profile from KnowledgeGraph and return system prompt."""
    import sys as _sys
    import os as _os

    scripts_dir = _os.path.join(_KG_BASE_DIR, "scripts")
    if scripts_dir not in _sys.path:
        _sys.path.insert(0, scripts_dir)

    from knowledge_graph import KnowledgeGraph  # type: ignore
    from question_setter import QuestionSetter  # type: ignore

    original_cwd = _os.getcwd()
    try:
        _os.chdir(scripts_dir)
        kg_obj = KnowledgeGraph(None)
    finally:
        _os.chdir(original_cwd)

    qs = QuestionSetter(kg_obj)

    disease_features = kg_obj.extract_features_for_disease(_DISEASE_CODE)
    sampled = qs.sample_features_from_disease(disease_features, difficulty_level=_DIFFICULTY)

    disease_name = sampled.get("disease_name", _DISEASE_CODE)

    # _format_sampled_features 인라인 구현 (kg_adapter 없이)
    lines: list[str] = []
    for sg_key, sg_info in sampled.get("sampled_symptom_groups", {}).items():
        group_name = sg_info.get("name", sg_key)
        lines.append(f"▸ {group_name}")
        for sym_code in sg_info.get("symptoms", []):
            sym_info = sampled.get("sampled_symptoms_descriptions", {}).get(sym_code, {})
            sym_name = sym_info.get("name", sym_code)
            sym_desc = sym_info.get("description", "")
            subtypes: dict | None = sym_info.get("subtypes")
            if subtypes:
                for sub_name, sub_desc in subtypes.items():
                    lines.append(f"  - {sub_name}: {sub_desc}")
            else:
                if sym_desc:
                    lines.append(f"  - {sym_name}: {sym_desc}")
                else:
                    lines.append(f"  - {sym_name}")
        if "duration" in sg_info:
            lines.append(f"  Duration: {sg_info['duration']}")
        fi = sg_info.get("functional_impairment_required")
        if isinstance(fi, dict) and fi.get("required"):
            lines.append(f"  Functional Impairment: {fi.get('event', '')}")

    criteria = sampled.get("sampled_diagnostic_criteria", {})
    crit_lines: list[str] = []
    if "duration" in criteria:
        crit_lines.append(f"  - Duration: {criteria['duration']}")
    fi = criteria.get("functional_impairment_required")
    if isinstance(fi, dict) and fi.get("required"):
        crit_lines.append(f"  - Functional Impairment: {fi.get('event', '')}")
    ts = criteria.get("traumatic_stressor_required")
    if isinstance(ts, dict) and ts.get("required"):
        crit_lines.append(f"  - Traumatic Stressor: {ts.get('event', '')}")
    ps = criteria.get("psychosocial_stressor_required")
    if isinstance(ps, dict) and ps.get("required"):
        crit_lines.append(f"  - Psychosocial Stressor: {ps.get('event', '')}")
    addreqs = criteria.get("additional_requirements")
    if isinstance(addreqs, list) and addreqs:
        for req in addreqs:
            crit_lines.append(f"  - Additional: {req}")
    if crit_lines:
        lines.append("▸ Critical Diagnostic Criteria")
        lines.extend(crit_lines)

    symptom_block = "\n".join(lines).strip() if lines else "(No symptom information)"

    # chief complaint: first symptom of first group
    chief_complaint = disease_name
    for sg_key, sg_info in sampled.get("sampled_symptom_groups", {}).items():
        symptoms = sg_info.get("symptoms", [])
        if symptoms:
            sym_code = symptoms[0]
            sym_info = sampled.get("sampled_symptoms_descriptions", {}).get(sym_code, {})
            chief_complaint = sym_info.get("name", sym_code)
            break

    # alignment prompt 재사용을 위해 cache
    _kg_symptom_block_cache["block"] = symptom_block
    global _SECTION_INDEX
    _kg_symptom_block_cache["alignment_block"] = symptom_block
    _SECTION_INDEX = _build_alignment_index(
        {"symptom": {"sampled_features": sampled},
         "add_requirements": {k: v for k, v in criteria.items() if isinstance(v, str)}}
    )

    print(
        f"[patient] KG profile generated: {_DISEASE_CODE} / {disease_name} "
        f"(difficulty={_DIFFICULTY})",
        flush=True,
    )

    return (
        PROMPT.replace("{symptom_profile}", symptom_block)
        .replace("{most_likely_diagnosis}", disease_name)
        .replace("{conversation_style}", CONVERSATION_STYLE)
    )


# ─── JSON 파일 기반 프롬프트 빌더 (폴백) ─────────────────────────────────────

def _build_system_prompt_from_json() -> str:
    """Generate the patient prompt from a configured profile JSON."""
    data = _load_profile()
    block = format_symptom_profile(data)
    diagnosis = ""
    symptom = data.get("symptom")
    if isinstance(symptom, dict):
        diagnosis = str(symptom.get("disease_name") or "").strip()
        sampled = symptom.get("sampled_features")
        if not diagnosis and isinstance(sampled, dict):
            diagnosis = str(sampled.get("disease_name") or "").strip()
    if not diagnosis:
        diagnosis = str(data.get("most_likely_diagnosis") or "").strip()
    if not diagnosis:
        cand = data.get("candidate_diagnosis")
        if isinstance(cand, list) and cand:
            diagnosis = str(cand[0]).strip()
    if not diagnosis:
        diagnosis = "Major Depressive Disorder"
    _kg_symptom_block_cache["block"] = block
    _kg_symptom_block_cache["alignment_block"] = format_symptom_block_for_alignment(data)
    global _SECTION_INDEX
    _SECTION_INDEX = _build_alignment_index(data)
    return (
        PROMPT.replace("{symptom_profile}", block)
        .replace("{most_likely_diagnosis}", diagnosis)
        .replace("{conversation_style}", CONVERSATION_STYLE)
    )


# ─── 최종 빌더 ────────────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    """
    Based on patient.use_knowledge_graph in config.json:
      - True  → Dynamically generate patient profile from KnowledgeGraph
      - False → Load patient.symptom_profile_path
    """
    if _USE_KG:
        try:
            return _build_system_prompt_from_kg()
        except Exception as exc:
            print(
                f"[patient] KG-based profile generation failed ({exc}). "
                f"Falling back to configured JSON: {_PROFILE_PATH}.",
                flush=True,
            )
    return _build_system_prompt_from_json()


SYSTEM_PROMPT = build_system_prompt()


def set_symptom_profile_path(path: "Path | str") -> None:
    """CLI 등에서 사용: 증상 프로필 JSON 경로로 전환해 SYSTEM_PROMPT를 다시 빌드.
    KG 모드와 무관하게 JSON 파일 기반 프롬프트로 재생성한다.
    """
    from pathlib import Path as _Path
    global _PROFILE_PATH, _USE_KG, SYSTEM_PROMPT
    resolved = _Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"symptom profile not found: {resolved}")
    _USE_KG = False
    _PROFILE_PATH = resolved
    SYSTEM_PROMPT = _build_system_prompt_from_json()


def set_conversation_style(style: str, *, seed: Any = None) -> str:
    """Switch the patient's conversation style and rebuild SYSTEM_PROMPT.

    `style` accepts a key from CONVERSATION_STYLES or "random". Returns the
    concrete style key that was applied.
    """
    global _CONVERSATION_STYLE, CONVERSATION_STYLE, SYSTEM_PROMPT
    _CONVERSATION_STYLE = _resolve_conversation_style(style, seed)
    CONVERSATION_STYLE = build_conversation_style_block(_CONVERSATION_STYLE)
    SYSTEM_PROMPT = build_system_prompt()
    print(f"[patient] conversation_style: {_CONVERSATION_STYLE}", flush=True)
    return _CONVERSATION_STYLE


def current_conversation_style() -> str:
    """Concrete style key currently baked into SYSTEM_PROMPT."""
    return _CONVERSATION_STYLE


def reinitialize(
    disease_code: str | None = None,
    difficulty_level: str | None = None,
    use_knowledge_graph: bool | None = None,
) -> str:
    """UI에서 환자 config을 변경한 뒤 SYSTEM_PROMPT를 재빌드한다.
    None인 파라미터는 현재 값을 유지한다.
    재빌드된 SYSTEM_PROMPT를 반환한다.
    """
    global _USE_KG, _DISEASE_CODE, _DIFFICULTY, SYSTEM_PROMPT
    if use_knowledge_graph is not None:
        _USE_KG = bool(use_knowledge_graph)
    if disease_code is not None:
        _DISEASE_CODE = str(disease_code).strip()
    if difficulty_level is not None:
        _DIFFICULTY = str(difficulty_level).strip()

    print(
        f"[patient] reinitialize: disease={_DISEASE_CODE}, "
        f"difficulty={_DIFFICULTY}, use_kg={_USE_KG}",
        flush=True,
    )
    SYSTEM_PROMPT = build_system_prompt()
    return SYSTEM_PROMPT


def set_context_window(window: int) -> int:
    """Change how many recent messages the two patient prompts see."""
    global _CONTEXT_WINDOW
    _CONTEXT_WINDOW = int(window)
    return _CONTEXT_WINDOW


def current_config() -> dict:
    """현재 환자 설정을 딕셔너리로 반환한다."""
    return {
        "use_knowledge_graph": _USE_KG,
        "conversation_style": _CONVERSATION_STYLE,
        "disease_code": _DISEASE_CODE,
        "difficulty_level": _DIFFICULTY,
        "kg_base_dir": _KG_BASE_DIR,
        "symptom_profile_path": str(_PROFILE_PATH),
        "context_window": _CONTEXT_WINDOW,
    }
