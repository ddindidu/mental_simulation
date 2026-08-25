"""
Diagnostic Reasoning Quality Scoring — spec §4.6 (Final Diagnosis Axis)

Evaluates whether the doctor's diagnostic checklist covers the required
criteria for the ground-truth diagnosis, using an LLM judge.

Score components (all against the GT disease's criteria):
  - must_include symptom groups: coverage ratio × must_include_all/one_of penalties  (weight 2)
  - include symptom groups: counted only when explicitly addressed                   (weight 1)
  - duration verification                                                             (weight 1)
  - functional impairment (if required by GT criteria)                               (weight 1)
  - traumatic / psychosocial stressor (if required)                                  (weight 1 each)
  - additional_requirements coverage                                                 (weight 1)

Public API:
  load_symptom_names(symptom_dir)  → dict[str, dict]
  build_gt_criteria_text(did, criteria, sym_names) → str
  judge_checklist(doctor_text, gt_text, disease_name, did, llm_chat) → dict
  compute_score(judgment, did, criteria)  → float
  score_episode(did, doctor_checklist, criteria, sym_names, llm_chat) → dict
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))
from typing import Any, Callable

# ── KG paths ──────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).resolve().parent.parent
SYMPTOM_DIR  = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "symptom"


# ── KG helpers ────────────────────────────────────────────────────────────────

def load_symptom_names(symptom_dir: Path = SYMPTOM_DIR) -> dict[str, dict]:
    """Return {sym_id: {"name": ..., "description": ...}} for all symptoms."""
    syms: dict[str, dict] = {}
    for p in sorted(symptom_dir.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for sid, v in data.items():
            syms[sid] = {"name": v.get("name", sid), "description": v.get("description", "")}
    return syms


def _sym_text(sid: str, sym_names: dict[str, dict]) -> str:
    info = sym_names.get(sid, {})
    name = info.get("name", sid).replace("_", " ")
    desc = info.get("description", "")
    return f"{name}: {desc}" if desc else name


def build_gt_criteria_text(
    disease_id: str,
    criteria: dict,
    sym_names: dict[str, dict],
) -> str:
    """Format GT criteria for the judge prompt."""
    disease_data = criteria.get(disease_id, {})
    disease_name = disease_data.get("name", disease_id)
    rc = disease_data.get("required_criteria", {})

    lines: list[str] = [f"Disease: {disease_name} ({disease_id})", ""]

    for key, val in rc.items():
        if not isinstance(val, dict):
            continue  # scalar fields handled separately below

        relation   = val.get("relation", "include")
        min_count  = val.get("min_count", 1)
        pool       = val.get("symptom_pool", [])
        mia        = val.get("must_include_all", [])
        mio        = val.get("must_include_one_of", [])
        grp_dur    = val.get("min_duration")
        grp_fi     = val.get("functional_impairment_required")

        rel_label = "MUST INCLUDE (mandatory)" if relation == "must_include" else "INCLUDE (optional)"
        lines.append(f"[Criterion Group: {key}]")
        lines.append(f"  Relation: {rel_label}")
        lines.append(f"  Required: at least {min_count} symptom(s) from this pool")

        if mia:
            lines.append(f"  Must include ALL of: {', '.join(_sym_text(s, sym_names) for s in mia)}")
        if mio:
            lines.append(f"  Must include AT LEAST ONE OF: {', '.join(_sym_text(s, sym_names) for s in mio)}")

        lines.append("  Symptom pool:")
        for sid in pool:
            lines.append(f"    - {_sym_text(sid, sym_names)}")

        if grp_dur:
            lines.append(f"  Group-level duration requirement: {grp_dur}")
        if grp_fi is not None:
            lines.append(f"  Group-level functional impairment required: {grp_fi}")
        lines.append("")

    # Scalar fields
    top_dur = rc.get("min_duration")
    if top_dur and not isinstance(top_dur, dict):
        lines.append(f"[Duration]: minimum {top_dur}")

    max_dur = rc.get("max_duration")
    if max_dur and not isinstance(max_dur, dict):
        lines.append(f"[Max Duration]: must not exceed {max_dur}")

    fi = rc.get("functional_impairment_required")
    if fi is not None and not isinstance(fi, dict):
        lines.append(f"[Functional Impairment]: {'Required' if fi else 'Not required'}")

    traumatic = rc.get("traumatic_stressor_required")
    if traumatic and not isinstance(traumatic, dict):
        lines.append(f"[Traumatic Stressor]: Required ({traumatic})")

    psycho = rc.get("psychosocial_stressor_required")
    if psycho and not isinstance(psycho, dict):
        lines.append(f"[Psychosocial Stressor]: Required ({psycho})")

    add_reqs = rc.get("additional_requirements")
    if add_reqs and isinstance(add_reqs, list):
        lines.append("[Additional Requirements]:")
        for req in add_reqs:
            lines.append(f"  - {req}")

    return "\n".join(lines)


# ── LLM judge ─────────────────────────────────────────────────────────────────

_JUDGE_SYSTEM = """/no_think
You are a clinical evaluation judge. Your task is to assess whether a doctor's
diagnostic checklist adequately covers the required diagnostic criteria for a
psychiatric disorder.

You will receive:
1. The ground-truth diagnosis (the correct disease and its required criteria)
2. The doctor's stated diagnostic checklist

Evaluate each required criterion group and overall requirements.

When matching doctor descriptions to criterion symptoms, be generous:
a doctor saying "patient often loses focus" matches "difficulty sustaining attention";
"racing thoughts and inflated self-esteem" matches typical manic symptoms, etc.
Count a symptom as matched if the doctor's description clearly refers to the
same clinical phenomenon, even if worded differently.

Output ONLY valid JSON, exactly in the format specified. No preamble or extra text.
"""

_JUDGE_TEMPLATE = """\
=== GROUND TRUTH CRITERIA ===
{gt_text}

=== DOCTOR'S DIAGNOSTIC CHECKLIST ===
{doctor_text}

=== EVALUATION TASK ===
For each criterion GROUP listed above (the bracketed [Criterion Group: ...] sections),
evaluate the doctor's checklist. Skip scalar fields (Duration, Functional Impairment, etc.)
in the criterion_evaluations array — those have dedicated fields below.

Return this JSON (no other text):
{{
  "criterion_evaluations": [
    {{
      "group": "<group key, e.g. inattention>",
      "relation": "<must_include | include>",
      "min_count_required": <integer>,
      "valid_symptom_count": <integer, how many of doctor's symptoms match this group's pool>,
      "symptom_coverage_score": <float 0.0–1.0, = min(1.0, valid_symptom_count / min_count_required)>,
      "must_include_one_of_satisfied": <true | false | null (null if no such requirement)>,
      "must_include_all_satisfied": <true | false | null (null if no such requirement)>,
      "matched_symptom_descriptions": ["brief description of which doctor symptoms were matched"],
      "missing_required_symptoms": ["brief description of required symptoms the doctor did NOT mention"]
    }}
  ],
  "duration_verified": <true | false | null (null if no duration requirement)>,
  "functional_impairment_verified": <true | false | null (null if not required by criteria)>,
  "traumatic_stressor_verified": <true | false | null (null if not required)>,
  "psychosocial_stressor_verified": <true | false | null (null if not required)>,
  "additional_requirements_coverage": <float 0.0–1.0 | null (null if no additional requirements)>,
  "additional_requirements_notes": "<brief note on what was / was not covered, or null>"
}}
"""


def _format_doctor_checklist(doctor_checklist: dict | str | None) -> str:
    if doctor_checklist is None:
        return "(No checklist provided — using reason text only)"
    if isinstance(doctor_checklist, str):
        return doctor_checklist
    # structured dict
    parts: list[str] = []
    groups = doctor_checklist.get("symptom_groups", [])
    for g in groups:
        name  = g.get("group", "unknown")
        syms  = g.get("confirmed_symptoms", [])
        count = g.get("count", len(syms))
        parts.append(f"Symptom Group [{name}] — {count} confirmed:")
        for s in syms:
            parts.append(f"  - {s}")
    dur = doctor_checklist.get("duration_verified")
    if dur:
        parts.append(f"Duration: {dur}")
    fi = doctor_checklist.get("functional_impairment")
    if fi is not None:
        parts.append(f"Functional impairment: {'confirmed' if fi else 'not confirmed'}")
    ts = doctor_checklist.get("traumatic_stressor")
    if ts is not None:
        parts.append(f"Traumatic stressor: {'confirmed' if ts else 'not confirmed'}")
    ps = doctor_checklist.get("psychosocial_stressor")
    if ps is not None:
        parts.append(f"Psychosocial stressor: {'confirmed' if ps else 'not confirmed'}")
    add = doctor_checklist.get("additional_requirements", [])
    if add:
        parts.append("Additional requirements verified:")
        for r in add:
            parts.append(f"  - {r}")
    return "\n".join(parts) if parts else "(Empty checklist)"


def judge_checklist(
    doctor_checklist: dict | str | None,
    gt_text: str,
    llm_chat: Callable,
) -> dict:
    """Call LLM judge; return parsed judgment dict (or error dict)."""
    doctor_text = _format_doctor_checklist(doctor_checklist)
    user_msg = _JUDGE_TEMPLATE.format(gt_text=gt_text, doctor_text=doctor_text)

    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM},
        {"role": "user",   "content": user_msg},
    ]
    raw = llm_chat(
        messages=messages,
        role="judge",
        phase="reasoning_checklist",
        source="score_diagnostic_reasoning.judge_checklist",
    )

    m = re.search(r"\{[\s\S]*\}", raw or "")
    if not m:
        return {"_parse_error": True, "_raw": (raw or "")[:500]}
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return {"_parse_error": True, "_raw": (raw or "")[:500]}


# ── Scoring ───────────────────────────────────────────────────────────────────

def _group_satisfied(crit: dict) -> bool:
    """A symptom group counts as 'satisfied' only if its min_count threshold is
    fully met AND no must_include_one_of/must_include_all constraint was violated."""
    if crit.get("must_include_one_of_satisfied") is False:
        return False
    if crit.get("must_include_all_satisfied") is False:
        return False
    s = float(crit.get("symptom_coverage_score", 0.0))
    return s >= 1.0


def compute_symptom_satisfaction(judgment: dict, disease_id: str, criteria: dict) -> float | None:
    """
    Symptom Satisfaction = (2 * satisfied_mandatory_groups + satisfied_optional_groups)
                            / (2 * total_mandatory_groups + total_optional_groups)

    Isolates compliance with mandatory (must_include) symptom groups and
    satisfaction of each group's minimum-count threshold, separate from the
    scalar checklist items (duration, stressors, etc.). Mandatory groups are
    weighted 2x, matching the weighting used elsewhere in this scorer.
    Returns None if the disease has no symptom groups defined.
    """
    rc = criteria.get(disease_id, {}).get("required_criteria", {})
    crit_by_group = {c.get("group"): c for c in judgment.get("criterion_evaluations", [])}

    mandatory_total = mandatory_satisfied = 0
    optional_total  = optional_satisfied  = 0

    for key, val in rc.items():
        if not isinstance(val, dict) or "symptom_pool" not in val:
            continue
        relation  = val.get("relation", "include")
        satisfied = _group_satisfied(crit_by_group.get(key, {}))
        if relation == "must_include":
            mandatory_total += 1
            mandatory_satisfied += int(satisfied)
        else:
            optional_total += 1
            optional_satisfied += int(satisfied)

    denom = 2 * mandatory_total + optional_total
    if denom == 0:
        return None
    return round((2 * mandatory_satisfied + optional_satisfied) / denom, 4)


def compute_score(judgment: dict, disease_id: str, criteria: dict) -> dict:
    """
    Aggregate judge output into a scalar score + sub-scores.

    "overall_score" is the macro-mean across all applicable metrics
    (symptom_satisfaction_score plus whichever scalar criteria the GT disease
    requires) — each metric contributes equally regardless of how many
    symptom groups or requirements it internally covers.

    Returns:
      {
        "overall_score": float,
        "symptom_satisfaction_score": float | None,
        "symptom_group_scores": {group: float},
        "duration_score": float | None,
        "functional_impairment_score": float | None,
        "traumatic_stressor_score": float | None,
        "psychosocial_stressor_score": float | None,
        "additional_requirements_score": float | None,
        "_parse_error": bool,
      }
    """
    if judgment.get("_parse_error"):
        return {"overall_score": 0.0, "_parse_error": True}

    rc = criteria.get(disease_id, {}).get("required_criteria", {})

    group_scores: dict[str, float] = {}
    for crit in judgment.get("criterion_evaluations", []):
        group    = crit.get("group", "")
        relation = crit.get("relation", "include")

        s = float(crit.get("symptom_coverage_score", 0.0))
        s = max(0.0, min(1.0, s))
        if crit.get("must_include_one_of_satisfied") is False:
            s *= 0.5
        if crit.get("must_include_all_satisfied") is False:
            s *= 0.5

        # For optional groups (include), only report if doctor actually addressed them
        if relation != "must_include" and crit.get("valid_symptom_count", 0) == 0:
            continue

        group_scores[group] = round(s, 4)

    symptom_satisfaction_score = compute_symptom_satisfaction(judgment, disease_id, criteria)

    def _bin_score(key: str) -> float | None:
        val = judgment.get(key)
        if val is None:
            return None
        return 1.0 if val else 0.0

    duration_score   = _bin_score("duration_verified")
    fi_score         = _bin_score("functional_impairment_verified")
    traumatic_score  = _bin_score("traumatic_stressor_verified")
    psycho_score     = _bin_score("psychosocial_stressor_verified")

    add_score = judgment.get("additional_requirements_coverage")
    if isinstance(add_score, (int, float)):
        add_score = float(max(0.0, min(1.0, add_score)))
    else:
        add_score = None

    # Include non-group criteria only when they are actually required
    fi_required = rc.get("functional_impairment_required")
    traumatic_required = rc.get("traumatic_stressor_required")
    psycho_required = rc.get("psychosocial_stressor_required")
    add_reqs = rc.get("additional_requirements")
    has_top_duration = bool(rc.get("min_duration")) and not isinstance(rc.get("min_duration"), dict)

    # overall_score = macro-mean over applicable metrics: each metric (symptom
    # satisfaction, duration, functional impairment, stressors, additional
    # requirements) contributes equally, regardless of how many symptom groups
    # or sub-requirements it aggregates internally.
    metrics: list[float] = []
    if symptom_satisfaction_score is not None:
        metrics.append(symptom_satisfaction_score)
    if has_top_duration and duration_score is not None:
        metrics.append(duration_score)
    if fi_required and fi_score is not None:
        metrics.append(fi_score)
    if traumatic_required and traumatic_score is not None:
        metrics.append(traumatic_score)
    if psycho_required and psycho_score is not None:
        metrics.append(psycho_score)
    if add_reqs and isinstance(add_reqs, list) and add_score is not None:
        metrics.append(add_score)

    overall = round(sum(metrics) / len(metrics), 4) if metrics else 0.0

    return {
        "overall_score":               overall,
        "symptom_satisfaction_score":  symptom_satisfaction_score,
        "symptom_group_scores":        group_scores,
        "duration_score":              round(duration_score, 4) if duration_score is not None else None,
        "functional_impairment_score": round(fi_score, 4) if fi_score is not None else None,
        "traumatic_stressor_score":    round(traumatic_score, 4) if traumatic_score is not None else None,
        "psychosocial_stressor_score": round(psycho_score, 4) if psycho_score is not None else None,
        "additional_requirements_score": round(add_score, 4) if add_score is not None else None,
        "_parse_error":                False,
    }


def score_episode(
    disease_id: str,
    doctor_checklist: dict | str | None,
    criteria: dict,
    sym_names: dict[str, dict],
    llm_chat: Callable,
) -> dict:
    """
    Full pipeline for one episode: build GT text → judge → score.

    Returns merged dict:
      judgment fields + score fields + "gt_criteria_text"
    """
    gt_text  = build_gt_criteria_text(disease_id, criteria, sym_names)
    judgment = judge_checklist(doctor_checklist, gt_text, llm_chat)
    scores   = compute_score(judgment, disease_id, criteria)
    return {**judgment, **scores, "gt_criteria_text": gt_text}
