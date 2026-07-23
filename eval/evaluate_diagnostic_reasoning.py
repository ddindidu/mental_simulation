#!/usr/bin/env python3
"""
Diagnostic Reasoning Quality Evaluation — spec §4.6

For each episode, extracts the doctor's final diagnostic_checklist (or falls
back to the free-text `reason` field for older logs), then uses an LLM judge
to evaluate coverage of the ground-truth disease's required criteria.

Outputs:
  results/<run_dir>/diagnostic_reasoning_eval.json
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
KG_DIR   = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=Path, default=None,
                   help="Results dir (default: results/<run_dir>)")
    p.add_argument("--logs",    type=Path, default=None,
                   help="Logs dir (default: logs/<run_dir>)")
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

def _extract_final_doctor_block(log_file: Path) -> dict | None:
    """Return parsed JSON from the last doctor OUTPUT block that contains 'diagnosis'."""
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


def _gt_id(log_name: str) -> str | None:
    m = re.match(r"(D\d+)", log_name)
    return m.group(1) if m else None


def _log_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


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

    all_scores = [ep["overall_score"] for ep in episode_results if not ep.get("_parse_error")]
    parse_errors = sum(1 for ep in episode_results if ep.get("_parse_error"))

    print("\n=== Diagnostic Reasoning Quality — Summary ===")
    if all_scores:
        print(f"  Mean overall score  : {np.mean(all_scores):.4f}")
        print(f"  Median              : {np.median(all_scores):.4f}")
        print(f"  Std dev             : {np.std(all_scores):.4f}")
        print(f"  Min / Max           : {min(all_scores):.4f} / {max(all_scores):.4f}")
    print(f"  Episodes evaluated  : {len(episode_results)}")
    if parse_errors:
        print(f"  Judge parse errors  : {parse_errors}")

    # Per-disease breakdown
    by_disease: dict[str, list[float]] = defaultdict(list)
    for ep in episode_results:
        if not ep.get("_parse_error"):
            by_disease[ep["ground_truth"]].append(ep["overall_score"])

    print("\n  Per-disease (mean score):")
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
    results_dir = args.results if args.results else BASE_DIR / "results" / run_dir
    logs_dir    = args.logs    if args.logs    else BASE_DIR / "logs"    / run_dir

    # Load KG
    criteria   = json.loads((KG_DIR / "diagnostic_criteria.json").read_text(encoding="utf-8"))
    disorder   = json.loads((KG_DIR / "disorder.json").read_text(encoding="utf-8"))
    id2name    = {k: v["name"] for k, v in disorder.items()}
    sym_names  = load_symptom_names()

    log_files = sorted(
        logs_dir.glob("*.txt"),
        key=lambda p: _log_sort_key(p.stem),
    )
    if not log_files:
        print(f"No log files found in {logs_dir}", file=sys.stderr)
        sys.exit(1)

    episode_results: list[dict] = []
    skipped = 0

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

        print(f"  Scoring {log_file.stem}  [{gt}]  has_checklist={has_structured} ...",
              flush=True)

        result = score_episode(
            disease_id       = gt,
            doctor_checklist = checklist_data,
            criteria         = criteria,
            sym_names        = sym_names,
            llm_chat         = _llm_chat,
        )

        episode_results.append({
            "log_file":           log_file.stem,
            "ground_truth":       gt,
            "ground_truth_name":  id2name.get(gt, gt),
            "doctor_diagnosis":   diagnosis,
            "has_structured_checklist": has_structured,
            "overall_score":      result.get("overall_score", 0.0),
            "symptom_satisfaction_score":   result.get("symptom_satisfaction_score"),
            "symptom_group_scores":         result.get("symptom_group_scores", {}),
            "duration_score":               result.get("duration_score"),
            "functional_impairment_score":  result.get("functional_impairment_score"),
            "traumatic_stressor_score":     result.get("traumatic_stressor_score"),
            "psychosocial_stressor_score":  result.get("psychosocial_stressor_score"),
            "additional_requirements_score": result.get("additional_requirements_score"),
            "_parse_error":       result.get("_parse_error", False),
            "judge_criterion_evaluations": result.get("criterion_evaluations", []),
            "judge_notes": {
                "duration_verified":             result.get("duration_verified"),
                "functional_impairment_verified": result.get("functional_impairment_verified"),
                "traumatic_stressor_verified":    result.get("traumatic_stressor_verified"),
                "psychosocial_stressor_verified": result.get("psychosocial_stressor_verified"),
                "additional_requirements_coverage": result.get("additional_requirements_coverage"),
                "additional_requirements_notes":    result.get("additional_requirements_notes"),
            },
        })

    _print_summary(episode_results, id2name)

    out_path = results_dir / "diagnostic_reasoning_eval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(episode_results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved → {out_path}")
    if skipped:
        print(f"({skipped} episodes skipped)")


if __name__ == "__main__":
    main()
