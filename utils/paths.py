"""프로젝트 루트 및 data/ 하위 경로 (app.py·patient.py·doctor.py와 utils/의 공통 상위)."""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
PROFILES_DIR = DATA_DIR / "profiles"
RESULTS_ROOT = PROJECT_ROOT / "results"
SIMULATION_RESULTS_DIR = RESULTS_ROOT / "simulation"
BATCH_RESULTS_DIR = RESULTS_ROOT / "batch"


def batch_artifact_dirs(run_dir: str) -> tuple[Path, Path, Path]:
    """Return sibling results/logs/analysis leaves for a versioned batch run."""
    parts = Path(run_dir).parts
    if len(parts) < 4 or parts[2] != "results":
        raise ValueError(f"Invalid versioned batch run path: {run_dir}")
    run_root = BATCH_RESULTS_DIR / parts[0] / parts[1]
    model_mode_path = Path(*parts[3:])
    return (
        run_root / "results" / model_mode_path,
        run_root / "logs" / model_mode_path,
        run_root / "analysis" / model_mode_path,
    )

# Backward-compatible name used by the interactive/CLI simulation code.
RESULTS_DIR = SIMULATION_RESULTS_DIR

DEFAULT_SYMPTOM_PROFILE_PATH = PROFILES_DIR / "symptom_profile.json"
DEFAULT_DOCTOR_MEMORY_PATH = RESULTS_DIR / "doctor_memory.json"
DEFAULT_TRANSCRIPT_PATH = RESULTS_DIR / "transcript.json"
