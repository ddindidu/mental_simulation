"""
Diagnostic Reasoning Quality Scoring — spec §4.6 (Final Diagnosis Axis)

Evaluates whether the required criteria for the ground-truth diagnosis were
actually covered during the interview, using HYBRID scoring:
  - symptom-group coverage (2x-weighted, the bulk of the score): ALGORITHMIC.
    Computed from cumulative_confirmed/cumulative_denied — the actual evidence
    extracted turn-by-turn by the symptom-extraction judge (symptom_diagnosis.py),
    same S-code ID space as diagnostic_criteria.json. No LLM call, no
    self-report bias (the doctor's own checklist wording is not the source of
    truth for this portion anymore).
  - non-symptom requirements (duration, functional impairment, stressors,
    additional requirements): still LLM-judged against the doctor's
    self-reported checklist text — the pipeline has no structured evidence
    extraction for these yet (tracked as an open gap).

Score components (all against the GT disease's criteria):
  - must_include symptom groups: coverage ratio × must_include_all/one_of penalties  (weight 2, algorithmic)
  - include symptom groups: counted only when explicitly addressed                   (weight 1, algorithmic)
  - duration verification                                                             (weight 1, LLM judge)
  - functional impairment (if required by GT criteria)                               (weight 1, LLM judge)
  - traumatic / psychosocial stressor (if required)                                  (weight 1 each, LLM judge)
  - additional_requirements coverage                                                 (weight 1, LLM judge)

Public API:
  load_symptom_names(symptom_dir)  → dict[str, dict]
  build_gt_criteria_text(did, criteria, sym_names) → str            (full text, debug display)
  build_gt_scalar_text(did, criteria) → str                          (non-symptom text, fed to the scalar judge)
  compute_symptom_criterion_evaluations(did, criteria, confirmed, denied, sym_names) → list[dict]
  judge_checklist(doctor_checklist, gt_scalar_text, llm_chat) → dict  (scalar fields only)
  compute_score(judgment, did, criteria) → dict
  score_episode(did, doctor_checklist, criteria, sym_names, llm_chat, confirmed, denied) → dict
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


def build_gt_scalar_text(disease_id: str, criteria: dict) -> str:
    """
    Non-symptom requirements only (duration, functional impairment, stressors,
    additional requirements) — the ONLY thing the scalar LLM judge sees.
    Symptom-group requirements are scored algorithmically (see
    compute_symptom_criterion_evaluations), not by this text or that judge.
    """
    disease_data = criteria.get(disease_id, {})
    disease_name = disease_data.get("name", disease_id)
    rc = disease_data.get("required_criteria", {})
    lines: list[str] = [f"Disease: {disease_name} ({disease_id})", ""]

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

    if len(lines) == 2:
        lines.append("(No non-symptom requirements for this disease.)")

    return "\n".join(lines)


# ── Algorithmic symptom-group scoring ──────────────────────────────────────────

def compute_symptom_criterion_evaluations(
    disease_id: str,
    criteria: dict,
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
    sym_names: dict[str, dict] | None = None,
) -> list[dict]:
    """
    Deterministic replacement for the LLM-judged symptom-group
    `criterion_evaluations`. Uses the ACTUAL evidence collected during the
    interview (`cumulative_confirmed`/`cumulative_denied`, produced by the
    per-turn symptom-extraction judge in symptom_diagnosis.py — same
    S-code ID space as diagnostic_criteria.json) instead of the doctor's
    self-reported free-text checklist, removing self-report bias for this
    2x-weighted portion of the score (see compute_score / weighting table).

    Output shape matches what the old LLM judge produced, so compute_score()
    and compute_symptom_satisfaction() need no changes.
    """
    rc = criteria.get(disease_id, {}).get("required_criteria", {})
    sym_names = sym_names or {}
    out: list[dict] = []

    for key, val in rc.items():
        if not isinstance(val, dict) or "symptom_pool" not in val:
            continue
        relation  = val.get("relation", "include")
        min_count = val.get("min_count", 1) or 1
        pool      = set(val.get("symptom_pool", []))
        mia       = set(val.get("must_include_all", []))
        mio       = set(val.get("must_include_one_of", []))

        confirmed_in_pool = pool & cumulative_confirmed
        valid_count = len(confirmed_in_pool)
        coverage = min(1.0, valid_count / min_count)

        mia_satisfied = (mia <= cumulative_confirmed) if mia else None
        mio_satisfied = bool(mio & cumulative_confirmed) if mio else None

        matched = sorted(confirmed_in_pool)
        missing = sorted(pool - cumulative_confirmed)

        out.append({
            "group":                        key,
            "relation":                      relation,
            "min_count_required":            min_count,
            "valid_symptom_count":           valid_count,
            "symptom_coverage_score":        round(coverage, 4),
            "must_include_one_of_satisfied": mio_satisfied,
            "must_include_all_satisfied":    mia_satisfied,
            "matched_symptom_descriptions":  [_sym_text(s, sym_names) for s in matched],
            "missing_required_symptoms":     [_sym_text(s, sym_names) for s in missing],
        })

    return out


# ── LLM judge (scalar / non-symptom requirements only) ────────────────────────

_JUDGE_SYSTEM = """/no_think
You are a clinical evaluation judge. Your task is to assess whether a doctor's
diagnostic checklist covers specific NON-SYMPTOM diagnostic requirements for a
psychiatric disorder: duration, functional impairment, traumatic/psychosocial
stressor, and any additional requirements.

Symptom-group coverage (mandatory/optional symptom pools) is scored
algorithmically from the interview's actual confirmed/denied evidence — do
NOT evaluate symptoms here, only the non-symptom fields below.

Output ONLY valid JSON, exactly in the format specified. No preamble or extra text.
"""

_JUDGE_TEMPLATE = """\
=== GROUND TRUTH NON-SYMPTOM REQUIREMENTS ===
{gt_text}

=== DOCTOR'S DIAGNOSTIC CHECKLIST (non-symptom fields) ===
{doctor_text}

=== EVALUATION TASK ===
Evaluate only the non-symptom fields above (Duration, Functional Impairment,
Traumatic/Psychosocial Stressor, Additional Requirements). If a requirement
is not listed under GROUND TRUTH, its field MUST be null.

Return this JSON (no other text):
{{
  "duration_verified": <true | false | null (null if no duration requirement)>,
  "functional_impairment_verified": <true | false | null (null if not required by criteria)>,
  "traumatic_stressor_verified": <true | false | null (null if not required)>,
  "psychosocial_stressor_verified": <true | false | null (null if not required)>,
  "additional_requirements_coverage": <float 0.0–1.0 | null (null if no additional requirements)>,
  "additional_requirements_notes": "<brief note on what was / was not covered, or null>"
}}
"""


def _format_doctor_checklist_scalar(doctor_checklist: dict | str | None) -> str:
    """Non-symptom fields only — the ONLY thing the scalar LLM judge sees.
    Symptom-group fields (symptom_groups) are intentionally omitted; those
    are scored algorithmically from actual interview evidence instead."""
    if doctor_checklist is None:
        return "(No checklist provided — using reason text only)"
    if isinstance(doctor_checklist, str):
        return doctor_checklist
    parts: list[str] = []
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
    gt_scalar_text: str,
    llm_chat: Callable,
) -> dict:
    """
    Call the scalar-only LLM judge (duration / functional impairment /
    stressors / additional requirements); return parsed judgment dict (or
    error dict). `gt_scalar_text` must come from build_gt_scalar_text() —
    symptom-group text is no longer part of this judge's input.
    """
    doctor_text = _format_doctor_checklist_scalar(doctor_checklist)
    user_msg = _JUDGE_TEMPLATE.format(gt_text=gt_scalar_text, doctor_text=doctor_text)

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
    # Symptom-group coverage is algorithmic and never depends on the scalar
    # LLM judge, so a scalar-judge parse failure only drops the scalar
    # metrics from the macro-mean below — it does NOT zero out the whole
    # score the way a full-judge parse failure used to.
    scalar_parse_error = bool(judgment.get("_parse_error"))

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
        if scalar_parse_error:
            return None
        val = judgment.get(key)
        if val is None:
            return None
        return 1.0 if val else 0.0

    duration_score   = _bin_score("duration_verified")
    fi_score         = _bin_score("functional_impairment_verified")
    traumatic_score  = _bin_score("traumatic_stressor_verified")
    psycho_score     = _bin_score("psychosocial_stressor_verified")

    add_score = None if scalar_parse_error else judgment.get("additional_requirements_coverage")
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
        "_parse_error":                scalar_parse_error,
    }


def score_episode(
    disease_id: str,
    doctor_checklist: dict | str | None,
    criteria: dict,
    sym_names: dict[str, dict],
    llm_chat: Callable,
    cumulative_confirmed: set[str] | None = None,
    cumulative_denied: set[str] | None = None,
) -> dict:
    """
    Full pipeline for one episode — HYBRID scoring:
      - symptom-group coverage (2x-weighted): algorithmic, from the actual
        cumulative_confirmed/cumulative_denied evidence collected during the
        interview (see compute_symptom_criterion_evaluations). No LLM call,
        no self-report bias.
      - non-symptom requirements (duration, functional impairment, stressors,
        additional requirements): still LLM-judged against the doctor's
        self-reported checklist, since the pipeline has no structured
        evidence extraction for these yet.

    Returns merged dict:
      judgment fields (criterion_evaluations + scalar fields) + score fields
      + "gt_criteria_text" for debug/case-study display.
    """
    cumulative_confirmed = cumulative_confirmed or set()
    cumulative_denied    = cumulative_denied or set()

    criterion_evaluations = compute_symptom_criterion_evaluations(
        disease_id, criteria, cumulative_confirmed, cumulative_denied, sym_names,
    )

    gt_scalar_text  = build_gt_scalar_text(disease_id, criteria)
    scalar_judgment = judge_checklist(doctor_checklist, gt_scalar_text, llm_chat)

    judgment = {**scalar_judgment, "criterion_evaluations": criterion_evaluations}
    scores   = compute_score(judgment, disease_id, criteria)
    gt_text  = build_gt_criteria_text(disease_id, criteria, sym_names)  # full text, for debug display only
    return {
        **judgment,
        **scores,
        "gt_criteria_text": gt_text,
        "scoring_method": {
            "symptom_groups": "algorithmic",
            "scalar_requirements": "llm_judge",
        },
    }
