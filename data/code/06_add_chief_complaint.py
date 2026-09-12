"""Add the rule-based case fields to every merged profile from 05_merge_symptom_patient.py.

04 only writes what the model has to compose (stressor_event / severity / stressor). The
two remaining patient fields need no model at all, so they are filled in here:

  * demographics — assembled from the persona columns the merge step carried through, and
    replacing them: the later stages only ever need this one-line summary rather than the
    full persona row.
  * chief_complaint_symptom_code — drawn at random from the profile's symptoms, minus the
    ones a clinician reviewer ruled out as a chief complaint, seeded off the profile name so
    a re-run reproduces the same draw. Random rather than "whichever symptom fits best",
    because letting a model choose collapses onto the same few universal symptoms and
    flattens the doctor's reasoning path.

Only the code is assigned here. The chief-complaint utterance is written later, alongside
the symptom manifestations, so that it comes out of the manifestation of this very symptom
rather than having to be kept consistent with a sentence written earlier.

Reads  add_stressor/<difficulty>/<disease>_S<NNN>.json
       chief_complaint_exclusions.json
Writes add_chief_complaint/<difficulty>/<disease>_S<NNN>.json

Usage:
    python 06_add_chief_complaint.py            # difficulty: low
    python 06_add_chief_complaint.py low medium high
    python 06_add_chief_complaint.py low --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
STRESSOR_ROOT = SCRIPT_DIR / "add_stressor"
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "add_chief_complaint"
DEFAULT_EXCLUSIONS_PATH = SCRIPT_DIR / "chief_complaint_exclusions.json"
DEFAULT_SEED = 42

PERSONA_FIELDS = ("sex", "age", "occupation", "education_level")

PATIENT_FIELDS = (
    "persona_uuid",
    "demographics",
    "stressor_event",
    "severity",
    "stressor",
    "chief_complaint_symptom_code",
)


def build_demographics(patient: dict) -> str:
    """The one-line persona summary the manifestation stage works from."""
    return " / ".join(str(patient.get(field, "")).strip() for field in PERSONA_FIELDS)


def load_exclusions(path: Path) -> set[str]:
    """Symptom codes a clinician reviewer ruled out as a chief complaint.

    Codes are global across diseases (S001-S084 are shared by whichever disorders list
    them), so this is a single flat list rather than a per-disease mapping. A missing file
    means no exclusions.
    """
    if not path.is_file():
        print(f"[warn] no exclusion file at {path.name}; every symptom stays eligible.")
        return set()

    with open(path, encoding="utf-8") as f:
        return set(json.load(f).get("excluded_symptom_codes") or [])


def symptom_codes(symptom: dict, excluded: set[str]) -> list[str]:
    """The profile's symptoms that may serve as a chief complaint.

    Some profiles carry only one or two symptoms, so an exclusion can empty the pool
    entirely; fall back to the full set rather than leaving the patients without a chief
    complaint, and say so.
    """
    sampled = symptom.get("sampled_features") or {}
    codes = list((sampled.get("sampled_symptoms_descriptions") or {}).keys())
    eligible = [code for code in codes if code not in excluded]
    if not eligible:
        print(
            f"[warn] {symptom.get('disease_code')}: every symptom is excluded "
            f"({sorted(set(codes) & excluded)}); falling back to the full symptom set."
        )
        return codes
    return eligible


def assign_chief_complaint_codes(rng: random.Random, codes: list[str], count: int) -> list[str]:
    """One symptom per patient, drawn uniformly and without replacement where possible.

    Profiles carry anywhere from one to fifteen symptoms, so a profile with fewer symptoms
    than patients simply reuses codes instead of failing.
    """
    assigned: list[str] = []
    while len(assigned) < count:
        chunk = codes[:]
        rng.shuffle(chunk)
        assigned.extend(chunk[: count - len(assigned)])
    return assigned


def process_profile(src_path: Path, difficulty: str, output_root: Path, seed: int, excluded: set[str]) -> bool:
    with open(src_path, encoding="utf-8") as f:
        data = json.load(f)

    symptom = data["symptom"]
    patients = data.get("patient", [])
    codes = symptom_codes(symptom, excluded)
    if not codes:
        print(f"[warn] {src_path.stem} has no symptoms to draw a chief complaint from, skipping.")
        return False

    rng = random.Random(f"{seed}:{difficulty}/{src_path.stem}")
    chief_complaint_codes = assign_chief_complaint_codes(rng, codes, len(patients))

    enriched = []
    for patient, code in zip(patients, chief_complaint_codes):
        patient["demographics"] = build_demographics(patient)
        patient["chief_complaint_symptom_code"] = code
        enriched.append({field: patient.get(field) for field in PATIENT_FIELDS})

    data["patient"] = enriched
    data["chief_complaint_seed"] = seed
    data["chief_complaint_candidates"] = codes

    out_path = output_root / difficulty / src_path.name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return True


def process_difficulty(difficulty: str, output_root: Path, seed: int, excluded: set[str]) -> None:
    src_dir = STRESSOR_ROOT / difficulty
    if not src_dir.is_dir():
        raise FileNotFoundError(f"No add_stressor directory for difficulty={difficulty!r}: {src_dir}")

    src_files = sorted(path for path in src_dir.glob("*.json") if not path.name.endswith("_result.json"))
    if not src_files:
        print(f"[{difficulty}] no merged profiles found in {src_dir}, skipping.")
        return

    written = sum(process_profile(path, difficulty, output_root, seed, excluded) for path in src_files)
    print(f"[{difficulty}] wrote {written}/{len(src_files)} files -> {output_root / difficulty}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "difficulties", nargs="*", default=["low"], help="Difficulty levels to process (default: low)."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Where to write the enriched profiles (default: {DEFAULT_OUTPUT_ROOT.name}/).",
    )
    parser.add_argument(
        "--exclusions",
        type=Path,
        default=DEFAULT_EXCLUSIONS_PATH,
        help=f"JSON file listing symptom codes that cannot be a chief complaint "
        f"(default: {DEFAULT_EXCLUSIONS_PATH.name}; no exclusions when the file is absent).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Seed for the chief-complaint draw (default: {DEFAULT_SEED}). Combined with the profile "
        f"name, so each profile draws independently but reproducibly.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    excluded = load_exclusions(args.exclusions)
    print(f"{len(excluded)} symptom codes excluded from chief-complaint selection.")
    for difficulty in args.difficulties:
        process_difficulty(difficulty, args.output_root, args.seed, excluded)


if __name__ == "__main__":
    main()
