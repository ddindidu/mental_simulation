"""Generate per-symptom manifestation sentences for one persona file produced by
07_split_patients.py (read from split_patients/, never modified),
and write the enriched result to the mirrored path under add_manifestation/ — merging
into whatever an earlier run already left there rather than clobbering it.

For every symptom code in the file's "symptom" block (shown to the model only as
code/name/description — no subtypes or examples), this asks the model to write one
plain sentence describing how this patient concretely experiences it in daily life —
calibrated to their assigned severity.

Usage:
    python 08_generate_manifestation.py
    python 08_generate_manifestation.py --profile add_manifestation/split_patients/low/D019/D019_S003_P002.json \
        --model gpt-5.1 --temperature 0.9
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent  # data/code
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # mental_simulation
MANIFESTATION_ROOT = SCRIPT_DIR / "add_manifestation"
SPLIT_ROOT = MANIFESTATION_ROOT / "split_patients"
DEFAULT_PROFILE_PATH = SPLIT_ROOT / "low" / "D014" / "D014_S004_P002.json"
FAILED_LOG_PATH = SCRIPT_DIR / "manifestation_retry_failed.txt"

load_dotenv(PROJECT_ROOT / ".env")

PROMPT_TEMPLATE = """You are a mental health expert creating realistic clinical cases for a doctor–patient interview simulator.

Using the disease information, symptom profile, and established patient case below, write how this specific patient would actually experience each assigned symptom in daily life. Write one manifestation sentence per symptom, in the patient's own voice, as though they were describing the experience during a psychiatric interview.

Do not invent new symptoms or change the established diagnosis, severity, or patient background. Your goal is to create clinically plausible, diverse, and highly individualized manifestations that reflect how a real person with {{disease_name}} might experience the assigned symptoms.

[A. Disease Information]
{{disease_info}}

[B. Symptom Profile]

Disorder: {{disease_name}} ({{disease_code}})
Duration: {{duration}}
Symptoms:
{{symptom_block}}

[C. Established Patient Case]

Demographics: {{demographics}}
Stressor event: {{stressor_event}}
Overall severity: {{severity}}
Stressor: {{stressor}}
Chief complaint symptom code: {{chief_complaint_symptom_code}}

[Writing Guidelines]

1. For each symptom code, write exactly ONE sentence describing its manifestation for this patient. Where a symptom lists reference subtypes/example presentations, use them as inspiration for a concrete, specific angle — you don't need to pick or report exactly one, and don't copy any example verbatim.
2. Write in the first person and in the patient's natural speaking voice. The sentence should sound like something the patient would actually report to a psychiatrist, not a clinical case description.
3. Describe the patient's concrete lived experience rather than naming the symptom, repeating diagnostic criteria, or using psychiatric terminology.
4. Make each manifestation specific to this individual by drawing naturally on the established demographics, stressor, severity, and daily environment. Avoid generic descriptions that could apply to any patient. Use the stressor only when it is clinically relevant to the specific symptom. Do not force every manifestation to explicitly mention or directly result from the stressor.
5. Match the vocabulary, sentence complexity, and manner of expression to the patient's education level and background.
6. The manifestations as a whole should reflect the assigned overall severity ({{severity}}). Individual symptoms may vary in intensity, prominence, and functional impact.
7. Reflect that the condition has persisted for {{duration}} rather than describing a single isolated event. Express the persistence naturally and do not force the exact duration into every sentence.
8. The chief-complaint symptom is what the patient opens the interview with, so write that one manifestation as the sentence they would volunteer first when asked what brings them in.
9. Taken together, all manifestations must sound like experiences reported by one coherent, realistic patient with {{disease_name}}, without contradicting the disease information or established patient case.

[Output format — JSON only, no other text. Include exactly one key for every symptom code listed above. Return exactly the symptom codes listed in the prompt. Do not omit, rename, or add any symptom code.]

{
"<symptom_code>": "<manifestation sentence>"
}
"""


def extract_duration(sampled_features: dict) -> str:
    """duration lives either under sampled_diagnostic_criteria or nested inside a
    sampled_symptom_group, depending on the disease — check both."""
    criteria = sampled_features.get("sampled_diagnostic_criteria") or {}
    duration = criteria.get("duration")
    for group in (sampled_features.get("sampled_symptom_groups") or {}).values():
        if duration is None:
            duration = group.get("duration")
    return duration or "unknown"


def build_symptom_block(sampled_features: dict) -> str:
    """List each symptom's code/name/description, plus subtypes/examples where they
    exist as loose reference material — the model isn't asked to pick or report one."""
    descriptions = sampled_features.get("sampled_symptoms_descriptions") or {}
    lines = []
    for code, info in descriptions.items():
        name = info.get("name", code)
        description = info.get("description", "")
        line = f"- {code} {name} — {description}"

        subtypes = info.get("subtypes") or {}
        examples = info.get("examples") or []
        if subtypes:
            reference = "; ".join(f"{k} ({v})" for k, v in subtypes.items())
            line += f" (reference — ways this can look: {reference})"
        elif examples:
            reference = "; ".join(examples)
            line += f" (reference — example presentations: {reference})"

        lines.append(line)
    return "\n".join(lines)


def build_prompt(symptom: dict, patient: dict) -> str:
    sampled_features = symptom["sampled_features"]
    mapping = {
        "disease_name": sampled_features.get("disease_name", ""),
        "disease_code": sampled_features.get("disease_code", ""),
        "disease_info": symptom.get("disease_info") or "(not available)",
        "duration": extract_duration(sampled_features),
        "symptom_block": build_symptom_block(sampled_features),
        "demographics": patient.get("demographics", ""),
        "stressor_event": patient.get("stressor_event", ""),
        "severity": patient.get("severity", ""),
        "stressor": patient.get("stressor", ""),
        "chief_complaint_symptom_code": patient.get("chief_complaint_symptom_code", ""),
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
        elif "temperature" in err:
            # Some models only accept the default temperature; drop it and let them use it.
            print(f"[warn] {model} does not accept temperature={temperature}; retrying with its default.", flush=True)
            kw.pop("temperature", None)
            resp = client.chat.completions.create(**kw)
        else:
            raise
    return resp.choices[0].message.content


def call_manifestation_with_retry(
    client, model: str, prompt: str, temperature: float, max_tokens: int, expected_codes: set[str], max_attempts: int = 5
) -> tuple[dict | None, str, bool]:
    """Call the model up to max_attempts times, retrying if the JSON fails to parse or
    is missing any expected symptom code (the model has been observed to sometimes only
    write one symptom and stop instead of all of them).
    Returns (parsed_dict_or_None, raw_text, success)."""
    last_raw = ""
    for attempt in range(1, max_attempts + 1):
        raw = call_openai(client, model, prompt, temperature, max_tokens)
        last_raw = raw
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[warn] attempt {attempt}/{max_attempts}: not valid JSON, retrying...", flush=True)
            continue

        missing = expected_codes - parsed.keys()
        if missing:
            print(
                f"[warn] attempt {attempt}/{max_attempts}: missing {len(missing)}/{len(expected_codes)} "
                f"symptom(s) ({sorted(missing)}), retrying...",
                flush=True,
            )
            continue

        return parsed, raw, True

    print(f"[warn] gave up after {max_attempts} attempts; saving the last (incomplete) response.", flush=True)
    try:
        return json.loads(last_raw), last_raw, False
    except json.JSONDecodeError:
        return None, last_raw, False


def enrich_manifestation(symptom: dict, manifestation: dict) -> dict:
    """Attach each symptom's name/description (already known locally, rule-based) to
    the model's manifestation output, so the saved file is self-contained per symptom."""
    descriptions = symptom["sampled_features"].get("sampled_symptoms_descriptions") or {}
    enriched = {}
    for code, sentence in manifestation.items():
        info = descriptions.get(code, {})
        enriched[code] = {
            "name": info.get("name", "(no name found)"),
            "description": info.get("description", "(no description found)"),
            "manifestation": sentence,
        }
    return enriched


def print_manifestation(enriched: dict) -> None:
    """Print each symptom as: code / name / description / manifestation sentence."""
    for code, entry in enriched.items():
        print(f"\n{code}")
        print(entry["name"])
        print(entry["description"])
        print(entry["manifestation"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE_PATH,
        help=f"Path to an add_manifestation/split_patients/<difficulty>/<disease>/<disease>_S<NNN>_P<NNN>.json "
        f"file from 07_split_patients.py (default: {DEFAULT_PROFILE_PATH.name}).",
    )
    parser.add_argument("--model", default="gpt-5.5", help="OpenAI model name (default: gpt-5.5).")
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.9,
        help="Sampling temperature (default: 0.9).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4000,
        help="Max output tokens (default: 4000 — one sentence per sampled symptom, plus the budget "
        "reasoning models spend before writing anything; they return an empty response when it runs out).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with open(args.profile, encoding="utf-8") as f:
        source_data = json.load(f)

    symptom = source_data["symptom"]
    patient = source_data["patient"]

    # Write to the mirrored path under add_manifestation/, never back to the split source.
    # If that output file already exists (i.e. this script already ran on it), load it
    # so we merge into it instead of clobbering it.
    rel_path = args.profile.resolve().relative_to(SPLIT_ROOT.resolve())
    out_path = MANIFESTATION_ROOT / rel_path
    if out_path.is_file():
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"symptom": symptom, "patient": patient}

    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = build_prompt(symptom, patient)
    # print("--- prompt ---", flush=True)
    # print(prompt, flush=True)

    expected_codes = set((symptom["sampled_features"].get("sampled_symptoms_descriptions") or {}).keys())
    manifestation, raw, success = call_manifestation_with_retry(
        client, args.model, prompt, args.temperature, args.max_tokens, expected_codes
    )
    if manifestation is None:
        print("[warn] model output was not valid JSON after retries; storing raw text instead.", flush=True)
        enriched = {"raw": raw}
    else:
        enriched = enrich_manifestation(symptom, manifestation)

    print("--- result ---", flush=True)
    if "raw" in enriched:
        print(enriched["raw"])
    else:
        print_manifestation(enriched)

    data["manifestation"] = enriched
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    if not success:
        with open(FAILED_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{args.profile}\n")
        print(f"[warn] still incomplete after retries — logged to {FAILED_LOG_PATH} for a manual re-run.", flush=True)

    print(f"\nWrote {out_path} with manifestation (source untouched: {args.profile}).", flush=True)


if __name__ == "__main__":
    main()
