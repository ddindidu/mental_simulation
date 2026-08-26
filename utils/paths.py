"""프로젝트 루트 및 실행 산출물 경로.

산출물은 실행 단위(run)로 묶여 saved/ 아래에 저장된다:

    saved/
      run_batch_20260820/{logs,results,analysis}/<patient>/<judge>/<doctor>/...
      run_single_20260820/{logs,results,analysis}/<patient>/<judge>/<doctor>/...
      latest -> run_batch_20260820

run 폴더는 날짜 단위이므로 같은 날 재실행하면 같은 폴더에 덮어쓴다.
파일명이 프로필 ID 기반이고 하위 경로가 모델별로 갈리므로,
같은 날 서로 다른 프로필/모델을 돌린 결과는 서로 충돌하지 않는다.

환경변수:
  MS_RUN_MODE : "batch"(기본) | "single" — 오늘 날짜로 새 run 폴더를 정한다.
  MS_RUN      : run 폴더를 직접 지정(예: "run_batch_20260819", "latest").
                절대경로도 허용. 지정 시 MS_RUN_MODE는 무시된다.

eval/reporting은 새 run을 만들지 않고 이미 있는 run에 붙어야 하므로,
과거 결과를 평가할 때는 MS_RUN으로 대상 run을 명시한다.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
PROFILES_DIR = DATA_DIR / "profiles"

SAVED_ROOT = PROJECT_ROOT / "saved"
LATEST_LINK = SAVED_ROOT / "latest"

RUN_MODES = ("batch", "single")
DEFAULT_RUN_MODE = "batch"


def run_dir_name(mode: str, day: str | None = None) -> str:
    """'run_batch_20260820' 형태의 run 폴더 이름."""
    if mode not in RUN_MODES:
        raise ValueError(f"Unknown run mode: {mode!r} (expected one of {RUN_MODES})")
    return f"run_{mode}_{day or datetime.now().strftime('%Y%m%d')}"


def get_run_mode() -> str:
    mode = os.getenv("MS_RUN_MODE", DEFAULT_RUN_MODE).strip().lower()
    return mode if mode in RUN_MODES else DEFAULT_RUN_MODE


def resolve_run_root() -> Path:
    """MS_RUN이 있으면 그 run, 없으면 오늘 날짜의 run 폴더."""
def resolve_run_root(mode: str | None = None) -> Path:
    """mode('batch'|'single')에 해당하는 run 폴더. mode 생략 시 MS_RUN_MODE.

    한 프로세스(app.py)가 배치와 단건을 모두 다루므로, 모듈 로드 시점에 하나로
    고정하지 않고 호출 시점에 모드별로 계산한다. MS_RUN이 지정돼 있으면 모드와
    무관하게 그 폴더가 우선한다 (과거 run 재평가용).
    """
    explicit = os.getenv("MS_RUN", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_absolute() else SAVED_ROOT / path
    return SAVED_ROOT / run_dir_name(mode or get_run_mode())


RUN_ROOT = resolve_run_root()

LOGS_ROOT = RUN_ROOT / "logs"
RESULTS_ROOT = RUN_ROOT / "results"
ANALYSIS_ROOT = RUN_ROOT / "analysis"


def ensure_run_root(mode: str | None = None) -> Path:
    """run 폴더와 logs/results/analysis를 만들고 saved/latest를 갱신한다.

    결과를 쓰는 쪽(시뮬레이션 실행 진입점)에서만 호출한다.
    """
    root = resolve_run_root(mode)
    for name in ("logs", "results", "analysis"):
        (root / name).mkdir(parents=True, exist_ok=True)
    _update_latest_link(root)
    return root


def _update_latest_link(root: Path) -> None:
    try:
        if LATEST_LINK.is_symlink() or LATEST_LINK.exists():
            if LATEST_LINK.is_symlink():
                LATEST_LINK.unlink()
            else:
                return  # 심링크가 아닌 실제 폴더면 건드리지 않는다
        LATEST_LINK.symlink_to(root.name)
    except OSError:
        pass  # 심링크를 못 만드는 환경이면 조용히 넘어간다


def artifact_dirs(run_dir: str | Path = "", mode: str | None = None) -> tuple[Path, Path, Path]:
    """run_dir('<patient>/<judge>/<doctor>')에 대한 (results, logs, analysis)."""
    root = resolve_run_root(mode)
    return (
        root / "results" / run_dir,
        root / "logs" / run_dir,
        root / "analysis" / run_dir,
    )


# 대화형/CLI 시뮬레이션이 transcript.json·doctor_memory.json을 두는 위치.
RESULTS_DIR = RESULTS_ROOT

DEFAULT_SYMPTOM_PROFILE_PATH = PROFILES_DIR / "symptom_profile.json"
DEFAULT_DOCTOR_MEMORY_PATH = RESULTS_DIR / "doctor_memory.json"
DEFAULT_TRANSCRIPT_PATH = RESULTS_DIR / "transcript.json"
