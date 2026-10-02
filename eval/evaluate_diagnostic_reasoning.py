#!/usr/bin/env python3
"""
Diagnostic Decision Quality — Diagnostic Evidence Sufficiency

For each episode, scores whether the interview gathered enough evidence to
support the DOCTOR'S OWN final diagnosis ("_pred"): the doctor's stated
ICD-10 code (possibly JSON-wrapped — see eval/common.py) is resolved
to a disease id via disorder_icd10.json (icd10_accepted_codes), and that
disease's required criteria are scored by
eval/score_diagnostic_reasoning.score_episode() (hybrid: algorithmic
symptom groups + LLM-judged non-symptom requirements against the doctor's
final diagnostic_checklist, falling back to the free-text `reason`).

Episodes whose diagnosis does not resolve to a disease id get
overall_score_pred = None (no LLM call).

[DEACTIVATED] "_gt" variant (evidence sufficiency for the ground-truth
disease) — not part of the headline set; disabling it removes one scalar
judge call per episode whose final diagnosis is wrong or unresolved.

Outputs:
  results/<run_dir>/diagnostic_reasoning_eval.json
  results/<run_dir>/diagnostic_reasoning_scalar_cache.json
  (printed summary to stdout)

Usage:
  python evaluate_diagnostic_reasoning.py
  python evaluate_diagnostic_reasoning.py --results path/to/results --logs path/to/logs
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
from utils.paths import ANALYSIS_ROOT, LOGS_ROOT, RESULTS_ROOT
KG_DIR   = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN"
DISORDER_ICD10_FILE = KG_DIR / "disorder_icd10.json"

from eval.common import load_code2id as _load_code2id, resolve_disease_id as _resolve_predicted_id


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=Path, default=None,
                   help="Results dir (default: results/<run_dir>)")
    p.add_argument("--logs",    type=Path, default=None,
                   help="Logs dir (default: logs/<run_dir>)")
    p.add_argument("--style", default=None,
                   help="Only process logs whose filename ends in _<style> (e.g. 'plain').")
    # [DEACTIVATED] --skip-pred: _gt is no longer scored, so skipping _pred would leave nothing.
    return p.parse_args()


# ── Lazy imports to avoid module-level side effects ───────────────────────────
def _setup() -> tuple:
    from utils.llm import get_run_dir as _get_run_dir, chat as _llm_chat
    from eval.score_diagnostic_reasoning import (
        load_symptom_names,
        build_gt_criteria_text,
        judge_checklist,
        compute_score,
        score_episode,
    )
    return _get_run_dir, _llm_chat, load_symptom_names, build_gt_criteria_text, judge_checklist, compute_score, score_episode


# ── Log parsing ───────────────────────────────────────────────────────────────

def _extract_final_doctor_block_from_txt(log_file: Path) -> dict | None:
    """Return parsed JSON from the last doctor OUTPUT block that contains 'diagnosis'.

    .txt-only fallback for logs written before doctor.finalize_doctor_memory()
    started persisting diagnostic_checklist into doctor_memory (see
    _extract_final_doctor_block below) — those episodes have the checklist
    only in the raw transcript, never in the .json log.
    """
    text = log_file.read_text(encoding="utf-8")
    blocks = re.findall(
        r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}",
        text, re.DOTALL,
    )
    for b in reversed(blocks):
        b = b.strip()
        # Strip markdown code fences if present
        b = re.sub(r"^```(?:json)?\s*", "", b)
        b = re.sub(r"\s*```$", "", b).strip()
        try:
            parsed = json.loads(b)
            if isinstance(parsed, dict) and "diagnosis" in parsed:
                return parsed
        except (json.JSONDecodeError, ValueError):
            # Try to extract JSON substring
            m = re.search(r"\{[\s\S]*\}", b)
            if m:
                try:
                    parsed = json.loads(m.group())
                    if isinstance(parsed, dict) and "diagnosis" in parsed:
                        return parsed
                except (json.JSONDecodeError, ValueError):
                    pass
            continue
    return None


def _extract_final_doctor_block(log_file: Path) -> dict | None:
    """
    Return the final diagnosis block ({diagnosis, candidates, reason,
    diagnostic_checklist}) for one episode.

    Reads doctor_memory.final_diagnosis from the .json log first. Falls back
    to regex-parsing the .txt transcript's last doctor OUTPUT block only when
    the .json's diagnostic_checklist is missing (logs written before
    doctor.finalize_doctor_memory() started persisting it) — this keeps
    pre-fix episodes scorable without needing a full resimulation.
    """
    json_path = log_file.with_suffix(".json")
    final_diag: dict | None = None
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            final_diag = data.get("doctor_memory", {}).get("final_diagnosis")
        except (json.JSONDecodeError, OSError):
            final_diag = None

    if final_diag and final_diag.get("diagnostic_checklist") is not None:
        return final_diag

    txt_path = log_file.with_suffix(".txt")
    if txt_path.exists():
        txt_block = _extract_final_doctor_block_from_txt(txt_path)
        if txt_block is not None:
            return txt_block

    return final_diag


def _gt_id(log_name: str) -> str | None:
    m = re.match(r"(D\d+)", log_name)
    return m.group(1) if m else None


def _log_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _load_final_cumulative_evidence(results_dir: Path, log_name: str) -> tuple[set[str], set[str]]:
    """
    Final-turn cumulative_confirmed/cumulative_denied from the *_result.json
    written by symptom_diagnosis.py — the algorithmic symptom-group scorer's
    evidence source. Empty sets if the result file or turns are missing.
    """
    result_path = results_dir / f"{log_name}_result.json"
    if not result_path.exists():
        return set(), set()
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set(), set()
    turns = data.get("turns", [])
    if not turns:
        return set(), set()
    last = turns[-1]
    return set(last.get("cumulative_confirmed", [])), set(last.get("cumulative_denied", []))


# ── Formatting ────────────────────────────────────────────────────────────────

def _checklist_or_reason(doc_block: dict) -> dict | str | None:
    """Return structured checklist if present, else reason string, else None."""
    cl = doc_block.get("diagnostic_checklist")
    if isinstance(cl, dict):
        return cl
    reason = str(doc_block.get("reason") or "").strip()
    return reason if reason else None


# ── Summary printing ──────────────────────────────────────────────────────────

def _print_summary(
    episode_results: list[dict],
    id2name: dict[str, str],
) -> None:
    if not episode_results:
        print("No episodes evaluated.")
        return

    pred_scores = [ep["overall_score_pred"] for ep in episode_results
                   if ep.get("overall_score_pred") is not None and not ep.get("_parse_error")]
    parse_errors = sum(1 for ep in episode_results if ep.get("_parse_error"))
    pred_missing = sum(1 for ep in episode_results if ep.get("overall_score_pred") is None)

    print("\n=== Diagnostic Evidence Sufficiency (_pred) — Summary ===")
    if pred_scores:
        print(f"  Mean score          : {np.mean(pred_scores):.4f}")
        print(f"  Median              : {np.median(pred_scores):.4f}")
        print(f"  Std dev             : {np.std(pred_scores):.4f}")
        print(f"  Min / Max           : {min(pred_scores):.4f} / {max(pred_scores):.4f}")
    print(f"  Episodes evaluated  : {len(episode_results)} "
          f"({pred_missing} with unresolved diagnosis -> None)")
    if parse_errors:
        print(f"  Judge parse errors  : {parse_errors}")

    # Per-disease breakdown, grouped by ground truth
    by_disease: dict[str, list[float]] = defaultdict(list)
    for ep in episode_results:
        if ep.get("overall_score_pred") is not None and not ep.get("_parse_error"):
            by_disease[ep["ground_truth"]].append(ep["overall_score_pred"])

    print("\n  Per ground-truth disease (mean _pred score):")
    print(f"    {'Code':<8} {'Score':>7}  {'N':>4}  Disease")
    print(f"    {'-'*50}")
    for did in sorted(by_disease, key=lambda x: int(x[1:])):
        vals  = by_disease[did]
        mean  = float(np.mean(vals))
        name  = id2name.get(did, did)
        print(f"    {did:<8} {mean:>7.4f}  {len(vals):>4}  {name}")

    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()

    _get_run_dir, _llm_chat, load_symptom_names, build_gt_criteria_text, \
        judge_checklist, compute_score, score_episode = _setup()

    run_dir     = _get_run_dir()
    results_dir = args.results if args.results else RESULTS_ROOT / run_dir
    logs_dir    = args.logs    if args.logs    else LOGS_ROOT    / run_dir

    # Load KG
    criteria   = json.loads((KG_DIR / "diagnostic_criteria.json").read_text(encoding="utf-8"))
    disorder   = json.loads((KG_DIR / "disorder.json").read_text(encoding="utf-8"))
    id2name    = {k: v["name"] for k, v in disorder.items()}
    sym_names  = load_symptom_names()

    log_files = sorted(
        logs_dir.glob("*.json"),
        key=lambda p: _log_sort_key(p.stem),
    )
    if args.style:
        log_files = [p for p in log_files if p.stem.endswith(f"_{args.style}")]
    if not log_files:
        print(f"No log files found in {logs_dir}", file=sys.stderr)
        sys.exit(1)

    out_path = results_dir / "diagnostic_reasoning_eval.json"
    code2id = _load_code2id()

    # Scalar cache: judge_checklist() only ever sees the doctor's own
    # self-reported checklist text + the GT's non-symptom requirements — it
    # never depends on the patient-side symptom extraction, so a
    # (checklist, GT) pairing seen before never needs a fresh LLM call. Keyed
    # by content hash (see score_diagnostic_reasoning._scalar_cache_key), not
    # by log_file name — this is what makes it safe to reuse even after
    # results/<log>_result.json changes (e.g. a symptom-extraction fix):
    # every episode's algorithmic symptom-group score is recomputed fresh
    # every run (it's free, no LLM), only the scalar LLM call is cached.
    scalar_cache_path = results_dir / "diagnostic_reasoning_scalar_cache.json"
    scalar_cache: dict[str, dict] = {}
    if scalar_cache_path.exists():
        try:
            scalar_cache = json.loads(scalar_cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            scalar_cache = {}

    episode_results: list[dict] = []
    skipped = 0
    pred_unresolved = 0

    for log_file in log_files:
        gt = _gt_id(log_file.stem)
        if not gt:
            continue
        if gt not in criteria:
            print(f"  [warn] {log_file.stem}: GT disease {gt} not in criteria — skipping",
                  file=sys.stderr)
            skipped += 1
            continue

        doc_block = _extract_final_doctor_block(log_file)
        if doc_block is None:
            print(f"  [warn] {log_file.stem}: no final doctor block found — skipping",
                  file=sys.stderr)
            skipped += 1
            continue

        diagnosis      = str(doc_block.get("diagnosis") or "").strip()
        checklist_data = _checklist_or_reason(doc_block)
        has_structured = isinstance(checklist_data, dict)
        final_confirmed, final_denied = _load_final_cumulative_evidence(results_dir, log_file.stem)

        predicted_id = _resolve_predicted_id(diagnosis, code2id)

        if predicted_id is None:
            pred_note = "pred=unresolved"
            pred_unresolved += 1
        else:
            pred_note = f"pred={predicted_id}"

        print(f"  Scoring {log_file.stem}  [gt={gt}]  has_checklist={has_structured} "
              f"evidence_symptoms={len(final_confirmed)}  {pred_note} ...",
              flush=True)

        # [DEACTIVATED] _gt variant (ground-truth disease's criteria).
        # result_gt = score_episode(
        #     disease_id            = gt,
        #     doctor_checklist      = checklist_data,
        #     criteria              = criteria,
        #     sym_names             = sym_names,
        #     llm_chat              = _llm_chat,
        #     cumulative_confirmed  = final_confirmed,
        #     cumulative_denied     = final_denied,
        #     scalar_cache          = scalar_cache,
        # )

        if predicted_id is None:
            result_pred = None
        else:
            result_pred = score_episode(
                disease_id            = predicted_id,
                doctor_checklist      = checklist_data,
                criteria              = criteria,
                sym_names             = sym_names,
                llm_chat              = _llm_chat,
                cumulative_confirmed  = final_confirmed,
                cumulative_denied     = final_denied,
                scalar_cache          = scalar_cache,
            )

        def _detail(result: dict | None) -> dict | None:
            if result is None:
                return None
            return {
                "scoring_method":     result.get("scoring_method", {}),
                "symptom_satisfaction_score":   result.get("symptom_satisfaction_score"),
                "symptom_group_scores":         result.get("symptom_group_scores", {}),
                "duration_score":               result.get("duration_score"),
                "functional_impairment_score":  result.get("functional_impairment_score"),
                "traumatic_stressor_score":     result.get("traumatic_stressor_score"),
                "psychosocial_stressor_score":  result.get("psychosocial_stressor_score"),
                "additional_requirements_score": result.get("additional_requirements_score"),
                "symptom_criterion_evaluations": result.get("criterion_evaluations", []),
                "judge_notes": {
                    "duration_verified":             result.get("duration_verified"),
                    "functional_impairment_verified": result.get("functional_impairment_verified"),
                    "traumatic_stressor_verified":    result.get("traumatic_stressor_verified"),
                    "psychosocial_stressor_verified": result.get("psychosocial_stressor_verified"),
                    "additional_requirements_coverage": result.get("additional_requirements_coverage"),
                    "additional_requirements_notes":    result.get("additional_requirements_notes"),
                },
            }

        pred_detail = _detail(result_pred)

        episode_results.append({
            "log_file":           log_file.stem,
            "ground_truth":       gt,
            "ground_truth_name":  id2name.get(gt, gt),
            "doctor_diagnosis":   diagnosis,
            "predicted_diagnosis_id": predicted_id,
            "predicted_diagnosis_name": id2name.get(predicted_id, predicted_id) if predicted_id else None,
            "has_structured_checklist": has_structured,
            "overall_score_pred": result_pred.get("overall_score") if result_pred is not None else None,
            "_parse_error":       result_pred.get("_parse_error", False) if result_pred is not None else False,
            # "overall_score_gt": result_gt.get("overall_score", 0.0),          # [DEACTIVATED]
            # **{f"{k}_gt": v for k, v in (_detail(result_gt) or {}).items()},  # [DEACTIVATED]
            **({f"{k}_pred": v for k, v in pred_detail.items()} if pred_detail is not None else {}),
        })

    _print_summary(episode_results, id2name)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(episode_results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved → {out_path}")

    scalar_cache_path.write_text(
        json.dumps(scalar_cache, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved scalar judge cache ({len(scalar_cache)} entries) → {scalar_cache_path}")

    if skipped:
        print(f"({skipped} episodes skipped)")
    print(f"_pred: {pred_unresolved} unresolved (doctor's diagnosis didn't map to a disease id)")


if __name__ == "__main__":
    main()
