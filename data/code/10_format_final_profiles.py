"""Rebuild the finished profiles into the shape the patient simulator consumes.

09 leaves the case spread over four blocks whose shapes disagree: symptom-level
`manifestation` entries carry name/description/manifestation, while `add_requirements`
entries are bare strings keyed however the model happened to word them. The simulator
treats both the same way — one selectable item, one sentence the patient says — so this
step gives them one shape:

    {
      "clinical_profiles": {disease_code, disease_name, sampled_features},
      "patient_info":      {persona_uuid, demographics, stressor_event, severity, ...},
      "manifestation": {
        "S029":                     {name, description, manifestation},
        "additional_requirement_1": {name, description, manifestation},
        "functional_impairment":    {name, description, manifestation},
        "duration":                 {name, description, manifestation}
      }
    }

`disease_info` is dropped: it is general knowledge about the disorder that the earlier
stages needed to write with, not something this patient can say.

Requirement keys are renumbered to additional_requirement_N, matching what the simulator
already looks for, since the model wrote them inconsistently (sometimes the criterion
text verbatim, sometimes a snake_cased version of it).

Reads  add_requirements/<difficulty>/<disease>/<disease>_S<NNN>_P<NNN>.json
Writes final_profiles/<difficulty>/<disease>/<disease>_S<NNN>_P<NNN>.json

Usage:
    python 10_format_final_profiles.py            # difficulty: low
    python 10_format_final_profiles.py low medium high
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REQUIREMENTS_ROOT = SCRIPT_DIR / "add_requirements"
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "final_profiles"

REQUIREMENT_KEY_PREFIX = "additional_requirement_"


def _tokens(text: object) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", str(text).lower()) if t}


def _match_requirement_key(criterion: str, candidates: list[str]) -> str | None:
    """Find the add_requirements key the model used for this criterion.

    The two are written independently — "Onset prior to age 12 years" comes back as either
    the sentence itself or "onset_prior_to_age_12_years" — so match on shared tokens.
    """
    wanted = _tokens(criterion)
    best, best_score = None, 0
    for key in candidates:
        score = len(wanted & _tokens(key))
        if score > best_score:
            best, best_score = key, score
    return best


def _criterion_text(value: object) -> str:
    if isinstance(value, bool):
        return "required" if value else "not required"
    if isinstance(value, dict):
        for field in ("text", "description", "name", "value"):
            if value.get(field):
                return str(value[field]).strip()
        return ""
    return str(value or "").strip()


def _entry(name: str, description: object, manifestation: object) -> dict | None:
    """One selectable item. Items the model left blank are dropped, not carried as holes."""
    text = str(manifestation or "").strip()
    if not text:
        return None
    return {"name": name, "description": _criterion_text(description), "manifestation": text}


def _label(key: str) -> str:
    return key.replace("_", " ").title()


def build_manifestation(data: dict) -> tuple[dict, list[str]]:
    """Symptom manifestations plus the diagnostic-criteria evidence, in one shape."""
    sampled = (data.get("symptom") or {}).get("sampled_features") or {}
    criteria = sampled.get("sampled_diagnostic_criteria") or {}
    source = data.get("manifestation") or {}
    requirements = dict(data.get("add_requirements") or {})

    out: dict[str, dict] = {}
    dropped: list[str] = []

    descriptions = sampled.get("sampled_symptoms_descriptions") or {}
    for code, entry in source.items():
        if not isinstance(entry, dict):
            continue
        described = descriptions.get(code) or {}
        item = _entry(
            entry.get("name") or described.get("name") or code,
            entry.get("description") or described.get("description"),
            entry.get("manifestation"),
        )
        if item is None:
            dropped.append(code)
            continue
        out[code] = item

    # 요건 키는 모델이 매번 다르게 지어서, 프로필의 요건 순서대로 다시 번호를 매긴다.
    reserved = {"functional_impairment"}
    free = [k for k in requirements if k not in reserved and not k.endswith("duration")]
    for i, criterion in enumerate(criteria.get("additional_requirements") or [], start=1):
        text = _criterion_text(criterion)
        matched = _match_requirement_key(text, free)
        if matched is None:
            dropped.append(f"{REQUIREMENT_KEY_PREFIX}{i}")
            continue
        free.remove(matched)
        item = _entry(f"Additional Requirement {i}", text, requirements.get(matched))
        if item is None:
            dropped.append(f"{REQUIREMENT_KEY_PREFIX}{i}")
            continue
        out[f"{REQUIREMENT_KEY_PREFIX}{i}"] = item

    item = _entry(
        "Functional Impairment",
        criteria.get("functional_impairment_required"),
        requirements.get("functional_impairment"),
    )
    if item is not None:
        out["functional_impairment"] = item
    elif "functional_impairment" in requirements:
        dropped.append("functional_impairment")

    groups = sampled.get("sampled_symptom_groups") or {}
    for key, value in requirements.items():
        if not key.endswith("duration"):
            continue
        if key == "duration":
            described = criteria.get("duration") or next(
                (g.get("duration") for g in groups.values() if g.get("duration")), ""
            )
        else:
            described = (groups.get(key[: -len("_duration")]) or {}).get("duration", "")
        item = _entry(_label(key), described, value)
        if item is None:
            dropped.append(key)
            continue
        out[key] = item

    return out, dropped


def rebuild(data: dict) -> tuple[dict, list[str]]:
    symptom = data.get("symptom") or {}
    manifestation, dropped = build_manifestation(data)
    return (
        {
            "clinical_profiles": {
                "disease_code": symptom.get("disease_code"),
                "disease_name": symptom.get("disease_name"),
                "sampled_features": symptom.get("sampled_features"),
            },
            "patient_info": data.get("patient") or {},
            "manifestation": manifestation,
        },
        dropped,
    )


def process_difficulty(difficulty: str, output_root: Path) -> None:
    src_dir = REQUIREMENTS_ROOT / difficulty
    if not src_dir.is_dir():
        raise FileNotFoundError(f"No add_requirements directory for difficulty={difficulty!r}: {src_dir}")

    src_files = sorted(src_dir.glob("*/*.json"))
    if not src_files:
        print(f"[{difficulty}] no profiles found in {src_dir}, skipping.")
        return

    written = 0
    for src_path in src_files:
        with open(src_path, encoding="utf-8") as f:
            data = json.load(f)

        rebuilt, dropped = rebuild(data)
        if dropped:
            print(f"[warn] {src_path.stem}: dropped empty item(s) {dropped}")

        out_path = output_root / difficulty / src_path.parent.name / src_path.name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rebuilt, f, indent=2, ensure_ascii=False)
            f.write("\n")
        written += 1

    print(f"[{difficulty}] rebuilt {written}/{len(src_files)} profiles -> {output_root / difficulty}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "difficulties", nargs="*", default=["low"], help="Difficulty levels to process (default: low)."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Where to write the rebuilt profiles (default: {DEFAULT_OUTPUT_ROOT.name}/).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for difficulty in args.difficulties:
        process_difficulty(difficulty, args.output_root)


if __name__ == "__main__":
    main()
