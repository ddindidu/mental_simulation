"""Generate onset narratives (disease_info + per-persona stressor_event/stressor) for
every persona attached to a symptom profile produced by 03_add_persona.py — one OpenAI call
per profile, covering all of its personas at once.

For a given "<disease>_S<NNN>.json" file (see add_persona/<difficulty>/, each of
which has a single "question" symptom-profile block plus an "info" list of
sampled personas), this script:

  1. Draws a random subset of life events from the Holmes-Rahe stressor inventory CSV
     (seeded off the profile name, so a re-run offers the same candidates) and puts them
     in the prompt as the candidate pool the model must choose each persona's event from.
  2. Builds ONE narrative-generation prompt covering every persona in "info" together
     (shared symptom-profile context in section A, one persona sub-block per persona
     in section B), and asks for one JSON result per persona back in a single response.
  3. Calls the OpenAI Chat Completions API once for the whole profile (JSON-mode output).
  4. Prints each persona's parsed result.
  5. Saves every persona's result — together with the candidate events that were offered —
     under add_stressor/only_stressor/<difficulty>/<profile_stem>_result.json.

Usage:
    python 04_generate_stressor.py
    python 04_generate_stressor.py --profile add_persona/low/D001_S001.json \
        --model gpt-5.5
    python 04_generate_stressor.py --num-stressor-candidates 7 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent  # data/code
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # mental_simulation
DEFAULT_PROFILE_PATH = SCRIPT_DIR / "add_persona" / "low" / "D018_S001.json"
STRESSOR_DIR = SCRIPT_DIR / "add_stressor" / "only_stressor"
DEFAULT_STRESSOR_INVENTORY = SCRIPT_DIR / "stressor_inventory_over20_wo_sexual.csv"
DEFAULT_NUM_STRESSOR_CANDIDATES = 7
DEFAULT_SEED = 42

NARRATIVE_FIELDS = ("stressor_event", "severity", "stressor")
SEVERITY_LEVELS = ("Mild", "Moderate", "Severe")

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

PROMPT_TEMPLATE = """You are a psychiatric case scenario writer. Combine the (A) diagnostic profile and (B) real personas below to write, in English, the life background and circumstances surrounding the onset, worsening, recognition, or presentation of this disorder for each persona — what happened and how the condition became clinically significant. The goal is a coherent background story, not a description of the symptoms themselves. Symptom-level detail will be written separately in a later stage, so keep the stressor focused on background rather than symptom description.

[A. Diagnostic Profile — shared by every persona below]
- Disorder: {{disease_name}} ({{disease_code}})
- Symptom group: {{symptom_group_name}} (duration: {{duration}}, functional impairment required: {{functional_impairment_required}})
- Symptoms this person has — the background must be built on these:
{{symptom_list_with_names}}

[B. Personas — write one independent result per persona, in the same order]
{{persona_blocks}}

[Decision Priorities — apply in this exact order]
1. Clinical plausibility: The relationship between the disorder and the life background must be clinically coherent. Do not assume that every disorder was directly caused by a single external event; represent the relationship between the circumstances and the onset, worsening, recognition, or presentation of the condition accurately.
2. Biographical coherence: The background must fit the persona's age, relationships, cultural and social environment, interests, daily life, education, and professional circumstances. Use these details to shape what matters to the person, how the circumstances affect them, and why they seek care.
3. Diversity across the three cases: When multiple backgrounds are similarly plausible, prefer meaningfully different life domains, events, and clinical pathways across the personas. Repetition is acceptable when it is clearly the most plausible choice.
4. Creativity: Make each background concrete, individualized, and memorable while remaining realistic. Creative details must never override clinical or biographical plausibility.

[Writing Guidelines]
1. First, fill in disease_info: In 2–3 sentences, summarize {{disease_name}} as a psychiatrist would already know it before seeing a patient — its defining diagnostic features, typical presentation and course, and what distinguishes it from similar disorders.
2. For EACH of the {{num_personas}} personas above, fill in exactly three fields: stressor_event, severity, stressor.
3. stressor_event: Each persona's background must be built on ONE life event taken from the candidate list below. Pick the event that this specific persona's age, marital status, occupation and living situation make most plausible — never one their circumstances rule out. The {{num_personas}} personas must each be given a DIFFERENT event. Copy the chosen event into stressor_event exactly as it is written in the list.
Candidate life events:
{{stressor_event_candidates}}
4. severity: Assign each persona one of Mild, Moderate, or Severe at random, using each of the three levels exactly once across the {{num_personas}} personas.
5. stressor: In 3-4 sentences, write this persona's disease course as a single arc, following these principles:
   (1) Imagine this persona at the moment they went through the assigned stressor_event.
   (2) Starting from the earliest signs, describe how those grew to a clinical level over the {{duration}}, in terms of the symptoms and diagnostic requirements listed above.
   (3) End with how this person came to receive psychiatric care.
   Cautions:
   - Build the narrative only on the symptoms and requirements given in the profile.
   - Vary the route into care across the personas so it is not always someone else urging them.
   - Keep the narrative consistent with the assigned severity.
6. Each persona's narrative must stay fully consistent with the shared diagnostic profile, and must not introduce conditions, episodes, or events the profile does not contain (e.g., manic episodes when no manic symptoms are present).
[Output format — JSON only, no other text. "results" must have exactly {{num_personas}} items, in the same order as the personas listed above]
{
  "disease_info": "...",
  "results": [
    {"stressor_event": "...", "severity": "Mild | Moderate | Severe", "stressor": "..."}
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


def load_stressor_inventory(path: Path) -> list[str]:
    """Read the life-event column of the Holmes-Rahe stressor inventory CSV."""
    with open(path, newline="", encoding="utf-8") as f:
        events = [row["event"].strip() for row in csv.DictReader(f) if row.get("event", "").strip()]
    if not events:
        raise ValueError(f"{path.name} contains no life events")
    return events


def sample_stressor_candidates(rng: random.Random, events: list[str], count: int) -> list[str]:
    """Offer a random subset of the inventory rather than the whole list.

    A short candidate pool keeps the model from falling back on the same few dramatic
    events for every case, while staying long enough that at least one option fits any
    persona. The mean values are deliberately left out so the choice is not pulled
    toward the highest-scoring events.
    """
    return rng.sample(events, min(count, len(events)))


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


def build_prompt(question: dict, personas: list[dict], stressor_candidates: list[str]) -> str:
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
        "stressor_event_candidates": "\n".join(f"- {event}" for event in stressor_candidates),
    }

    prompt = PROMPT_TEMPLATE
    for key, value in mapping.items():
        prompt = prompt.replace("{{" + key + "}}", str(value))
    return prompt


def validate_narratives(narratives: list, stressor_candidates: list[str]) -> None:
    """Warn when a generated narrative misses a field, invents an event, or repeats one.

    The prompt asks for one distinct candidate event per persona and one of each severity
    level, so a repeat means the model ignored the constraint rather than that the profile
    ran out of options.
    """
    seen_events: set[str] = set()
    for index, narrative in enumerate(narratives, start=1):
        if not isinstance(narrative, dict):
            print(f"[warn] persona {index}: narrative is not a JSON object", flush=True)
            continue

        for field in NARRATIVE_FIELDS:
            if not narrative.get(field):
                print(f"[warn] persona {index}: {field} is missing", flush=True)

        event = narrative.get("stressor_event")
        if event and event not in stressor_candidates:
            print(f"[warn] persona {index}: stressor_event={event!r} is not one of the offered candidates", flush=True)
        if event in seen_events:
            print(f"[warn] persona {index}: stressor_event={event!r} was already used by another persona", flush=True)
        seen_events.add(event)

        severity = narrative.get("severity")
        if severity and severity not in SEVERITY_LEVELS:
            print(f"[warn] persona {index}: severity={severity!r} is not one of {list(SEVERITY_LEVELS)}", flush=True)

    severities = [n.get("severity") for n in narratives if isinstance(n, dict)]
    if len(severities) == len(SEVERITY_LEVELS) and set(severities) != set(SEVERITY_LEVELS):
        print(f"[warn] severities {severities} do not cover each of {list(SEVERITY_LEVELS)} exactly once", flush=True)


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
        elif "temperature" in err:
            # Some models only accept the default temperature; drop it and let them use it.
            print(f"[warn] {model} does not accept temperature={temperature}; retrying with its default.", flush=True)
            kw.pop("temperature", None)
            resp = client.chat.completions.create(**kw)
        else:
            raise
    return resp.choices[0].message.content


def call_narratives_with_retry(
    client, model: str, prompt: str, temperature: float, max_tokens: int, num_personas: int, max_attempts: int = 3
) -> tuple[str | None, list, str]:
    """Call the model until it returns one narrative object per persona.

    The model has been observed to write every persona's fields into a single object
    instead of opening a new one per persona; duplicate JSON keys collapse silently, so a
    short "results" list is the only sign that happened — hence the length check rather
    than relying on the JSON parsing to fail.
    Returns (disease_info, narratives, raw_text_of_last_attempt)."""
    last_raw = ""
    for attempt in range(1, max_attempts + 1):
        raw = call_openai(client, model, prompt, temperature, max_tokens)
        last_raw = raw
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[warn] attempt {attempt}/{max_attempts}: not valid JSON, retrying...", flush=True)
            continue

        narratives = parsed.get("results")
        if not isinstance(narratives, list) or len(narratives) != num_personas:
            found = len(narratives) if isinstance(narratives, list) else "none"
            print(
                f"[warn] attempt {attempt}/{max_attempts}: expected {num_personas} results, got {found}, retrying...",
                flush=True,
            )
            continue

        return parsed.get("disease_info"), narratives, raw

    print(f"[warn] gave up after {max_attempts} attempts; storing raw text for every persona.", flush=True)
    return None, [], last_raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE_PATH,
        help=f"Path to a <disease>_S<NNN>.json profile from 03_add_persona.py (default: {DEFAULT_PROFILE_PATH.name}).",
    )
    parser.add_argument("--model", default="gpt-5.5", help="OpenAI model name (default: gpt-5.5).")
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.9,
        help="Sampling temperature (default: 0.9 — creative but still coherent for narrative writing).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=6000,
        help="Max output tokens for the whole batched (all-personas) response (default: 6000 — "
        "reasoning models spend part of this budget before writing anything, and return an empty "
        "response when it runs out).",
    )
    parser.add_argument(
        "--stressor-inventory",
        type=Path,
        default=DEFAULT_STRESSOR_INVENTORY,
        help=f"Life-event inventory CSV with an 'event' column (default: {DEFAULT_STRESSOR_INVENTORY.name}).",
    )
    parser.add_argument(
        "--num-stressor-candidates",
        type=int,
        default=DEFAULT_NUM_STRESSOR_CANDIDATES,
        help=f"How many life events to offer the model per profile (default: {DEFAULT_NUM_STRESSOR_CANDIDATES}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Seed for drawing the candidate events (default: {DEFAULT_SEED}). Combined with the profile "
        f"name, so each profile draws independently but reproducibly.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.profile, encoding="utf-8") as f:
        profile = json.load(f)

    question = profile["question"]
    personas = profile["info"]
    difficulty = args.profile.resolve().parent.name

    # Seed off the profile's identity so one profile is offered the same candidates whether
    # it runs alone or inside the full batch, and stays stable across re-runs.
    rng = random.Random(f"{args.seed}:{difficulty}/{args.profile.stem}")
    inventory = load_stressor_inventory(args.stressor_inventory)
    stressor_candidates = sample_stressor_candidates(rng, inventory, args.num_stressor_candidates)
    print(f"--- stressor candidates (seed={args.seed}, {len(stressor_candidates)}/{len(inventory)}) ---", flush=True)
    for event in stressor_candidates:
        print(f"- {event}", flush=True)

    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = build_prompt(question, personas, stressor_candidates)
    print("--- prompt ---", flush=True)
    print(prompt, flush=True)

    disease_info, narratives, raw = call_narratives_with_retry(
        client, args.model, prompt, args.temperature, args.max_tokens, len(personas)
    )

    validate_narratives(narratives, stressor_candidates)

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

    out_dir = STRESSOR_DIR / difficulty
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.profile.stem}_result.json"
    payload = {
        "profile_path": str(args.profile),
        "disease_code": question["sampled_features"].get("disease_code"),
        "model": args.model,
        "temperature": args.temperature,
        "seed": args.seed,
        "stressor_candidates": stressor_candidates,
        "disease_info": disease_info,
        "results": results,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nSaved {len(results)} results -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
