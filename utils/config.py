from __future__ import annotations

import json

from dotenv import load_dotenv

from .paths import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

_CONFIG_PATH = PROJECT_ROOT / "config.json"

def load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_config()
