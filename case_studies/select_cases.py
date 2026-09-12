#!/usr/bin/env python3
"""
Case-study selection: for each of 5 evaluation axes, find the doctor model that
is characteristically strongest / weakest on that axis, then pick one
representative high-scoring and one low-scoring episode (or turn, for the
question-quality axis) from that model.

Writes case_studies/data/<axis>_<high|low>.json (full joined data bundle)
and prints a selection report to stdout.
"""
import json
import statistics as stats
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RESULTS = BASE / "results" / "gemini-3.5-flash" / "gemini-3.5-flash"
ANALYSIS = BASE / "analysis" / "gemini-3.5-flash" / "gemini-3.5-flash"
OUT = Path(__file__).resolve().parent / "data"
OUT.mkdir(parents=True, exist_ok=True)

DOCTOR_MODELS = [
    "gpt-5.4",
    "gpt-5.4-mini-2026-03-17",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "qwen3-235b-a22b-2507",
    "llama-3.3-70b-instruct",
]

KG = BASE / "mentalbench" / "resources" / "knowledge_graph" / "EN"


def load_json(p: Path):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


DISORDER_NAMES = {k: v["name"] for k, v in load_json(KG / "disorder.json").items()}
N_DISORDERS = len(DISORDER_NAMES)

SYMPTOM_NAMES = {}
for f in (KG / "symptom").glob("*.json"):
    SYMPTOM_NAMES.update(load_json(f))

SAFETY_SYMPTOM_IDS = ["S019", "S020", "S021", "S022", "S032", "S078"]


def sname(sid: str) -> str:
    v = SYMPTOM_NAMES.get(sid)
    return v["name"].replace("_", " ") if v else sid


def dname(did: str) -> str:
    return DISORDER_NAMES.get(did, did)


# ── Load all per-model data ────────────────────────────────────────────────

class ModelData:
    def __init__(self, model: str):
        self.model = model
        d = RESULTS / model
        self.summary = {e["log_file"]: e for e in load_json(d / "summary.json")}
        self.question_eval = {e["log_file"]: e for e in load_json(d / "question_eval.json")}
        self.diagnostic_reasoning = {e["log_file"]: e for e in load_json(d / "diagnostic_reasoning_eval.json")}
        self.efficiency = {e["log_file"]: e for e in load_json(d / "efficiency_eval.json")}
        turn_eval_list = load_json(ANALYSIS / model / "turn_eval.json")
        self.turn_eval = {}
        for t in turn_eval_list:
            self.turn_eval.setdefault(t["log_file"], {})[t["turn"]] = t
        self.log_files = sorted(self.summary.keys())


MODELS = {m: ModelData(m) for m in DOCTOR_MODELS}

print(f"Loaded {len(MODELS)} doctor models, {N_DISORDERS} disorders, {len(SYMPTOM_NAMES)} symptoms\n")
for m, md in MODELS.items():
    print(f"  {m:28s} episodes={len(md.log_files):4d}")
print()

# ── Axis 1: Diagnosis inference precision ──────────────────────────────────

def episode_precision_stats(md: ModelData, log: str):
    te = md.turn_eval.get(log, {})
    precisions = [t["precision"] for t in te.values()]
    if not precisions:
        return None
    eff = md.efficiency.get(log, {})
    return {
        "mean_precision": stats.mean(precisions),
        "final_accuracy": eff.get("final_accuracy"),
        "turn_count": eff.get("turn_count"),
    }

print("=" * 70)
print("AXIS 1: Diagnosis inference precision (turn-level, vs KG-derived truth set)")
print("=" * 70)
axis1_model_stats = {}
for m, md in MODELS.items():
    vals = []
    for log in md.log_files:
        s = episode_precision_stats(md, log)
        if s:
            vals.append(s["mean_precision"])
    axis1_model_stats[m] = stats.mean(vals) if vals else 0.0
    print(f"  {m:28s} mean_precision={axis1_model_stats[m]:.4f}  n={len(vals)}")

best_model = max(axis1_model_stats, key=axis1_model_stats.get)
worst_model = min(axis1_model_stats, key=axis1_model_stats.get)
print(f"  -> HIGH exemplar model: {best_model}")
print(f"  -> LOW  exemplar model: {worst_model}")
print()

# pick episode within each exemplar model
def pick_axis1_episode(md: ModelData, want_high: bool):
    scored = []
    for log in md.log_files:
        s = episode_precision_stats(md, log)
        if not s or s["turn_count"] is None or s["turn_count"] < 4:
            continue
        acc_match = (s["final_accuracy"] == (1.0 if want_high else 0.0))
        scored.append((acc_match, s["mean_precision"] if want_high else -s["mean_precision"], log, s))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return scored[0] if scored else None

a1_high = pick_axis1_episode(MODELS[best_model], True)
a1_low = pick_axis1_episode(MODELS[worst_model], False)
print(f"  HIGH case: {best_model} / {a1_high[2]}  mean_precision={a1_high[3]['mean_precision']:.3f} final_acc={a1_high[3]['final_accuracy']}")
print(f"  LOW  case: {worst_model} / {a1_low[2]}  mean_precision={a1_low[3]['mean_precision']:.3f} final_acc={a1_low[3]['final_accuracy']}")
print()

# ── Axis 2: Information acquisition (turn-level within episode, IAS) ──────

print("=" * 70)
print("AXIS 2: Information acquisition (LLM-judge IAS, per turn)")
print("=" * 70)
axis2_model_stats = {}
for m, md in MODELS.items():
    vals = []
    for log, qe in md.question_eval.items():
        em = qe.get("episode_metrics", {}).get("llm_judge", {})
        if em.get("mean_ias") is not None:
            vals.append(em["mean_ias"])
    axis2_model_stats[m] = stats.mean(vals) if vals else 0.0
    print(f"  {m:28s} mean_ias={axis2_model_stats[m]:.4f}  n={len(vals)}")

a2_best_model = max(axis2_model_stats, key=axis2_model_stats.get)
a2_worst_model = min(axis2_model_stats, key=axis2_model_stats.get)
print(f"  -> HIGH exemplar model: {a2_best_model}")
print(f"  -> LOW  exemplar model: {a2_worst_model}")
print()


def pick_axis2_turn(md: ModelData, want_good: bool):
    """Return (log, turn_idx_in_list, turn_entry, prev_size, this_size) best/worst example."""
    best = None
    for log, qe in md.question_eval.items():
        turns = qe.get("turns", [])
        for i, t in enumerate(turns):
            lj = t.get("scores_by_mapper", {}).get("llm_judge", {})
            comp = lj.get("ias")
            if comp is None:
                continue
            prev_size = turns[i - 1]["candidate_size"] if i > 0 else N_DISORDERS
            this_size = t["candidate_size"]
            shrank = this_size < prev_size
            grew_or_same = this_size >= prev_size
            if want_good:
                if i == len(turns) - 1:
                    continue  # need a "what happened after" turn
                if not shrank:
                    continue
                key = comp
            else:
                if not grew_or_same:
                    continue
                key = -comp
            cand = (key, log, i, t, prev_size, this_size)
            if best is None or cand[0] > best[0]:
                best = cand
    return best

a2_high = pick_axis2_turn(MODELS[a2_best_model], True)
a2_low = pick_axis2_turn(MODELS[a2_worst_model], False)
print(f"  HIGH case: {a2_best_model} / {a2_high[1]} turn {a2_high[3]['turn']}  ias={a2_high[3]['scores_by_mapper']['llm_judge']['ias']:.3f}  cand {a2_high[4]}->{a2_high[5]}")
print(f"  LOW  case: {a2_worst_model} / {a2_low[1]} turn {a2_low[3]['turn']}  ias={a2_low[3]['scores_by_mapper']['llm_judge']['ias']:.3f}  cand {a2_low[4]}->{a2_low[5]}")
print()

# ── Axis 3: Diagnostic reasoning coverage ──────────────────────────────────

print("=" * 70)
print("AXIS 3: Diagnostic reasoning coverage (final-diagnosis checklist vs DSM-5 criteria)")
print("=" * 70)
axis3_model_stats = {}
for m, md in MODELS.items():
    vals = [e["overall_score"] for e in md.diagnostic_reasoning.values()
            if e.get("overall_score") is not None and not e.get("_parse_error") and e.get("has_structured_checklist")]
    axis3_model_stats[m] = stats.mean(vals) if vals else 0.0
    print(f"  {m:28s} mean_overall_score={axis3_model_stats[m]:.4f}  n={len(vals)}")

a3_best_model = max(axis3_model_stats, key=axis3_model_stats.get)
a3_worst_model = min(axis3_model_stats, key=axis3_model_stats.get)
print(f"  -> HIGH exemplar model: {a3_best_model}")
print(f"  -> LOW  exemplar model: {a3_worst_model}")
print()


def pick_axis3_episode(md: ModelData, want_high: bool):
    scored = []
    for log, e in md.diagnostic_reasoning.items():
        if e.get("overall_score") is None or e.get("_parse_error") or not e.get("has_structured_checklist"):
            continue
        eff = md.efficiency.get(log, {})
        if (eff.get("turn_count") or 0) < 4:
            continue
        scored.append((e["overall_score"], log, e))
    scored.sort(key=lambda x: x[0], reverse=want_high)
    return scored[0] if scored else None

a3_high = pick_axis3_episode(MODELS[a3_best_model], True)
a3_low = pick_axis3_episode(MODELS[a3_worst_model], False)
print(f"  HIGH case: {a3_best_model} / {a3_high[1]}  overall_score={a3_high[2]['overall_score']:.3f}")
print(f"  LOW  case: {a3_worst_model} / {a3_low[1]}  overall_score={a3_low[2]['overall_score']:.3f}")
print()

# ── Axis 4: Efficiency / redundancy ────────────────────────────────────────

print("=" * 70)
print("AXIS 4: Interview efficiency (candidate-set shrink rate, backtracking, redundancy)")
print("=" * 70)
axis4_model_stats = {}
for m, md in MODELS.items():
    cssrs, redund, mono = [], [], []
    for e in md.efficiency.values():
        if e.get("cssr") is None:
            continue
        cssrs.append(e["cssr"])
        redund.append(e.get("redundant_turn_ratio") or 0)
        mono.append(e.get("monotonicity_violations") or 0)
    m_cssr = stats.mean(cssrs) if cssrs else 0.0
    m_red = stats.mean(redund) if redund else 0.0
    m_mono = stats.mean(mono) if mono else 0.0
    composite = m_cssr - 3 * m_red - 1 * m_mono
    axis4_model_stats[m] = composite
    print(f"  {m:28s} mean_cssr={m_cssr:6.3f}  mean_redundant_ratio={m_red:.3f}  mean_monotonicity_viol={m_mono:.3f}  composite={composite:6.3f}")

a4_best_model = max(axis4_model_stats, key=axis4_model_stats.get)
a4_worst_model = min(axis4_model_stats, key=axis4_model_stats.get)
print(f"  -> HIGH (efficient) exemplar model: {a4_best_model}")
print(f"  -> LOW  (inefficient) exemplar model: {a4_worst_model}")
print()


def pick_axis4_episode(md: ModelData, want_efficient: bool):
    scored = []
    for log, e in md.efficiency.items():
        if e.get("cssr") is None or (e.get("turn_count") or 0) < 4:
            continue
        comp = e["cssr"] - 3 * (e.get("redundant_turn_ratio") or 0) - (e.get("monotonicity_violations") or 0)
        if want_efficient and e.get("final_accuracy") != 1.0:
            continue
        scored.append((comp, log, e))
    scored.sort(key=lambda x: x[0], reverse=want_efficient)
    return scored[0] if scored else None

a4_high = pick_axis4_episode(MODELS[a4_best_model], True)
a4_low = pick_axis4_episode(MODELS[a4_worst_model], False)
print(f"  HIGH case: {a4_best_model} / {a4_high[1]}  cssr={a4_high[2]['cssr']:.3f} redund={a4_high[2]['redundant_turn_ratio']:.3f} mono={a4_high[2]['monotonicity_violations']}")
print(f"  LOW  case: {a4_worst_model} / {a4_low[1]}  cssr={a4_low[2]['cssr']:.3f} redund={a4_low[2]['redundant_turn_ratio']:.3f} mono={a4_low[2]['monotonicity_violations']}")
print()

# ── Axis 5: Safety-critical screening compliance ───────────────────────────

print("=" * 70)
print("AXIS 5: Safety-critical symptom screening compliance")
print("=" * 70)
axis5_model_stats = {}
for m, md in MODELS.items():
    rates = []
    for log, qe in md.question_eval.items():
        ssc = qe.get("safety_screening_compliance")
        if not ssc:
            continue
        covered = sum(1 for k in SAFETY_SYMPTOM_IDS if ssc.get(k))
        rates.append(covered / len(SAFETY_SYMPTOM_IDS))
    axis5_model_stats[m] = stats.mean(rates) if rates else 0.0
    print(f"  {m:28s} mean_coverage_fraction={axis5_model_stats[m]:.4f}  n={len(rates)}")

a5_best_model = max(axis5_model_stats, key=axis5_model_stats.get)
a5_worst_model = min(axis5_model_stats, key=axis5_model_stats.get)
print(f"  -> HIGH exemplar model: {a5_best_model}")
print(f"  -> LOW  exemplar model: {a5_worst_model}")
print()


def pick_axis5_episode(md: ModelData, want_high: bool):
    scored = []
    for log, qe in md.question_eval.items():
        ssc = qe.get("safety_screening_compliance")
        if not ssc:
            continue
        eff = md.efficiency.get(log, {})
        if (eff.get("turn_count") or 0) < 4:
            continue
        covered = sum(1 for k in SAFETY_SYMPTOM_IDS if ssc.get(k))
        scored.append((covered, log, qe))
    scored.sort(key=lambda x: x[0], reverse=want_high)
    return scored[0] if scored else None

a5_high = pick_axis5_episode(MODELS[a5_best_model], True)
a5_low = pick_axis5_episode(MODELS[a5_worst_model], False)
print(f"  HIGH case: {a5_best_model} / {a5_high[1]}  covered={a5_high[0]}/{len(SAFETY_SYMPTOM_IDS)}")
print(f"  LOW  case: {a5_worst_model} / {a5_low[1]}  covered={a5_low[0]}/{len(SAFETY_SYMPTOM_IDS)}")
print()

# ════════════════════════════════════════════════════════════════════════
# Bundle construction: join every source for the 10 selected cases and
# write self-contained JSON bundles to case_studies/data/.
# ════════════════════════════════════════════════════════════════════════

import re

LOGS_ROOT = BASE / "logs" / "gemini-3.5-flash" / "gemini-3.5-flash"
ICD10_MAP = load_json(KG / "disorder_icd10.json")
CODE2ID = {}
for k, v in ICD10_MAP.items():
    for code in v.get("icd10_accepted_codes") or [v["icd10_code"]]:
        CODE2ID[code.strip().upper()] = k

DOCTOR_BLOCK_RE = re.compile(r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}", re.DOTALL)


def _strip_fences(b: str) -> str:
    b = b.strip()
    b = re.sub(r"^```(?:json)?\s*", "", b)
    b = re.sub(r"\s*```$", "", b).strip()
    return b


def parse_doctor_blocks(model: str, log: str):
    """Return (opening_question_text, final_block_dict) parsed from the raw txt log."""
    path = LOGS_ROOT / model / f"{log}.txt"
    if not path.exists():
        return None, None
    text = path.read_text(encoding="utf-8")
    blocks = DOCTOR_BLOCK_RE.findall(text)
    opening_q = None
    final_block = None
    for b in blocks:
        stripped = _strip_fences(b)
        try:
            parsed = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            m = re.search(r"\{[\s\S]*\}", stripped)
            if not m:
                continue
            try:
                parsed = json.loads(m.group())
            except (json.JSONDecodeError, ValueError):
                continue
        if not isinstance(parsed, dict):
            continue
        if opening_q is None and "question" in parsed:
            opening_q = parsed.get("question")
        if "diagnosis" in parsed:
            final_block = parsed  # keep overwriting -> ends on the LAST diagnosis block
    return opening_q, final_block


def resolve_disease_id(code: str | None) -> str | None:
    if not code:
        return None
    return CODE2ID.get(code.strip().upper())


def annotate_symptom_ids(ids):
    return [{"id": s, "name": sname(s)} for s in ids]


def annotate_disease_ids(ids):
    return [{"id": d, "name": dname(d)} for d in ids]


def build_bundle(axis: str, level: str, model: str, log: str, rationale: str,
                  model_aggregate_all: dict, highlighted_turn: int | None = None):
    md = MODELS[model]
    summ = md.summary[log]
    qe = md.question_eval.get(log, {})
    dre = md.diagnostic_reasoning.get(log, {})
    eff = md.efficiency.get(log, {})
    te = md.turn_eval.get(log, {})

    gt_id = qe.get("ground_truth") or (log[:4] if log[0] == "D" else None)
    opening_q, final_block = parse_doctor_blocks(model, log)

    final_code = eff.get("final_diagnosis")
    final_id = resolve_disease_id(final_code)

    qe_turns = {t["turn"]: t for t in qe.get("turns", [])}

    turns_out = []
    for t in summ.get("turns", []):
        i = t["turn"]
        prior_qe = qe_turns.get(i - 1)  # question that elicited THIS patient_response
        tev = te.get(i)
        prior_q_text = prior_qe.get("question") if prior_qe else None
        rec = {
            "turn": i,
            "question": prior_q_text if prior_q_text else (opening_q if prior_qe is None else None),
            "is_opening": prior_qe is None,
            "question_skipped_reason": prior_qe.get("skipped") if prior_qe and not prior_q_text else None,
            "patient_response": t["patient_response"],
            "new_confirmed_symptoms": annotate_symptom_ids(t.get("new_confirmed_symptoms", [])),
            "new_denied_symptoms": annotate_symptom_ids(t.get("new_denied_symptoms", [])),
            "symptom_reasoning": t.get("symptom_reasoning", {}),
            "reference_candidates": {
                "high_likely": annotate_disease_ids(t.get("candidate_set", {}).get("high_likely", [])),
                "moderate_likely": annotate_disease_ids(t.get("candidate_set", {}).get("moderate_likely", [])),
                "low_likely": annotate_disease_ids(t.get("candidate_set", {}).get("low_likely", [])),
                "excluded": annotate_disease_ids(t.get("candidate_set", {}).get("excluded", [])),
            },
            "doctor_stated": None,
            "question_scores": None,
        }
        if tev:
            rec["doctor_stated"] = {
                "predicted": annotate_disease_ids(tev.get("predicted", [])),
                "predicted_codes": tev.get("predicted_codes", []),
                "truth_set": annotate_disease_ids(tev.get("truth_set", [])),
                "precision": tev.get("precision"),
                "recall": tev.get("recall"),
                "accuracy": tev.get("accuracy"),
                "jaccard": tev.get("jaccard"),
                "weighted_recall": tev.get("weighted_recall"),
                "tp": tev.get("tp"), "fp": tev.get("fp"), "fn": tev.get("fn"),
            }
        if prior_qe and prior_q_text:
            lj = prior_qe.get("scores_by_mapper", {}).get("llm_judge", {})
            rec["question_scores"] = {
                "question_targets": annotate_symptom_ids(lj.get("question_targets", [])),
                "discriminative_targets": annotate_symptom_ids(lj.get("discriminative_targets", [])),
                "required_targets": annotate_symptom_ids(lj.get("required_targets", [])),
                "resolved_targets": annotate_symptom_ids(lj.get("resolved_targets", [])),
                "diagnostic_relevance": lj.get("diagnostic_relevance"),
                "redundancy_penalty": lj.get("redundancy_penalty"),
                "ias": lj.get("ias"),
                "ecr": lj.get("ecr"),
                "candidate_size_after": prior_qe.get("candidate_size"),
            }
        turns_out.append(rec)

    ssc = qe.get("safety_screening_compliance") or {}
    ssc_annotated = {
        "items": [{"id": s, "name": sname(s), "covered": bool(ssc.get(s))} for s in SAFETY_SYMPTOM_IDS],
        "all_covered": ssc.get("all_covered"),
    }

    bundle = {
        "axis": axis,
        "level": level,
        "doctor_model": model,
        "log_file": log,
        "rationale": rationale,
        "highlighted_turn": highlighted_turn,
        "ground_truth_id": gt_id,
        "ground_truth_name": dname(gt_id) if gt_id else None,
        "final_diagnosis_code": final_code,
        "final_diagnosis_id": final_id,
        "final_diagnosis_name": dname(final_id) if final_id else final_code,
        "final_accuracy": eff.get("final_accuracy"),
        "turn_count": eff.get("turn_count"),
        "doctor_final_reason": (final_block or {}).get("reason"),
        "doctor_diagnostic_checklist": (final_block or {}).get("diagnostic_checklist"),
        "episode_metrics": qe.get("episode_metrics"),
        "safety_screening_compliance": ssc_annotated,
        "diagnostic_reasoning": dre,
        "efficiency": eff,
        "model_aggregate_all_models": model_aggregate_all,
        "turns": turns_out,
    }
    out_path = OUT / f"{axis}_{level}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    print(f"  wrote {out_path.relative_to(BASE)}  ({len(turns_out)} turns)")
    return bundle


# ════════════════════════════════════════════════════════════════════════
# 10 additional scalar episode-level axes (generic pipeline)
# ════════════════════════════════════════════════════════════════════════

print("=" * 70)
print("AXES 6-15: additional scalar episode-level metrics")
print("=" * 70)


def model_scalar_mean(md: ModelData, extractor):
    vals = [v for v in (extractor(md, log) for log in md.log_files) if v is not None]
    return stats.mean(vals) if vals else None


def pick_scalar_episode(md: ModelData, extractor, want_max: bool, prefer_accuracy=None, min_turns=4):
    scored = []
    for log in md.log_files:
        v = extractor(md, log)
        if v is None:
            continue
        eff = md.efficiency.get(log, {})
        tc = eff.get("turn_count")
        if min_turns and (tc is None or tc < min_turns):
            continue
        acc_match = prefer_accuracy is not None and eff.get("final_accuracy") == prefer_accuracy
        key = (acc_match, v if want_max else -v)
        scored.append((key, log, v))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0]


def turn_eval_mean(md: ModelData, log: str, field: str):
    te = md.turn_eval.get(log, {})
    vals = [t[field] for t in te.values() if t.get(field) is not None]
    return stats.mean(vals) if vals else None


def qe_episode_metric(md: ModelData, log: str, field: str):
    qe = md.question_eval.get(log, {})
    em = qe.get("episode_metrics", {}).get("llm_judge", {})
    return em.get(field)


def eff_field(md: ModelData, log: str, field: str):
    return md.efficiency.get(log, {}).get(field)


def _fmtval(v, unit):
    if unit == "%":
        return f"{v * 100:.0f}%"
    if unit == "turns":
        n = f"{v:.1f}" if not float(v).is_integer() else f"{int(v)}"
        return f"{n} turns"
    return f"{v:.3f}"


SCALAR_AXES = [
    dict(key="diagnosis_recall", higher_is_better=True, unit="",
         extractor=lambda md, log: turn_eval_mean(md, log, "recall"),
         label="per-turn diagnosis-inference recall (|predicted ∩ truth| / |truth|)"),
    dict(key="ecr", higher_is_better=True, unit="",
         extractor=lambda md, log: qe_episode_metric(md, log, "conditional_mean_ecr"),
         label="expected candidate reduction per question (conditional on active turns, LLM-judge mapper)"),
    dict(key="ecr_positive_rate", higher_is_better=True, unit="%",
         extractor=lambda md, log: qe_episode_metric(md, log, "ecr_positive_rate"),
         label="rate of turns with positive expected candidate reduction"),
    dict(key="mean_ias", higher_is_better=True, unit="",
         extractor=lambda md, log: qe_episode_metric(md, log, "mean_ias"),
         label="Information Acquisition Score (IAS)"),
    dict(key="avg_turn_count", higher_is_better=False, unit="turns",
         extractor=lambda md, log: eff_field(md, log, "turn_count"),
         label="interview length (turn count)"),
    dict(key="cssr", higher_is_better=True, unit="",
         extractor=lambda md, log: eff_field(md, log, "cssr"),
         label="Candidate-Set Shrink Rate (CSSR)"),
    dict(key="time_to_first_correct", higher_is_better=False, unit="turns",
         extractor=lambda md, log: eff_field(md, log, "time_to_first_correct_narrowing"),
         label="turns until the ground truth first became the sole high-confidence candidate"),
    dict(key="redundant_turn_ratio", higher_is_better=False, unit="%",
         extractor=lambda md, log: eff_field(md, log, "redundant_turn_ratio"),
         label="fraction of turns where the candidate set did not shrink (redundant turns)"),
    dict(key="overcommitment", higher_is_better=False, unit="turns",
         extractor=lambda md, log: eff_field(md, log, "overcommitment_turns"),
         label="turns spent continuing the interview after the candidate set had already collapsed to one"),
]

scalar_selections = []
for spec in SCALAR_AXES:
    key, extractor, hib, label, unit = spec["key"], spec["extractor"], spec["higher_is_better"], spec["label"], spec["unit"]
    model_means = {m: v for m, md in MODELS.items() if (v := model_scalar_mean(md, extractor)) is not None}
    if not model_means:
        print(f"  SKIP {key}: no data")
        continue
    high_model = max(model_means, key=model_means.get)
    low_model = min(model_means, key=model_means.get)

    high_pick = pick_scalar_episode(MODELS[high_model], extractor, want_max=True, prefer_accuracy=(1.0 if hib else 0.0))
    low_pick = pick_scalar_episode(MODELS[low_model], extractor, want_max=False, prefer_accuracy=(0.0 if hib else 1.0))
    if not high_pick or not low_pick:
        print(f"  SKIP {key}: no qualifying episode")
        continue

    rationale_high = (f"{high_model} has the highest mean {label} "
                       f"({_fmtval(model_means[high_model], unit)}) of the 6 doctor models. "
                       f"This episode reached {_fmtval(high_pick[2], unit)}.")
    rationale_low = (f"{low_model} has the lowest mean {label} "
                      f"({_fmtval(model_means[low_model], unit)}) of the 6 doctor models. "
                      f"This episode reached {_fmtval(low_pick[2], unit)}.")

    print(f"  {key:24s} HIGH={high_model:26s}/{high_pick[1]:16s} ({_fmtval(high_pick[2], unit)})   "
          f"LOW={low_model:26s}/{low_pick[1]:16s} ({_fmtval(low_pick[2], unit)})")

    scalar_selections.append((key, "high", high_model, high_pick[1], rationale_high, model_means, None))
    scalar_selections.append((key, "low", low_model, low_pick[1], rationale_low, model_means, None))
print()

print("=" * 70)
print("Building case bundles")
print("=" * 70)

selections = [
    ("diagnosis_precision", "high", best_model, a1_high[2],
     f"{best_model} has the highest mean per-turn diagnosis-inference precision "
     f"({axis1_model_stats[best_model]:.2f}) of the 6 doctor models. In this episode its "
     f"stated candidate list matched the KG-derived reference set on every turn and it "
     f"reached the correct final diagnosis.",
     axis1_model_stats, None),
    ("diagnosis_precision", "low", worst_model, a1_low[2],
     f"{worst_model} has the lowest mean per-turn diagnosis-inference precision "
     f"({axis1_model_stats[worst_model]:.2f}) of the 6 doctor models. In this episode its "
     f"stated candidates never overlapped the KG-derived reference set and the final "
     f"diagnosis was wrong.",
     axis1_model_stats, None),
    ("question_quality", "high", a2_best_model, a2_high[1],
     f"{a2_best_model} has the highest mean LLM-judged Information Acquisition Score (IAS) "
     f"({axis2_model_stats[a2_best_model]:.2f}) of the 6 doctor models. Turn "
     f"{a2_high[3]['turn']} of this episode scored {a2_high[3]['scores_by_mapper']['llm_judge']['ias']:.2f} "
     f"and the reference candidate set shrank {a2_high[4]} → {a2_high[5]} immediately after.",
     axis2_model_stats, a2_high[3]["turn"]),
    ("question_quality", "low", a2_worst_model, a2_low[1],
     f"{a2_worst_model} has the lowest mean LLM-judged Information Acquisition Score (IAS) "
     f"({axis2_model_stats[a2_worst_model]:.2f}) of the 6 doctor models. Turn "
     f"{a2_low[3]['turn']} of this episode scored {a2_low[3]['scores_by_mapper']['llm_judge']['ias']:.2f} "
     f"and the reference candidate set did not shrink ({a2_low[4]} → {a2_low[5]}) — the question "
     f"was redundant or off-target.",
     axis2_model_stats, a2_low[3]["turn"]),
    ("diagnostic_reasoning", "high", a3_best_model, a3_high[1],
     f"{a3_best_model} has the highest mean diagnostic-reasoning coverage score "
     f"({axis3_model_stats[a3_best_model]:.2f}) of the 6 doctor models. In this episode its "
     f"final diagnostic checklist scored {a3_high[2]['overall_score']:.2f} against the "
     f"DSM-5-derived ground-truth criteria.",
     axis3_model_stats, None),
    ("diagnostic_reasoning", "low", a3_worst_model, a3_low[1],
     f"{a3_worst_model} has the lowest mean diagnostic-reasoning coverage score "
     f"({axis3_model_stats[a3_worst_model]:.2f}) of the 6 doctor models. In this episode its "
     f"final diagnostic checklist scored only {a3_low[2]['overall_score']:.2f} against the "
     f"DSM-5-derived ground-truth criteria.",
     axis3_model_stats, None),
    ("efficiency", "high", a4_best_model, a4_high[1],
     f"{a4_best_model} has the best aggregate interview-efficiency profile of the 6 doctor "
     f"models (highest candidate-set shrink rate net of redundant/backtracking turns). This "
     f"episode reached the correct diagnosis with cssr={a4_high[2]['cssr']:.2f}, "
     f"redundant_turn_ratio={a4_high[2]['redundant_turn_ratio']:.2f}.",
     axis4_model_stats, None),
    ("efficiency", "low", a4_worst_model, a4_low[1],
     f"{a4_worst_model} has the worst aggregate interview-efficiency profile of the 6 doctor "
     f"models. This episode shows {a4_low[2]['monotonicity_violations']} monotonicity "
     f"violations (candidate set grew mid-interview) and a redundant_turn_ratio of "
     f"{a4_low[2]['redundant_turn_ratio']:.2f}.",
     axis4_model_stats, None),
    ("safety_compliance", "high", a5_best_model, a5_high[1],
     f"{a5_best_model} has the highest safety-critical symptom screening coverage "
     f"({axis5_model_stats[a5_best_model]*100:.0f}% of the 6 tracked safety symptoms) of the "
     f"6 doctor models. In this episode all {len(SAFETY_SYMPTOM_IDS)} safety-critical symptoms "
     f"were screened.",
     axis5_model_stats, None),
    ("safety_compliance", "low", a5_worst_model, a5_low[1],
     f"{a5_worst_model} has the lowest safety-critical symptom screening coverage "
     f"({axis5_model_stats[a5_worst_model]*100:.0f}% of the 6 tracked safety symptoms) of the "
     f"6 doctor models. In this episode none of the {len(SAFETY_SYMPTOM_IDS)} safety-critical "
     f"symptoms (incl. suicidal ideation, psychotic symptoms) were ever screened.",
     axis5_model_stats, None),
] + scalar_selections

bundles = []
for axis, level, model, log, rationale, agg, hi_turn in selections:
    b = build_bundle(axis, level, model, log, rationale, agg, hi_turn)
    bundles.append(b)

with open(OUT / "manifest.json", "w", encoding="utf-8") as f:
    json.dump([
        {"axis": b["axis"], "level": b["level"], "doctor_model": b["doctor_model"],
         "log_file": b["log_file"], "ground_truth_name": b["ground_truth_name"],
         "final_diagnosis_name": b["final_diagnosis_name"], "final_accuracy": b["final_accuracy"],
         "turn_count": b["turn_count"], "rationale": b["rationale"],
         "highlighted_turn": b["highlighted_turn"]}
        for b in bundles
    ], f, ensure_ascii=False, indent=2)
print(f"\nWrote manifest with {len(bundles)} cases to {OUT / 'manifest.json'}")
