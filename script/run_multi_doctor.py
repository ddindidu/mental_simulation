#!/usr/bin/env python3
"""
Multi-doctor batch evaluation orchestrator.

For each doctor configuration:
  1. Patch config/config.json with the new doctor model + provider
  2. Start Flask server (app.py)
  3. Wait until /api/status reports loaded
  4. POST /api/batch_eval  (10 runs per disorder, all diseases)
  5. Poll /api/batch_status until running=false
  6. Stop Flask

Patient and judge are fixed:
  patient : gemini-3.5-flash  (provider: gemini)
  judge   : gemini-3.5-flash  (provider: gemini)

Doctor variants:
  1. gemini-3.1-flash-lite  (provider: gemini)
  2. gemini-3.5-flash        (provider: gemini)
  3. gpt-5.4-mini-2026-03-17 (provider: openai)
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

# ── Constants ─────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH  = PROJECT_ROOT / "config" / "config.json"
SERVER_PORT  = 5001
BASE_URL     = f"http://localhost:{SERVER_PORT}"
RUNS_PER_DISORDER = 10
DIFFICULTY        = "medium"

# Python interpreter for the 'mental' conda environment (has openai + google-generativeai)
PYTHON_BIN = "/home/jsshin/anaconda3/envs/mental/bin/python3"

DOCTOR_VARIANTS: list[dict] = [
    {"model": "gemini-3.5-flash",               "provider": "gemini"},
    {"model": "gpt-5.4-mini-2026-03-17",        "provider": "openai"},
    {"model": "qwen/qwen3-235b-a22b-2507",      "provider": "openrouter"},
]


# ── Config helpers ─────────────────────────────────────────────────────────────

def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")


def _patch_doctor(cfg: dict, model: str, provider: str) -> dict:
    cfg["llm"]["doctor"] = {"provider": provider, "model": model}
    return cfg


# ── Server lifecycle ───────────────────────────────────────────────────────────

def _start_server() -> subprocess.Popen:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        [PYTHON_BIN, str(PROJECT_ROOT / "app.py")],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    return proc


def _wait_for_server(timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/api/status", timeout=5)
            if r.ok:
                data = r.json()
                if data.get("loaded"):
                    return True
                if data.get("error"):
                    print(f"[orchestrator] Server error: {data['error']}", flush=True)
                    return False
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(2)
    return False


def _stop_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    print("[orchestrator] Server stopped.", flush=True)


# ── Batch helpers ──────────────────────────────────────────────────────────────

def _start_batch() -> bool:
    payload = {
        "runs_per_disorder": RUNS_PER_DISORDER,
        "difficulty": DIFFICULTY,
    }
    r = requests.post(f"{BASE_URL}/api/batch_eval", json=payload, timeout=30)
    if not r.ok:
        print(f"[orchestrator] batch_eval failed: {r.status_code} {r.text}", flush=True)
        return False
    data = r.json()
    if not data.get("ok"):
        print(f"[orchestrator] batch_eval error: {data.get('error')}", flush=True)
        return False
    print(
        f"[orchestrator] Batch started: {data['disorders']} diseases × "
        f"{data['runs_per_disorder']} runs → {data['run_dir']}",
        flush=True,
    )
    return True


def _poll_batch(interval: int = 30) -> dict | None:
    """Poll until batch finishes. Returns final status dict or None on server failure."""
    while True:
        try:
            r = requests.get(f"{BASE_URL}/api/batch_status", timeout=10)
            if not r.ok:
                print(f"[orchestrator] status poll error {r.status_code}", flush=True)
                time.sleep(interval)
                continue
            s = r.json()
            done = s.get("done", 0)
            total = s.get("total", 0)
            current = s.get("current", "")
            print(
                f"\r[orchestrator] {done}/{total}  {current}                    ",
                end="",
                flush=True,
            )
            if not s.get("running", True) and s.get("current") in ("Done", ""):
                print()
                return s
        except requests.exceptions.ConnectionError:
            print("\n[orchestrator] Lost connection to server.", flush=True)
            return None
        time.sleep(interval)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    base_cfg = _load_config()
    results_summary: list[dict] = []

    for i, variant in enumerate(DOCTOR_VARIANTS, 1):
        model    = variant["model"]
        provider = variant["provider"]
        print(
            f"\n{'='*70}\n"
            f"[orchestrator] Run {i}/{len(DOCTOR_VARIANTS)}: "
            f"doctor = {model}  (provider={provider})\n"
            f"{'='*70}",
            flush=True,
        )

        # 1. Patch config
        cfg = _patch_doctor(dict(base_cfg), model, provider)
        # Deep-copy llm section to avoid reference aliasing
        import copy
        cfg = copy.deepcopy(base_cfg)
        cfg["llm"]["doctor"] = {"provider": provider, "model": model}
        _save_config(cfg)
        print(f"[orchestrator] config/config.json updated → doctor: {model}", flush=True)

        # 2. Start Flask
        proc = _start_server()
        print(f"[orchestrator] Flask started (pid={proc.pid})", flush=True)

        try:
            # 3. Wait for model load
            print("[orchestrator] Waiting for server to be ready...", flush=True)
            ready = _wait_for_server(timeout=180)
            if not ready:
                print("[orchestrator] Server did not become ready — skipping.", flush=True)
                _stop_server(proc)
                results_summary.append({"model": model, "status": "server_not_ready"})
                continue

            # 4. Trigger batch
            started = _start_batch()
            if not started:
                _stop_server(proc)
                results_summary.append({"model": model, "status": "batch_start_failed"})
                continue

            # 5. Poll to completion
            final_status = _poll_batch(interval=30)
            if final_status is None:
                results_summary.append({"model": model, "status": "connection_lost"})
            else:
                n_results = final_status.get("results_count", 0)
                fmt_rate  = final_status.get("format_compliance_rate", "N/A")
                print(
                    f"[orchestrator] Batch done: {n_results} diseases, "
                    f"format compliance={fmt_rate}",
                    flush=True,
                )
                results_summary.append({
                    "model": model,
                    "status": "done",
                    "results_count": n_results,
                    "format_compliance_rate": fmt_rate,
                })

        except KeyboardInterrupt:
            print("\n[orchestrator] Interrupted by user.", flush=True)
            _stop_server(proc)
            # Restore original config
            _save_config(base_cfg)
            sys.exit(1)
        finally:
            _stop_server(proc)
            # Brief pause to ensure port is freed
            time.sleep(5)

    # Restore original config (last doctor model stays, which is fine, but restore base)
    _save_config(base_cfg)
    print("\n" + "="*70, flush=True)
    print("[orchestrator] All runs complete. Summary:", flush=True)
    for r in results_summary:
        status = r["status"]
        extra = ""
        if status == "done":
            extra = f"  diseases={r.get('results_count')}  fmt={r.get('format_compliance_rate')}"
        print(f"  {r['model']:<35} → {status}{extra}", flush=True)
    print("="*70, flush=True)


if __name__ == "__main__":
    main()
