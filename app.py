import json
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
from utils.llm import rotate_log_file
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
        doctor_inference_html=system_prompt_to_html(doctor.get_inference_system_prompt()),
        doctor_questioning_html=system_prompt_to_html(
            doctor.get_questioning_system_prompt(MAX_TURNS, [])
        ),
        doctor_final_html=system_prompt_to_html(doctor.get_final_diagnosis_system_prompt()),
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


def _diagnosis_matches(final_diag: str, true_name: str) -> bool:
    """정답 질환명과 예측 진단명이 정확히 일치하는지 비교 (대소문자 무시, exact match)."""
    fd = (final_diag or "").lower().strip()
    tn = (true_name or "").lower().strip()
    if not fd or not tn:
        return False
    return fd == tn


def _run_eval_pipeline() -> None:
    """배치 완료 후 symptom_diagnosis → evaluate_* 파이프라인을 순서대로 실행한다.

    실행 순서 (의존성 순):
      1. symptom_diagnosis     → D{code}_{n}_result.json, summary.json
      2. evaluate_final_diagnosis → final_diagnosis_eval.txt
      3. evaluate_turns        → turn_eval.json + PNG (non-strict)
      4. evaluate_turns_strict → turn_eval_strict.json + PNG (LLM 호출)
    """
    import traceback as _tb
    from utils.paths import PROJECT_ROOT

    # 파이프라인 LLM 호출(symptom_diagnosis judge 호출 등)이
    # 마지막 시뮬레이션 로그 파일에 섞이지 않도록 별도 로그로 분리
    set_log_path(PROJECT_ROOT / "results" / get_run_dir() / "_pipeline_llm.log")

    print("[pipeline] Starting post-batch evaluation pipeline...", flush=True)
    print(f"[pipeline] logs dir  : {PROJECT_ROOT / 'logs' / get_run_dir()}", flush=True)
    print(f"[pipeline] results dir: {PROJECT_ROOT / 'results' / get_run_dir()}", flush=True)

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
        sd = _load("symptom_diagnosis")
        sd.main()
    except Exception as _e:
        print(f"[pipeline] symptom_diagnosis failed: {_e}", flush=True)
        _tb.print_exc()

    with _batch_lock:
        _batch_state["current"] = "[pipeline] final diagnosis eval"
    try:
        efd = _load("evaluate_final_diagnosis")
        efd.main()
    except SystemExit:
        print("[pipeline] evaluate_final_diagnosis: no log files, skipping.", flush=True)
    except Exception as _e:
        print(f"[pipeline] evaluate_final_diagnosis failed: {_e}", flush=True)
        _tb.print_exc()

    with _batch_lock:
        _batch_state["current"] = "[pipeline] turn-level eval (non-strict)"
    try:
        et = _load("evaluate_turns")
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
        ets = _load("evaluate_turns_strict")
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
        ee = _load("evaluate_efficiency")
        ee.evaluate()
    except SystemExit:
        print("[pipeline] evaluate_efficiency: no result files, skipping.", flush=True)
    except Exception as _e:
        print(f"[pipeline] evaluate_efficiency failed: {_e}", flush=True)
        _tb.print_exc()

    with _batch_lock:
        _batch_state["current"] = "[pipeline] question reasonability eval"
    try:
        eq = _load("evaluate_question")
        eq.evaluate()
    except SystemExit:
        print("[pipeline] evaluate_question: no result files, skipping.", flush=True)
    except Exception as _e:
        print(f"[pipeline] evaluate_question failed: {_e}", flush=True)
        _tb.print_exc()

    with _batch_lock:
        _batch_state["current"] = "Done"
    print("[pipeline] All done.", flush=True)


def _run_batch_evaluation(
    disorder_map: dict[str, str],
    runs_per_disorder: int,
    difficulty: str,
    logs_dir: Path,
    acc_path: Path,
) -> None:
    """백그라운드 스레드에서 전체 disorder × N회 시뮬레이션 실행."""
    from simulation_core import run_interview_simulation

    codes = sorted(disorder_map.keys())
    total = len(codes) * runs_per_disorder

    with _batch_lock:
        _batch_state["running"] = True
        _batch_state["total"] = total
        _batch_state["done"] = 0
        _batch_state["results"] = {}
        _batch_state["error"] = None
        _batch_state["format_failures"] = 0

    # symptom_diagnosis 리소스를 배치 내에서 한 번만 로드하는 lazy cache
    _sd_cache: list = []  # [module, all_symptoms, diagnostic_criteria]

    def _ensure_sd() -> tuple:
        if not _sd_cache:
            import importlib as _il, sys as _sys
            name = "symptom_diagnosis"
            mod = _il.reload(_sys.modules[name]) if name in _sys.modules else _il.import_module(name)
            _sd_cache.extend([mod, mod.load_all_symptoms(), mod.load_diagnostic_criteria()])
        return _sd_cache[0], _sd_cache[1], _sd_cache[2]

    def _run_symptom_diagnosis(txt_path: Path, out_path: Path) -> None:
        """시뮬레이션 직후 호출: txt_log → _result.json 즉시 생성."""
        if not txt_path.exists():
            return
        try:
            sd, sd_syms, sd_crit = _ensure_sd()
            sd_result = sd.process_log(txt_path, sd_syms, sd_crit)
            if sd_result is not None:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(
                    json.dumps(sd_result, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                print(f"[batch] symptom_diagnosis → {out_path.name}", flush=True)
        except Exception as _e:
            print(f"[batch] symptom_diagnosis failed ({txt_path.stem}): {_e}", flush=True)

    try:
        for code in codes:
            true_name = disorder_map[code]
            correct = 0
            runs_log: list[dict] = []

            for run_idx in range(1, runs_per_disorder + 1):
                with _batch_lock:
                    _batch_state["current"] = f"{code} run {run_idx}/{runs_per_disorder}"

                json_log_path    = logs_dir / f"{code}_{run_idx}.json"
                txt_log_path     = logs_dir / f"{code}_{run_idx}.txt"
                result_json_path = acc_path.parent / f"{code}_{run_idx}_result.json"

                has_json_log = json_log_path.exists()
                has_result   = result_json_path.exists()

                # ── Skip 조건 ────────────────────────────────────────────
                if has_json_log or has_result:
                    if has_json_log and not has_result:
                        # Case 2: json_log 있고 _result.json 없음 → 즉시 생성
                        _run_symptom_diagnosis(txt_log_path, result_json_path)

                    # final_diag는 json_log에서 읽음
                    final_diag_skip, is_correct_skip = "", False
                    if has_json_log:
                        try:
                            existing = json.loads(json_log_path.read_text(encoding="utf-8"))
                            final_diag_skip = existing.get("final_diagnosis", "")
                            is_correct_skip = _diagnosis_matches(final_diag_skip, true_name)
                            if is_correct_skip:
                                correct += 1
                        except Exception:
                            pass

                    status = (
                        "log+result" if (has_json_log and has_result) else
                        "log→result" if has_json_log else
                        "result_only"
                    )
                    print(f"[batch] {code} run {run_idx}: skip ({status})", flush=True)
                    runs_log.append({
                        "run": run_idx,
                        "final_diagnosis": final_diag_skip,
                        "correct": is_correct_skip,
                        "skipped": True,
                    })
                    with _batch_lock:
                        _batch_state["done"] += 1
                    continue

                # ── Case 4: 둘 다 없음 → 시뮬레이션 실행 ────────────────
                set_log_path(txt_log_path)

                # 환자 프로파일 재생성 (같은 disease, 매번 랜덤 증상)
                try:
                    patient.reinitialize(
                        disease_code=code,
                        difficulty_level=difficulty,
                        use_knowledge_graph=True,
                    )
                    patient_system = patient.SYSTEM_PROMPT
                except Exception as e:
                    print(f"[batch] patient reinit failed {code} run {run_idx}: {e}")
                    with _batch_lock:
                        _batch_state["done"] += 1
                    continue

                # 시뮬레이션 실행
                try:
                    result = run_interview_simulation(
                        patient_system=patient_system,
                        max_turns=MAX_TURNS,
                        verbose=False,
                    )
                    mem = result["doctor_memory"]
                    fd = mem.get("final_diagnosis") or {}
                    final_diag = fd.get("diagnosis", "")
                    is_correct = _diagnosis_matches(final_diag, true_name)
                    if is_correct:
                        correct += 1
                    runs_log.append({
                        "run": run_idx,
                        "final_diagnosis": final_diag,
                        "correct": is_correct,
                        "closed_at_turn": mem.get("closed_at_patient_turn"),
                        "candidates": fd.get("candidates", []),
                        "reason": fd.get("reason", ""),
                    })

                    # 시뮬레이션 결과 JSON 로그 저장
                    json_log_data = {
                        "disease_code": code,
                        "run": run_idx,
                        "closed_at_patient_turn": result.get("closed_at_patient_turn"),
                        "final_diagnosis": final_diag,
                        "is_correct": is_correct,
                        "transcript": [
                            {"role": r, "content": c}
                            for r, c in result.get("transcript", [])
                        ],
                        "doctor_memory": mem,
                    }
                    json_log_path.write_text(
                        json.dumps(json_log_data, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

                    print(
                        f"[batch] {code} run {run_idx}: {final_diag!r} "
                        f"→ {'✓' if is_correct else '✗'}  (true={true_name!r})",
                        flush=True,
                    )

                    # 시뮬레이션 직후 즉시 symptom_diagnosis 실행 → _result.json 생성
                    _run_symptom_diagnosis(txt_log_path, result_json_path)

                except Exception as e:
                    print(f"[batch] simulation error {code} run {run_idx}: {e}", flush=True)
                    runs_log.append({"run": run_idx, "error": str(e), "correct": False})

                with _batch_lock:
                    _batch_state["done"] += 1

            acc = correct / runs_per_disorder if runs_per_disorder else 0.0
            with _batch_lock:
                _batch_state["results"][code] = {
                    "disease_name": true_name,
                    "correct": correct,
                    "total": runs_per_disorder,
                    "accuracy": round(acc, 4),
                    "runs": runs_log,
                }

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

        lines: list[str] = [
            "=" * 60,
            f"Batch Evaluation Results  (difficulty={difficulty}, runs={runs_per_disorder})",
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
      { "runs_per_disorder": 10, "difficulty": "medium" }
    """
    with _batch_lock:
        if _batch_state["running"]:
            return jsonify({"ok": False, "error": "Batch already running"}), 409

    body = request.get_json(force=True) or {}
    runs = int(body.get("runs_per_disorder", 10))
    difficulty = str(body.get("difficulty", "medium")).strip()

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

    from utils.paths import PROJECT_ROOT
    run_dir = get_run_dir()
    logs_dir = PROJECT_ROOT / "logs" / run_dir
    logs_dir.mkdir(parents=True, exist_ok=True)
    acc_path = PROJECT_ROOT / "results" / run_dir / "acc.txt"

    print(f"[batch] run_dir = {run_dir}", flush=True)

    t = threading.Thread(
        target=_run_batch_evaluation,
        args=(disorder_map, runs, difficulty, logs_dir, acc_path),
        daemon=True,
    )
    t.start()

    return jsonify({
        "ok": True,
        "disorders": len(disorder_map),
        "runs_per_disorder": runs,
        "difficulty": difficulty,
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
            "results": {
                code: {k: v for k, v in info.items() if k != "runs"}
                for code, info in _batch_state["results"].items()
            },
        }
    return jsonify(snapshot)


@app.route("/simulate") # start simulation
def simulate(): # prompts loading
    rotate_log_file()  # 시뮬레이션마다 새 loggingN.txt 생성
    patient_system = patient.SYSTEM_PROMPT 
    inference_system = doctor.get_inference_system_prompt()
    final_system = doctor.get_final_diagnosis_system_prompt()
    diag_tokens = get_doctor_diagnosis_max_tokens()
    inf_tokens = get_doctor_inference_max_tokens()
    align_tokens = get_patient_alignment_max_tokens()

    @stream_with_context
    def _gen(): # run simulation
        doctor_memory: dict = doctor.new_doctor_memory() # initializing doctor memory
        patient_hist: list[dict] = [{"role": "system", "content": patient_system}] # initializing patient history
        questioning_hist: list[dict] = [ # initializing questioning history
            {
                "role": "system",
                "content": doctor.get_questioning_system_prompt(MAX_TURNS, [], []),
            }
        ]
        transcript: list[tuple[str, str]] = [] 

        def emit(obj: dict) -> str: 
            return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        yield emit({"event": "start"})
        yield emit({"event": "doctor_memory", "state": doctor_memory})

        try:
            questioning_hist.append({"role": "user", "content": doctor.opening_user_message()})
            _log_llm_history("Doctor LLM (questioning)", "opening", questioning_hist)
            doctor_raw = llm_chat(questioning_hist, role="doctor")
            questioning_hist.append({"role": "assistant", "content": doctor_raw})
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
                patient_msg = llm_chat(resp_messages, role="patient")
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
                inf_raw = llm_chat(inf_messages, max_new_tokens=inf_tokens, role="doctor")
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
                    diagnosis_raw = llm_chat(fin_messages, max_new_tokens=diag_tokens, role="doctor")
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
                asked_questions = [q for role, q in transcript if role == "doctor"]
                questioning_hist[0] = {
                    "role": "system",
                    "content": doctor.get_questioning_system_prompt(
                        MAX_TURNS, candidates, asked_questions
                    ),
                }
                questioning_hist.append(
                    {
                        "role": "user",
                        "content": doctor.questioning_followup_user_payload(
                            patient_msg, tr_text, candidates
                        ),
                    }
                )
                _log_llm_history(
                    "Doctor LLM (questioning)",
                    f"follow-up after turn {t}",
                    questioning_hist,
                )
                doctor_raw = llm_chat(questioning_hist, role="doctor")
                questioning_hist.append({"role": "assistant", "content": doctor_raw})
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
