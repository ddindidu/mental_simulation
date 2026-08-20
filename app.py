import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request
from flask import stream_with_context

import doctor
import patient
from utils.config import CONFIG
from utils.llm import chat as llm_chat
from utils.llm import get_display_model_name
from utils.llm import get_doctor_diagnosis_max_tokens
from utils.llm import get_doctor_inference_max_tokens
from utils.llm import get_doctor_model_name
from utils.llm import get_patient_alignment_max_tokens
from utils.llm import get_patient_model_name
from utils.llm import get_run_dir
from utils.llm import get_status
from utils.llm import set_log_path
from utils.llm import set_run_dir_prefix
from utils.llm import set_run_dir_variant
from utils.paths import PROJECT_ROOT, RESULTS_DIR, batch_artifact_dirs
from utils.prompt_display import system_prompt_to_html

app = Flask(__name__)

MAX_TURNS = CONFIG["simulation"]["max_turns"]
SIMULATION_PROFILE_ROOTS = {
    "add_requirements": PROJECT_ROOT / "data" / "profiles" / "add_requirements",
}

_SERVER = CONFIG["server"]

# ── Batch evaluation state ────────────────────────────────────────────────────
_batch_lock = threading.Lock()
_batch_state: dict = {
    "running": False,
    "total": 0,
    "done": 0,
    "current": "",   # e.g. "D009 run 3/10"
    "results": {},   # { "D001": {"correct": 0, "total": 10, "runs": [...]} }
    "error": None,
    "format_failures": 0,   # spec §3: Doctor format-violation count across the batch
}


def _should_log_llm_messages() -> bool:  # log message 출력 설정
    return bool((CONFIG.get("debug") or {}).get("log_llm_messages", False))


def _log_llm_history(which: str, step: str, messages: list) -> None: # terminal에 log message 출력
    if not _should_log_llm_messages():
        return
    print(
        f"\n========== {which} | {step} | {len(messages)} messages ==========",
        flush=True,
    )
    print(json.dumps(messages, ensure_ascii=False, indent=2), flush=True)


@app.route("/")
def index(): # prompt 불러와서 html 화면에 출력 
    return render_template(
        "index.html",
        patient_system_html=system_prompt_to_html(patient.SYSTEM_PROMPT),
        doctor_inference_html=system_prompt_to_html(
            doctor.get_inference_system_prompt(get_doctor_model_name())
        ),
        doctor_questioning_html=system_prompt_to_html(
            doctor.get_questioning_system_prompt(MAX_TURNS, [], get_doctor_model_name())
        ),
        doctor_final_html=system_prompt_to_html(
            doctor.get_final_diagnosis_system_prompt(get_doctor_model_name())
        ),
        model_name=get_display_model_name(),
        max_turns=MAX_TURNS,
    )


@app.route("/api/status") # model loading 완료 여부 출력 
def status():
    return jsonify(get_status())


@app.route("/api/diseases")  # KG에서 사용 가능한 disease 목록 반환
def diseases():
    """disorder.json에서 code→name 매핑을 읽어 반환한다."""
    try:
        kg_base_dir = patient.current_config()["kg_base_dir"]
        disorder_path = os.path.join(kg_base_dir, "resources", "knowledge_graph", "EN", "disorder.json")
        with open(disorder_path, encoding="utf-8") as f:
            data = json.load(f)
        result = [{"code": k, "name": v["name"]} for k, v in data.items()]
        return jsonify({"diseases": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/patient_config", methods=["GET"])  # 현재 환자 config 조회
def get_patient_config():
    return jsonify(patient.current_config())


@app.route("/api/patient_config", methods=["POST"])  # 환자 config 변경 및 SYSTEM_PROMPT 재빌드
def set_patient_config():
    body = request.get_json(force=True) or {}
    disease_code     = body.get("disease_code")
    difficulty_level = body.get("difficulty_level")
    use_kg           = body.get("use_knowledge_graph")
    try:
        patient.reinitialize(
            disease_code=disease_code,
            difficulty_level=difficulty_level,
            use_knowledge_graph=use_kg,
        )
        return jsonify({
            "ok": True,
            "config": patient.current_config(),
            "system_prompt_preview": patient.SYSTEM_PROMPT[:400],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/patient_system_html")  # config 변경 후 patient 패널 HTML 반환
def patient_system_html():
    return jsonify({"html": system_prompt_to_html(patient.SYSTEM_PROMPT)})


@app.route("/api/simulation_profiles")
def simulation_profiles():
    """Return the server-approved profile roots, folders, and JSON files."""
    roots = []
    current_profile = Path(patient.current_config()["symptom_profile_path"]).resolve()
    current = None

    for root_id, configured_root in SIMULATION_PROFILE_ROOTS.items():
        root = configured_root.resolve()
        folders: dict[str, list[dict]] = {}
        if root.is_dir():
            for profile_path in sorted(root.rglob("*.json")):
                relative_path = profile_path.relative_to(root)
                folder = relative_path.parent.as_posix()
                folders.setdefault(folder, []).append({
                    "name": profile_path.name,
                    "relative_path": relative_path.as_posix(),
                })

                if profile_path.resolve() == current_profile:
                    current = {
                        "root_id": root_id,
                        "folder": folder,
                        "relative_path": relative_path.as_posix(),
                    }

        roots.append({
            "id": root_id,
            "label": f"data/profiles/{root.name}",
            "path": str(root),
            "folders": [
                {"path": folder, "files": files}
                for folder, files in sorted(folders.items())
            ],
        })

    return jsonify({"roots": roots, "current": current})


@app.route("/api/simulation_profile", methods=["POST"])
def select_simulation_profile():
    """Select one JSON from an approved root and rebuild the patient prompt."""
    body = request.get_json(force=True) or {}
    root_id = str(body.get("root_id") or "").strip()
    relative_path = str(body.get("relative_path") or "").strip()
    configured_root = SIMULATION_PROFILE_ROOTS.get(root_id)
    if configured_root is None:
        return jsonify({"ok": False, "error": "Unknown profile path"}), 400
    if not relative_path:
        return jsonify({"ok": False, "error": "A JSON profile is required"}), 400

    root = configured_root.resolve()
    selected = (root / relative_path).resolve()
    if not selected.is_relative_to(root) or selected.suffix.lower() != ".json":
        return jsonify({"ok": False, "error": "Invalid profile path"}), 400
    if not selected.is_file():
        return jsonify({"ok": False, "error": "Profile JSON not found"}), 404

    try:
        patient.set_symptom_profile_path(selected)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    return jsonify({
        "ok": True,
        "profile_path": str(selected),
        "profile_file": selected.name,
        "patient_system_html": system_prompt_to_html(patient.SYSTEM_PROMPT),
    })


# ── Batch Evaluation ──────────────────────────────────────────────────────────

def _load_disorder_map() -> dict[str, str]:
    """disorder.json → {code: name}"""
    kg_base_dir = patient.current_config()["kg_base_dir"]
    disorder_path = os.path.join(
        kg_base_dir, "resources", "knowledge_graph", "EN", "disorder.json"
    )
    with open(disorder_path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v["name"] for k, v in data.items()}


def _run_eval_pipeline() -> None:
    """배치 완료 후 symptom_diagnosis → evaluate_* 파이프라인을 순서대로 실행한다.

    실행 순서 (의존성 순):
      1. symptom_diagnosis     → D{code}_{n}_result.json, summary.json
      2. evaluate_final_diagnosis → final_diagnosis_eval.txt
      3. evaluate_turns        → turn_eval.json + PNG (non-strict)
      4. evaluate_turns_strict → turn_eval_strict.json + PNG (LLM 호출)
    """
    import traceback as _tb

    # 후처리 LLM 호출은 최종 평가 JSON/TXT에 반영되므로 별도 원본 로그는 남기지 않는다.
    set_log_path(None)
    batch_results_dir, batch_logs_dir, _ = batch_artifact_dirs(get_run_dir())


    print("[pipeline] Starting post-batch evaluation pipeline...", flush=True)
    print(f"[pipeline] logs dir  : {batch_logs_dir}", flush=True)
    print(f"[pipeline] results dir: {batch_results_dir}", flush=True)

    import importlib

    def _load(name: str):
        """import 후 reload 하여 module-level 경로 상수가 최신 run_dir를 쓰게 한다."""
        import sys
        import importlib as _il
        if name in sys.modules:
            return _il.reload(sys.modules[name])
        return _il.import_module(name)

    with _batch_lock:
        _batch_state["current"] = "[pipeline] symptom extraction & disease matching"
    try:
        sd = _load("eval.symptom_diagnosis")
        sd.main()
    except Exception as _e:
        print(f"[pipeline] symptom_diagnosis failed: {_e}", flush=True)
        _tb.print_exc()

    with _batch_lock:
        _batch_state["current"] = "[pipeline] final diagnosis eval"
    try:
        efd = _load("eval.evaluate_final_diagnosis")
        efd.main()
    except SystemExit:
        print("[pipeline] evaluate_final_diagnosis: no log files, skipping.", flush=True)
    except Exception as _e:
        print(f"[pipeline] evaluate_final_diagnosis failed: {_e}", flush=True)
        _tb.print_exc()

    with _batch_lock:
        _batch_state["current"] = "[pipeline] turn-level eval (non-strict)"
    try:
        et = _load("eval.evaluate_turns")
        _turns = et.evaluate()
        et.plot(_turns)
    except SystemExit:
        print("[pipeline] evaluate_turns: no result files, skipping.", flush=True)
    except Exception as _e:
        print(f"[pipeline] evaluate_turns failed: {_e}", flush=True)
        _tb.print_exc()

    with _batch_lock:
        _batch_state["current"] = "[pipeline] turn-level eval (strict)"
    try:
        ets = _load("eval.evaluate_turns_strict")
        _turns_s, _crit, _ = ets.evaluate()
        ets.plot(_turns_s, _crit)
    except SystemExit:
        print("[pipeline] evaluate_turns_strict: no result files, skipping.", flush=True)
    except Exception as _e:
        print(f"[pipeline] evaluate_turns_strict failed: {_e}", flush=True)
        _tb.print_exc()

    with _batch_lock:
        _batch_state["current"] = "[pipeline] efficiency eval"
    try:
        ee = _load("eval.evaluate_efficiency")
        ee.evaluate()
    except SystemExit:
        print("[pipeline] evaluate_efficiency: no result files, skipping.", flush=True)
    except Exception as _e:
        print(f"[pipeline] evaluate_efficiency failed: {_e}", flush=True)
        _tb.print_exc()

    with _batch_lock:
        _batch_state["current"] = "[pipeline] question reasonability eval"
    try:
        eq = _load("eval.evaluate_question")
        eq.evaluate()
    except SystemExit:
        print("[pipeline] evaluate_question: no result files, skipping.", flush=True)
    except Exception as _e:
        print(f"[pipeline] evaluate_question failed: {_e}", flush=True)
        _tb.print_exc()

    with _batch_lock:
        _batch_state["current"] = "[pipeline] diagnostic reasoning eval"
    try:
        edr = _load("eval.evaluate_diagnostic_reasoning")
        edr.main()
    except SystemExit:
        print("[pipeline] evaluate_diagnostic_reasoning: no log files, skipping.", flush=True)
    except Exception as _e:
        print(f"[pipeline] evaluate_diagnostic_reasoning failed: {_e}", flush=True)
        _tb.print_exc()

    with _batch_lock:
        _batch_state["current"] = "Done"
    print("[pipeline] All done.", flush=True)


def _run_batch_evaluation(
    disorder_map: dict[str, str],
    runs_per_disorder: int,
    difficulty: str,
    max_turns: int,
    logs_dir: Path,
    acc_path: Path,
    parallel_disorders: int = 4,
    use_knowledge_graph: bool = True,
    profiles_by_code: dict[str, list[str]] | None = None,
    runs_per_profile: int = 1,
) -> None:
    """백그라운드 스레드에서 전체 disorder × N회 시뮬레이션 실행.

    disorder 단위로 최대 parallel_disorders개의 별도 프로세스(ProcessPoolExecutor,
    spawn)를 동시에 띄운다. patient.py / utils/llm.py는 SYSTEM_PROMPT나 현재 로그
    경로 등을 모듈 전역 변수로 관리하기 때문에, 여러 disorder를 같은 프로세스
    안에서 스레드로 병렬 실행하면 서로의 상태를 덮어쓰는 레이스 컨디션이 생긴다.
    프로세스를 분리하면 disorder마다 독립된 전역 상태 사본을 가지므로 안전하다.
    실제 시뮬레이션 로직은 batch_worker.run_disorder()에 있다.
    """
    import queue as _queue
    import multiprocessing as mp
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    from batch_worker import run_disorder

    codes = sorted(disorder_map.keys())
    profiles_by_code = profiles_by_code or {}
    expected_per_code = {
        code: (
            runs_per_disorder
            if use_knowledge_graph
            else len(profiles_by_code.get(code, [])) * runs_per_profile
        )
        for code in codes
    }
    total = sum(expected_per_code.values())

    with _batch_lock:
        _batch_state["running"] = True
        _batch_state["total"] = total
        _batch_state["done"] = 0
        _batch_state["results"] = {}
        _batch_state["error"] = None
        _batch_state["format_failures"] = 0

    try:
        max_workers = max(1, min(int(parallel_disorders), len(codes)))
        print(
            f"[batch] parallel_disorders={max_workers} (of {len(codes)} disorders)",
            flush=True,
        )

        ctx = mp.get_context("spawn")
        manager = ctx.Manager()
        progress_queue = manager.Queue()
        received_per_code: dict[str, int] = {code: 0 for code in codes}

        def _drain_progress() -> None:
            while True:
                try:
                    msg = progress_queue.get_nowait()
                except _queue.Empty:
                    return
                with _batch_lock:
                    _batch_state["done"] += 1
                    _batch_state["current"] = f"{msg['code']} run {msg['run']}/{msg['total_runs']}"
                received_per_code[msg["code"]] = received_per_code.get(msg["code"], 0) + 1

        with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as executor:
            futures = {
                executor.submit(
                    run_disorder,
                    code,
                    disorder_map[code],
                    runs_per_disorder,
                    difficulty,
                    max_turns,
                    str(logs_dir),
                    str(acc_path.parent),
                    progress_queue,
                    use_knowledge_graph,
                    profiles_by_code.get(code, []),
                    runs_per_profile,
                ): code
                for code in codes
            }
            pending = set(futures)

            while pending:
                _drain_progress()
                finished, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                for fut in finished:
                    code = futures[fut]
                    try:
                        result = fut.result()
                    except Exception as e:
                        print(f"[batch] disorder {code} failed: {e}", flush=True)
                        result = {
                            "disease_name": disorder_map[code],
                            "source_mode": "knowledge_graph" if use_knowledge_graph else "profile",
                            "correct": 0,
                            "total": expected_per_code[code],
                            "accuracy": 0.0,
                            "runs": [],
                        }
                        # 프로세스가 통째로 죽어 progress 메시지가 덜 도착한 만큼 done을 보정
                        missing = expected_per_code[code] - received_per_code.get(code, 0)
                        if missing > 0:
                            with _batch_lock:
                                _batch_state["done"] += missing
                            received_per_code[code] = expected_per_code[code]
                    with _batch_lock:
                        _batch_state["results"][code] = result
            _drain_progress()

        manager.shutdown()

        # ── acc.txt 작성 ───────────────────────────────────────────────────
        with _batch_lock:
            results_snapshot = dict(_batch_state["results"])

        with _batch_lock:
            batch_format_failures = _batch_state["format_failures"]

        total_simulations = sum(r["total"] for r in results_snapshot.values())
        fmt_compliance = (
            round(1.0 - batch_format_failures / total_simulations, 4)
            if total_simulations > 0 else 1.0
        )

        source_mode = "knowledge_graph" if use_knowledge_graph else "profile"
        run_description = (
            f"difficulty={difficulty}, runs_per_disorder={runs_per_disorder}, max_turns={max_turns}"
            if use_knowledge_graph
            else f"profiles={sum(len(v) for v in profiles_by_code.values())}, runs_per_profile={runs_per_profile}, max_turns={max_turns}"
        )
        lines: list[str] = [
            "=" * 60,
            f"Batch Evaluation Results  (source={source_mode}, {run_description})",
            f"Format compliance rate: {fmt_compliance:.2%}  "
            f"({batch_format_failures} format failures / {total_simulations} simulations)",
            "=" * 60,
            f"{'Code':<8} {'Accuracy':>10}  {'Correct':>8}  Disease Name",
            "-" * 60,
        ]
        overall_correct = 0
        overall_total = 0
        for code in sorted(results_snapshot.keys()):
            r = results_snapshot[code]
            overall_correct += r["correct"]
            overall_total += r["total"]
            lines.append(
                f"{code:<8} {r['accuracy']:>10.2%}  {r['correct']:>3}/{r['total']:<3}  {r['disease_name']}"
            )
        lines.append("-" * 60)
        if overall_total:
            overall_acc = overall_correct / overall_total
            lines.append(
                f"{'TOTAL':<8} {overall_acc:>10.2%}  {overall_correct:>3}/{overall_total:<3}"
            )
        lines.append("=" * 60)

        acc_path.parent.mkdir(parents=True, exist_ok=True)
        acc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[batch] acc.txt written → {acc_path}", flush=True)

        _run_eval_pipeline()

    except Exception as e:
        with _batch_lock:
            _batch_state["error"] = str(e)
        print(f"[batch] FATAL: {e}", flush=True)
    finally:
        with _batch_lock:
            _batch_state["running"] = False
            _batch_state["current"] = "Done"


@app.route("/api/batch_eval", methods=["POST"])
def batch_eval():
    """배치 평가 시작 엔드포인트.
    Body (JSON, optional):
      { "runs_per_disorder": 10, "difficulty": "medium", "parallel_disorders": 4 }
    parallel_disorders: 동시에 실행할 disorder(프로세스) 개수. 생략 시
    config.json의 batch.parallel_disorders(기본 4)를 사용한다.
    """
    with _batch_lock:
        if _batch_state["running"]:
            return jsonify({"ok": False, "error": "Batch already running"}), 409

    body = request.get_json(force=True) or {}
    use_knowledge_graph = body.get("use_knowledge_graph", True)
    if not isinstance(use_knowledge_graph, bool):
        return jsonify({
            "ok": False,
            "error": "use_knowledge_graph must be true or false",
        }), 400

    try:
        runs = int(body.get("runs_per_disorder", 1))
        max_turns = int(body.get("max_turns", MAX_TURNS))
        runs_per_profile = int(body.get("runs_per_profile", 1))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Run counts and max_turns must be integers"}), 400
    if not 1 <= runs <= 100 or not 1 <= runs_per_profile <= 100:
        return jsonify({
            "ok": False,
            "error": "Run counts must be between 1 and 100",
        }), 400
    if not 1 <= max_turns <= 100:
        return jsonify({
            "ok": False,
            "error": "max_turns must be between 1 and 100",
        }), 400

    difficulty = str(body.get("difficulty", "medium")).strip()
    default_parallel = int((CONFIG.get("batch") or {}).get("parallel_disorders", 4))
    try:
        parallel_disorders = max(1, int(body.get("parallel_disorders", default_parallel)))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "parallel_disorders must be an integer"}), 400

    try:
        disorder_map = _load_disorder_map()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    # config.json "batch.disease_codes" 로 필터링
    # 예: [1, 3, 9]  →  D001, D003, D009 만 실행; 빈 리스트 = 전체
    selected_codes: list = (CONFIG.get("batch") or {}).get("disease_codes") or []
    if selected_codes:
        allowed = {f"D{int(n):03d}" for n in selected_codes}
        disorder_map = {k: v for k, v in disorder_map.items() if k in allowed}
        if not disorder_map:
            return jsonify({
                "ok": False,
                "error": f"No matching disease codes for {selected_codes}",
            }), 400
        print(f"[batch] disease filter → {sorted(disorder_map.keys())}", flush=True)

    profiles_by_code: dict[str, list[str]] = {}
    profile_root: Path | None = None
    if use_knowledge_graph:
        if difficulty not in {"low", "medium", "high"}:
            return jsonify({
                "ok": False,
                "error": "difficulty must be low, medium, or high",
            }), 400
        source_dir = "kg"
        mode_variant = difficulty
    else:
        raw_profile_root = str(body.get("profile_root") or "").strip()
        if not raw_profile_root:
            return jsonify({"ok": False, "error": "profile_root is required"}), 400

        from utils.paths import PROJECT_ROOT
        allowed_profiles_root = (PROJECT_ROOT / "data" / "profiles").resolve()
        profile_root = Path(raw_profile_root).expanduser().resolve()
        if not profile_root.is_relative_to(allowed_profiles_root):
            return jsonify({
                "ok": False,
                "error": f"profile_root must be inside {allowed_profiles_root}",
            }), 400
        if not profile_root.is_dir():
            return jsonify({
                "ok": False,
                "error": f"Profile directory not found: {profile_root}",
            }), 400

        for profile_path in sorted(profile_root.rglob("*.json")):
            match = re.match(r"^(D\d{3})_", profile_path.stem)
            if not match:
                continue
            code = match.group(1)
            if code in disorder_map:
                profiles_by_code.setdefault(code, []).append(str(profile_path))

        disorder_map = {
            code: name for code, name in disorder_map.items()
            if profiles_by_code.get(code)
        }
        if not disorder_map:
            return jsonify({"ok": False, "error": "No matching profile JSON files found"}), 400
        source_dir = "profile"
        mode_variant = profile_root.name

    run_id = f"run_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    set_run_dir_prefix(f"{source_dir}/{run_id}/results")
    set_run_dir_variant(mode_variant)
    run_dir = get_run_dir()
    batch_results_dir, logs_dir, _ = batch_artifact_dirs(run_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    acc_path = batch_results_dir / "acc.txt"

    print(f"[batch] run_dir = {run_dir}", flush=True)

    t = threading.Thread(
        target=_run_batch_evaluation,
        args=(disorder_map, runs, difficulty, max_turns, logs_dir, acc_path, parallel_disorders),
        kwargs={
            "use_knowledge_graph": use_knowledge_graph,
            "profiles_by_code": profiles_by_code,
            "runs_per_profile": runs_per_profile,
        },
        daemon=True,
    )
    t.start()

    profile_count = sum(len(paths) for paths in profiles_by_code.values())
    total_simulations = (
        len(disorder_map) * runs
        if use_knowledge_graph
        else profile_count * runs_per_profile
    )
    return jsonify({
        "ok": True,
        "source_mode": "knowledge_graph" if use_knowledge_graph else "profile",
        "disorders": len(disorder_map),
        "runs_per_disorder": runs,
        "profiles": profile_count,
        "runs_per_profile": runs_per_profile,
        "max_turns": max_turns,
        "total_simulations": total_simulations,
        "difficulty": difficulty,
        "profile_root": str(profile_root) if profile_root else None,
        "parallel_disorders": parallel_disorders,
        "run_dir": run_dir,
        "run_id": run_id,
        "results_dir": str(batch_results_dir),
        "logs_dir": str(logs_dir),
        "acc_path": str(acc_path),
    })


@app.route("/api/batch_status")
def batch_status():
    """배치 평가 진행 상황 조회."""
    with _batch_lock:
        total_sims = sum(r["total"] for r in _batch_state["results"].values())
        ff = _batch_state["format_failures"]
        snapshot = {
            "running": _batch_state["running"],
            "total": _batch_state["total"],
            "done": _batch_state["done"],
            "current": _batch_state["current"],
            "error": _batch_state["error"],
            "results_count": len(_batch_state["results"]),
            "format_failures": ff,
            "format_compliance_rate": round(1.0 - ff / total_sims, 4) if total_sims else 1.0,
            "results": {
                code: {
                    **{k: v for k, v in info.items() if k != "runs"},
                    "runs": [
                        {
                            key: run.get(key)
                            for key in (
                                "run",
                                "artifact_id",
                                "final_diagnosis",
                                "correct",
                                "error",
                            )
                            if key in run
                        }
                        for run in info.get("runs", [])
                    ],
                }
                for code, info in _batch_state["results"].items()
            },
        }
    return jsonify(snapshot)


@app.route("/simulate") # start simulation
def simulate(): # prompts loading
    # doctor_memory.json, transcript.json과 같은 디렉터리에 이번 실행의
    # 모든 LLM 입력 프롬프트와 출력을 저장한다.
    set_log_path(RESULTS_DIR / "prompt.txt")
    patient_system = patient.SYSTEM_PROMPT
    doctor_model = get_doctor_model_name()
    inference_system = doctor.get_inference_system_prompt(doctor_model)
    final_system = doctor.get_final_diagnosis_system_prompt(doctor_model)
    diag_tokens = get_doctor_diagnosis_max_tokens()
    inf_tokens = get_doctor_inference_max_tokens()
    align_tokens = get_patient_alignment_max_tokens()

    @stream_with_context
    def _gen(): # run simulation
        doctor_memory: dict = doctor.new_doctor_memory() # initializing doctor memory
        patient_hist: list[dict] = [{"role": "system", "content": patient_system}] # initializing patient history
        transcript: list[tuple[str, str]] = []

        def emit(obj: dict) -> str:
            return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        yield emit({"event": "start"})
        yield emit({"event": "doctor_memory", "state": doctor_memory})

        try:
            opening_messages = [
                {
                    "role": "system",
                    "content": doctor.get_questioning_system_prompt(MAX_TURNS, [], doctor_model),
                },
                {"role": "user", "content": doctor.opening_user_message()},
            ]
            _log_llm_history("Doctor LLM (questioning)", "opening", opening_messages)
            doctor_raw = llm_chat(
                opening_messages,
                role="doctor",
                call_name="opening-question",
                turn=0,
            )
            q_open = doctor.parse_questioning_result(doctor_raw)
            question_text = q_open["question"]
            doctor_memory["opening_question"] = {
                "category": q_open["category"],
                "subcategory": q_open["subcategory"],
                "question": question_text,
            }
            doctor.persist_doctor_memory_json(doctor_memory)
            yield emit({"event": "doctor_memory", "state": doctor_memory})

            transcript.append(("doctor", question_text))

            yield emit(
                {
                    "event": "turn",
                    "turn": 0,
                    "role": "doctor",
                    "content": question_text,
                    "category": q_open.get("category", ""),
                    "subcategory": q_open.get("subcategory"),
                    "raw": doctor_raw,
                }
            )
            yield emit(
                {
                    "event": "question_log",
                    "turn": 0,
                    "phase": "questioning",
                    "content": question_text,
                    "category": q_open["category"],
                    "subcategory": q_open["subcategory"],
                    "raw": doctor_raw,
                }
            )

            patient_hist.append({"role": "user", "content": question_text})

            for t in range(1, MAX_TURNS + 1):
                doctor_last = patient_hist[-1]["content"]
                align_messages = patient.build_alignment_messages(doctor_last, t)
                _log_llm_history("Patient LLM (alignment)", f"turn {t}", align_messages)
                align_raw = llm_chat(
                    align_messages,
                    max_new_tokens=align_tokens,
                    role="patient",
                    call_name="profile-alignment",
                    turn=t,
                )
                parsed = patient.parse_alignment_result(align_raw)
                strategy_text = patient.format_alignment_for_response(parsed)
                yield emit(
                    {
                        "event": "patient_alignment",
                        "turn": t,
                        "raw": align_raw,
                        "parsed": parsed,
                    }
                )

                resp_messages = patient.build_response_messages(
                    patient_hist, strategy_text
                )
                _log_llm_history("Patient LLM (response)", f"turn {t}", resp_messages)
                patient_msg = llm_chat(
                    resp_messages,
                    role="patient",
                    call_name="response",
                    turn=t,
                )
                patient_hist.append({"role": "assistant", "content": patient_msg})
                transcript.append(("patient", patient_msg))

                yield emit({"event": "turn", "turn": t, "role": "patient", "content": patient_msg})

                tr_text = doctor.format_interview_transcript(transcript)

                # ── Inference phase ─────────────────────────────────────
                prev_cands = (
                    doctor_memory["inference_history"][-1]["candidates"]
                    if doctor_memory["inference_history"]
                    else []
                )
                inf_messages = [
                    {"role": "system", "content": inference_system},
                    {"role": "user", "content": doctor.inference_user_payload(tr_text, previous_candidates=prev_cands)},
                ]
                _log_llm_history("Doctor LLM (inference)", f"turn {t}", inf_messages)
                inf_raw = llm_chat(
                    inf_messages,
                    max_new_tokens=inf_tokens,
                    role="doctor",
                    call_name="clinical-inference",
                    turn=t,
                )
                candidates, inf_note, is_final = doctor.parse_inference_result(inf_raw)

                doctor.update_doctor_memory_after_inference(
                    doctor_memory,
                    turn=t,
                    candidates=candidates,
                    note=inf_note,
                    raw_model=inf_raw,
                    is_final=is_final,
                )
                doctor.persist_doctor_memory_json(doctor_memory)
                yield emit({"event": "doctor_memory", "state": doctor_memory})

                yield emit(
                    {
                        "event": "inference",
                        "turn": t,
                        "candidates": candidates,
                        "note": inf_note,
                        "is_final": is_final,
                        "raw": inf_raw,
                    }
                )

                if doctor.should_finish_interview(is_final, t, MAX_TURNS):
                    fin_messages = [
                        {"role": "system", "content": final_system},
                        {
                            "role": "user",
                            "content": doctor.final_diagnosis_user_payload(
                                tr_text, candidates
                            ),
                        },
                    ]
                    _log_llm_history("Doctor LLM (final)", f"turn {t}", fin_messages)
                    diagnosis_raw = llm_chat(
                        fin_messages,
                        max_new_tokens=diag_tokens,
                        role="doctor",
                        call_name="final-diagnosis",
                        turn=t,
                    )
                    yield emit(
                        {
                            "event": "diagnosis",
                            "turn": t,
                            "role": "doctor",
                            "content": diagnosis_raw,
                        }
                    )
                    fd = doctor.parse_final_diagnosis_result(diagnosis_raw)
                    doctor.finalize_doctor_memory(
                        doctor_memory,
                        closed_at_patient_turn=t,
                        final_diagnosis=fd,
                        final_candidates_used=candidates,
                    )
                    doctor.persist_doctor_memory_json(doctor_memory)
                    yield emit({"event": "doctor_memory", "state": doctor_memory})
                    tx_payload = doctor.build_interview_transcript_payload(
                        transcript,
                        max_turns_config=MAX_TURNS,
                        closed_at_patient_turn=t,
                        patient_model=get_patient_model_name(),
                        doctor_model=get_doctor_model_name(),
                    )
                    doctor.persist_interview_transcript_json(tx_payload)
                    break

                # ── Questioning phase (follow-up) ────────────────────────
                questioning_messages = [
                    {
                        "role": "system",
                        "content": doctor.get_questioning_system_prompt(MAX_TURNS, candidates, doctor_model),
                    },
                    {
                        "role": "user",
                        "content": doctor.questioning_followup_user_payload(patient_msg, tr_text, candidates),
                    },
                ]
                _log_llm_history(
                    "Doctor LLM (questioning)",
                    f"follow-up after turn {t}",
                    questioning_messages,
                )
                doctor_raw = llm_chat(
                    questioning_messages,
                    role="doctor",
                    call_name="followup-question",
                    turn=t,
                )
                q_follow = doctor.parse_questioning_result(doctor_raw)
                question_text = q_follow["question"]

                transcript.append(("doctor", question_text))

                yield emit(
                    {
                        "event": "turn",
                        "turn": t,
                        "role": "doctor",
                        "content": question_text,
                        "category": q_follow["category"],
                        "subcategory": q_follow["subcategory"],
                        "raw": doctor_raw,
                    }
                )
                yield emit(
                    {
                        "event": "question_log",
                        "turn": t,
                        "phase": "questioning",
                        "content": question_text,
                        "category": q_follow["category"],
                        "subcategory": q_follow["subcategory"],
                        "raw": doctor_raw,
                    }
                )

                patient_hist.append({"role": "user", "content": question_text})

        except Exception as e:
            doctor_memory["status"] = "error"
            doctor_memory["error"] = str(e)
            doctor.persist_doctor_memory_json(doctor_memory)
            yield emit({"event": "doctor_memory", "state": doctor_memory})
            yield emit({"event": "error", "message": str(e)})

        yield emit({"event": "done"})

    return Response(
        _gen(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    app.run(
        host=str(_SERVER["host"]),
        port=int(_SERVER["port"]),
        debug=bool(_SERVER.get("debug", False)),
        threaded=bool(_SERVER.get("threaded", True)),
    )
