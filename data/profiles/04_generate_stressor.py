"""Generate onset narratives (demographics/stressor_category/severity/stressor/
chief_complaint_symptom_code/chief_complaint) for every persona attached to a symptom profile produced by
03_add_persona.py — one OpenAI call per profile, covering all of its personas at once.

For a given "<disease>_S<NNN>.json" file (see add_persona/<difficulty>/, each of
which has a single "question" symptom-profile block plus an "info" list of
sampled personas), this script:

  1. Builds ONE narrative-generation prompt covering every persona in "info" together
     (shared symptom-profile context in section A, one persona sub-block per persona
     in section B, while the model selects each persona's most natural chief-complaint symptom), and
     asks for one JSON result per persona back in a single response.
  2. Calls the OpenAI Chat Completions API once for the whole profile (JSON-mode output).
  3. Prints each persona's parsed result.
  4. Saves every persona's result together under add_stressor/only_stressor/<difficulty>/<profile_stem>_result.json.

Usage:
    python 04_generate_stressor.py
    python 04_generate_stressor.py --profile add_persona/low/D001_S001.json \
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
DEFAULT_PROFILE_PATH = SCRIPT_DIR / "add_persona" / "low" / "D018_S001.json"
STRESSOR_DIR = SCRIPT_DIR / "add_stressor" / "only_stressor"

load_dotenv(PROJECT_ROOT / ".env")

PERSONA_BLOCK_TEMPLATE = """--- Persona {{index}} (uuid: {{uuid}}) ---
- Sex / Age: {{sex}} / {{age}}
- Marital status: {{marital_status}}
- Education: {{education_level}}
- Occupation: {{occupation}}
- General persona: {{persona}}
- Professional background: {{professional_persona}}
- Cultural background: {{cultural_background}}
- Hobbies / interests: {{hobbies_and_interests}}
- Sports context: {{sports_persona}}
- Arts context: {{arts_persona}}
- Travel context: {{travel_persona}}
- Culinary context: {{culinary_persona}}
"""

PROMPT_TEMPLATE = """You are a psychiatric case scenario writer. Combine the (A) diagnostic profile and (B) real personas below to write, in English, the life background and circumstances surrounding the onset, worsening, recognition, or presentation of this disorder for each persona — what happened and how the condition became clinically significant. The goal is a coherent background story, not a description of the symptoms themselves. Symptom-level detail will be written separately in a later stage, so keep demographics and stressor focused on background rather than symptom description.

[A. Diagnostic Profile — shared by every persona below]
- Disorder: {{disease_name}} ({{disease_code}})
- Symptom group: {{symptom_group_name}} (duration: {{duration}}, functional impairment required: {{functional_impairment_required}})
- Eligible symptoms these persons have (use these as clinical reference; for each persona, select exactly one code from this list for chief_complaint_symptom_code):
{{symptom_list_with_names}}

[B. Personas — write one independent result per persona, in the same order]
{{persona_blocks}}

[Decision Priorities — apply in this exact order]
1. Clinical plausibility: The relationship between the disorder and the life background must be clinically coherent. Do not assume that every disorder was directly caused by a single external event; represent the relationship between the circumstances and the onset, worsening, recognition, or presentation of the condition accurately.
2. Biographical coherence: The background must fit the persona's age, relationships, cultural and social environment, interests, daily life, education, and professional circumstances. Use these details to shape what matters to the person, how the circumstances affect them, and why they seek care.
3. Diversity across the three cases: When multiple backgrounds are similarly plausible, prefer meaningfully different life domains, events, and clinical pathways across the personas. Repetition is acceptable when it is clearly the most plausible choice.
4. Creativity: Make each background concrete, individualized, and memorable while remaining realistic. Creative details must never override clinical or biographical plausibility.

[Writing Guidelines]
1. First, fill in disease_info: Write 2–4 sentences of clinically accurate background knowledge about {{disease_name}} itself—the kind of information a psychiatrist would already know before evaluating a patient. Briefly summarize its defining diagnostic features, typical clinical presentation, course, and distinguishing characteristics from similar disorders. This section should contain only general disease knowledge and will serve as the clinical reference for generating the persona-specific cases below.
2. For EACH of the {{num_personas}} personas above, fill in exactly six fields: demographics, stressor_category, severity, stressor, chief_complaint_symptom_code, chief_complaint.
3. demographics: Write concisely in the format "sex / age / occupation / education". Use the persona information exactly as provided without adding new details.
4. stressor_category: Based on the disease characteristics described in disease_info, choose the category that most naturally fits this specific persona's clinical and life background, considering the full persona information above. Use a diverse range of categories across the personas in this batch whenever clinically plausible, rather than repeatedly selecting the same category. Repeat a category only when it is clearly the most appropriate choice for multiple personas.
Available categories:
- Relationship / Family
- Health / Caregiving
- Financial
- Housing / Environmental
- Loss / Bereavement
- Accident / Crime / Community
- Occupational / Academic
- Major Life Transition
- Others
5. severity: Determine the most clinically plausible severity (Mild / Moderate / Severe) based on the disease, the persona, the selected stressor_category, and the overall clinical course. Do not artificially balance severity levels across personas.
6. stressor: In 3–4 sentences, describe the life background surrounding the onset, worsening, recognition, or presentation of {{disease_name}} for this persona. Begin with the most relevant event, life circumstance, or presentation context; explain how the condition developed, became apparent, or persisted over the {{duration}}; and conclude with why the person ultimately sought psychiatric care. Do not imply that an external circumstance directly caused the disorder unless that relationship is clinically appropriate. Focus on the background, progression, and functional impact leading to the diagnosis rather than explicitly listing or describing the disorder's symptoms. Ensure the narrative remains consistent with the persona's full life context, demographics, and selected stressor_category.
7. chief_complaint_symptom_code and chief_complaint: After establishing this persona's background and clinical course, select exactly ONE code from the eligible symptom list as chief_complaint_symptom_code. Choose the symptom that would most naturally dominate this person's subjective distress, functional difficulty, or reason for seeking care within the established background. Then express it as a short, natural first-visit chief_complaint. The complaint must describe the selected symptom rather than merely repeating the stressor or life event, and it must not combine multiple symptoms. When multiple symptoms are similarly plausible, prefer different chief complaints across the three personas; clinical plausibility takes priority over diversity.
8. Each persona's narrative should form one coherent clinical case with a logical progression from life background → onset, worsening, or recognition → clinical course → psychiatric consultation, while remaining fully consistent with the shared diagnostic profile and avoiding contradictory conditions or events (e.g., manic episodes when no manic symptoms are present).
[Output format — JSON only, no other text. "results" must have exactly {{num_personas}} items, in the same order as the personas listed above]
{
  "disease_info": "...",
  "results": [
    {"demographics": "...", "stressor_category": "...", "severity": "...", "stressor": "...", "chief_complaint_symptom_code": "Sxxx", "chief_complaint": "..."}
  ]
}
"""


def extract_duration_and_impairment(sampled_features: dict) -> tuple[str, bool]:
    """duration / functional_impairment_required live either under sampled_diagnostic_criteria
    or nested inside a sampled_symptom_group, depending on the disease — check both."""
    criteria = sampled_features.get("sampled_diagnostic_criteria") or {}
    duration = criteria.get("duration")
    impairment = criteria.get("functional_impairment_required")

    for group in (sampled_features.get("sampled_symptom_groups") or {}).values():
        if duration is None:
            duration = group.get("duration")
        if impairment is None:
            impairment = group.get("functional_impairment_required")

    return (duration or "unknown"), bool(impairment)


def symptom_group_names(sampled_features: dict) -> str:
    groups = sampled_features.get("sampled_symptom_groups") or {}
    names = [g.get("name", key) for key, g in groups.items()]
    return ", ".join(names) if names else "unknown"


def symptom_list_with_names(sampled_features: dict) -> str:
    """List every eligible chief-complaint symptom with enough context to choose naturally."""
    descriptions = sampled_features.get("sampled_symptoms_descriptions") or {}
    return "\n".join(
        f"- {code} {info.get('name', code)} — {info.get('description', '')}"
        for code, info in descriptions.items()
    )


def build_persona_block(index: int, persona: dict) -> str:
    mapping = {
        "index": str(index),
        "uuid": persona.get("uuid", ""),
        "sex": persona.get("sex", ""),
        "age": persona.get("age", ""),
        "marital_status": persona.get("marital_status", ""),
        "education_level": persona.get("education_level", ""),
        "occupation": persona.get("occupation", ""),
        "persona": persona.get("persona", ""),
        "professional_persona": persona.get("professional_persona", ""),
        "cultural_background": persona.get("cultural_background", ""),
        "hobbies_and_interests": persona.get("hobbies_and_interests", ""),
        "sports_persona": persona.get("sports_persona", ""),
        "arts_persona": persona.get("arts_persona", ""),
        "travel_persona": persona.get("travel_persona", ""),
        "culinary_persona": persona.get("culinary_persona", ""),
    }
    block = PERSONA_BLOCK_TEMPLATE
    for key, value in mapping.items():
        block = block.replace("{{" + key + "}}", str(value))
    return block


def build_prompt(question: dict, personas: list[dict]) -> str:
    sampled_features = question["sampled_features"]
    duration, impairment = extract_duration_and_impairment(sampled_features)

    persona_blocks = "\n".join(
        build_persona_block(i, persona) for i, persona in enumerate(personas, start=1)
    )

    mapping = {
        "disease_name": sampled_features.get("disease_name", ""),
        "disease_code": sampled_features.get("disease_code", ""),
        "symptom_group_name": symptom_group_names(sampled_features),
        "duration": duration,
        "functional_impairment_required": "yes" if impairment else "no",
        "symptom_list_with_names": symptom_list_with_names(sampled_features),
        "persona_blocks": persona_blocks,
        "num_personas": str(len(personas)),
    }

    prompt = PROMPT_TEMPLATE
    for key, value in mapping.items():
        prompt = prompt.replace("{{" + key + "}}", str(value))
    return prompt


def validate_chief_complaint_choices(narratives: list, sampled_features: dict) -> None:
    """Warn when a model-selected chief complaint is missing or outside the sampled symptoms."""
    valid_codes = set((sampled_features.get("sampled_symptoms_descriptions") or {}).keys())
    for index, narrative in enumerate(narratives, start=1):
        if not isinstance(narrative, dict):
            print(f"[warn] persona {index}: narrative is not a JSON object", flush=True)
            continue
        code = narrative.get("chief_complaint_symptom_code")
        if code not in valid_codes:
            print(
                f"[warn] persona {index}: chief_complaint_symptom_code={code!r} "
                f"is not one of {sorted(valid_codes)}",
                flush=True,
            )
        if not narrative.get("chief_complaint"):
            print(f"[warn] persona {index}: chief_complaint is missing", flush=True)


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE_PATH,
        help=f"Path to a <disease>_S<NNN>.json profile from 03_add_persona.py (default: {DEFAULT_PROFILE_PATH.name}).",
    )
    parser.add_argument("--model", default="gpt-5.1", help="OpenAI model name (default: gpt-5.1).")
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.9,
        help="Sampling temperature (default: 0.9 — creative but still coherent for narrative writing).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2000,
        help="Max output tokens for the whole batched (all-personas) response (default: 2000).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.profile, encoding="utf-8") as f:
        profile = json.load(f)

    question = profile["question"]
    personas = profile["info"]

    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = build_prompt(question, personas)
    print("--- prompt ---", flush=True)
    print(prompt, flush=True)

    raw = call_openai(client, args.model, prompt, args.temperature, args.max_tokens)
    disease_info = None
    try:
        parsed = json.loads(raw)
        disease_info = parsed.get("disease_info")
        narratives = parsed.get("results", [])
        if not isinstance(narratives, list):
            narratives = []
    except json.JSONDecodeError:
        print("[warn] model output was not valid JSON; storing raw text for every persona instead.", flush=True)
        narratives = []

    validate_chief_complaint_choices(narratives, question["sampled_features"])

    print(f"\n--- disease_info ---\n{disease_info}", flush=True)

    results = []
    for idx, persona in enumerate(personas, start=1):
        if idx - 1 < len(narratives):
            narrative = narratives[idx - 1]
        else:
            narrative = {"raw": raw}
        print(f"\n===== Persona {idx}/{len(personas)} (uuid={persona.get('uuid')}) =====", flush=True)
        print(json.dumps(narrative, indent=2, ensure_ascii=False), flush=True)
        results.append({"persona_uuid": persona.get("uuid"), "persona_index": idx, "narrative": narrative})

    difficulty = args.profile.resolve().parent.name
    out_dir = STRESSOR_DIR / difficulty
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.profile.stem}_result.json"
    payload = {
        "profile_path": str(args.profile),
        "disease_code": question["sampled_features"].get("disease_code"),
        "model": args.model,
        "temperature": args.temperature,
        "disease_info": disease_info,
        "results": results,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nSaved {len(results)} results -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
