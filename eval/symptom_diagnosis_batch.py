#!/usr/bin/env python3
"""
Batch (async) version of symptom_diagnosis.py's judge calls.

Same output as symptom_diagnosis.py (results/<run_dir>/<log>_result.json,
same schema) but submits every turn's symptom-extraction prompt as ONE batch
job instead of one blocking call per turn — see utils/batch_llm.py's
module docstring for why this is safe (no turn-to-turn prompt dependency).

Two-phase, since a batch job is async (minutes to 24h):

  python eval/symptom_diagnosis_batch.py --submit [--style plain]
      Builds every turn's prompt across all (unprocessed) logs, submits as
      a batch job, saves job state to results/<run_dir>/symptom_diagnosis_batch_job.json.

  python eval/symptom_diagnosis_batch.py --collect
      Polls the saved job. If not done yet, reports status and exits. If
      done, parses responses and writes the *_result.json files exactly as
      the synchronous script would (same cumulative-merge / candidate-set
      logic), then removes the job-state file.

Only OpenAI and Gemini judges support batching (see utils/batch_llm.py).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from eval.symptom_diagnosis import (
    load_all_symptoms,
    load_diagnostic_criteria,
    extract_patient_turns,
    extract_doctor_questions,
    build_extraction_prompt,
    parse_extraction_response,
    _EXTRACTION_SYSTEM,
    merge_symptom_status,
    compute_candidate_set,
    match_diseases,
    _needs_migration,
    _migrate_candidate_sets,
)
from utils.llm import get_run_dir as _get_run_dir, get_judge_model_name, get_judge_provider
from utils.paths import LOGS_ROOT, RESULTS_ROOT
from utils import batch_llm

_RUN_DIR    = _get_run_dir()
LOGS_DIR    = LOGS_ROOT    / _RUN_DIR
OUTPUT_DIR  = RESULTS_ROOT / _RUN_DIR
JOB_PATH    = OUTPUT_DIR / "symptom_diagnosis_batch_job.json"


def _api_key_for(provider: str) -> str | None:
    import os
    if provider == "gemini":
        return os.environ.get("GEMINI_API_KEY")
    return None  # openai client reads OPENAI_API_KEY itself


def _custom_id(log_stem: str, turn_idx: int) -> str:
    return f"{log_stem}::{turn_idx}"


def cmd_submit(style: str | None) -> None:
    all_symptoms = load_all_symptoms()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log_files = sorted(LOGS_DIR.glob("*.json"))
    if style:
        log_files = [p for p in log_files if p.stem.endswith(f"_{style}")]

    pending = [p for p in log_files if not (OUTPUT_DIR / f"{p.stem}_result.json").exists()]
    print(f"Found {len(log_files)} log files"
          + (f" (style={style})" if style else "")
          + f"; {len(pending)} not yet scored → building batch requests...")

    requests: list[dict] = []
    for log_file in pending:
        turns_raw = extract_patient_turns(log_file)
        questions = extract_doctor_questions(log_file)
        for turn_idx, pt in enumerate(turns_raw):
            question  = questions[turn_idx] if turn_idx < len(questions) else ""
            alignment = pt.get("alignment")
            prompt = build_extraction_prompt(question, alignment, pt["response"], all_symptoms)
            requests.append({
                "custom_id": _custom_id(log_file.stem, turn_idx),
                "system": _EXTRACTION_SYSTEM,
                "user": prompt,
                "max_tokens": 8192,
            })

    if not requests:
        print("Nothing to submit (all logs already scored, or none found).")
        return

    provider = get_judge_provider()
    model    = get_judge_model_name()
    print(f"Submitting {len(requests)} requests as a batch job (provider={provider}, model={model})...")
    job = batch_llm.submit_batch(
        requests, provider=provider, model=model, api_key=_api_key_for(provider),
    )
    job["style"] = style
    JOB_PATH.write_text(json.dumps(job, indent=2), encoding="utf-8")
    print(f"Submitted {len(job['chunks'])} chunk(s) → job state saved to {JOB_PATH}")
    print("Run --collect later (after the job finishes) to write results.")


def _score_log(log_file: Path, all_symptoms: dict, diagnostic_criteria: dict,
                responses_by_turn: dict[int, tuple[list[str], list[str], dict]]) -> dict:
    """Same cumulative-merge / candidate-set logic as symptom_diagnosis.process_log(),
    but consuming already-fetched (confirmed, denied, reasoning) per turn instead of
    calling the judge inline."""
    name = log_file.stem
    turns_raw = extract_patient_turns(log_file)
    questions = extract_doctor_questions(log_file)

    cumulative_confirmed: set[str] = set()
    cumulative_denied: set[str]    = set()
    label_conflict_log: list[dict] = []
    turns = []

    for turn_idx, pt in enumerate(turns_raw):
        turn_num = turn_idx + 1
        response  = pt["response"]
        question  = questions[turn_idx] if turn_idx < len(questions) else ""
        alignment = pt.get("alignment")
        targeted_symptom_id = (
            alignment.get("key") if alignment and alignment.get("matched") else None
        )

        new_confirmed, new_denied, reasoning = responses_by_turn.get(turn_idx, ([], [], {}))

        merge_symptom_status(
            cumulative_confirmed, cumulative_denied,
            new_confirmed, new_denied,
            label_conflict_log, turn_num,
        )

        high_likely, moderate_likely, low_likely, excluded = compute_candidate_set(
            cumulative_confirmed, cumulative_denied, diagnostic_criteria
        )
        matches  = match_diseases(cumulative_confirmed, cumulative_denied, diagnostic_criteria)
        fully_met   = [d for d in matches if d["all_required_met"]]
        top_partial = [d for d in matches if not d["all_required_met"]
                       and not d["in_excluded"]
                       and d["total_symptom_matches"] > 0]

        turns.append({
            "turn":                   turn_num,
            "doctor_question":        question,
            "targeted_symptom":       targeted_symptom_id,
            "patient_response":       response,
            "new_confirmed_symptoms": new_confirmed,
            "new_denied_symptoms":    new_denied,
            "cumulative_confirmed":   sorted(cumulative_confirmed),
            "cumulative_denied":      sorted(cumulative_denied),
            "symptom_reasoning":      reasoning,
            "candidate_set": {
                "high_likely":    sorted(high_likely),
                "moderate_likely": sorted(moderate_likely),
                "low_likely":     sorted(low_likely),
                "excluded":       sorted(excluded),
            },
            "disease_matches": {
                "fully_met":   fully_met,
                "top_partial": top_partial,
            },
        })

    return {
        "log_file":           name,
        "total_turns":        len(turns_raw),
        "label_conflict_log": label_conflict_log,
        "turns":              turns,
    }


def cmd_collect() -> None:
    if not JOB_PATH.exists():
        print(f"No pending batch job at {JOB_PATH} — run --submit first.", file=sys.stderr)
        sys.exit(1)

    job = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    provider = job["provider"]
    status = batch_llm.poll_batch(job, api_key=_api_key_for(provider))
    print(f"Batch status: {status} ({len(job['chunks'])} chunk(s))")
    if status == "in_progress":
        print("Not done yet — run --collect again later.")
        return

    results, errors = batch_llm.collect_batch(job, api_key=_api_key_for(provider))
    print(f"Collected {len(results)} response(s), {len(errors)} error(s).")
    if errors:
        for cid, msg in list(errors.items())[:10]:
            print(f"  [error] {cid}: {msg[:200]}", file=sys.stderr)

    all_symptoms = load_all_symptoms()
    diagnostic_criteria = load_diagnostic_criteria()

    # Group parsed responses by log_stem -> {turn_idx: (confirmed, denied, reasoning)}
    by_log: dict[str, dict[int, tuple[list[str], list[str], dict]]] = {}
    for cid, raw in results.items():
        log_stem, turn_str = cid.rsplit("::", 1)
        turn_idx = int(turn_str)
        confirmed, denied, reasoning = parse_extraction_response(raw, all_symptoms)
        by_log.setdefault(log_stem, {})[turn_idx] = (confirmed, denied, reasoning)
    for cid in errors:
        log_stem, turn_str = cid.rsplit("::", 1)
        by_log.setdefault(log_stem, {}).setdefault(int(turn_str), ([], [], {}))

    written = 0
    for log_stem, responses_by_turn in by_log.items():
        log_file = LOGS_DIR / f"{log_stem}.json"
        if not log_file.exists():
            print(f"  [warn] log missing for {log_stem}, skipping", file=sys.stderr)
            continue
        result = _score_log(log_file, all_symptoms, diagnostic_criteria, responses_by_turn)
        out_path = OUTPUT_DIR / f"{log_stem}_result.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        written += 1

    print(f"Wrote {written} result file(s) → {OUTPUT_DIR}/")
    JOB_PATH.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--submit", action="store_true", help="Build and submit the batch job.")
    parser.add_argument("--collect", action="store_true", help="Poll the submitted job and write results if done.")
    parser.add_argument("--style", default=None, help="--submit only: restrict to logs ending in _<style>.")
    args = parser.parse_args()

    if args.submit == args.collect:
        parser.error("Pass exactly one of --submit or --collect.")

    if args.submit:
        cmd_submit(args.style)
    else:
        cmd_collect()


if __name__ == "__main__":
    main()
