#!/usr/bin/env python3
"""Run one simulation per profile JSON under a profiles root, using whichever
patient/judge/doctor models config.json currently specifies.

Intended to be invoked once per doctor model by script/run_all_doctors_profiles.py
(which patches config.json's llm.doctor before each call), but can be run directly
against whatever config.json already has.

Parallelizes across profiles with a spawn-context ProcessPoolExecutor — see
profile_batch_worker.py for why per-profile isolation is required.

Usage:
  python3 script/run_profile_batch.py
  python3 script/run_profile_batch.py --profiles-root data/profiles/add_requirements/low --workers 4
  python3 script/run_profile_batch.py --limit 2   # smoke test
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--profiles-root", type=Path,
        default=PROJECT_ROOT / "data" / "profiles" / "add_requirements" / "low",
        help="Root directory to recursively glob *.json profiles from.",
    )
    parser.add_argument("--workers", type=int, default=4, help="Parallel simulation processes.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N profiles (smoke test).")
    args = parser.parse_args()

    from utils.config import CONFIG
    from utils.llm import (
        get_run_dir,
        get_doctor_model_name,
        get_patient_model_name,
        get_judge_model_name,
    )
    from profile_batch_worker import run_profile

    run_dir = get_run_dir()
    logs_dir = PROJECT_ROOT / "logs" / run_dir
    results_dir = PROJECT_ROOT / "results" / run_dir
    logs_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    max_turns = int(CONFIG["simulation"]["max_turns"])

    profiles = sorted(args.profiles_root.rglob("*.json"))
    if not profiles:
        print(f"[run_profile_batch] No profile JSON files found under {args.profiles_root}", file=sys.stderr)
        return 1
    if args.limit:
        profiles = profiles[: args.limit]

    print(
        f"[run_profile_batch] patient={get_patient_model_name()} "
        f"judge={get_judge_model_name()} doctor={get_doctor_model_name()} "
        f"run_dir={run_dir} profiles={len(profiles)} workers={args.workers} max_turns={max_turns}",
        flush=True,
    )

    ctx = mp.get_context("spawn")
    done = 0
    n_skipped = 0
    n_ok = 0
    errors: list[str] = []
    with ProcessPoolExecutor(max_workers=max(1, args.workers), mp_context=ctx) as executor:
        futures = {
            executor.submit(run_profile, str(p), str(logs_dir), str(results_dir), max_turns): p
            for p in profiles
        }
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"profile_id": p.stem, "status": "error", "error": str(e)}
            done += 1
            status = res.get("status")
            marker = {
                "done": "OK", "skipped": "SKIP", "error": "ERR", "sim_ok_sd_failed": "SD_ERR",
            }.get(status, "?")
            if status == "skipped":
                n_skipped += 1
            elif status == "done":
                n_ok += 1
            print(
                f"[{done}/{len(profiles)}] {res.get('profile_id')}: {marker}"
                + (f" ({res.get('final_diagnosis')})" if res.get("final_diagnosis") else "")
                + (f"  !! {res.get('error')}" if res.get("error") else ""),
                flush=True,
            )
            if status not in ("done", "skipped"):
                errors.append(f"{res.get('profile_id')}: {res.get('error')}")

    print(
        f"[run_profile_batch] Done. {len(profiles)} total, {n_ok} ran, "
        f"{n_skipped} skipped, {len(errors)} errors.",
        flush=True,
    )
    if errors:
        for e in errors[:30]:
            print(f"  ! {e}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
