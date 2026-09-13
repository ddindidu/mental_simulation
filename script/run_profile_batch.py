#!/usr/bin/env python3
"""Run one SIMULATION (dialogue generation only, no evaluation) per profile
JSON under a profiles root, using whichever patient/judge/doctor models
config/config.json currently specifies.

This writes only the dialogue log files (.txt + .json) — it does not run
symptom extraction or produce *_result.json. Run `eval/symptom_diagnosis.py`
afterward for that: it's a separate, standalone, resumable pass over an
entire run_dir's logs (own existing-output check: skips a log whose
*_result.json is already up to date; own source check: it only processes
.txt logs that actually exist). Splitting these means you can regenerate/
re-run dialogues without forcing re-evaluation, or re-run evaluation alone
(e.g. after changing scoring logic) without re-simulating anything.

Intended to be invoked once per doctor model by script/run_all_doctors_profiles.py
(which patches config/config.json's llm.doctor before each call), but can be run directly
against whatever config/config.json already has.

Parallelizes across profiles with a spawn-context ProcessPoolExecutor — see
profile_batch_worker.py for why per-profile isolation is required.

Usage:
  python3 script/run_profile_batch.py
  python3 script/run_profile_batch.py --profiles-root data/v1_only_manifestation --workers 4
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
        default=PROJECT_ROOT / "data" / "v2_final_profiles",
        help="Root directory to recursively glob *.json profiles from.",
    )
    parser.add_argument(
        "--styles", nargs="*", default=None,
        help="Conversation styles to run each profile under (default: the config's single "
             "style). Every style of one profile is queued before the next profile.",
    )
    parser.add_argument("--workers", type=int, default=4, help="Parallel simulation processes.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N profiles (smoke test).")
    args = parser.parse_args()

    from utils.config import CONFIG

    # 프로필 배치는 KG 모드를 지원하지 않기 때문에 시뮬레이션 시작 전에 차단
    if bool((CONFIG.get("patient") or {}).get("use_knowledge_graph", False)):
        print(
            "[run_profile_batch] ERROR: config 의 patient.use_knowledge_graph 가 true 입니다.\n"
            "  프로필 배치는 KG 모드에서 실행할 수 없습니다 (symptom_diagnosis import 가 깨집니다).\n"
            "  config/config.json 에서 patient.use_knowledge_graph 를 false 로 바꾼 뒤 다시 실행하세요.\n"
            "  KG 환자로 배치를 돌리려면 웹 UI 의 batch(KG 모드) 또는 batch_worker.run_disorder 를 쓰세요.",
            file=sys.stderr,
        )
        return 1

    from utils.llm import (
        get_run_dir,
        get_doctor_model_name,
        get_patient_model_name,
        get_judge_model_name,
    )
    from profile_batch_worker import run_profile

    # 웹 UI 배치(app.py)와 같은 saved/run_batch_<날짜>/ 아래에 쓴다.
    # eval/*.py 와 reporting/*.py 가 utils.paths 의 LOGS_ROOT/RESULTS_ROOT 로
    # 같은 위치를 읽는다.
    from utils.paths import artifact_dirs, ensure_run_root

    run_dir = get_run_dir()
    ensure_run_root("batch")
    results_dir, logs_dir, _ = artifact_dirs(run_dir, mode="batch")
    logs_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    max_turns = int(CONFIG["simulation"]["max_turns"])

    profiles = sorted(args.profiles_root.rglob("*.json"))
    if not profiles:
        print(f"[run_profile_batch] No profile JSON files found under {args.profiles_root}", file=sys.stderr)
        return 1
    if args.limit:
        profiles = profiles[: args.limit]

    # 프로필 하나를 모든 스타일로 끝내고 다음 프로필로 넘어가도록 profile-major 로 세운다.
    styles = args.styles or [None]
    jobs = [(p, st) for p in profiles for st in styles]

    print(
        f"[run_profile_batch] patient={get_patient_model_name()} "
        f"judge={get_judge_model_name()} doctor={get_doctor_model_name()} "
        f"run_dir={run_dir} profiles={len(profiles)} styles={styles} "
        f"runs={len(profiles) * len(styles)} workers={args.workers} max_turns={max_turns}",
        flush=True,
    )

    ctx = mp.get_context("spawn")
    done = 0
    n_skipped = 0
    n_ok = 0
    errors: list[str] = []
    with ProcessPoolExecutor(max_workers=max(1, args.workers), mp_context=ctx) as executor:
        futures = {
            executor.submit(run_profile, str(p), str(logs_dir), max_turns, st): p
            for p, st in jobs
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
                "done": "OK", "skipped": "SKIP", "error": "ERR",
            }.get(status, "?")
            if status == "skipped":
                n_skipped += 1
            elif status == "done":
                n_ok += 1
            case = res.get("profile_id")
            if res.get("style"):
                case = f"{case}_{res['style']}"
            print(
                f"[{done}/{len(jobs)}] {case}: {marker}"
                + (f" ({res.get('final_diagnosis')})" if res.get("final_diagnosis") else "")
                + (f"  !! {res.get('error')}" if res.get("error") else ""),
                flush=True,
            )
            if status not in ("done", "skipped"):
                errors.append(f"{res.get('profile_id')}: {res.get('error')}")

    print(
        f"[run_profile_batch] Done. {len(jobs)} runs ({len(profiles)} profiles x {len(styles)} styles), {n_ok} ran, "
        f"{n_skipped} skipped, {len(errors)} errors.",
        flush=True,
    )
    if errors:
        for e in errors[:30]:
            print(f"  ! {e}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
