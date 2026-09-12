"""단일 disorder에 대한 배치 시뮬레이션 워커.

app.py의 배치 평가는 disorder마다 이 모듈의 run_disorder()를 별도 프로세스
(ProcessPoolExecutor, spawn)에서 실행한다. patient.py / utils/llm.py는
SYSTEM_PROMPT, 현재 로그 경로 등을 모듈 전역 변수로 관리하므로, 여러 disorder를
같은 프로세스(스레드)에서 동시에 돌리면 서로의 상태를 덮어써 레이스 컨디션이
발생한다. 프로세스를 분리하면 각 disorder가 자신만의 전역 상태 사본을 가지므로
이 문제가 원천적으로 사라진다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


_ICD10_FILE = (
    Path(__file__).resolve().parent
    / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "disorder_icd10.json"
)

_code2id_cache: dict[str, str] | None = None


def _load_code2id() -> dict[str, str]:
    """ICD-10 코드 → disease_id 매핑. eval/evaluate_final_diagnosis.py와 동일 기준."""
    global _code2id_cache
    if _code2id_cache is None:
        mapping: dict[str, str] = {}
        try:
            with open(_ICD10_FILE, encoding="utf-8") as f:
                icd10_data = json.load(f)
            for disease_id, v in icd10_data.items():
                for code in v.get("icd10_accepted_codes") or [v["icd10_code"]]:
                    mapping[code.strip().upper()] = disease_id
        except Exception as e:  # 매핑을 못 읽으면 이름 비교로만 폴백
            print(f"[batch] disorder_icd10.json load failed: {e}", flush=True)
        _code2id_cache = mapping
    return _code2id_cache


def _true_icd10_code(disease_id: str) -> str:
    """disease_id(D001 등)의 정답 ICD-10 코드. 표시용."""
    try:
        with open(_ICD10_FILE, encoding="utf-8") as f:
            return str(json.load(f).get(disease_id, {}).get("icd10_code", ""))
    except Exception:
        return ""


def _diagnosis_matches(final_diag: str, true_name: str, true_code: str = "") -> bool:
    """예측 진단이 정답 질환과 일치하는지 판정.

    doctor는 ICD-10 코드(예: "F90.2")로 답하므로, 코드를 disease_id로 정규화해
    정답 코드(D001 등)와 비교하는 것이 1차 기준이다. 코드로 판정할 수 없을 때만
    질환명 exact match로 폴백한다 (구 형식 로그 호환).
    """
    fd = (final_diag or "").strip()
    if not fd:
        return False

    if true_code:
        predicted_id = _load_code2id().get(fd.upper())
        if predicted_id is not None:
            return predicted_id == true_code

    tn = (true_name or "").lower().strip()
    return bool(tn) and fd.lower() == tn


def _style_suffix() -> str:
    """파일명에 붙일 conversation style 접미사 ('_verbose' 등)."""
    style = _current_conversation_style()
    return f"_{style}" if style else ""


def _current_conversation_style() -> str:
    """현재 patient에 적용된 conversation style (조회 실패 시 빈 문자열)."""
    try:
        import patient
        return patient.current_conversation_style()
    except Exception:
        return ""


def _make_symptom_diagnosis_runner(label: str):
    """txt 로그 → *_result.json(증상 추출 + KG 후보군). eval/* 가 이 파일을 읽는다."""
    sd_cache: list = []

    def _load_symptom_diagnosis():
        """eval/symptom_diagnosis.py 를 파일 경로로 직접 로드한다.

        평범하게 `import eval.symptom_diagnosis` 를 쓰면 안 되는 이유:
        patient.py의 KG 빌더(_build_system_prompt_from_kg)가 mentalbench/scripts 를
        sys.path 맨 앞에 넣고 되돌리지 않는데, 그 디렉터리에 eval.py 라는 무관한
        모듈이 있다. 그래서 KG를 한 번 띄운 프로세스에서는 `import eval...` 이
        프로젝트의 eval/ 패키지 대신 mentalbench/scripts/eval.py 를 집어
        ModuleNotFoundError: No module named 'api_keys' 로 죽는다.
        여기서는 고유 이름으로 로드해 sys.modules['eval'] 을 건드리지 않는다.
        """
        import importlib.util

        module_name = "_ms_eval_symptom_diagnosis"
        cached = sys.modules.get(module_name)
        if cached is not None:
            return cached
        path = Path(__file__).resolve().parent / "eval" / "symptom_diagnosis.py"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def _ensure_sd() -> tuple:
        if not sd_cache:
            sd = _load_symptom_diagnosis()
            sd_cache.extend([sd, sd.load_all_symptoms(), sd.load_diagnostic_criteria()])
        return sd_cache[0], sd_cache[1], sd_cache[2]

    def _run(txt_path: Path, out_path: Path) -> None:
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
                print(f"[batch:{label}] symptom_diagnosis → {out_path.name}", flush=True)
        except Exception as _e:
            print(f"[batch:{label}] symptom_diagnosis failed ({txt_path.stem}): {_e}", flush=True)

    return _run


def _run_case_group(
    label: str,
    case_id_fn: Any,
    n_runs: int,
    setup_fn: Any,
    true_name: str,
    true_code: str,
    max_turns: int,
    logs_dir: str,
    results_dir: str,
    extra_meta: dict[str, Any] | None = None,
    progress_queue: Any = None,
) -> tuple[int, list[dict]]:
    """한 그룹(질환 또는 프로필 파일)에 대해 n_runs회 시뮬레이션을 순차 실행.

    KG 모드와 프로필 모드의 유일한 차이는 setup_fn(환자 준비)과 case_id_fn(파일명)
    뿐이므로, 그 둘만 주입받고 나머지(스킵 판정·로그 기록·채점·증상추출)는 공유한다.

    Returns: (정답 수, run 단위 로그 리스트)
    """
    from simulation_core import run_interview_simulation
    from utils.llm import set_log_path

    logs_path = Path(logs_dir)
    results_path = Path(results_dir)
    logs_path.mkdir(parents=True, exist_ok=True)
    results_path.mkdir(parents=True, exist_ok=True)
    run_symptom_diagnosis = _make_symptom_diagnosis_runner(label)

    def _report(run_idx: int) -> None:
        if progress_queue is None:
            return
        try:
            progress_queue.put({"code": label, "run": run_idx, "total_runs": n_runs})
        except Exception:
            pass

    correct = 0
    runs_log: list[dict] = []

    for run_idx in range(1, n_runs + 1):
        case_id = case_id_fn(run_idx)
        json_log_path = logs_path / f"{case_id}.json"
        txt_log_path = logs_path / f"{case_id}.txt"
        result_json_path = results_path / f"{case_id}_result.json"

        has_json_log = json_log_path.exists()
        has_result = result_json_path.exists()

        # ── Skip 조건: 대화가 완주된 흔적(json 로그)이나 결과가 이미 있으면 재실행하지 않는다
        if has_json_log or has_result:
            if has_json_log and not has_result:
                # 증상추출 로그를 이 케이스 파일에 이어 붙인다 (기존 대화 로그 보존).
                set_log_path(txt_log_path, truncate=False)
                run_symptom_diagnosis(txt_log_path, result_json_path)

            final_diag_skip, is_correct_skip = "", False
            if has_json_log:
                try:
                    existing = json.loads(json_log_path.read_text(encoding="utf-8"))
                    final_diag_skip = existing.get("final_diagnosis", "")
                    is_correct_skip = _diagnosis_matches(final_diag_skip, true_name, true_code)
                    if is_correct_skip:
                        correct += 1
                except Exception:
                    pass

            status = (
                "log+result" if (has_json_log and has_result) else
                "log→result" if has_json_log else
                "result_only"
            )
            print(f"[batch:{label}] run {run_idx}: skip ({status})", flush=True)
            runs_log.append({
                "run": run_idx,
                "final_diagnosis": final_diag_skip,
                "correct": is_correct_skip,
                "skipped": True,
            })
            _report(run_idx)
            continue

        # ── 둘 다 없음 → 시뮬레이션 실행 ────────────────────────────────
        set_log_path(txt_log_path)

        try:
            patient_system = setup_fn()
        except Exception as e:
            print(f"[batch:{label}] patient setup failed run {run_idx}: {e}", flush=True)
            runs_log.append({"run": run_idx, "error": f"patient setup failed: {e}", "correct": False})
            _report(run_idx)
            continue

        try:
            result = run_interview_simulation(
                patient_system=patient_system,
                max_turns=max_turns,
                verbose=False,
            )
            mem = result["doctor_memory"]
            fd = mem.get("final_diagnosis") or {}
            final_diag = fd.get("diagnosis", "")
            is_correct = _diagnosis_matches(final_diag, true_name, true_code)
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

            json_log_data = {
                "run": run_idx,
                "conversation_style": _current_conversation_style(),
                "closed_at_patient_turn": result.get("closed_at_patient_turn"),
                "final_diagnosis": final_diag,
                "is_correct": is_correct,
                "transcript": [
                    {"role": r, "content": c}
                    for r, c in result.get("transcript", [])
                ],
                "doctor_memory": mem,
            }
            json_log_data.update(extra_meta or {})
            json_log_path.write_text(
                json.dumps(json_log_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            print(
                f"[batch:{label}] run {run_idx}: {final_diag!r} "
                f"→ {'✓' if is_correct else '✗'}  (true={true_name!r})",
                flush=True,
            )

            run_symptom_diagnosis(txt_log_path, result_json_path)

        except Exception as e:
            print(f"[batch:{label}] simulation error run {run_idx}: {e}", flush=True)
            runs_log.append({"run": run_idx, "error": str(e), "correct": False})

        _report(run_idx)

    return correct, runs_log


def run_disorder(
    code: str,
    true_name: str,
    runs_per_disorder: int,
    difficulty: str,
    max_turns: int,
    logs_dir: str,
    results_dir: str,
    progress_queue: Any = None,
) -> dict[str, Any]:
    """KG 모드: 하나의 disorder를 runs_per_disorder회 시뮬레이션한다.

    환자 프로필은 매 회차 KnowledgeGraph에서 즉석 생성된다.
    app.py의 _batch_state["results"][code]와 동일한 형태의 dict를 반환한다.
    """
    import patient

    def _setup() -> str:
        patient.reinitialize(
            disease_code=code,
            difficulty_level=difficulty,
            use_knowledge_graph=True,
        )
        return patient.SYSTEM_PROMPT

    style_suffix = _style_suffix()
    correct, runs_log = _run_case_group(
        label=code,
        case_id_fn=lambda i: f"{code}_{i}{style_suffix}",
        n_runs=runs_per_disorder,
        setup_fn=_setup,
        true_name=true_name,
        true_code=code,
        max_turns=max_turns,
        logs_dir=logs_dir,
        results_dir=results_dir,
        extra_meta={"disease_code": code},
        progress_queue=progress_queue,
    )

    acc = correct / runs_per_disorder if runs_per_disorder else 0.0
    return {
        "disease_name": true_name,
        "disease_code": code,
        "icd10_code": _true_icd10_code(code),  # 표시용 정답 코드 (판정은 accepted_codes 기준)
        "correct": correct,
        "total": runs_per_disorder,
        "accuracy": round(acc, 4),
        "runs": runs_log,
    }


def run_profile(
    profile_path: str,
    true_name: str,
    disease_code: str,
    runs_per_profile: int,
    max_turns: int,
    logs_dir: str,
    results_dir: str,
    progress_queue: Any = None,
) -> dict[str, Any]:
    """프로필 모드: 미리 생성된 프로필 JSON 하나를 runs_per_profile회 시뮬레이션한다.

    KG에서 환자를 즉석 생성하는 대신 파일의 증상 프로필을 그대로 쓴다.
    runs_per_profile=1이면 파일명이 '<profile_id>.json' 이 되어 기존 산출물 및
    script/run_profile_batch.py 와 호환된다.
    """
    import patient

    profile_p = Path(profile_path)
    profile_id = profile_p.stem

    def _setup() -> str:
        patient.set_symptom_profile_path(profile_p)
        return patient.SYSTEM_PROMPT

    style_suffix = _style_suffix()

    def _case_id(i: int) -> str:
        base = profile_id if runs_per_profile == 1 else f"{profile_id}_{i}"
        return f"{base}{style_suffix}"

    correct, runs_log = _run_case_group(
        label=profile_id,
        case_id_fn=_case_id,
        n_runs=runs_per_profile,
        setup_fn=_setup,
        true_name=true_name,
        true_code=disease_code,
        max_turns=max_turns,
        logs_dir=logs_dir,
        results_dir=results_dir,
        extra_meta={
            "disease_code": disease_code,
            "profile_id": profile_id,
            "profile_path": str(profile_p),
        },
        progress_queue=progress_queue,
    )

    acc = correct / runs_per_profile if runs_per_profile else 0.0
    return {
        "disease_name": true_name,
        "disease_code": disease_code,
        "profile_id": profile_id,
        "icd10_code": _true_icd10_code(disease_code),
        "correct": correct,
        "total": runs_per_profile,
        "accuracy": round(acc, 4),
        "runs": runs_log,
    }
