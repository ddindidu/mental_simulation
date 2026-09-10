"""Attach pre-sampled NVIDIA Nemotron-Personas-USA rows to symptom profiles.

Reads data/code/option_removed/<difficulty>/<disease>.json (see
01_strip_options.py), whose entries carry irregular original keys (e.g.
"0", "1", "3", "7", "8"), and for each difficulty:

  1. Renumbers each disease's surviving profiles to a stable 1..N sequence
     (sorted by the original numeric key).
  2. Reads the sex/age-stratified CSV produced by 02_sampling_persona.py in
     its existing balanced order.
  3. Assigns `--personas-per-profile` consecutive persona rows to every
     profile in stable difficulty/disease/profile order, without resampling.
  4. Writes one file per profile to data/code/add_persona/<difficulty>/,
     named "<disease_code>_S<renumbered index, zero-padded to 3>.json":

         {
             "question": <unchanged symptom-profile question block>,
             "info": [ {<sampled csv columns...>}, ... ]
         }

Usage:
    python 03_add_persona.py low
    python 03_add_persona.py low --diseases D001
    python 03_add_persona.py low --persona-csv sampled_personas_n345_seed42.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
OPTION_REMOVED_ROOT = SCRIPT_DIR / "option_removed"
OUTPUT_ROOT = SCRIPT_DIR / "add_persona"
DEFAULT_PERSONA_CSV_PATH = SCRIPT_DIR / "sampled_personas_n345_seed42.csv"


def discover_profile_files(difficulty: str) -> list[Path]:
    src_dir = OPTION_REMOVED_ROOT / difficulty
    if not src_dir.is_dir():
        raise FileNotFoundError(f"No option-removed directory for difficulty={difficulty!r}: {src_dir}")
    return sorted(src_dir.glob("*.json"))


def load_and_renumber(path: Path) -> dict[int, dict]:
    """Sort a disease file's original (irregular) keys numerically and remap to 1..N."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    ordered_original_keys = sorted(data.keys(), key=int)
    return {new_idx: data[old_key] for new_idx, old_key in enumerate(ordered_original_keys, start=1)}


def normalize_persona_row(row: dict[str, str]) -> dict:
    """Normalize a sampled CSV row for JSON output."""
    normalized: dict = dict(row)
    normalized.pop("hobbies_and_interests_list", None)
    age = normalized.get("age")
    if age not in (None, ""):
        try:
            normalized["age"] = int(age)
        except ValueError:
            pass
    return normalized


def load_sampled_personas(csv_path: Path, expected_count: int) -> list[dict]:
    """Load exactly the pre-sampled rows needed for the complete stable job list."""
    personas: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            personas.append(normalize_persona_row(row))

    if len(personas) != expected_count:
        raise ValueError(
            f"{csv_path.name} contains {len(personas)} persona rows, "
            f"but the complete profile set needs exactly {expected_count}"
        )

    uuids = [persona.get("uuid") for persona in personas]
    if any(not uuid for uuid in uuids):
        raise ValueError(f"{csv_path.name} contains a missing persona UUID")
    if len(set(uuids)) != len(uuids):
        raise ValueError(f"{csv_path.name} contains duplicate persona UUIDs")
    return personas


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "difficulties",
        nargs="*",
        default=["low"],
        help="Difficulty levels to process (default: low). e.g. low medium high",
    )
    parser.add_argument(
        "-k",
        "--personas-per-profile",
        type=int,
        default=3,
        help="Number of consecutive personas to assign per symptom profile (default: 3).",
    )
    parser.add_argument(
        "--persona-csv",
        type=Path,
        default=DEFAULT_PERSONA_CSV_PATH,
        help=f"Pre-sampled persona CSV (default: {DEFAULT_PERSONA_CSV_PATH.name}).",
    )
    parser.add_argument(
        "--diseases",
        nargs="+",
        default=None,
        help="Only write these disease codes while preserving global assignments. e.g. D001 D002",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.personas_per_profile <= 0:
        raise ValueError("--personas-per-profile must be positive")
    if not args.persona_csv.is_file():
        raise FileNotFoundError(f"Pre-sampled persona CSV not found: {args.persona_csv}")

    # Always build the complete stable job list before filtering which files to
    # write. This keeps D002's rows identical whether it is run alone or in a batch.
    jobs: list[tuple[str, str, int, dict]] = []
    for difficulty in args.difficulties:
        for profile_path in discover_profile_files(difficulty):
            disease_code = profile_path.stem
            for profile_index, entry in load_and_renumber(profile_path).items():
                jobs.append((difficulty, disease_code, profile_index, entry))

    if not jobs:
        print("No profiles found for the requested difficulties.")
        return

    total_needed = len(jobs) * args.personas_per_profile
    print(
        f"Loading {total_needed} pre-sampled personas "
        f"({args.personas_per_profile} x {len(jobs)} profiles) from {args.persona_csv.name} ..."
    )
    personas = load_sampled_personas(args.persona_csv, total_needed)

    requested_diseases = set(args.diseases or [])
    known_diseases = {disease_code for _, disease_code, _, _ in jobs}
    unknown_diseases = requested_diseases - known_diseases
    if unknown_diseases:
        raise ValueError(f"Unknown disease code(s): {', '.join(sorted(unknown_diseases))}")

    # Filtering affects only which JSON files are written, never the stable
    # persona-to-profile mapping derived from the complete job list.
    cursor = 0
    written = 0
    for difficulty, disease_code, profile_index, entry in jobs:
        chunk = personas[cursor : cursor + args.personas_per_profile]
        cursor += args.personas_per_profile

        if requested_diseases and disease_code not in requested_diseases:
            continue

        out_dir = OUTPUT_ROOT / difficulty
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{disease_code}_S{profile_index:03d}.json"

        payload = {"question": entry["question"], "info": chunk}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
            f.write("\n")
        written += 1

    print(
        f"Wrote {written} profile files "
        f"-> {OUTPUT_ROOT.relative_to(SCRIPT_DIR.parent.parent)}/<difficulty>/"
    )


if __name__ == "__main__":
    main()
