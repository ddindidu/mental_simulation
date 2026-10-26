#!/usr/bin/env python3
"""
Symptom-level variant of Diagnostic Evidence Sufficiency.

eval/score_diagnostic_reasoning.py's compute_symptom_satisfaction() weights
mandatory/optional SYMPTOM GROUPS (2x/1x), not individual symptoms — a group
with 9 possible symptoms and a group with 2 both count as "1 group". This
script adds a symptom-level counterpart that instead weights individual
MANDATORY symptoms 2x and OPTIONAL symptoms 1x:

  n_mand = |mandatory_symptom_ids(d) ∩ final_confirmed|
  N_mand = |mandatory_symptom_ids(d)|
  n_opt  = |optional_symptom_ids(d)  ∩ final_confirmed|
  N_opt  = |optional_symptom_ids(d)|
  symptom_satisfaction_score_symptom = (2*n_mand + n_opt) / (2*N_mand + N_opt)

No new LLM calls: mandatory/optional symptom pools come from the static
diagnostic_criteria.json, final_confirmed is the same final-turn
cumulative_confirmed already used by the group-level score (from
*_result.json, itself produced earlier by symptom_diagnosis.py — not
recomputed here), and the scalar (duration/functional impairment/stressor/
additional-requirements) sub-scores are the ones ALREADY CACHED per episode
in diagnostic_reasoning_eval.json (*_score_pred, from the existing LLM-judge
run) — reused as-is, same applicability gating as
score_diagnostic_reasoning.compute_score()'s macro-mean.

Writes two new fields into the existing results/<combo>/diagnostic_reasoning_eval.json,
in place, alongside the existing *_pred fields (which are left untouched and
should now be read as the GROUP-level variant — see markdown/evaluation_v5.md §4.2):
  symptom_satisfaction_score_symptom
  overall_score_symptom

Usage:
  MS_RUN=run_batch_20260912 python eval/compute_evidence_sufficiency_symptom.py [--style plain]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.paths import RESULTS_ROOT
from eval.question_targeting_score import mandatory_symptom_ids
from eval.question_score import _optional_symptom_ids_for_disorder

BASE_DIR = Path(__file__).resolve().parent.parent
KG_DIR = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN"


def _load(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _final_cumulative_confirmed(results_dir: Path, log_name: str) -> set[str]:
    result_path = results_dir / f"{log_name}_result.json"
    if not result_path.exists():
        return set()
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    turns = data.get("turns", [])
    if not turns:
        return set()
    return set(turns[-1].get("cumulative_confirmed", []))


def symptom_satisfaction_symptom(disease_id: str, criteria: dict, confirmed: set[str]) -> float | None:
    mand = mandatory_symptom_ids(disease_id, criteria)
    opt = _optional_symptom_ids_for_disorder(disease_id, criteria)
    n_mand, n_opt = len(mand & confirmed), len(opt & confirmed)
    denom = 2 * len(mand) + len(opt)
    if denom == 0:
        return None
    return round((2 * n_mand + n_opt) / denom, 4)


def overall_score_symptom(episode: dict, disease_id: str, criteria: dict, sym_sat: float | None) -> float:
    """Same macro-mean + applicability gating as
    score_diagnostic_reasoning.compute_score(), with the group-level
    symptom_satisfaction_score swapped for the symptom-level one and the
    scalar sub-scores reused from the cached *_pred fields."""
    rc = criteria.get(disease_id, {}).get("required_criteria", {})
    has_top_duration = bool(rc.get("min_duration")) and not isinstance(rc.get("min_duration"), dict)
    fi_required = rc.get("functional_impairment_required")
    traumatic_required = rc.get("traumatic_stressor_required")
    psycho_required = rc.get("psychosocial_stressor_required")
    add_reqs = rc.get("additional_requirements")

    metrics: list[float] = []
    if sym_sat is not None:
        metrics.append(sym_sat)
    if has_top_duration and episode.get("duration_score_pred") is not None:
        metrics.append(episode["duration_score_pred"])
    if fi_required and episode.get("functional_impairment_score_pred") is not None:
        metrics.append(episode["functional_impairment_score_pred"])
    if traumatic_required and episode.get("traumatic_stressor_score_pred") is not None:
        metrics.append(episode["traumatic_stressor_score_pred"])
    if psycho_required and episode.get("psychosocial_stressor_score_pred") is not None:
        metrics.append(episode["psychosocial_stressor_score_pred"])
    if add_reqs and isinstance(add_reqs, list) and episode.get("additional_requirements_score_pred") is not None:
        metrics.append(episode["additional_requirements_score_pred"])

    return round(sum(metrics) / len(metrics), 4) if metrics else 0.0


def process_combo(dr_path: Path, criteria: dict, style: str | None) -> int:
    episodes = _load(dr_path)
    if not episodes:
        return 0
    results_dir = dr_path.parent
    n_scored = 0
    for ep in episodes:
        if style and not str(ep.get("log_file", "")).endswith(f"_{style}"):
            continue
        disease_id = ep.get("predicted_diagnosis_id")
        if disease_id is None or disease_id not in criteria:
            ep["symptom_satisfaction_score_symptom"] = None
            ep["overall_score_symptom"] = None
            continue
        confirmed = _final_cumulative_confirmed(results_dir, ep["log_file"])
        sym_sat = symptom_satisfaction_symptom(disease_id, criteria, confirmed)
        ep["symptom_satisfaction_score_symptom"] = sym_sat
        ep["overall_score_symptom"] = overall_score_symptom(ep, disease_id, criteria, sym_sat)
        n_scored += 1

    dr_path.write_text(json.dumps(episodes, indent=2, ensure_ascii=False), encoding="utf-8")
    return n_scored


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default=None, help="Only recompute episodes ending in _<style>.")
    args = parser.parse_args()

    criteria = json.loads((KG_DIR / "diagnostic_criteria.json").read_text(encoding="utf-8"))

    total = 0
    for dr_path in sorted(RESULTS_ROOT.glob("*/*/*/diagnostic_reasoning_eval.json")):
        n = process_combo(dr_path, criteria, args.style)
        rel = dr_path.relative_to(RESULTS_ROOT).parent
        print(f"  {rel}: {n} episodes scored")
        total += n

    print(f"\n[done] {total} episodes scored across all combos")


if __name__ == "__main__":
    main()
