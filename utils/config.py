from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .paths import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

_DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"


def _resolve_config_path() -> Path:
    """
    MS_CONFIG_PATH lets independent parallel runs each patch/restore their own
    config file instead of racing on the shared config/config.json. Every
    process that reads CONFIG (this module is a singleton import) — including
    ProcessPoolExecutor(spawn) workers and subprocess.run() children, both of
    which inherit the parent's os.environ by default — resolves the same
    isolated path as long as the top-level process set the env var before
    spawning anything downstream.

    See script/run_all_doctors_profiles.py, which sets this per invocation so
    two runs (e.g. different patient/judge model pairs) can execute at the
    same time without corrupting each other's config.
    """
    override = os.environ.get("MS_CONFIG_PATH", "").strip()
    return Path(override) if override else _DEFAULT_CONFIG_PATH


_CONFIG_PATH = _resolve_config_path()

def load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_config()
