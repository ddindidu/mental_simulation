"""Strip the option/option_* blocks from mentalbench seed data and save under data/code/option_removed/<difficulty>/.

Source layout (per difficulty):
    mentalbench/resources/features/seed/final/<difficulty>/json/*.json
Each file maps an ordinal key ("0", "1", ...) to an entry containing a
"question" (low/medium) or "question_both"/"question_a"/"question_b" (high)
block plus a matching "option"/"option_*" block. This script keeps every
non-option block untouched and drops the option block(s).

Usage:
    python 01_strip_options.py low
    python 01_strip_options.py low medium high
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_ROOT = PROJECT_ROOT / "mentalbench" / "resources" / "features" / "seed" / "final"
OUTPUT_ROOT = Path(__file__).resolve().parent / "option_removed"


def _is_option_key(key: str) -> bool:
    return key == "option" or key.startswith("option_")


def strip_options(data: dict) -> dict:
    return {
        entry_key: {k: v for k, v in entry.items() if not _is_option_key(k)}
        for entry_key, entry in data.items()
    }


def process_difficulty(difficulty: str) -> None:
    src_dir = SOURCE_ROOT / difficulty / "json"
    if not src_dir.is_dir():
        raise FileNotFoundError(f"No source directory for difficulty={difficulty!r}: {src_dir}")

    dst_dir = OUTPUT_ROOT / difficulty
    dst_dir.mkdir(parents=True, exist_ok=True)

    for src_path in sorted(src_dir.glob("*.json")):
        with open(src_path, encoding="utf-8") as f:
            data = json.load(f)

        cleaned = strip_options(data)

        dst_path = dst_dir / src_path.name
        with open(dst_path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=4, ensure_ascii=False)
            f.write("\n")

        print(f"[{difficulty}] {src_path.name}: {len(cleaned)} entries -> {dst_path.relative_to(PROJECT_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "difficulties",
        nargs="*",
        default=["low"],
        help="Difficulty levels to process (default: low). e.g. low medium high",
    )
    args = parser.parse_args()

    for difficulty in args.difficulties:
        process_difficulty(difficulty)


if __name__ == "__main__":
    main()
