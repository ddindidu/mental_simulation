#!/usr/bin/env python3
"""
Symptom extraction and disease matching from patient conversation logs.

Pipeline:
  1. Parse patient dialogue from logs/
  2. Use Judge LLM to identify confirmed AND denied symptoms per turn
  3. Maintain cumulative symptom state (monotonically informative — no reversion)
  4. Compute KG-deterministic CandidateSet (high_likely / moderate_likely / excluded)
     per turn based on cumulative state
  5. Save per-file (turn-level) and summary results to results/

CandidateSet semantics (spec §4.2):
  high_likely   : ALL mandatory criterion groups satisfied (count >= min_count)
  moderate_likely: at least ONE mandatory symptom confirmed; not excluded
  excluded      : any mandatory pool rendered impossible (len(pool − denied) < min_count)
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

_ANALYST_KEYS = {"matched", "matched_sections", "answer_strategy"}

def extract_patient_responses(log_file: Path) -> list[str]:
    """Return a list of natural-language patient utterances from a log file."""
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
        try:
            parsed = json.loads(block)
            if isinstance(parsed, dict) and _ANALYST_KEYS & parsed.keys():
                continue
        except (json.JSONDecodeError, ValueError):
            pass
        responses.append(block)
    return responses


# ── LLM symptom identification (per-turn, confirmed + denied) ─────────────────

def _build_symptom_catalogue(all_symptoms: dict) -> str:
    lines = []
    for sid, sdata in all_symptoms.items():
        subtypes = ", ".join(sdata.get("subtypes", {}).keys())
        subtype_str = f"  Subtypes: {subtypes}" if subtypes else ""
        lines.append(
            f"[{sid}] {sdata['name']}: {sdata['description']}{subtype_str}"
        )
    return "\n".join(lines)


_EXTRACTION_PROMPT = """You are a clinical psychiatrist reviewing a single patient utterance.

=== SYMPTOM CATALOGUE ===
{catalogue}

=== PATIENT UTTERANCE ===
{utterance}

Task:
- CONFIRMED: symptoms clearly present or strongly implied by the patient's words.
- DENIED: symptoms the patient explicitly says they do NOT have
  (e.g. "No", "I don't", "I haven't", "never").
- Do NOT speculate. Err toward UNKNOWN (omit) rather than guessing.

Reply ONLY with valid JSON (no markdown, no extra text):
{{
  "confirmed": ["S001", ...],
  "denied": ["S025", ...],
  "reasoning": {{
    "S001": "one-sentence justification",
    ...
  }}
}}"""


def identify_symptoms_turn(
    patient_utterance: str,
    all_symptoms: dict,
) -> tuple[list[str], list[str], dict]:
    """
    Extract confirmed and denied symptom IDs from a single patient utterance.
    Returns (confirmed_ids, denied_ids, reasoning_dict).
    """
    catalogue = _build_symptom_catalogue(all_symptoms)
    prompt = _EXTRACTION_PROMPT.format(
        catalogue=catalogue,
        utterance=patient_utterance,
    )

    raw = _llm_chat(
        [
            {"role": "system", "content": "You are a clinical psychiatrist. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        max_new_tokens=2048,
        role="judge",
    ).strip()

    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group()

    try:
        parsed = json.loads(raw)
        valid_ids = set(all_symptoms.keys())
        confirmed = [s for s in parsed.get("confirmed", []) if s in valid_ids]
        denied    = [s for s in parsed.get("denied",    []) if s in valid_ids]
        reasoning = parsed.get("reasoning", {})
        return confirmed, denied, reasoning
    except json.JSONDecodeError:
        print(f"  [warn] Could not parse LLM JSON:\n{raw[:300]}", file=sys.stderr)
        return [], [], {}


# ── Cumulative state merge (monotonic invariant — spec §2) ────────────────────

def merge_symptom_status(
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
    new_confirmed: list[str],
    new_denied: list[str],
    label_conflict_log: list[dict],
    turn: int,
) -> None:
    """
    Merge new extraction results into cumulative state.
    Once CONFIRMED or DENIED, a symptom does NOT revert; conflicts are logged.
    """
    for sid in new_confirmed:
        if sid in cumulative_denied:
            label_conflict_log.append({
                "turn": turn, "symptom": sid,
                "existing": "denied", "new": "confirmed", "kept": "denied",
            })
        elif sid not in cumulative_confirmed:
            cumulative_confirmed.add(sid)

    for sid in new_denied:
        if sid in cumulative_confirmed:
            label_conflict_log.append({
                "turn": turn, "symptom": sid,
                "existing": "confirmed", "new": "denied", "kept": "confirmed",
            })
        elif sid not in cumulative_denied:
            cumulative_denied.add(sid)


# ── KG-deterministic CandidateSet (spec §4.2) ────────────────────────────────

def _mandatory_pools(disease_data: dict) -> list[tuple[set[str], int]]:
    """Return [(pool_set, min_count), ...] for all must_include groups."""
    pools = []
    for grp in disease_data["required_criteria"].values():
        if isinstance(grp, dict) and grp.get("relation") == "must_include":
            pools.append((set(grp.get("symptom_pool", [])), grp.get("min_count", 1)))
    return pools


def _all_symptom_ids(disease_data: dict) -> set[str]:
    """Union of ALL symptom pools for a disease (mandatory + optional)."""
    ids: set[str] = set()
    for grp in disease_data["required_criteria"].values():
        if isinstance(grp, dict) and "symptom_pool" in grp:
            ids |= set(grp["symptom_pool"])
    return ids


def compute_candidate_set(
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
    diagnostic_criteria: dict,
) -> tuple[set[str], set[str], set[str]]:
    """
    Symptom-coverage based CandidateSet — uses ALL symptom pools (not just mandatory).

    Given patient-reported confirmed = {s1, s2, s3} and denied = {s4}:

      high_likely   : disease whose symptom pool COVERS all confirmed symptoms
                      i.e. confirmed_set ⊆ D.all_symptoms
      moderate_likely: disease whose symptom pool overlaps confirmed_set partially
                      i.e. D.all_symptoms ∩ confirmed_set ≠ ∅ AND confirmed_set ⊄ D.all_symptoms
      excluded      : disease whose symptom pool contains any denied symptom
                      i.e. D.all_symptoms ∩ denied_set ≠ ∅
    Diseases with zero confirmed-symptom overlap are not added to any set.
    """
    high_likely: set[str]     = set()
    moderate_likely: set[str] = set()
    excluded: set[str]        = set()

    for did, ddata in diagnostic_criteria.items():
        d_symptoms = _all_symptom_ids(ddata)
        if not d_symptoms:
            continue

        # Excluded: any denied symptom appears in this disease's pool
        if d_symptoms & cumulative_denied:
            excluded.add(did)
            continue

        overlap = d_symptoms & cumulative_confirmed
        if not overlap:
            # No confirmed symptom is a symptom of this disease → not a candidate
            continue

        if cumulative_confirmed.issubset(d_symptoms):
            # All confirmed symptoms belong to this disease → high_likely
            high_likely.add(did)
        else:
            # Only a partial subset of confirmed symptoms → moderate_likely
            moderate_likely.add(did)

    return high_likely, moderate_likely, excluded


# ── Disease matching (kept for backward compatibility, now uses cumulative state) ─

def match_diseases(
    cumulative_confirmed: set[str],
    cumulative_denied: set[str],
    diagnostic_criteria: dict,
) -> list[dict]:
    """
    Produce a ranked disease list based on symptom-coverage logic.

    fully_met   = high_likely  (confirmed ⊆ D.all_symptoms)
    top_partial = moderate_likely (partial overlap, not excluded)
    """
    high_likely, moderate_likely, excluded = compute_candidate_set(
        cumulative_confirmed, cumulative_denied, diagnostic_criteria
    )

    results = []
    for disease_id, disease_data in diagnostic_criteria.items():
        d_symptoms     = _all_symptom_ids(disease_data)
        overlap        = d_symptoms & cumulative_confirmed
        total_matches  = len(overlap)
        all_required_met = disease_id in high_likely

        matched_criteria = {}
        for group_name, grp in disease_data["required_criteria"].items():
            if not isinstance(grp, dict) or "symptom_pool" not in grp:
                continue
            pool = grp["symptom_pool"]
            min_count = grp.get("min_count", 1)
            matched_in_pool = [s for s in cumulative_confirmed if s in pool]
            count = len(matched_in_pool)
            matched_criteria[group_name] = {
                "matched": matched_in_pool,
                "count": count,
                "required": min_count,
                "met": count >= min_count,
            }

        results.append({
            "disease_id":            disease_id,
            "disease_name":          disease_data["name"],
            "all_required_met":      all_required_met,
            "total_symptom_matches": total_matches,
            "matched_criteria":      matched_criteria,
            "in_excluded":           disease_id in excluded,
        })

    results.sort(key=lambda x: (not x["all_required_met"], -x["total_symptom_matches"]))
    return results


# ── Per-file processing (cumulative turn-level) ──────────────────────────────

def process_log(log_file: Path, all_symptoms: dict, diagnostic_criteria: dict) -> dict | None:
    name = log_file.stem
    print(f"\n[{name}] Extracting patient responses...")

    responses = extract_patient_responses(log_file)
    if not responses:
        print(f"  → No patient responses found, skipping.")
        return None
    print(f"  → {len(responses)} response(s) found. Running cumulative turn-level analysis...")

    cumulative_confirmed: set[str] = set()
    cumulative_denied: set[str]    = set()
    label_conflict_log: list[dict] = []
    turns = []

    for turn_idx, response in enumerate(responses):
        turn_num = turn_idx + 1
        print(f"  → Turn {turn_num}/{len(responses)}: calling LLM...")

        new_confirmed, new_denied, reasoning = identify_symptoms_turn(response, all_symptoms)
        print(f"     Confirmed: {new_confirmed}  Denied: {new_denied}")

        merge_symptom_status(
            cumulative_confirmed, cumulative_denied,
            new_confirmed, new_denied,
            label_conflict_log, turn_num,
        )

        high_likely, moderate_likely, excluded = compute_candidate_set(
            cumulative_confirmed, cumulative_denied, diagnostic_criteria
        )

        matches  = match_diseases(cumulative_confirmed, cumulative_denied, diagnostic_criteria)
        fully_met   = [d for d in matches if d["all_required_met"]]
        top_partial = [d for d in matches if not d["all_required_met"]
                       and not d["in_excluded"]
                       and d["total_symptom_matches"] > 0]

        turns.append({
            "turn":                   turn_num,
            "patient_response":       response,
            "new_confirmed_symptoms": new_confirmed,
            "new_denied_symptoms":    new_denied,
            "cumulative_confirmed":   sorted(cumulative_confirmed),
            "cumulative_denied":      sorted(cumulative_denied),
            "symptom_reasoning":      reasoning,
            "candidate_set": {
                "high_likely":    sorted(high_likely),
                "moderate_likely": sorted(moderate_likely),
                "excluded":       sorted(excluded),
            },
            "disease_matches": {
                "fully_met":   fully_met,
                "top_partial": top_partial,
            },
        })

    return {
        "log_file":           name,
        "total_turns":        len(responses),
        "label_conflict_log": label_conflict_log,
        "turns":              turns,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Symptom Extraction & Disease Matching (cumulative) ===\n")

    print("Loading symptoms...")
    all_symptoms = load_all_symptoms()
    print(f"  {len(all_symptoms)} symptoms loaded.\n")

    print("Loading diagnostic criteria...")
    diagnostic_criteria = load_diagnostic_criteria()
    print(f"  {len(diagnostic_criteria)} diseases loaded.\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log_files  = sorted(LOGS_DIR.glob("*.txt"))
    print(f"Found {len(log_files)} log files in {LOGS_DIR.name}/")

    all_results = []
    for log_file in log_files:
        out_path = OUTPUT_DIR / f"{log_file.stem}_result.json"

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
        out_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 80)
    print(f"{'Log':<14} {'Turns':>6} {'Conf':>5} {'Denied':>6} {'HighL':>6} {'ModL':>5}  Top Disease @ final turn")
    print("=" * 80)
    for r in all_results:
        final_turn = r["turns"][-1]
        n_conf   = len(final_turn["cumulative_confirmed"])
        n_denied = len(final_turn["cumulative_denied"])
        cs       = final_turn["candidate_set"]
        n_hl     = len(cs["high_likely"])
        n_ml     = len(cs["moderate_likely"])

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

        print(f"{r['log_file']:<14} {r['total_turns']:>6} {n_conf:>5} {n_denied:>6} {n_hl:>6} {n_ml:>5}  {top} {tag}")

    print("=" * 80)
    print(f"\nDone. Results saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
