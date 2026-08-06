"""Generate manifestation content for additional_requirements and functional_impairment
for one persona file that 07_generate_manifestation.py has already written under
add_manifestation/ (i.e. it already has "symptom", "patient", "manifestation" — read-only
source here, never modified), and write the enriched result (source + "add_requirements")
to the mirrored path under add_requirements/ — a separate folder, not a key stuffed back
into add_manifestation/.

This is a separate, focused call from 07_generate_manifestation.py on purpose — mixing
"one sentence per symptom code" with "pick a functional-impairment domain and justify it"
in a single prompt risks the model dropping items (already observed with symptom-only
prompts once the list got long).

Usage:
    python 08_generate_additional_manifestation.py
    python 08_generate_additional_manifestation.py \
        --profile add_manifestation/low/D001/D001_S004_P001.json \
        --model gpt-5.1 --temperature 0.9
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent  # data/profiles
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # mental_simulation
MANIFESTATION_ROOT = SCRIPT_DIR / "add_manifestation"
REQUIREMENTS_ROOT = SCRIPT_DIR / "add_requirements"
DEFAULT_PROFILE_PATH = MANIFESTATION_ROOT / "low" / "D007" / "D007_S001_P001.json"

load_dotenv(PROJECT_ROOT / ".env")

PROMPT_TEMPLATE = """You are a mental health expert creating realistic clinical cases for a doctor–patient interview simulator.

The patient's symptom manifestations have already been written.
Your task is to generate brief manifestation-style evidence for information that is not captured by the symptom manifestations, including:

(C) additional diagnostic requirements,
(D) functional impairment, and
(E) duration-related evidence.

────────────────────────────
[A. Disease Information]

{{disease_info}}

Disorder: {{disease_name}} ({{disease_code}})

────────────────────────────
[B. Established Patient Case]

Demographics:
{{demographics}}

Stressor category:
{{stressor_category}}

Overall severity:
{{severity}}

Stressor:
{{stressor}}

Chief complaint:
{{chief_complaint}}

────────────────────────────
[B2. Established Symptom Manifestations]
(Reference only)

{{manifestation_block}}

────────────────────────────
[C. Additional Diagnostic Requirements]

{{additional_requirements_block}}

────────────────────────────
[D. Functional Impairment]

Functional impairment required:
{{functional_impairment_required}}

────────────────────────────
[E. Duration Information]

{{duration_items_block}}

────────────────────────────
Writing Guidelines

1. Generate ONE brief manifestation (1–2 sentences maximum) for each item.

2. Use the patient's first-person voice throughout.

3. Additional diagnostic requirements
- Write concrete evidence showing that the requirement is satisfied.
- Ground it in the patient's own history or lived experience.
- Do not simply restate the criterion.
- If there are no additional requirements, return an empty object.

4. Functional impairment
- Describe the real-life consequence of the accumulated symptoms rather than repeating the symptoms themselves.
- Focus on impairment in occupational, academic, social, self-care, or safety domains.
- Keep it brief (1–2 sentences).

5. Duration
There are two kinds of duration:

• duration
    Refers to the overall duration of the disorder.

• <symptom_group>_duration
    Refers only to how long that specific symptom group has been present within the overall illness.

For every duration item:

- Write one brief first-person sentence.
- It is sufficient to mention that the symptoms have been present since a memorable life event, season, job change, or approximate period (e.g., "Ever since the station rebranding...", "It's been going on for about two years now...").
- Do NOT make the duration overly detailed.
- Ensure that symptom-group durations are consistent with the overall duration.

6. Keep everything consistent with the patient's demographics, stressor, severity, and existing manifestations.

7. Do not introduce new symptoms or contradict the established manifestations.

────────────────────────────
Output JSON only.

{
  "additional_requirements": {
    "<requirement>": "<1–2 sentence manifestation>"
  },
  "functional_impairment": "<1–2 sentence manifestation>",
  "<duration key>": "<1–2 sentence manifestation>"
}
"""


def build_duration_items(sampled_features: dict) -> list[tuple[str, str]]:
    """Returns [(key, duration_value), ...] to address: "duration" (overall — falling
    back to the first symptom group's own duration if there's no top-level one) plus a
    "<group>_duration" entry for every OTHER symptom group that has its own explicit
    duration distinct from the overall one (e.g. schizoaffective disorder's psychotic vs.
    depressive episode durations)."""
    criteria = sampled_features.get("sampled_diagnostic_criteria") or {}
    groups = sampled_features.get("sampled_symptom_groups") or {}

    items: list[tuple[str, str]] = []
    overall = criteria.get("duration")
    fallback_group_key = None
    if overall:
        items.append(("duration", overall))
    else:
        for group_key, group in groups.items():
            group_duration = group.get("duration")
            if group_duration:
                items.append(("duration", group_duration))
                fallback_group_key = group_key
                break

    for group_key, group in groups.items():
        if group_key == fallback_group_key:
            continue
        group_duration = group.get("duration")
        if group_duration:
            items.append((f"{group_key}_duration", group_duration))

    return items


def build_duration_items_block(items: list[tuple[str, str]]) -> str:
    if not items:
        return "(none available)"
    return "\n".join(f"- {key}: {value}" for key, value in items)


def extract_additional_requirements(sampled_features: dict) -> list[str]:
    criteria = sampled_features.get("sampled_diagnostic_criteria") or {}
    return criteria.get("additional_requirements") or []


def extract_functional_impairment_required(sampled_features: dict) -> bool:
    criteria = sampled_features.get("sampled_diagnostic_criteria") or {}
    required = criteria.get("functional_impairment_required")
    if required is None:
        for group in (sampled_features.get("sampled_symptom_groups") or {}).values():
            if group.get("functional_impairment_required") is not None:
                required = group.get("functional_impairment_required")
                break
    return bool(required)


def build_additional_requirements_block(requirements: list[str]) -> str:
    if not requirements:
        return "(none for this disorder — return an empty object for additional_requirements)"
    return "\n".join(f"- {r}" for r in requirements)


def build_manifestation_block(manifestation: dict) -> str:
    """Format 06's already-generated per-symptom manifestations (code/name/sentence) as
    reference context — so functional_impairment can build on them instead of repeating
    or contradicting them. Handles a missing/raw-fallback manifestation gracefully."""
    if not manifestation or "raw" in manifestation:
        return "(none available)"
    lines = []
    for code, entry in manifestation.items():
        if isinstance(entry, dict):
            name = entry.get("name", code)
            sentence = entry.get("manifestation", "")
        else:
            name = code
            sentence = entry
        lines.append(f"- {code} {name}: {sentence}")
    return "\n".join(lines)


def build_prompt(symptom: dict, patient: dict, manifestation: dict) -> str:
    sampled_features = symptom["sampled_features"]
    requirements = extract_additional_requirements(sampled_features)
    impairment_required = extract_functional_impairment_required(sampled_features)

    duration_items = build_duration_items(sampled_features)

    mapping = {
        "disease_name": sampled_features.get("disease_name", ""),
        "disease_code": sampled_features.get("disease_code", ""),
        "disease_info": symptom.get("disease_info") or "(not available)",
        "manifestation_block": build_manifestation_block(manifestation),
        "additional_requirements_block": build_additional_requirements_block(requirements),
        "functional_impairment_required": "true" if impairment_required else "false",
        "duration_items_block": build_duration_items_block(duration_items),
        "demographics": patient.get("demographics", ""),
        "stressor_category": patient.get("stressor_category", ""),
        "severity": patient.get("severity", ""),
        "stressor": patient.get("stressor", ""),
        "chief_complaint": patient.get("chief_complaint", ""),
    }
    prompt = PROMPT_TEMPLATE
    for key, value in mapping.items():
        prompt = prompt.replace("{{" + key + "}}", str(value))
    return prompt


def _is_reasoning_style_model(model: str) -> bool:
    m = model.lower()
    return "gpt-5" in m or m.startswith("o1") or m.startswith("o3") or m.startswith("o4")


def call_openai(client, model: str, prompt: str, temperature: float, max_tokens: int) -> str:
    """Chat Completions call. gpt-5-style models take max_completion_tokens instead of
    max_tokens; fall back and swap the kwarg name if the API rejects the first attempt."""
    token_key = "max_completion_tokens" if _is_reasoning_style_model(model) else "max_tokens"
    kw = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        token_key: max_tokens,
    }
    try:
        resp = client.chat.completions.create(**kw)
    except Exception as e:
        err = str(e).lower()
        if "max_completion_tokens" in err or "max_tokens" in err:
            alt_key = "max_tokens" if token_key == "max_completion_tokens" else "max_completion_tokens"
            kw.pop(token_key)
            kw[alt_key] = max_tokens
            resp = client.chat.completions.create(**kw)
        else:
            raise
    return resp.choices[0].message.content


def print_additional_manifestation(result: dict, duration_items: list[tuple[str, str]]) -> None:
    additional = result.get("additional_requirements") or {}
    if additional:
        print("\nadditional_requirements")
        for requirement, sentence in additional.items():
            print(f"- {requirement}")
            print(f"  {sentence}")
    else:
        print("\nadditional_requirements: (none)")

    print("\nfunctional_impairment")
    print(result.get("functional_impairment", "(missing)"))

    for key, _ in duration_items:
        print(f"\n{key}")
        print(result.get(key, "(missing)"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE_PATH,
        help=f"Path to an add_manifestation/<difficulty>/<disease>/<disease>_S<NNN>_P<NNN>.json file already "
        f"processed by 07_generate_manifestation.py (default: {DEFAULT_PROFILE_PATH.name}).",
    )
    parser.add_argument("--model", default="gpt-5.1", help="OpenAI model name (default: gpt-5.1).")
    parser.add_argument("--temperature", type=float, default=0.9, help="Sampling temperature (default: 0.9).")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=800,
        help="Max output tokens (default: 800 — this call only writes a couple of sentences).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Read-only source: the file 06 already wrote (has "symptom", "patient", "manifestation").
    with open(args.profile, encoding="utf-8") as f:
        source_data = json.load(f)

    symptom = source_data["symptom"]
    patient = source_data["patient"]
    manifestation = source_data.get("manifestation", {})

    # Write to the mirrored path under add_requirements/, never back to add_manifestation/.
    # If that output file already exists (e.g. re-run), load it so we merge into it.
    rel_path = args.profile.resolve().relative_to(MANIFESTATION_ROOT.resolve())
    out_path = REQUIREMENTS_ROOT / rel_path
    if out_path.is_file():
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = dict(source_data)

    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    duration_items = build_duration_items(symptom["sampled_features"])

    prompt = build_prompt(symptom, patient, manifestation)
    print("--- prompt ---", flush=True)
    print(prompt, flush=True)

    raw = call_openai(client, args.model, prompt, args.temperature, args.max_tokens)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print("[warn] model output was not valid JSON; storing raw text instead.", flush=True)
        result = {"additional_requirements": {}, "functional_impairment": None, "raw": raw}

    print("--- result ---", flush=True)
    print_additional_manifestation(result, duration_items)

    # Flat, one level — same shape as "manifestation" (code -> value): each additional
    # requirement's own text is a key, plus "functional_impairment" and each duration
    # item ("duration", "<group>_duration", ...), all mapping directly to their sentence.
    add_requirements: dict = dict(result.get("additional_requirements", {}))
    add_requirements["functional_impairment"] = result.get("functional_impairment")
    for key, _ in duration_items:
        add_requirements[key] = result.get(key)
    data["add_requirements"] = add_requirements

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nWrote {out_path} with add_requirements (source untouched: {args.profile}).", flush=True)


if __name__ == "__main__":
    main()
