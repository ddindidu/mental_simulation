#!/usr/bin/env python3
"""
Build classified case-study markdown files from existing per-model evaluation outputs.

Classification 1 (median split on per-case mean precision / mean recall):
  - high_precision_high_recall
  - high_precision_low_recall
  - low_precision_high_recall
  (low/low intentionally excluded per user request)

Classification 2 (median split on per-case mean inference quality (jaccard) /
mean question reasonability (composite_score)):
  - high_inference_high_question
  - high_inference_low_question
  - low_inference_high_question
  - low_inference_low_question

Median thresholds are computed globally across all cases from the four models
combined (gemini-3.5-flash, gemini-3.1-flash-lite, gpt-5.4-mini-2026-03-17,
qwen3-235b-a22b-2507). For each bucket, the N most "extreme" cases (largest
distance from the median on the relevant axis/axes) are selected, one output
markdown file per case, diversified across models.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
ANALYSIS_ROOT = BASE_DIR / "analysis" / "gemini-3.5-flash" / "gemini-3.5-flash"
LOGS_ROOT = BASE_DIR / "logs" / "gemini-3.5-flash" / "gemini-3.5-flash"
OUT_ROOT = BASE_DIR / "case_studies"

MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gpt-5.4-mini-2026-03-17",
    "qwen3-235b-a22b-2507",
]

N_PER_BUCKET = 5


def load_turn_eval(model: str) -> list[dict]:
    p = ANALYSIS_ROOT / model / "turn_eval.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_question_eval(model: str) -> list[dict]:
    p = ANALYSIS_ROOT / model / "question_eval_semantic.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_transcript(model: str, log_file: str) -> dict | None:
    p = LOGS_ROOT / model / f"{log_file}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def aggregate_cases() -> list[dict]:
    """Return one record per (model, log_file) with mean precision/recall/jaccard/composite."""
    cases: dict[tuple[str, str], dict] = {}

    for model in MODELS:
        turn_rows = load_turn_eval(model)
        by_log: dict[str, list[dict]] = {}
        for r in turn_rows:
            by_log.setdefault(r["log_file"], []).append(r)
        for log_file, rows in by_log.items():
            key = (model, log_file)
            cases[key] = {
                "model": model,
                "log_file": log_file,
                "ground_truth": rows[0].get("ground_truth"),
                "mean_precision": statistics.fmean(r["precision"] for r in rows),
                "mean_recall": statistics.fmean(r["recall"] for r in rows),
                "mean_jaccard": statistics.fmean(r["jaccard"] for r in rows),
                "n_turns_inference": len(rows),
            }

        q_rows = load_question_eval(model)
        for q in q_rows:
            key = (model, q["log_file"])
            turns = [t for t in q.get("turns", []) if not t.get("skipped")]
            if not turns or key not in cases:
                continue
            cases[key]["mean_composite"] = statistics.fmean(
                t["composite_score"] for t in turns
            )
            dcs_vals = [t["dcs"] for t in turns if t.get("dcs") is not None]
            cases[key]["mean_dcs"] = statistics.fmean(dcs_vals) if dcs_vals else 0.0
            cases[key]["mean_mandatory_first"] = statistics.fmean(
                t["mandatory_first_compliance"] for t in turns
            )
            cases[key]["mean_redundancy_penalty"] = statistics.fmean(
                t["redundancy_penalty"] for t in turns
            )
            cases[key]["n_turns_question"] = len(turns)
            cases[key]["safety_all_covered"] = q.get(
                "safety_screening_compliance", {}
            ).get("all_covered")
            cases[key]["question_turns"] = turns

    # keep only cases that have both inference and question data
    return [c for c in cases.values() if "mean_composite" in c]


def median_split(cases: list[dict]) -> dict[str, float]:
    return {
        "precision": statistics.median(c["mean_precision"] for c in cases),
        "recall": statistics.median(c["mean_recall"] for c in cases),
        "jaccard": statistics.median(c["mean_jaccard"] for c in cases),
        "composite": statistics.median(c["mean_composite"] for c in cases),
        "dcs": statistics.median(c["mean_dcs"] for c in cases),
        "mandatory_first": statistics.median(c["mean_mandatory_first"] for c in cases),
        "redundancy_penalty": statistics.median(c["mean_redundancy_penalty"] for c in cases),
    }


def classify(cases: list[dict], med: dict[str, float]) -> None:
    for c in cases:
        c["prec_level"] = "high" if c["mean_precision"] >= med["precision"] else "low"
        c["rec_level"] = "high" if c["mean_recall"] >= med["recall"] else "low"
        c["inf_level"] = "high" if c["mean_jaccard"] >= med["jaccard"] else "low"
        c["q_level"] = "high" if c["mean_composite"] >= med["composite"] else "low"
        c["cls1"] = f"{c['prec_level']}_precision_{c['rec_level']}_recall"
        c["cls2"] = f"{c['inf_level']}_inference_{c['q_level']}_question"


def pick_top(cases: list[dict], bucket_key: str, bucket_val: str, score_fn, n: int) -> list[dict]:
    subset = [c for c in cases if c[bucket_key] == bucket_val]
    subset.sort(key=score_fn, reverse=True)
    # diversify across models: greedily take highest score but skip if model already has 2 picks, until forced
    picked: list[dict] = []
    per_model_count: dict[str, int] = {}
    remaining = list(subset)
    while remaining and len(picked) < n:
        for i, c in enumerate(remaining):
            if per_model_count.get(c["model"], 0) < 2:
                picked.append(c)
                per_model_count[c["model"]] = per_model_count.get(c["model"], 0) + 1
                remaining.pop(i)
                break
        else:
            picked.append(remaining.pop(0))
    return picked


def render_case_md(c: dict, med: dict[str, float], axis_note: str) -> str:
    tx = load_transcript(c["model"], c["log_file"])
    lines = []
    lines.append(f"# Case {c['log_file']} — {c['model']}")
    lines.append("")
    lines.append(f"**Category axis:** {axis_note}")
    lines.append("")
    lines.append(f"- Ground truth disease: `{c['ground_truth']}`")
    if tx:
        lines.append(f"- Final diagnosis: {tx.get('final_diagnosis')}")
        lines.append(f"- Correct: {tx.get('is_correct')}")
        lines.append(f"- Closed at patient turn: {tx.get('closed_at_patient_turn')}")
    lines.append("")
    lines.append("## Metrics (case mean vs. global median)")
    lines.append("")
    lines.append("| Metric | Case mean | Global median | Level |")
    lines.append("|---|---|---|---|")
    lines.append(f"| Precision | {c['mean_precision']:.3f} | {med['precision']:.3f} | {c['prec_level']} |")
    lines.append(f"| Recall | {c['mean_recall']:.3f} | {med['recall']:.3f} | {c['rec_level']} |")
    lines.append(f"| Inference quality (jaccard) | {c['mean_jaccard']:.3f} | {med['jaccard']:.3f} | {c['inf_level']} |")
    def _level(value: float, median: float, hi: str, lo: str) -> str:
        if value > median:
            return hi
        if value < median:
            return lo
        return "at median"

    lines.append(f"| Question reasonability (composite) | {c['mean_composite']:.3f} | {med['composite']:.3f} | {c['q_level']} |")
    lines.append(f"|  ↳ DCS (discrimination coverage) | {c['mean_dcs']:.3f} | {med['dcs']:.3f} | {_level(c['mean_dcs'], med['dcs'], 'high', 'low')} |")
    lines.append(f"|  ↳ Mandatory-first compliance | {c['mean_mandatory_first']:.3f} | {med['mandatory_first']:.3f} | {_level(c['mean_mandatory_first'], med['mandatory_first'], 'high', 'low')} |")
    lines.append(f"|  ↳ Redundancy penalty (1=violation) | {c['mean_redundancy_penalty']:.3f} | {med['redundancy_penalty']:.3f} | {_level(c['mean_redundancy_penalty'], med['redundancy_penalty'], 'worse (more redundant)', 'better (less redundant)')} |")
    lines.append(f"| Safety screening fully covered | {c.get('safety_all_covered')} | | |")
    lines.append("")
    lines.append("## Question reasonability — per-turn breakdown")
    lines.append("")
    lines.append("| Turn | Question | DCS | Mandatory-first | Redundancy penalty | Composite |")
    lines.append("|---|---|---|---|---|---|")
    for t in c.get("question_turns", []):
        q_text = (t.get("question") or "").replace("|", "/").replace("\n", " ")
        dcs_str = f"{t['dcs']:.2f}" if t.get("dcs") is not None else "n/a (single candidate)"
        lines.append(
            f"| {t['turn']} | {q_text} | {dcs_str} | {t['mandatory_first_compliance']} | "
            f"{t['redundancy_penalty']} | {t['composite_score']:.2f} |"
        )
    lines.append("")
    lines.append("## Dialogue transcript")
    lines.append("")
    if tx:
        for turn in tx.get("transcript", []):
            role = turn.get("role", "?")
            content = turn.get("content", "")
            speaker = "**Doctor**" if role == "doctor" else "**Patient**"
            lines.append(f"{speaker}: {content}")
            lines.append("")
    else:
        lines.append("_Transcript file not found._")
    return "\n".join(lines)


def main() -> None:
    cases = aggregate_cases()
    med = median_split(cases)
    classify(cases, med)

    print(f"Total cases with full data: {len(cases)}")
    print(f"Global medians: {med}")

    OUT_ROOT.mkdir(exist_ok=True)

    cls1_buckets = {
        "high_precision_high_recall": lambda c: min(c["mean_precision"] - med["precision"], c["mean_recall"] - med["recall"]),
        "high_precision_low_recall": lambda c: (c["mean_precision"] - med["precision"]) - (c["mean_recall"] - med["recall"]),
        "low_precision_high_recall": lambda c: (c["mean_recall"] - med["recall"]) - (c["mean_precision"] - med["precision"]),
    }
    for bucket, score_fn in cls1_buckets.items():
        prec_level, _, rec_level, _ = bucket.split("_", 3)
        picked = pick_top(cases, "cls1", bucket, score_fn, N_PER_BUCKET)
        out_dir = OUT_ROOT / "classification1_precision_recall" / bucket
        out_dir.mkdir(parents=True, exist_ok=True)
        for c in picked:
            md = render_case_md(c, med, f"Classification 1: {bucket}")
            (out_dir / f"{c['model']}__{c['log_file']}.md").write_text(md, encoding="utf-8")
        print(f"cls1 {bucket}: {len(picked)} cases -> {out_dir}")

    cls2_buckets = {
        "high_inference_high_question": lambda c: min(c["mean_jaccard"] - med["jaccard"], c["mean_composite"] - med["composite"]),
        "high_inference_low_question": lambda c: (c["mean_jaccard"] - med["jaccard"]) - (c["mean_composite"] - med["composite"]),
        "low_inference_high_question": lambda c: (c["mean_composite"] - med["composite"]) - (c["mean_jaccard"] - med["jaccard"]),
        "low_inference_low_question": lambda c: -max(c["mean_jaccard"] - med["jaccard"], c["mean_composite"] - med["composite"]),
    }
    for bucket, score_fn in cls2_buckets.items():
        picked = pick_top(cases, "cls2", bucket, score_fn, N_PER_BUCKET)
        out_dir = OUT_ROOT / "classification2_inference_question" / bucket
        out_dir.mkdir(parents=True, exist_ok=True)
        for c in picked:
            md = render_case_md(c, med, f"Classification 2: {bucket}")
            (out_dir / f"{c['model']}__{c['log_file']}.md").write_text(md, encoding="utf-8")
        print(f"cls2 {bucket}: {len(picked)} cases -> {out_dir}")


if __name__ == "__main__":
    main()
