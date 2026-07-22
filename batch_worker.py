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
from pathlib import Path
from typing import Any


def _diagnosis_matches(final_diag: str, true_name: str) -> bool:
    """정답 질환명과 예측 진단명이 정확히 일치하는지 비교 (대소문자 무시, exact match)."""
    fd = (final_diag or "").lower().strip()
    tn = (true_name or "").lower().strip()
    if not fd or not tn:
        return False
    return fd == tn


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
    """단일 disorder에 대해 runs_per_disorder회 시뮬레이션을 순차 실행하고
    app.py의 _batch_state["results"][code]와 동일한 형태의 dict를 반환한다."""
    import patient
    from simulation_core import run_interview_simulation
    from utils.llm import set_log_path

    logs_path = Path(logs_dir)
    results_path = Path(results_dir)

    sd_cache: list = []

    def _ensure_sd() -> tuple:
        if not sd_cache:
            import eval.symptom_diagnosis as sd
            sd_cache.extend([sd, sd.load_all_symptoms(), sd.load_diagnostic_criteria()])
        return sd_cache[0], sd_cache[1], sd_cache[2]

    def _run_symptom_diagnosis(txt_path: Path, out_path: Path) -> None:
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
                print(f"[batch:{code}] symptom_diagnosis → {out_path.name}", flush=True)
        except Exception as _e:
            print(f"[batch:{code}] symptom_diagnosis failed ({txt_path.stem}): {_e}", flush=True)

    def _report(run_idx: int) -> None:
        if progress_queue is None:
            return
        try:
            progress_queue.put({"code": code, "run": run_idx, "total_runs": runs_per_disorder})
        except Exception:
            pass

    correct = 0
    runs_log: list[dict] = []

    for run_idx in range(1, runs_per_disorder + 1):
        json_log_path = logs_path / f"{code}_{run_idx}.json"
        txt_log_path = logs_path / f"{code}_{run_idx}.txt"
        result_json_path = results_path / f"{code}_{run_idx}_result.json"

        has_json_log = json_log_path.exists()
        has_result = result_json_path.exists()

        # ── Skip 조건 ────────────────────────────────────────────────────
        if has_json_log or has_result:
            if has_json_log and not has_result:
                _run_symptom_diagnosis(txt_log_path, result_json_path)

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
            print(f"[batch:{code}] run {run_idx}: skip ({status})", flush=True)
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
            patient.reinitialize(
                disease_code=code,
                difficulty_level=difficulty,
                use_knowledge_graph=True,
            )
            patient_system = patient.SYSTEM_PROMPT
        except Exception as e:
            print(f"[batch:{code}] patient reinit failed run {run_idx}: {e}", flush=True)
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
                f"[batch:{code}] run {run_idx}: {final_diag!r} "
                f"→ {'✓' if is_correct else '✗'}  (true={true_name!r})",
                flush=True,
            )

            _run_symptom_diagnosis(txt_log_path, result_json_path)

        except Exception as e:
            print(f"[batch:{code}] simulation error run {run_idx}: {e}", flush=True)
            runs_log.append({"run": run_idx, "error": str(e), "correct": False})

        _report(run_idx)

    acc = correct / runs_per_disorder if runs_per_disorder else 0.0
    return {
        "disease_name": true_name,
        "correct": correct,
        "total": runs_per_disorder,
        "accuracy": round(acc, 4),
        "runs": runs_log,
    }
