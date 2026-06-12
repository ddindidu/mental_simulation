"""프로젝트 루트 및 data/ 하위 경로 (app.py·patient.py·doctor.py와 utils/의 공통 상위)."""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
PROFILES_DIR = DATA_DIR / "profiles"
RESULTS_DIR = DATA_DIR / "results"

DEFAULT_SYMPTOM_PROFILE_PATH = PROFILES_DIR / "symptom_profile.json"
DEFAULT_DOCTOR_MEMORY_PATH = RESULTS_DIR / "doctor_memory.json"
DEFAULT_TRANSCRIPT_PATH = RESULTS_DIR / "transcript.json"
