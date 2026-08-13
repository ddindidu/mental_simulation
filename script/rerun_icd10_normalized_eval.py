#!/usr/bin/env python3
"""One-off re-run of the eval/reporting steps affected by the icd10_accepted_codes
normalization, for all 6 doctors. Skips simulation (no new LLM conversations
needed) and skips evaluate_diagnostic_reasoning.py (unaffected — it scores
against ground-truth criteria unconditionally, never matches the doctor's
stated code). evaluate_final_diagnosis.py / evaluate_turns.py / evaluate_efficiency.py
were already re-run separately (fast, no LLM calls) — this covers the
remaining LLM-judge-dependent steps plus the reporting plots.
"""
import copy
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
PYTHON_BIN = sys.executable

DOCTOR_VARIANTS = [
    {"key": "gemini-3.5-flash", "model": "gemini-3.5-flash", "provider": "gemini"},
    {"key": "gemini-3.1-flash-lite", "model": "gemini-3.1-flash-lite", "provider": "gemini"},
    {"key": "gpt-5.4", "model": "gpt-5.4", "provider": "openai"},
    {"key": "gpt-5.4-mini", "model": "gpt-5.4-mini-2026-03-17", "provider": "openai"},
    {"key": "llama-3.3-70b-instruct", "model": "meta-llama/llama-3.3-70b-instruct", "provider": "openrouter"},
    {"key": "qwen3-235b", "model": "qwen/qwen3-235b-a22b-2507", "provider": "openrouter"},
]

STEPS = [
    "eval/evaluate_turns_strict.py",
    "eval/evaluate_question.py",
    "reporting/plot_question_eval.py",
    "reporting/plot_efficiency_eval.py",
    "reporting/summarize_efficiency.py",
    "reporting/plot_turn_abs.py",
    "reporting/plot_turn_rel.py",
    "reporting/plot_confusion.py",
]


def _run(cmd, label):
    print(f"\n{'-'*70}\n[rerun] {label}: {' '.join(cmd)}\n{'-'*70}", flush=True)
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    dt = time.time() - t0
    ok = proc.returncode == 0
    print(f"[rerun] {label} {'OK' if ok else f'FAILED (rc={proc.returncode})'} in {dt:.1f}s", flush=True)
    return ok


def main():
    base_cfg = json.loads(CONFIG_PATH.read_text())
    try:
        for i, doctor in enumerate(DOCTOR_VARIANTS, 1):
            print(f"\n{'='*70}\n[rerun] Doctor {i}/{len(DOCTOR_VARIANTS)}: {doctor['key']}\n{'='*70}", flush=True)
            cfg = copy.deepcopy(base_cfg)
            cfg["llm"]["patient"] = {"provider": "gemini", "model": "gemini-3.5-flash"}
            cfg["llm"]["judge"] = {"provider": "gemini", "model": "gemini-3.5-flash"}
            cfg["llm"]["doctor"] = {"provider": doctor["provider"], "model": doctor["model"]}
            CONFIG_PATH.write_text(json.dumps(cfg, indent=4, ensure_ascii=False))

            for step in STEPS:
                _run([PYTHON_BIN, step], f"{doctor['key']}:{step}")
    finally:
        CONFIG_PATH.write_text(json.dumps(base_cfg, indent=4, ensure_ascii=False))
        print("[rerun] config.json restored to original.", flush=True)


if __name__ == "__main__":
    main()
