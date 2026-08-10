"""Split add_stressor's per-profile files (symptom + a list of 3 patients) into
one file per persona, organized by disease code — the pristine source that
06/07_generate_*manifestation*.py read from and never overwrite.

Input:  add_stressor/<difficulty>/<disease>_S<NNN>.json
        { "symptom": {...}, "patient": [ {persona1}, {persona2}, {persona3} ] }

Output: add_manifestation/split_patients/<difficulty>/<disease>/<disease>_S<NNN>_P<NNN>.json  (one per persona)
        { "symptom": {...}, "patient": {persona} }

07_generate_manifestation.py and 08_generate_additional_manifestation.py read from
here and write their enriched result to the mirrored path under add_manifestation/
(one level up), so this folder always stays exactly what 05 produced.

Usage:
    python 06_split_patients.py            # difficulty: low
    python 06_split_patients.py low medium high
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
STRESSOR_ROOT = SCRIPT_DIR / "add_stressor"
MANIFESTATION_ROOT = SCRIPT_DIR / "add_manifestation"
SPLIT_ROOT = MANIFESTATION_ROOT / "split_patients"


def process_difficulty(difficulty: str) -> None:
    src_dir = STRESSOR_ROOT / difficulty
    if not src_dir.is_dir():
        raise FileNotFoundError(f"No add_stressor directory for difficulty={difficulty!r}: {src_dir}")

    src_files = sorted(path for path in src_dir.glob("*.json") if not path.name.endswith("_result.json"))
    written = 0

    for src_path in src_files:
        with open(src_path, encoding="utf-8") as f:
            data = json.load(f)

        symptom = data["symptom"]
        patients = data["patient"]
        disease_code = symptom.get("disease_code") or src_path.stem.split("_")[0]

        out_dir = SPLIT_ROOT / difficulty / disease_code
        out_dir.mkdir(parents=True, exist_ok=True)

        for idx, patient in enumerate(patients, start=1):
            out_path = out_dir / f"{src_path.stem}_P{idx:03d}.json"
            payload = {"symptom": symptom, "patient": patient}
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.write("\n")
            written += 1

    print(f"[{difficulty}] split {len(src_files)} profiles -> {written} persona files under {SPLIT_ROOT / difficulty}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "difficulties", nargs="*", default=["low"], help="Difficulty levels to process (default: low)."
    )
    args = parser.parse_args()
    for difficulty in args.difficulties:
        process_difficulty(difficulty)


if __name__ == "__main__":
    main()
