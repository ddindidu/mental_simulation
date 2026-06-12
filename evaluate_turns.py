#!/usr/bin/env python3
"""
Turn-level evaluation: accuracy, precision, recall based on doctor's
per-turn candidate diagnoses parsed from simulation logs.

Ground truth : disease ID extracted from log filename (e.g. D001_3.txt → D001)
Predicted set: doctor's inference candidates after each patient turn
Truth set    : {ground_truth} ∪ {all diseases in disease_matches (fully_met + top_partial)}

Definitions (per sample per turn):
  TP = |predicted ∩ truth_set|
  FP = |predicted − truth_set|
  FN = |truth_set − predicted|
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR    = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR    = BASE_DIR / "logs"
CRITERIA_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "diagnostic_criteria.json"


# ── Disease name ↔ ID mapping ────────────────────────────────────────────────

def _build_name_to_id() -> dict[str, str]:
    """Return {lowercase disease name: disease_id} from diagnostic_criteria.json."""
    with open(CRITERIA_FILE, encoding="utf-8") as f:
        criteria = json.load(f)
    return {v["name"].lower().strip(): k for k, v in criteria.items()}


# ── Log parsing: extract doctor candidates per turn ──────────────────────────

def extract_doctor_candidates_per_turn(log_file: Path) -> list[list[str]]:
    """
    Parse a simulation log and return the doctor's inference candidates
    (disease NAMES) for each patient turn, in order.

    The inference output has keys {"candidates", "note"} (no "diagnosis" key).
    """
    text = log_file.read_text(encoding="utf-8")
    blocks = re.findall(
        r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}",
        text,
        re.DOTALL,
    )
    per_turn: list[list[str]] = []
    for b in blocks:
        b = b.strip()
        try:
            parsed = json.loads(b)
            # Inference block: has "candidates" + "note", but NOT "diagnosis"
            if (
                isinstance(parsed, dict)
                and "candidates" in parsed
                and "note" in parsed
                and "diagnosis" not in parsed
            ):
                per_turn.append(parsed["candidates"])
        except (json.JSONDecodeError, ValueError):
            continue
    return per_turn


def _names_to_ids(names: list[str], name2id: dict[str, str]) -> set[str]:
    """Map a list of disease names to their IDs. Skip unknown names."""
    ids = set()
    for name in names:
        did = name2id.get(name.lower().strip())
        if did:
            ids.add(did)
    return ids


# ── Result loading ───────────────────────────────────────────────────────────

def _log_sort_key(name: str) -> tuple[int, int]:
    """'D001_3' → (1, 3) for natural numeric sorting."""
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def load_results() -> list[dict]:
    """Load all per-file result JSONs (skip summary.json), naturally sorted."""
    results = []
    for path in RESULTS_DIR.glob("*_result.json"):
        with open(path, encoding="utf-8") as f:
            results.append(json.load(f))
    results.sort(key=lambda r: _log_sort_key(r["log_file"]))
    return results


def ground_truth_disease(log_name: str) -> str:
    """Extract disease ID from log filename, e.g. 'D001_3' → 'D001'."""
    m = re.match(r"(D\d+)", log_name)
    if not m:
        raise ValueError(f"Cannot extract disease ID from '{log_name}'")
    return m.group(1)


def all_matched_disease_ids(turn: dict) -> set[str]:
    """Return ALL disease IDs from disease_matches (fully_met + top_partial)."""
    dm = turn["disease_matches"]
    ids = set()
    for d in dm.get("fully_met", []):
        ids.add(d["disease_id"])
    for d in dm.get("top_partial", []):
        ids.add(d["disease_id"])
    return ids


# ── Main evaluation ──────────────────────────────────────────────────────────

def evaluate():
    name2id = _build_name_to_id()
    results = load_results()
    if not results:
        print("No result files found.", file=sys.stderr)
        sys.exit(1)

    max_turn = max(r["total_turns"] for r in results)

    turn_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "n": 0, "total_pred": 0})
    sample_turns = []
    skipped = 0

    for r in results:
        log_name = r["log_file"]
        gt = ground_truth_disease(log_name)
        log_file = LOGS_DIR / f"{log_name}.txt"

        if not log_file.exists():
            print(f"  [warn] Log file not found: {log_file}, skipping.", file=sys.stderr)
            skipped += 1
            continue

        doctor_cands = extract_doctor_candidates_per_turn(log_file)
        n_turns = len(r["turns"])

        if len(doctor_cands) < n_turns:
            print(
                f"  [warn] {log_name}: {len(doctor_cands)} doctor inference blocks "
                f"but {n_turns} patient turns, skipping.",
                file=sys.stderr,
            )
            skipped += 1
            continue

        for turn in r["turns"]:
            t = turn["turn"]
            turn_idx = t - 1  # 0-based

            # Doctor's candidates after this patient turn
            if turn_idx < len(doctor_cands):
                preds = _names_to_ids(doctor_cands[turn_idx], name2id)
                raw_candidates = doctor_cands[turn_idx]
            else:
                preds = set()
                raw_candidates = []

            # possible_truth = all diseases in disease_matches (fully_met + top_partial)
            pt = all_matched_disease_ids(turn)
            truth_set = {gt} | pt

            tp = len(preds & truth_set)
            fp = len(preds - truth_set)
            fn = len(truth_set - preds)
            n_truth = len(truth_set)

            stats = turn_stats[t]
            stats["tp"] += tp
            stats["fp"] += fp
            stats["fn"] += fn
            stats["n"] += 1
            stats["total_pred"] += len(preds)

            sample_turns.append({
                "log_file": log_name,
                "turn": t,
                "patient_response": turn["patient_response"],
                "identified_symptoms": turn["identified_symptoms"],
                "symptom_reasoning": turn["symptom_reasoning"],
                "ground_truth": gt,
                "possible_truth": sorted(pt),
                "predicted": sorted(preds),
                "predicted_names": raw_candidates,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": round(tp / len(preds), 4) if preds else 0.0,
                "recall": round(tp / n_truth, 4),
                "accuracy": round(tp / len(preds | truth_set), 4) if (preds | truth_set) else 0.0,
            })

    # Print table
    header = f"{'Turn':>5}  {'N':>5}  {'Acc':>8}  {'Prec':>8}  {'Recall':>8}  {'TP':>5}  {'FP':>5}  {'FN':>5}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)

    for t in range(1, max_turn + 1):
        s = turn_stats[t]
        n = s["n"]
        if n == 0:
            continue
        prec = s["tp"] / s["total_pred"] if s["total_pred"] > 0 else 0.0
        rec = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) > 0 else 0.0
        acc = s["tp"] / (s["tp"] + s["fp"] + s["fn"]) if (s["tp"] + s["fp"] + s["fn"]) > 0 else 0.0
        print(
            f"{t:>5}  {n:>5}  {acc:>8.4f}  {prec:>8.4f}  {rec:>8.4f}  "
            f"{s['tp']:>5}  {s['fp']:>5}  {s['fn']:>5}"
        )

    print(sep)

    all_tp = sum(s["tp"] for s in turn_stats.values())
    all_fp = sum(s["fp"] for s in turn_stats.values())
    all_fn = sum(s["fn"] for s in turn_stats.values())
    all_n = sum(s["n"] for s in turn_stats.values())
    all_pred = sum(s["total_pred"] for s in turn_stats.values())

    overall_prec = all_tp / all_pred if all_pred else 0
    overall_rec = all_tp / (all_tp + all_fn) if (all_tp + all_fn) else 0
    overall_acc = all_tp / (all_tp + all_fp + all_fn) if (all_tp + all_fp + all_fn) else 0
    print(
        f"{'ALL':>5}  {all_n:>5}  {overall_acc:>8.4f}  {overall_prec:>8.4f}  {overall_rec:>8.4f}  "
        f"{all_tp:>5}  {all_fp:>5}  {all_fn:>5}"
    )
    print(sep)
    if skipped:
        print(f"\n({skipped} log files not found, skipped)")

    out_path = RESULTS_DIR / "turn_eval.json"
    out_path.write_text(json.dumps(sample_turns, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(sample_turns)} sample-turn entries to {out_path}")


if __name__ == "__main__":
    evaluate()
