#!/usr/bin/env python3
"""
Symptom extraction and disease matching from patient conversation logs.

Pipeline:
  1. Parse patient dialogue from logs/
  2. Use Qwen (vLLM, port 8001) to identify symptoms from symptom/ JSONs
  3. Match identified symptoms to diseases via diagnostic_criteria.json
  4. Save per-file (turn-level) and summary results to results/

Turn-level analysis:
  For each patient turn T (1-indexed), the LLM is called with the
  cumulative patient responses [1..T], so we can track how symptom
  identification and disease matching evolve across the conversation.
"""

import json
import re
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
SYMPTOM_DIR   = BASE_DIR / "mentalbench/resources/knowledge_graph/EN/symptom"
CRITERIA_FILE = BASE_DIR / "mentalbench/resources/knowledge_graph/EN/diagnostic_criteria.json"

from utils.llm import get_run_dir as _get_run_dir
_RUN_DIR   = _get_run_dir()
LOGS_DIR   = BASE_DIR / "logs"    / _RUN_DIR
OUTPUT_DIR = BASE_DIR / "results" / _RUN_DIR

from utils.llm import chat as _llm_chat


# ── Data loading ──────────────────────────────────────────────────────────────

def load_all_symptoms() -> dict:
    """Return {symptom_id: symptom_dict} merged from all symptom JSON files."""
    symptoms = {}
    for path in sorted(SYMPTOM_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            symptoms.update(json.load(f))
    return symptoms


def load_diagnostic_criteria() -> dict:
    with open(CRITERIA_FILE, encoding="utf-8") as f:
        return json.load(f)


# ── Log parsing ───────────────────────────────────────────────────────────────

# Blocks that the *analyst* LLM produces — structured JSON, not patient speech
_ANALYST_KEYS = {"matched", "matched_sections", "answer_strategy"}

def extract_patient_responses(log_file: Path) -> list[str]:
    """
    Return a list of natural-language patient utterances from a log file.
    Skips analyst JSON blobs (matched / answer_strategy outputs).
    """
    text = log_file.read_text(encoding="utf-8")
    raw_blocks = re.findall(
        r"={10} OUTPUT \[patient\] ={10}\n(.*?)\n={37}",
        text,
        re.DOTALL,
    )
    responses = []
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        # Try parsing as JSON — analyst outputs are JSON objects
        try:
            parsed = json.loads(block)
            if isinstance(parsed, dict) and _ANALYST_KEYS & parsed.keys():
                continue          # analyst block → skip
        except (json.JSONDecodeError, ValueError):
            pass                  # not JSON → real patient speech
        responses.append(block)
    return responses


# ── LLM symptom identification ────────────────────────────────────────────────

def _build_symptom_catalogue(all_symptoms: dict) -> str:
    lines = []
    for sid, sdata in all_symptoms.items():
        subtypes = ", ".join(sdata.get("subtypes", {}).keys())
        subtype_str = f"  Subtypes: {subtypes}" if subtypes else ""
        lines.append(
            f"[{sid}] {sdata['name']}: {sdata['description']}{subtype_str}"
        )
    return "\n".join(lines)


def identify_symptoms(patient_responses: list[str], all_symptoms: dict) -> tuple[list[str], dict]:
    """
    Ask the LLM to identify which symptom IDs from all_symptoms are present
    in the patient's responses.

    Returns (identified_symptom_ids, reasoning_dict).
    """
    catalogue   = _build_symptom_catalogue(all_symptoms)
    patient_text = "\n".join(f"Patient: {r}" for r in patient_responses)

    prompt = f"""You are a clinical psychiatrist reviewing a patient interview transcript.

=== SYMPTOM CATALOGUE ===
{catalogue}

=== PATIENT RESPONSES ===
{patient_text}

Task:
- Identify which symptom IDs from the catalogue are clearly present or strongly implied by the patient's own words.
- Do NOT speculate beyond what the patient explicitly states.

Reply ONLY with valid JSON (no markdown, no explanation outside the JSON):
{{
  "identified_symptoms": ["S001", "S024", ...],
  "reasoning": {{
    "S001": "one-sentence justification",
    ...
  }}
}}"""

    raw = _llm_chat(
        [
            {"role": "system", "content": "You are a clinical psychiatrist. Output only valid JSON."},
            {"role": "user",   "content": prompt},
        ],
        max_new_tokens=2048,
        role="judge",
    ).strip()

    # Strip accidental markdown fences
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$",       "", raw)

    # Extract first JSON object in case of extra text
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group()

    try:
        parsed = json.loads(raw)
        return parsed.get("identified_symptoms", []), parsed.get("reasoning", {})
    except json.JSONDecodeError:
        print(f"  [warn] Could not parse LLM JSON:\n{raw[:300]}", file=sys.stderr)
        return [], {}


# ── Disease matching ──────────────────────────────────────────────────────────

def _symptom_pool_keys(criteria: dict) -> list[str]:
    """Return all criterion-group keys that contain a symptom_pool."""
    return [k for k, v in criteria.items() if isinstance(v, dict) and "symptom_pool" in v]


def match_diseases(identified_ids: list[str], diagnostic_criteria: dict) -> list[dict]:
    """
    Score every disease against the identified symptom IDs.

    Scoring rules:
    - A criterion group with relation='must_include' is *required*.
    - all_required_met=True when every must_include group reaches its min_count.
    - 'must_include_one_of' (e.g. Schizophrenia) is checked as an extra constraint.
    - Diseases are ranked: fully-met first, then by total matched symptoms.
    """
    id_set   = set(identified_ids)
    results  = []

    for disease_id, disease_data in diagnostic_criteria.items():
        criteria         = disease_data["required_criteria"]
        matched_criteria = {}
        all_required_met = True
        total_matches    = 0

        for group_name in _symptom_pool_keys(criteria):
            grp        = criteria[group_name]
            pool       = grp["symptom_pool"]
            min_count  = grp.get("min_count", 1)
            relation   = grp.get("relation", "must_include")

            matched_in_pool = [s for s in identified_ids if s in pool]
            count            = len(matched_in_pool)
            total_matches   += count
            met              = count >= min_count

            # Extra 'must_include_one_of' constraint (e.g. Schizophrenia)
            must_one_of      = grp.get("must_include_one_of", [])
            must_one_met     = not must_one_of or bool(id_set & set(must_one_of))

            group_met = met and must_one_met
            matched_criteria[group_name] = {
                "matched":        matched_in_pool,
                "count":          count,
                "required":       min_count,
                "met":            group_met,
                "must_one_of_met": must_one_met,
            }

            if relation == "must_include" and not group_met:
                all_required_met = False

        results.append({
            "disease_id":         disease_id,
            "disease_name":       disease_data["name"],
            "all_required_met":   all_required_met,
            "total_symptom_matches": total_matches,
            "matched_criteria":   matched_criteria,
        })

    # Sort: fully-met diseases first, then by descending symptom match count
    results.sort(key=lambda x: (not x["all_required_met"], -x["total_symptom_matches"]))
    return results


# ── Per-file processing (turn-level) ─────────────────────────────────────────

def process_log(log_file: Path, all_symptoms: dict, diagnostic_criteria: dict) -> dict | None:
    name = log_file.stem
    print(f"\n[{name}] Extracting patient responses...")

    responses = extract_patient_responses(log_file)
    if not responses:
        print(f"  → No patient responses found, skipping.")
        return None
    print(f"  → {len(responses)} response(s) found. Running turn-level analysis...")

    turns = []
    for turn_idx, _ in enumerate(responses):
        # Cumulative responses up to and including this turn (1-indexed in output)
        responses_so_far = responses[: turn_idx + 1]
        turn_num = turn_idx + 1

        print(f"  → Turn {turn_num}/{len(responses)}: calling LLM...")
        identified, reasoning = identify_symptoms([responses[turn_idx]], all_symptoms)
        print(f"     Identified {len(identified)} symptom(s): {identified}")

        matches     = match_diseases(identified, diagnostic_criteria)
        fully_met   = [d for d in matches if d["all_required_met"]]
        top_partial = [d for d in matches if not d["all_required_met"] and d["total_symptom_matches"] > 0][:5]

        turns.append({
            "turn":                    turn_num,
            "patient_response":        responses[turn_idx],
            "responses_so_far":        responses_so_far,
            "identified_symptoms":     identified,
            "symptom_reasoning":       reasoning,
            "disease_matches": {
                "fully_met":   fully_met,
                "top_partial": top_partial,
            },
        })

    return {
        "log_file": name,
        "total_turns": len(responses),
        "turns": turns,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Symptom Extraction & Disease Matching ===\n")

    print("Loading symptoms...")
    all_symptoms = load_all_symptoms()
    print(f"  {len(all_symptoms)} symptoms loaded from {SYMPTOM_DIR.name}/\n")

    print("Loading diagnostic criteria...")
    diagnostic_criteria = load_diagnostic_criteria()
    print(f"  {len(diagnostic_criteria)} diseases loaded.\n")

    OUTPUT_DIR.mkdir(exist_ok=True)

    log_files   = sorted(LOGS_DIR.glob("*.txt"))
    print(f"Found {len(log_files)} log files in {LOGS_DIR.name}/")

    all_results = []
    for log_file in log_files:
        out_path = OUTPUT_DIR / f"{log_file.stem}_result.json"

        # 이미 결과가 있으면 스킵하고, 기존 결과를 summary에 포함
        if out_path.exists():
            print(f"\n[{log_file.stem}] Result already exists → skip.")
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
                all_results.append(existing)
            except (json.JSONDecodeError, OSError) as e:
                print(f"  [warn] Could not load existing result ({e}); re-processing.")
            else:
                continue

        result = process_log(log_file, all_symptoms, diagnostic_criteria)
        if result is None:
            continue

        all_results.append(result)

        # Save individual result
        out_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # Save combined summary
    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Print summary table (final-turn snapshot per log) ─────────────────
    print("\n" + "=" * 80)
    print(f"{'Log':<14} {'Turns':>6} {'Symptoms@end':>13}  {'Top Disease @ final turn'}")
    print("=" * 80)
    for r in all_results:
        final_turn  = r["turns"][-1]
        symptoms    = final_turn["identified_symptoms"]
        fully_met   = final_turn["disease_matches"]["fully_met"]
        top_partial = final_turn["disease_matches"]["top_partial"]

        if fully_met:
            top = fully_met[0]["disease_name"]
            tag = "(full)"
        elif top_partial:
            top = top_partial[0]["disease_name"]
            tag = "(partial)"
        else:
            top, tag = "No match", ""

        print(f"{r['log_file']:<14} {r['total_turns']:>6} {len(symptoms):>13}  {top} {tag}")

    print("=" * 80)
    print(f"\nDone. Results saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
