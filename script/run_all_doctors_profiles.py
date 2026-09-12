#!/usr/bin/env python3
"""Run the fixed-profile simulation + evaluation pipeline for several doctor models.

For each doctor model:
  1. Patch --config's llm.patient / llm.judge / llm.doctor.
  2. Run script/run_profile_batch.py — one simulation per profile JSON under
     --profiles-root (default: data/v2_final_profiles) and one per conversation
     style, skipping any run that already has both a log and a result JSON so the
     batch is safely resumable.
  3. Run the eval/*.py + reporting/*.py pipeline for that doctor's run_dir
     (mirrors app.py's _run_eval_pipeline, plus the cross-analysis reporting plots).

Every model, profile set and conversation style is an argument, so one script covers
whatever combination an experiment needs; the patched config file is restored to its
original contents when the script exits (normally or via Ctrl-C).

Running two invocations at once (e.g. to compare patient/judge model pairs)
is only safe if each uses a DIFFERENT --config path — every downstream
subprocess (run_profile_batch.py, its ProcessPoolExecutor(spawn) workers, and
every eval/*.py + reporting/*.py step) resolves its config via the
MS_CONFIG_PATH env var this script sets for its own process tree, so two
invocations pointed at two different --config files never touch the same
file and can genuinely run in parallel. Two invocations sharing the default
config/config.json (or the same --config path) WILL race and corrupt each
other's runs — never do that.

Usage:
  python3 script/run_all_doctors_profiles.py
  python3 script/run_all_doctors_profiles.py --limit 2 --skip-eval   # smoke test
  python3 script/run_all_doctors_profiles.py --doctors gemini-3.5-flash qwen3-235b
  python3 script/run_all_doctors_profiles.py --doctors gpt-5.5@openai   # not in the list
  python3 script/run_all_doctors_profiles.py --patient-model gemini-3.5-flash --patient-provider gemini
  python3 script/run_all_doctors_profiles.py --styles plain verbose reserved tangent pleasing
  python3 script/run_all_doctors_profiles.py --config config/config_mgk.json

  # Two genuinely parallel runs (distinct --config each; auto-bootstrapped
  # from config/config.json on first use, then patched/restored independently):
  python3 script/run_all_doctors_profiles.py --config config/config.run_a.json --patient-model gpt-5.5 --patient-provider openai --judge-model gpt-5.5 --judge-provider openai &
  python3 script/run_all_doctors_profiles.py --config config/config.run_b.json --patient-model gemini-3.1-pro-preview --patient-provider gemini --judge-model gemini-3.1-pro-preview --judge-provider gemini &
  wait
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
PYTHON_BIN = sys.executable

DEFAULT_PATIENT = {"provider": "openai", "model": "gpt-5.5"}
DEFAULT_JUDGE = {"provider": "openai", "model": "gpt-5.5"}
CONVERSATION_STYLES = ["plain", "verbose", "reserved", "tangent", "pleasing"]

DOCTOR_VARIANTS: list[dict] = [
    {"key": "gemini-3.8-flash", "model": "gemini-3.8-flash", "provider": "gemini"},
    {"key": "gemini-3.1-flash-lite", "model": "gemini-3.1-flash-lite", "provider": "gemini"},
    {"key": "gpt-5.4", "model": "gpt-5.4", "provider": "openai"},
    {"key": "gpt-5.4-mini", "model": "gpt-5.4-mini-2026-03-17", "provider": "openai"},
    {"key": "claude-sonnet-5", "model": "anthropic/claude-sonnet-5", "provider": "openrouter"},
    {"key": "claude-haiku-4.5", "model": "anthropic/claude-haiku-4.5", "provider": "openrouter"},
    {"key": "llama-3.3-70b-instruct", "model": "meta-llama/llama-3.3-70b-instruct", "provider": "vllm"},
    {"key": "qwen3-235b", "model": "qwen/qwen3-235b-a22b-2507", "provider": "vllm"},
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


def _load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_config(path: Path, cfg: dict) -> None:
    path.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")


def _patch_config(base_cfg: dict, doctor: dict, patient: dict, judge: dict) -> dict:
    cfg = copy.deepcopy(base_cfg)
    cfg["llm"]["patient"] = dict(patient)
    cfg["llm"]["judge"] = dict(judge)
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
        default=PROJECT_ROOT / "data" / "v2_final_profiles",
        help="Root directory to recursively glob *.json profiles from.",
    )
    parser.add_argument(
        "--styles", nargs="*", default=CONVERSATION_STYLES,
        help=f"Conversation styles to run each profile under (default: all {len(CONVERSATION_STYLES)}). "
             "Every style of one profile runs before the next profile.",
    )
    parser.add_argument(
        "--doctors", nargs="*", default=None,
        help="Doctor models to run. Either a key from the built-in list "
             f"({[d['key'] for d in DOCTOR_VARIANTS]}) or 'model@provider' for one that is not.",
    )
    parser.add_argument("--patient-model", default=DEFAULT_PATIENT["model"], help="Patient LLM.")
    parser.add_argument("--patient-provider", default=DEFAULT_PATIENT["provider"])
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE["model"], help="Judge LLM.")
    parser.add_argument("--judge-provider", default=DEFAULT_JUDGE["provider"])
    parser.add_argument(
        "--config", type=Path, default=CONFIG_PATH,
        help=f"Config file to patch and restore (default: {CONFIG_PATH.name}).",
    )
    parser.add_argument("--workers", type=int, default=4, help="Parallel simulation processes per doctor.")
    parser.add_argument("--limit", type=int, default=None, help="Only the first N profiles per doctor (smoke test).")
    parser.add_argument("--skip-eval", action="store_true", help="Skip the eval/reporting pipeline, simulate only.")
    args = parser.parse_args()

    known = {d["key"]: d for d in DOCTOR_VARIANTS}
    variants = DOCTOR_VARIANTS
    if args.doctors:
        variants = []
        for name in args.doctors:
            if name in known:
                variants.append(known[name])
            elif "@" in name:
                model, _, provider = name.partition("@")
                variants.append({"key": model, "model": model, "provider": provider})
            else:
                print(
                    f"[orchestrator] Unknown doctor {name!r}. Use a key from "
                    f"{list(known)} or 'model@provider'.", file=sys.stderr,
                )
                return 1

    patient_llm = {"provider": args.patient_provider, "model": args.patient_model}
    judge_llm = {"provider": args.judge_provider, "model": args.judge_model}
    config_path = args.config.resolve()

    if not config_path.exists():
        # Bootstrap a fresh isolated config from the real default so a custom
        # --config path can be used without pre-creating the file by hand.
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    # Propagate this run's config path to every subprocess this process
    # spawns (run_profile_batch.py, its ProcessPoolExecutor(spawn) workers,
    # and each eval/*.py + reporting/*.py step) via inherited os.environ —
    # see utils/config.py's MS_CONFIG_PATH handling. This is what makes two
    # invocations with two different --config paths safe to run at once.
    os.environ["MS_CONFIG_PATH"] = str(config_path)

    print(
        f"[orchestrator] config={config_path} | patient={args.patient_model} "
        f"judge={args.judge_model} | styles={args.styles} | profiles={args.profiles_root}",
        flush=True,
    )

    base_cfg = _load_config(config_path)
    summary: list[dict] = []

    try:
        for i, doctor in enumerate(variants, 1):
            print(
                f"\n{'='*70}\n[orchestrator] Doctor {i}/{len(variants)}: {doctor['key']} "
                f"({doctor['model']}, provider={doctor['provider']})\n{'='*70}",
                flush=True,
            )
            _save_config(config_path, _patch_config(base_cfg, doctor, patient_llm, judge_llm))

            sim_cmd = [
                PYTHON_BIN, "script/run_profile_batch.py",
                "--profiles-root", str(args.profiles_root),
                "--workers", str(args.workers),
            ]
            if args.styles:
                sim_cmd += ["--styles", *args.styles]
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
        _save_config(config_path, base_cfg)
        print(f"[orchestrator] {config_path.name} restored to original.", flush=True)

    print(f"\n{'='*70}\n[orchestrator] Summary\n{'='*70}", flush=True)
    for s in summary:
        print(f"  {s['doctor']:<24} simulate={'OK' if s['simulate_ok'] else 'FAIL'}", flush=True)
        for name, ok in s["eval_results"]:
            print(f"      {'OK  ' if ok else 'FAIL'}  {name}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
