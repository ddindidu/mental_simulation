#!/usr/bin/env python3
"""Run the fixed-profile simulation + evaluation pipeline for several doctor models.

For each doctor model:
  1. Patch config/config.json's llm.patient / llm.judge / llm.doctor.
  2. Run script/run_profile_batch.py — one simulation per profile JSON under
     --profiles-root (default: data/v1_only_manifestation), skipping any
     profile that already has both a log and a result JSON so the batch is safely
     resumable.
  3. Run the eval/*.py + reporting/*.py pipeline for that doctor's run_dir
     (mirrors app.py's _run_eval_pipeline, plus the cross-analysis reporting plots).

Patient and judge are fixed to gpt-5.4 (openai); config/config.json is restored to its
original contents when the script exits (normally or via Ctrl-C).

Usage:
  python3 script/run_all_doctors_profiles_mgk.py
  python3 script/run_all_doctors_profiles_mgk.py --limit 2 --skip-eval   # smoke test
  python3 script/run_all_doctors_profiles_mgk.py --doctors gpt-5.4
  python3 script/run_all_doctors_profiles_mgk.py --workers 6
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
PYTHON_BIN = sys.executable

PATIENT_MODEL = {"provider": "openai", "model": "gpt-5.4"}
JUDGE_MODEL = {"provider": "openai", "model": "gpt-5.4"}

DOCTOR_VARIANTS: list[dict] = [
    {"key": "gpt-5.4", "model": "gpt-5.4", "provider": "openai"},
    {"key": "gpt-5.4-mini", "model": "gpt-5.4-mini-2026-03-17", "provider": "openai"},
]

# Mirrors app.py's _run_eval_pipeline() order, plus the cross-analysis reporting
# scripts described in analysis/README.md. Each runs with no CLI args — every
# script resolves logs/results/analysis paths itself via get_run_dir(), which
# reads the just-patched config/config.json fresh (each step is its own subprocess).
EVAL_PIPELINE: list[list[str]] = [
    ["eval/symptom_diagnosis.py"],
    ["eval/evaluate_final_diagnosis.py"],
    ["eval/evaluate_turns.py"],
    ["eval/evaluate_turns_strict.py"],
    ["eval/evaluate_efficiency.py"],
    ["eval/evaluate_question.py"],
    ["eval/evaluate_diagnostic_reasoning.py"],
    ["reporting/plot_question_eval.py"],
    ["reporting/plot_efficiency_eval.py"],
    ["reporting/summarize_efficiency.py"],
    ["reporting/plot_turn_abs.py"],
    ["reporting/plot_turn_rel.py"],
    ["reporting/plot_confusion.py"],
]


def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")


def _patch_config(base_cfg: dict, doctor: dict) -> dict:
    cfg = copy.deepcopy(base_cfg)
    cfg["llm"]["patient"] = dict(PATIENT_MODEL)
    cfg["llm"]["judge"] = dict(JUDGE_MODEL)
    cfg["llm"]["doctor"] = {"provider": doctor["provider"], "model": doctor["model"]}
    return cfg


def _run(cmd: list[str], label: str) -> bool:
    print(f"\n{'-'*70}\n[orchestrator] {label}: {' '.join(cmd)}\n{'-'*70}", flush=True)
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    dt = time.time() - t0
    ok = proc.returncode == 0
    print(f"[orchestrator] {label} {'OK' if ok else f'FAILED (rc={proc.returncode})'} in {dt:.1f}s", flush=True)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--profiles-root", type=Path,
        default=PROJECT_ROOT / "data" / "v1_only_manifestation",
    )
    parser.add_argument("--doctors", nargs="*", default=None,
                         help="Subset of doctor keys to run (default: all). "
                              f"Choices: {[d['key'] for d in DOCTOR_VARIANTS]}")
    parser.add_argument("--workers", type=int, default=4, help="Parallel simulation processes per doctor.")
    parser.add_argument("--limit", type=int, default=None, help="Only the first N profiles per doctor (smoke test).")
    parser.add_argument("--skip-eval", action="store_true", help="Skip the eval/reporting pipeline, simulate only.")
    args = parser.parse_args()

    variants = DOCTOR_VARIANTS
    if args.doctors:
        chosen = set(args.doctors)
        variants = [d for d in DOCTOR_VARIANTS if d["key"] in chosen]
        missing = chosen - {d["key"] for d in variants}
        if missing:
            print(f"[orchestrator] Unknown doctor key(s): {missing}", file=sys.stderr)
            return 1

    base_cfg = _load_config()
    summary: list[dict] = []

    try:
        for i, doctor in enumerate(variants, 1):
            print(
                f"\n{'='*70}\n[orchestrator] Doctor {i}/{len(variants)}: {doctor['key']} "
                f"({doctor['model']}, provider={doctor['provider']})\n{'='*70}",
                flush=True,
            )
            _save_config(_patch_config(base_cfg, doctor))

            sim_cmd = [
                PYTHON_BIN, "script/run_profile_batch.py",
                "--profiles-root", str(args.profiles_root),
                "--workers", str(args.workers),
            ]
            if args.limit:
                sim_cmd += ["--limit", str(args.limit)]
            sim_ok = _run(sim_cmd, f"simulate[{doctor['key']}]")

            eval_results: list[tuple[str, bool]] = []
            if not args.skip_eval:
                for step in EVAL_PIPELINE:
                    ok = _run([PYTHON_BIN, *step], f"eval[{doctor['key']}]:{step[0]}")
                    eval_results.append((step[0], ok))

            summary.append({
                "doctor": doctor["key"],
                "simulate_ok": sim_ok,
                "eval_results": eval_results,
            })

    except KeyboardInterrupt:
        print("\n[orchestrator] Interrupted by user.", flush=True)
    finally:
        _save_config(base_cfg)
        print("[orchestrator] config/config.json restored to original.", flush=True)

    print(f"\n{'='*70}\n[orchestrator] Summary\n{'='*70}", flush=True)
    for s in summary:
        print(f"  {s['doctor']:<24} simulate={'OK' if s['simulate_ok'] else 'FAIL'}", flush=True)
        for name, ok in s["eval_results"]:
            print(f"      {'OK  ' if ok else 'FAIL'}  {name}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
