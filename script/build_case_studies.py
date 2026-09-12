#!/usr/bin/env python3
"""
Build classified case-study markdown files from existing per-model evaluation outputs.

Classification 1 (median split on per-case mean precision / mean recall):
  - high_precision_high_recall
  - high_precision_low_recall
  - low_precision_high_recall
  (low/low intentionally excluded per user request)

Classification 2 (median split on per-case mean inference quality (jaccard) /
mean information acquisition score (IAS)):
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
RESULTS_ROOT = BASE_DIR / "results" / "gemini-3.5-flash" / "gemini-3.5-flash"
SYMPTOM_DIR = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "symptom"
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


def load_symptom_result(model: str, log_file: str) -> dict | None:
    p = RESULTS_ROOT / model / f"{log_file}_result.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_symptom_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for p in sorted(SYMPTOM_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for sid, info in data.items():
            names[sid] = info.get("name", sid)
    return names


SYMPTOM_NAMES = load_symptom_names()


def fmt_symptoms(ids: list[str]) -> str:
    if not ids:
        return "(none)"
    return ", ".join(f"{sid} {SYMPTOM_NAMES.get(sid, '?')}" for sid in ids)


def aggregate_cases() -> list[dict]:
    """Return one record per (model, log_file) with mean precision/recall/jaccard/IAS."""
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
                "turn_eval_rows": rows,
            }

        q_rows = load_question_eval(model)
        for q in q_rows:
            key = (model, q["log_file"])
            turns = [t for t in q.get("turns", []) if not t.get("skipped")]
            if not turns or key not in cases:
                continue
            cases[key]["mean_ias"] = statistics.fmean(
                t["ias"] for t in turns
            )
            ecr_vals = [t["ecr"] for t in turns if t.get("ecr") is not None]
            cases[key]["mean_ecr"] = statistics.fmean(ecr_vals) if ecr_vals else 0.0
            cases[key]["mean_redundancy_penalty"] = statistics.fmean(
                t["redundancy_penalty"] for t in turns
            )
            cases[key]["n_turns_question"] = len(turns)
            cases[key]["safety_all_covered"] = q.get(
                "safety_screening_compliance", {}
            ).get("all_covered")
            cases[key]["question_turns"] = turns

    # keep only cases that have both inference and question data
    return [c for c in cases.values() if "mean_ias" in c]


def median_split(cases: list[dict]) -> dict[str, float]:
    return {
        "precision": statistics.median(c["mean_precision"] for c in cases),
        "recall": statistics.median(c["mean_recall"] for c in cases),
        "jaccard": statistics.median(c["mean_jaccard"] for c in cases),
        "ias": statistics.median(c["mean_ias"] for c in cases),
        "ecr": statistics.median(c["mean_ecr"] for c in cases),
        "redundancy_penalty": statistics.median(c["mean_redundancy_penalty"] for c in cases),
    }


def classify(cases: list[dict], med: dict[str, float]) -> None:
    for c in cases:
        c["prec_level"] = "high" if c["mean_precision"] >= med["precision"] else "low"
        c["rec_level"] = "high" if c["mean_recall"] >= med["recall"] else "low"
        c["inf_level"] = "high" if c["mean_jaccard"] >= med["jaccard"] else "low"
        c["q_level"] = "high" if c["mean_ias"] >= med["ias"] else "low"
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

    lines.append(f"| Information acquisition (IAS) | {c['mean_ias']:.3f} | {med['ias']:.3f} | {c['q_level']} |")
    lines.append(f"|  ↳ ECR (expected candidate reduction) | {c['mean_ecr']:.3f} | {med['ecr']:.3f} | {_level(c['mean_ecr'], med['ecr'], 'high', 'low')} |")
    lines.append(f"|  ↳ Redundancy penalty (1=violation) | {c['mean_redundancy_penalty']:.3f} | {med['redundancy_penalty']:.3f} | {_level(c['mean_redundancy_penalty'], med['redundancy_penalty'], 'worse (more redundant)', 'better (less redundant)')} |")
    lines.append(f"| Safety screening fully covered | {c.get('safety_all_covered')} | | |")
    lines.append("")
    lines.append("## Information acquisition — per-turn breakdown")
    lines.append("")
    lines.append("| Turn | Question | ECR | Redundancy penalty | IAS |")
    lines.append("|---|---|---|---|---|")
    for t in c.get("question_turns", []):
        q_text = (t.get("question") or "").replace("|", "/").replace("\n", " ")
        ecr_str = f"{t['ecr']:.2f}" if t.get("ecr") is not None else "n/a (single candidate)"
        lines.append(
            f"| {t['turn']} | {q_text} | {ecr_str} | "
            f"{t['redundancy_penalty']} | {t['ias']:.2f} |"
        )
    lines.append("")
    lines.append("## Dialogue transcript")
    lines.append("")
    if tx:
        inference_by_turn = {
            inf["turn"]: inf
            for inf in tx.get("doctor_memory", {}).get("inference_history", [])
        }
        turn_eval_by_turn = {r["turn"]: r for r in c.get("turn_eval_rows", [])}
        question_by_turn = {t["turn"]: t for t in c.get("question_turns", [])}
        symptom_result = load_symptom_result(c["model"], c["log_file"])
        symptom_by_turn = (
            {t["turn"]: t for t in symptom_result.get("turns", [])}
            if symptom_result
            else {}
        )

        def render_symptom_judge(k: int) -> None:
            s = symptom_by_turn.get(k)
            if s is None:
                return
            lines.append(
                f"> **Judge (symptom extraction)** — confirmed: {fmt_symptoms(s.get('new_confirmed_symptoms', []))}"
            )
            lines.append(
                f"> denied: {fmt_symptoms(s.get('new_denied_symptoms', []))}"
            )
            reasoning = s.get("symptom_reasoning") or {}
            for sid, why in reasoning.items():
                lines.append(f"> - {sid} {SYMPTOM_NAMES.get(sid, '?')}: {why}")
            lines.append("")

        def render_inference(inf: dict) -> None:
            label = "Doctor's inference (final)" if inf.get("is_final") else "Doctor's inference"
            candidates = ", ".join(inf.get("candidates", []))
            lines.append(f"> {label} — candidates: {candidates}")
            note = (inf.get("note") or "").strip()
            if note:
                lines.append(f"> {note}")
            lines.append("")

        def render_inference_judge(k: int) -> None:
            r = turn_eval_by_turn.get(k)
            if r is None:
                return
            lines.append(
                f"> **Judge (inference scoring)** — predicted: {', '.join(r['predicted'])}"
            )
            lines.append(f"> reference (truth) set: {', '.join(r['truth_set'])}")
            lines.append(
                f"> TP={r['tp']} FP={r['fp']} FN={r['fn']} | "
                f"precision={r['precision']:.2f} recall={r['recall']:.2f} "
                f"accuracy={r['accuracy']:.2f} jaccard={r['jaccard']:.2f} "
                f"weighted_recall={r['weighted_recall']:.2f}"
            )
            lines.append("")

        def render_question_judge(k: int) -> None:
            q = question_by_turn.get(k)
            if q is None or q.get("skipped"):
                return
            ecr_str = f"{q['ecr']:.2f}" if q.get("ecr") is not None else "n/a (single candidate)"
            lines.append(
                f"> **Judge (question scoring)** — targeted symptoms: "
                f"{fmt_symptoms(q.get('question_targets', []))}"
            )
            lines.append(
                f"> diagnostic_relevance={q.get('diagnostic_relevance')} "
                f"redundancy_penalty={q['redundancy_penalty']} "
                f"ECR={ecr_str} "
                f"IAS={q['ias']:.2f}"
            )
            lines.append("")

        patient_turn_count = 0
        pending_turn: int | None = None
        for turn in tx.get("transcript", []):
            role = turn.get("role", "?")
            content = turn.get("content", "")
            if role == "doctor":
                if pending_turn is not None:
                    inf = inference_by_turn.get(pending_turn)
                    if inf is not None:
                        render_inference(inf)
                    render_inference_judge(pending_turn)
                lines.append(f"**Doctor**: {content}")
                lines.append("")
                if pending_turn is not None:
                    render_question_judge(pending_turn)
                    pending_turn = None
            else:
                lines.append(f"**Patient**: {content}")
                lines.append("")
                patient_turn_count += 1
                render_symptom_judge(patient_turn_count)
                pending_turn = patient_turn_count
        if pending_turn is not None:
            inf = inference_by_turn.get(pending_turn)
            if inf is not None:
                render_inference(inf)
            render_inference_judge(pending_turn)
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
        "high_inference_high_question": lambda c: min(c["mean_jaccard"] - med["jaccard"], c["mean_ias"] - med["ias"]),
        "high_inference_low_question": lambda c: (c["mean_jaccard"] - med["jaccard"]) - (c["mean_ias"] - med["ias"]),
        "low_inference_high_question": lambda c: (c["mean_ias"] - med["ias"]) - (c["mean_jaccard"] - med["jaccard"]),
        "low_inference_low_question": lambda c: -max(c["mean_jaccard"] - med["jaccard"], c["mean_ias"] - med["ias"]),
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
