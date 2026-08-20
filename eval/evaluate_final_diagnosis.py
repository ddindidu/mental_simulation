#!/usr/bin/env python3
"""
Per-disease accuracy of the doctor's final diagnosis.

Ground truth : disease ID from log filename (e.g. D001_8.txt → D001)
Prediction   : "diagnosis" field from the last doctor block in the log
               (an ICD-10 code, e.g. "F32.9")
Mapping      : disorder_icd10.json (disease_id → ICD-10 code)

A sample is correct when the predicted ICD-10 code maps to the
ground-truth disease ID (case-insensitive exact match).
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

BASE_DIR      = Path(__file__).resolve().parent.parent
DISORDER_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "disorder.json"
DISORDER_ICD10_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "disorder_icd10.json"

from utils.llm import get_run_dir as _get_run_dir
from utils.paths import batch_artifact_dirs
_RUN_DIR = _get_run_dir()
RUN_ROOT, LOGS_DIR, _ = batch_artifact_dirs(_RUN_DIR)


def load_disorder_map() -> tuple[dict[str, str], dict[str, str]]:
    """Return (id→name, icd10_code→id). Names come from disorder.json (for display
    only); the code map comes from disorder_icd10.json and is what predictions
    are matched against, since the doctor now outputs ICD-10 codes."""
    with open(DISORDER_FILE, encoding="utf-8") as f:
        data = json.load(f)
    id2name = {k: v["name"] for k, v in data.items()}
    with open(DISORDER_ICD10_FILE, encoding="utf-8") as f:
        icd10_data = json.load(f)
    code2id = {v["icd10_code"].strip().upper(): k for k, v in icd10_data.items()}
    return id2name, code2id


def extract_final_diagnosis(log_file: Path) -> str | None:
    """Return the doctor's final diagnosis string, or None if missing."""
    text = log_file.read_text(encoding="utf-8")
    blocks = re.findall(
        r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}",
        text,
        re.DOTALL,
    )
    for b in reversed(blocks):  # final diagnosis is the last doctor block
        b = b.strip()
        # Strip markdown code fences if present (e.g. ```json ... ```)
        b = re.sub(r"^```(?:json)?\s*", "", b)
        b = re.sub(r"\s*```$", "", b).strip()
        try:
            parsed = json.loads(b)
            if isinstance(parsed, dict) and "diagnosis" in parsed:
                return str(parsed["diagnosis"]).strip()
        except (json.JSONDecodeError, ValueError):
            m = re.search(r"\{[\s\S]*\}", b)
            if m:
                try:
                    parsed = json.loads(m.group())
                    if isinstance(parsed, dict) and "diagnosis" in parsed:
                        return str(parsed["diagnosis"]).strip()
                except (json.JSONDecodeError, ValueError):
                    pass
            continue
    return None


def ground_truth_id(log_name: str) -> str | None:
    m = re.match(r"(D\d+)", log_name)
    return m.group(1) if m else None


def _log_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def main():
    id2name, code2id = load_disorder_map()

    log_files = sorted(LOGS_DIR.glob("*.txt"), key=lambda p: _log_sort_key(p.stem))
    if not log_files:
        print(f"No log files in {LOGS_DIR}", file=sys.stderr)
        sys.exit(1)

    # per-disease stats
    stats = defaultdict(lambda: {"total": 0, "correct": 0, "runs": []})
    no_diagnosis = 0

    for log_file in log_files:
        gt = ground_truth_id(log_file.stem)
        if gt is None:
            continue

        diagnosis = extract_final_diagnosis(log_file)
        if diagnosis is None:
            no_diagnosis += 1
            stats[gt]["total"] += 1
            stats[gt]["runs"].append({
                "log": log_file.stem,
                "diagnosis": None,
                "predicted_id": None,
                "correct": False,
            })
            continue

        pred_id = code2id.get(diagnosis.strip().upper())
        is_correct = pred_id == gt

        stats[gt]["total"] += 1
        if is_correct:
            stats[gt]["correct"] += 1
        stats[gt]["runs"].append({
            "log": log_file.stem,
            "diagnosis": diagnosis,
            "predicted_id": pred_id,
            "correct": is_correct,
        })

    # ── Build output lines ────────────────────────────────────────────────
    disease_ids = sorted(stats.keys(), key=lambda x: int(x[1:]))
    runs_per_disease = max((s["total"] for s in stats.values()), default=0)

    lines: list[str] = [
        "=" * 60,
        f"Batch Evaluation Results  (difficulty=medium, runs={runs_per_disease})",
        "=" * 60,
        f"{'Code':<8} {'Accuracy':>10}  {'Correct':>8}  Disease Name",
        "-" * 60,
    ]

    total_n, total_correct = 0, 0
    for did in disease_ids:
        s = stats[did]
        acc = s["correct"] / s["total"] if s["total"] else 0.0
        total_n += s["total"]
        total_correct += s["correct"]
        name = id2name.get(did, did)
        lines.append(
            f"{did:<8} {acc:>10.2%}  {s['correct']:>3}/{s['total']:<3}  {name}"
        )

    lines.append("-" * 60)
    overall = total_correct / total_n if total_n else 0.0
    lines.append(f"{'TOTAL':<8} {overall:>10.2%}  {total_correct:>3}/{total_n:<3}")
    lines.append("=" * 60)

    output = "\n".join(lines) + "\n"
    print(output)
    if no_diagnosis:
        print(f"({no_diagnosis} log file(s) had no final diagnosis)")

    # ── Save TXT ──────────────────────────────────────────────────────────
    out_path = RUN_ROOT / "final_diagnosis_eval.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
