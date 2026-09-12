"""Merge each add_persona profile's symptom info with its add_stressor narrative
results into one final combined file.

Reads the narrative-only add_stressor/only_stressor/<difficulty>/*_result.json files
written by 04_generate_stressor.py, then rebuilds
add_stressor/<difficulty>/<disease>_S<NNN>.json as the merged form:

    {
      "symptom": <add_persona's "question" block, verbatim>,
      "patient": [
        {"persona_uuid": ..., "sex": ..., "age": ..., "occupation": ..., "education_level": ...,
         "stressor_event": ..., "severity": ..., "stressor": ...},
        ...
      ]
    }

"patient" entries carry the fields produced by 04_generate_stressor.py plus the few
persona columns 06_add_chief_complaint.py needs to build "demographics" from, so that
step only has to read this one file.

Usage:
    python 06_merge_symptom_patient.py            # difficulty: low
    python 06_merge_symptom_patient.py low medium high
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PERSONA_ROOT = SCRIPT_DIR / "add_persona"
STRESSOR_ROOT = SCRIPT_DIR / "add_stressor"
ONLY_STRESSOR_ROOT = STRESSOR_ROOT / "only_stressor"

NARRATIVE_FIELDS = ("stressor_event", "severity", "stressor")

# Carried through so the chief-complaint step can assemble "demographics" without
# having to re-open the add_persona file.
PERSONA_FIELDS = ("sex", "age", "occupation", "education_level")


def flatten_patient(entry: dict, personas: dict[str, dict]) -> dict:
    narrative = entry.get("narrative", {})
    uuid = entry.get("persona_uuid")
    flat = {"persona_uuid": uuid}
    persona = personas.get(uuid, {})
    for field in PERSONA_FIELDS:
        flat[field] = persona.get(field)
    for field in NARRATIVE_FIELDS:
        flat[field] = narrative.get(field)
    return flat


def process_difficulty(difficulty: str) -> None:
    stressor_dir = STRESSOR_ROOT / difficulty
    persona_dir = PERSONA_ROOT / difficulty
    raw_stressor_dir = ONLY_STRESSOR_ROOT / difficulty

    if not raw_stressor_dir.is_dir():
        raise FileNotFoundError(
            f"No raw add_stressor directory for difficulty={difficulty!r}: {raw_stressor_dir}"
        )
    if not persona_dir.is_dir():
        raise FileNotFoundError(f"No add_persona directory for difficulty={difficulty!r}: {persona_dir}")

    stressor_dir.mkdir(parents=True, exist_ok=True)

    stressor_files = sorted(raw_stressor_dir.glob("*_result.json"))
    if not stressor_files:
        print(f"[{difficulty}] no *_result.json files found in {raw_stressor_dir}, skipping.")
        return

    merged_count = 0
    for stressor_path in stressor_files:
        with open(stressor_path, encoding="utf-8") as f:
            stressor_data = json.load(f)

        base_name = stressor_path.name.removesuffix("_result.json")
        persona_path = persona_dir / f"{base_name}.json"
        if not persona_path.is_file():
            print(f"[warn] no matching add_persona file for {stressor_path.name} (expected {persona_path.name}), skipping merge.")
            continue

        with open(persona_path, encoding="utf-8") as f:
            persona_data = json.load(f)

        symptom = {**persona_data["question"], "disease_info": stressor_data.get("disease_info")}
        personas = {persona.get("uuid"): persona for persona in persona_data.get("info", [])}
        merged = {
            "symptom": symptom,
            "patient": [flatten_patient(entry, personas) for entry in stressor_data.get("results", [])],
        }

        out_path = stressor_dir / f"{base_name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
            f.write("\n")
        merged_count += 1

    print(f"[{difficulty}] merged {merged_count}/{len(stressor_files)} files -> {stressor_dir}")
    print(f"[{difficulty}] raw narrative-only results -> {raw_stressor_dir}")


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
