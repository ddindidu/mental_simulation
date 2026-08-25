import json
import re
import os
import threading
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
from utils.prompt_display import system_prompt_to_html

app = Flask(__name__)

MAX_TURNS = CONFIG["simulation"]["max_turns"]
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


# ── Simulation profile catalog ────────────────────────────────────────────────
#
# data/ 아래의 프로필 버전 디렉터리(v1_..., v2_... 등)를 훑어 UI 드롭다운에 채운다.
# data/code/ 는 프로필 생성 스크립트 모음이므로 카탈로그에서 제외한다.

_PROFILE_ROOT_EXCLUDE = {"code"}


def _profile_roots() -> list[Path]:
    from utils.paths import DATA_DIR
    if not DATA_DIR.is_dir():
        return []
    return sorted(
        d for d in DATA_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name not in _PROFILE_ROOT_EXCLUDE
    )


def _scan_profile_root(root: Path) -> dict:
    """하나의 프로필 루트를 {id, label, path, folders:[{path, files:[...]}]} 로 만든다.

    루트 바로 아래에 있는 JSON은 folder path "." 로 묶는다.
    """
    folders: dict[str, list[dict]] = {}
    for jf in sorted(root.rglob("*.json")):
        rel = jf.relative_to(root)
        folder = rel.parent.as_posix()  # 루트 직속이면 "."
        folders.setdefault(folder, []).append(
            {"name": jf.name, "relative_path": rel.as_posix()}
        )
    return {
        "id": root.name,
        "label": root.name,
        "path": str(root),
        "folders": [{"path": k, "files": v} for k, v in sorted(folders.items())],
    }


def _current_profile_selection(catalog: list[dict]) -> dict | None:
    """현재 patient가 물고 있는 프로필을 카탈로그 좌표(root_id/folder/relative_path)로 환산."""
    current_path = patient.current_config().get("symptom_profile_path")
    if not current_path:
        return None
    cur = Path(current_path).resolve()
    for root in catalog:
        root_path = Path(root["path"]).resolve()
        try:
            rel = cur.relative_to(root_path)
        except ValueError:
            continue
        return {
            "root_id": root["id"],
            "folder": rel.parent.as_posix(),
            "relative_path": rel.as_posix(),
        }
    return None


@app.route("/api/simulation_profiles")  # 프로필 카탈로그 조회
def simulation_profiles():
    try:
        catalog = [_scan_profile_root(r) for r in _profile_roots()]
        catalog = [r for r in catalog if r["folders"]]  # JSON이 하나도 없는 루트는 숨김
        return jsonify({"roots": catalog, "current": _current_profile_selection(catalog)})
    except Exception as e:
        return jsonify({"roots": [], "current": None, "error": str(e)}), 500


@app.route("/api/simulation_profile", methods=["POST"])  # 프로필 선택 → patient 재빌드
def set_simulation_profile():
    body = request.get_json(force=True) or {}
    root_id = str(body.get("root_id", "")).strip()
    relative_path = str(body.get("relative_path", "")).strip()
    if not root_id or not relative_path:
        return jsonify({"ok": False, "error": "root_id and relative_path are required"}), 400

    root = next((r for r in _profile_roots() if r.name == root_id), None)
    if root is None:
        return jsonify({"ok": False, "error": f"Unknown profile root: {root_id}"}), 400

    target = (root / relative_path).resolve()
    # 경로 탈출 방지 (../ 등)
    if not str(target).startswith(str(root.resolve())):
        return jsonify({"ok": False, "error": "Invalid relative_path"}), 400
    if not target.is_file():
        return jsonify({"ok": False, "error": f"Profile not found: {relative_path}"}), 404

    try:
        patient.set_symptom_profile_path(target)
        return jsonify({
            "ok": True,
            "profile_path": str(target),
            "patient_system_html": system_prompt_to_html(patient.SYSTEM_PROMPT),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Batch Evaluation ──────────────────────────────────────────────────────────

_PROFILE_ID_RE = re.compile(r"^(D\d+)")


def _collect_profiles(profile_root: Path) -> list[Path]:
    """프로필 루트 아래 *.json 을 재귀 수집 (파일명 정렬)."""
    root = Path(profile_root).expanduser()
    if not root.is_dir():
        raise ValueError(f"Profile root not found: {root}")
    return sorted(root.rglob("*.json"))


def _disease_code_from_profile(profile_path: Path) -> str:
    """프로필 파일명에서 정답 질환 코드를 얻는다 (D001_S001_P001.json → D001).

    프로필 JSON에는 질환 코드 필드가 없으므로 파일명 규약에 의존한다.
    """
    m = _PROFILE_ID_RE.match(profile_path.stem)
    return m.group(1) if m else ""


def _persist_single_artifacts(
    case_id: str,
    json_log_path: Path,
    txt_log_path: Path,
    result_json_path: Path,
    transcript: list,
    doctor_memory: dict,
) -> None:
    """단건 실행 산출물을 배치와 같은 형식으로 저장한다.

    실패해도 화면 스트리밍에는 영향을 주지 않도록 예외를 삼킨다.
    """
    fd = (doctor_memory.get("final_diagnosis") or {})
    try:
        json_log_path.write_text(
            json.dumps({
                "case_id": case_id,
                "closed_at_patient_turn": doctor_memory.get("closed_at_patient_turn"),
                "final_diagnosis": fd.get("diagnosis", ""),
                "transcript": [{"role": r, "content": c} for r, c in transcript],
                "doctor_memory": doctor_memory,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[simulate] log saved → {json_log_path}", flush=True)
    except Exception as e:
        print(f"[simulate] json log save failed: {e}", flush=True)

    # 증상 추출 + KG 후보군. batch_worker와 같은 로더를 써서 import 충돌을 피한다.
    try:
        from batch_worker import _make_symptom_diagnosis_runner
        _make_symptom_diagnosis_runner(case_id)(txt_log_path, result_json_path)
    except Exception as e:
        print(f"[simulate] symptom_diagnosis failed: {e}", flush=True)


def _single_case_id() -> str:
    """단건 실행의 케이스 이름. 배치의 D001_1 / D001_S001_P001 자리에 대응한다.

    프로필 모드면 프로필 파일명(D005_S001_P001), KG 모드면 '<질환코드>_kg'.
    같은 날 같은 대상을 다시 돌리면 덮어쓴다 (배치와 동일한 규칙).
    """
    cfg = patient.current_config()
    if cfg.get("use_knowledge_graph"):
        return f"{cfg.get('disease_code') or 'unknown'}_kg"
    profile_path = cfg.get("symptom_profile_path") or ""
    return Path(profile_path).stem or "single"


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
    from utils.paths import LOGS_ROOT, RESULTS_ROOT

    # 파이프라인 LLM 호출(symptom_diagnosis judge 호출 등)이
    # 마지막 시뮬레이션 로그 파일에 섞이지 않도록 별도 로그로 분리
    set_log_path(RESULTS_ROOT / get_run_dir() / "_pipeline_llm.log")

    print("[pipeline] Starting post-batch evaluation pipeline...", flush=True)
    print(f"[pipeline] logs dir  : {LOGS_ROOT / get_run_dir()}", flush=True)
    print(f"[pipeline] results dir: {RESULTS_ROOT / get_run_dir()}", flush=True)

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
    tasks: list[dict],
    difficulty: str,
    logs_dir: Path,
    acc_path: Path,
    parallel_disorders: int = 4,
    max_turns: int | None = None,
    mode: str = "kg",
) -> None:
    """백그라운드 스레드에서 배치 시뮬레이션을 실행한다.

    tasks의 각 항목이 병렬 단위다 — KG 모드는 disorder 하나, 프로필 모드는
    프로필 JSON 파일 하나. 각 항목을 별도 프로세스(ProcessPoolExecutor, spawn)에서
    실행하며 동시 실행 수는 parallel_disorders로 제한한다. patient.py / utils/llm.py는
    SYSTEM_PROMPT나 현재 로그 경로 등을 모듈 전역 변수로 관리하기 때문에, 같은
    프로세스 안에서 스레드로 병렬 실행하면 서로의 상태를 덮어쓰는 레이스 컨디션이
    생긴다. 프로세스를 분리하면 각자 독립된 전역 상태 사본을 가지므로 안전하다.
    실제 시뮬레이션 로직은 batch_worker.run_disorder() / run_profile()에 있다.
    """
    import queue as _queue
    import multiprocessing as mp
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    total = sum(t["n_runs"] for t in tasks)

    with _batch_lock:
        _batch_state["running"] = True
        _batch_state["total"] = total
        _batch_state["done"] = 0
        _batch_state["results"] = {}
        _batch_state["error"] = None
        _batch_state["format_failures"] = 0

    try:
        max_workers = max(1, min(int(parallel_disorders), len(tasks)))
        print(
            f"[batch] mode={mode} parallel={max_workers} "
            f"(of {len(tasks)} {'disorders' if mode == 'kg' else 'profiles'}), total_runs={total}",
            flush=True,
        )

        ctx = mp.get_context("spawn")
        manager = ctx.Manager()
        progress_queue = manager.Queue()
        received_per_key: dict[str, int] = {t["key"]: 0 for t in tasks}

        def _drain_progress() -> None:
            while True:
                try:
                    msg = progress_queue.get_nowait()
                except _queue.Empty:
                    return
                with _batch_lock:
                    _batch_state["done"] += 1
                    _batch_state["current"] = f"{msg['code']} run {msg['run']}/{msg['total_runs']}"
                received_per_key[msg["code"]] = received_per_key.get(msg["code"], 0) + 1

        with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as executor:
            futures = {
                executor.submit(task["target"], *task["args"], progress_queue): task["key"]
                for task in tasks
            }
            task_by_key = {t["key"]: t for t in tasks}
            pending = set(futures)

            while pending:
                _drain_progress()
                finished, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                for fut in finished:
                    code = futures[fut]
                    task = task_by_key[code]
                    try:
                        result = fut.result()
                    except Exception as e:
                        print(f"[batch] task {code} failed: {e}", flush=True)
                        from batch_worker import _true_icd10_code
                        result = {
                            "disease_name": task["disease_name"],
                            "disease_code": task["disease_code"],
                            "icd10_code": _true_icd10_code(task["disease_code"]),
                            "correct": 0,
                            "total": task["n_runs"],
                            "accuracy": 0.0,
                            "runs": [],
                        }
                        # 프로세스가 통째로 죽어 progress 메시지가 덜 도착한 만큼 done을 보정
                        missing = task["n_runs"] - received_per_key.get(code, 0)
                        if missing > 0:
                            with _batch_lock:
                                _batch_state["done"] += missing
                            received_per_code[code] = runs_per_disorder
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

        runs_each = max((t["n_runs"] for t in tasks), default=0)
        source = f"difficulty={difficulty}" if mode == "kg" else "source=profiles"
        key_header = "Code" if mode == "kg" else "Profile"
        lines: list[str] = [
            "=" * 72,
            f"Batch Evaluation Results  (mode={mode}, {source}, runs={runs_each}, "
            f"max_turns={max_turns})",
            f"Format compliance rate: {fmt_compliance:.2%}  "
            f"({batch_format_failures} format failures / {total_simulations} simulations)",
            "=" * 72,
            f"{key_header:<22} {'Accuracy':>10}  {'Correct':>8}  Disease Name (ICD-10)",
            "-" * 72,
        ]
        overall_correct = 0
        overall_total = 0
        for code in sorted(results_snapshot.keys()):
            r = results_snapshot[code]
            overall_correct += r["correct"]
            overall_total += r["total"]
            icd = r.get("icd10_code")
            target = f"{r['disease_name']} ({icd})" if icd else r["disease_name"]
            lines.append(
                f"{code:<22} {r['accuracy']:>10.2%}  {r['correct']:>3}/{r['total']:<3}  {target}"
            )
        lines.append("-" * 72)
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
      { "runs_per_disorder": 10, "difficulty": "medium",
        "max_turns": 10, "parallel_disorders": 4 }
    max_turns: 생략 시 config의 simulation.max_turns.
    parallel_disorders: 동시에 실행할 disorder(프로세스) 개수. 생략 시
    config.json의 batch.parallel_disorders(기본 4)를 사용한다.
    """
    with _batch_lock:
        if _batch_state["running"]:
            return jsonify({"ok": False, "error": "Batch already running"}), 409

    body = request.get_json(force=True) or {}
    runs = int(body.get("runs_per_disorder", 10))
    difficulty = str(body.get("difficulty", "medium")).strip()
    default_parallel = int((CONFIG.get("batch") or {}).get("parallel_disorders", 4))
    parallel_disorders = int(body.get("parallel_disorders", default_parallel))

    try:
        max_turns = int(body.get("max_turns", MAX_TURNS))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "max_turns must be an integer"}), 400
    if max_turns < 1:
        return jsonify({"ok": False, "error": "max_turns must be >= 1"}), 400

    # 환자 소스: True = KnowledgeGraph에서 즉석 생성, False = 미리 만든 프로필 JSON 순회
    use_kg = bool(body.get("use_knowledge_graph", True))
    runs_per_profile = int(body.get("runs_per_profile", 1))
    if runs_per_profile < 1:
        return jsonify({"ok": False, "error": "runs_per_profile must be >= 1"}), 400
    profile_root = Path(str(body.get("profile_root", "")).strip()) if not use_kg else None
    if not use_kg and not str(profile_root):
        return jsonify({"ok": False, "error": "profile_root is required when use_knowledge_graph is false"}), 400

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

    from utils.paths import artifact_dirs, ensure_run_root
    run_dir = get_run_dir()
    ensure_run_root("batch")
    results_dir, logs_dir, _ = artifact_dirs(run_dir, mode="batch")
    logs_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    acc_path = results_dir / "acc.txt"

    # ── 실행 단위(task) 구성 ──────────────────────────────────────────────
    # KG 모드   : disorder 하나 = task 하나 (질환마다 runs_per_disorder회)
    # 프로필 모드: 프로필 JSON 하나 = task 하나 (파일마다 runs_per_profile회)
    from batch_worker import run_disorder, run_profile

    tasks: list[dict] = []
    if use_kg:
        for code in sorted(disorder_map.keys()):
            tasks.append({
                "key": code,
                "disease_name": disorder_map[code],
                "disease_code": code,
                "n_runs": runs,
                "target": run_disorder,
                "args": (code, disorder_map[code], runs, difficulty, max_turns,
                         str(logs_dir), str(results_dir)),
            })
    else:
        try:
            profiles = _collect_profiles(profile_root)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        if not profiles:
            return jsonify({
                "ok": False,
                "error": f"No profile JSON found under {profile_root}",
            }), 400
        for p in profiles:
            code = _disease_code_from_profile(p)
            name = disorder_map.get(code, code or p.stem)
            tasks.append({
                "key": p.stem,
                "disease_name": name,
                "disease_code": code,
                "n_runs": runs_per_profile,
                "target": run_profile,
                "args": (str(p), name, code, runs_per_profile, max_turns,
                         str(logs_dir), str(results_dir)),
            })

    print(
        f"[batch] run_dir = {run_dir} | mode={'kg' if use_kg else 'profile'} | "
        f"tasks={len(tasks)}",
        flush=True,
    )

    t = threading.Thread(
        target=_run_batch_evaluation,
        args=(tasks, difficulty, logs_dir, acc_path, parallel_disorders, max_turns,
              "kg" if use_kg else "profile"),
        daemon=True,
    )
    t.start()

    return jsonify({
        "ok": True,
        "mode": "kg" if use_kg else "profile",
        "disorders": len(tasks),
        "total_simulations": sum(t_["n_runs"] for t_ in tasks),
        "runs_per_disorder": runs,
        "runs_per_profile": runs_per_profile,
        "profile_root": str(profile_root) if not use_kg else None,
        "difficulty": difficulty,
        "max_turns": max_turns,
        "parallel_disorders": parallel_disorders,
        "run_dir": run_dir,
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
            # UI(batch 결과 표)는 run 단위로 Pred/Match를 그리므로 runs를 함께 내려준다.
            # 다만 reason/candidates 같은 긴 필드는 표에서 쓰지 않으므로 제외해 응답을 가볍게 유지한다.
            "results": {
                code: {
                    **{k: v for k, v in info.items() if k != "runs"},
                    "runs": [
                        {k: run.get(k) for k in ("run", "final_diagnosis", "correct", "error")
                         if k in run}
                        for run in (info.get("runs") or [])
                    ],
                }
                for code, info in _batch_state["results"].items()
            },
        }
    return jsonify(snapshot)


@app.route("/simulate") # start simulation
def simulate(): # prompts loading
    # 단건 실행도 배치와 같은 run 폴더 규칙을 따른다:
    #   saved/run_single_<날짜>/{logs,results,analysis}/<patient>/<judge>/<doctor>/
    # analysis는 폴더만 만들어 두고 비워 둔다 — 단건은 화면에서 바로 확인하는 용도이고,
    # 필요하면 나중에 single 결과를 모아 eval/reporting을 따로 돌린다.
    from utils.paths import artifact_dirs, ensure_run_root

    ensure_run_root("single")
    single_run_dir = get_run_dir()
    single_results_dir, single_logs_dir, _ = artifact_dirs(single_run_dir, mode="single")
    single_logs_dir.mkdir(parents=True, exist_ok=True)
    single_results_dir.mkdir(parents=True, exist_ok=True)

    case_id = _single_case_id()
    txt_log_path = single_logs_dir / f"{case_id}.txt"
    json_log_path = single_logs_dir / f"{case_id}.json"
    result_json_path = single_results_dir / f"{case_id}_result.json"
    set_log_path(txt_log_path)

    # doctor.py의 저장 경로는 모듈 로드 시점(배치 기준)에 고정되어 있다. None으로 두어
    # 단건이 doctor_memory.json/transcript.json을 따로 남기지 않게 한다 — 두 정보 모두
    # logs/<case>.json 에 이미 들어가고, 배치도 별도 파일을 만들지 않는다.
    doctor.DOCTOR_MEMORY_FILE = None
    doctor.TRANSCRIPT_FILE = None
    print(f"[simulate] case={case_id} → {txt_log_path}", flush=True)
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
                phase="opening",
                turn=0,
                source="doctor.opening_user_message",
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
                    phase="alignment",
                    turn=t,
                    source="patient.build_alignment_messages",
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
                    phase="response",
                    turn=t,
                    source="patient.build_response_messages",
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
                    phase="inference",
                    turn=t,
                    source="doctor.inference_user_payload",
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
                        phase="final",
                        turn=t,
                        source="doctor.final_diagnosis_user_payload",
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
                        "content": doctor.questioning_followup_user_payload(tr_text, candidates),
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
                    phase="followup",
                    turn=t,
                    source="doctor.questioning_followup_user_payload",
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

        # 배치와 동일한 산출물을 남긴다: <case>.json(전사) + <case>_result.json(증상/후보군)
        _persist_single_artifacts(
            case_id, json_log_path, txt_log_path, result_json_path,
            transcript, doctor_memory,
        )

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
