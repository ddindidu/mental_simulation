#!/usr/bin/env python3
"""
Method B evaluation: turn-level accuracy / precision / recall with
rule-based constraint propagation using confirmed + denied symptoms.

Pipeline:
  1. Parse each log file → per-turn (doctor_question, patient_response)
  2. One LLM call per log → extract per-turn DENIED symptoms
     (cached to results/denials/{log_name}.json)
  3. Accumulate confirmed + denied symptoms across turns
  4. Method B truth_set per turn:
       truth_set = {gt} ∪ {disease D :
         every must_include group G satisfies  |G.pool − denied_t| ≥ G.min_count }
  5. Compute TP/FP/FN/TN and Accuracy (TN-included) / Precision / Recall
  6. Save JSON + 4x6 plot

Outputs:
  - results/turn_eval_strict.json
  - results/turn_eval_plot_strict.png
  - results/denials/{log_name}.json  (per-log denial cache)
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

BASE_DIR      = Path(__file__).parent

from utils.llm import get_run_dir as _get_run_dir
_RUN_DIR    = _get_run_dir()
RESULTS_DIR = BASE_DIR / "results" / _RUN_DIR
LOGS_DIR    = BASE_DIR / "logs"    / _RUN_DIR
DENIAL_DIR  = RESULTS_DIR / "denials"
CRITERIA_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "diagnostic_criteria.json"
SYMPTOM_DIR   = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "symptom"

from utils.llm import chat as _llm_chat


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_criteria() -> dict:
    with open(CRITERIA_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_all_symptoms() -> dict:
    symptoms = {}
    for p in sorted(SYMPTOM_DIR.glob("*.json")):
        with open(p, encoding="utf-8") as f:
            symptoms.update(json.load(f))
    return symptoms


def _name_to_id(criteria: dict) -> dict[str, str]:
    return {v["name"].lower().strip(): k for k, v in criteria.items()}


# ── Log parsing ──────────────────────────────────────────────────────────────

def parse_dialogue(log_file: Path) -> tuple[list[tuple[str, str]], list[list[str]]]:
    """Return ([(doctor_question, patient_response), ...], doctor_candidates_per_turn)."""
    text = log_file.read_text(encoding="utf-8")

    doc_blocks = re.findall(
        r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}",
        text, re.DOTALL,
    )
    pat_blocks = re.findall(
        r"={10} OUTPUT \[patient\] ={10}\n(.*?)\n={37}",
        text, re.DOTALL,
    )

    # Extract doctor questions (has 'question' key) and inference blocks
    questions: list[str] = []
    candidates_per_turn: list[list[str]] = []
    for b in doc_blocks:
        b = b.strip()
        try:
            p = json.loads(b)
            if isinstance(p, dict) and "question" in p and "category" in p:
                questions.append(p["question"])
            elif (
                isinstance(p, dict)
                and "candidates" in p
                and "note" in p
                and "diagnosis" not in p
            ):
                candidates_per_turn.append(p["candidates"])
        except (json.JSONDecodeError, ValueError):
            continue

    # Extract patient natural-language responses (skip analyst JSON blobs)
    responses: list[str] = []
    ANALYST = {"matched", "matched_sections", "answer_strategy"}
    for b in pat_blocks:
        b = b.strip()
        if not b:
            continue
        try:
            p = json.loads(b)
            if isinstance(p, dict) and ANALYST & p.keys():
                continue
        except (json.JSONDecodeError, ValueError):
            pass
        responses.append(b)

    # Pair them: the doctor asks question i, patient responds i
    pairs = list(zip(questions, responses))
    return pairs, candidates_per_turn


# ── LLM denial extraction ────────────────────────────────────────────────────

def _build_symptom_catalogue(all_symptoms: dict) -> str:
    return "\n".join(
        f"[{sid}] {s['name']}: {s['description']}"
        for sid, s in all_symptoms.items()
    )


DENIAL_PROMPT = """You are a clinical analyst reading a doctor-patient interview.

For EACH turn below, identify which symptoms from the catalogue the patient
EXPLICITLY DENIED having.

Rules:
- Only count clear denial: "No", "I don't", "I haven't", "I've never", "not really".
- Vague answers like "I'm not sure", "I haven't thought about it" are NOT denial.
- If the patient confirms a symptom, do NOT include it in the denial list.
- You MUST match to symptom IDs from the catalogue (e.g., S025, S033).

=== SYMPTOM CATALOGUE ===
{catalogue}

=== CONVERSATION ===
{dialogue}

Reply ONLY with JSON (no markdown, no explanation):
{{
  "turn_1": {{"denied": ["S001", ...]}},
  "turn_2": {{"denied": [...]}},
  ...
}}
"""


def _strip_fences(s: str) -> str:
    s = re.sub(r"^```[a-z]*\n?", "", s)
    s = re.sub(r"\n?```$", "", s)
    return s


def extract_denials_for_log(
    log_name: str,
    pairs: list[tuple[str, str]],
    all_symptoms: dict,
) -> dict[int, list[str]]:
    """Return {1-indexed turn: [denied symptom ids]}. Uses cache if available."""
    cache_path = DENIAL_DIR / f"{log_name}.json"
    if cache_path.exists():
        try:
            return {int(k): v for k, v in json.loads(cache_path.read_text()).items()}
        except Exception:
            pass

    if not pairs:
        return {}

    dialogue_text = "\n\n".join(
        f"Turn {i+1}:\n  Doctor: {q}\n  Patient: {r}"
        for i, (q, r) in enumerate(pairs)
    )
    catalogue = _build_symptom_catalogue(all_symptoms)
    prompt = DENIAL_PROMPT.format(catalogue=catalogue, dialogue=dialogue_text)

    raw = _llm_chat(
        [
            {"role": "system", "content": "You are a clinical analyst. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        max_new_tokens=3072,
        role="judge",
    ).strip()
    raw = _strip_fences(raw)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [warn] {log_name}: could not parse LLM JSON", file=sys.stderr)
        return {}

    result: dict[int, list[str]] = {}
    for key, val in parsed.items():
        m = re.match(r"turn[_ ]?(\d+)", str(key), re.IGNORECASE)
        if not m:
            continue
        t = int(m.group(1))
        denied = val.get("denied", []) if isinstance(val, dict) else []
        result[t] = [s for s in denied if isinstance(s, str) and s.startswith("S")]

    DENIAL_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


# ── Method B truth-set rule ──────────────────────────────────────────────────

def method_b_truth_set(
    gt: str,
    new_confirmed: set[str],
    denied_cumulative: set[str],
    criteria: dict,
    prev_truth_set: "set[str] | None",
) -> set[str]:
    """
    Intersection-based truth set: narrow candidate diseases each turn.

    1. Start from prev_truth_set (or all diseases on turn 1).
    2. If new symptoms were confirmed this turn, intersect with diseases
       that have at least one must_include group overlapping those symptoms.
    3. Remove any disease that is now infeasible (denied symptoms exhaust a
       must_include group below its min_count).
    4. Ground truth is always kept.
    """
    # Step 1: candidate pool
    if prev_truth_set is None:
        candidate_pool = set(criteria.keys())
    else:
        candidate_pool = set(prev_truth_set)

    # Step 2: narrow by diseases compatible with this turn's new evidence
    if new_confirmed:
        supported_now: set[str] = set()
        for did, ddata in criteria.items():
            for grp in ddata["required_criteria"].values():
                if not isinstance(grp, dict) or "symptom_pool" not in grp:
                    continue
                if grp.get("relation") != "must_include":
                    continue
                if set(grp["symptom_pool"]) & new_confirmed:
                    supported_now.add(did)
                    break
        candidate_pool &= supported_now

    # Step 3: remove infeasible diseases; always keep gt
    truth: set[str] = {gt}
    for did in candidate_pool:
        if did == gt:
            continue
        feasible = True
        for grp in criteria[did]["required_criteria"].values():
            if not isinstance(grp, dict) or "symptom_pool" not in grp:
                continue
            if grp.get("relation") != "must_include":
                continue
            pool = set(grp["symptom_pool"])
            if len(pool - denied_cumulative) < grp.get("min_count", 1):
                feasible = False
                break
        if feasible:
            truth.add(did)
    return truth


# ── Result loading ───────────────────────────────────────────────────────────

def _log_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def load_results() -> list[dict]:
    results = []
    for path in RESULTS_DIR.glob("*_result.json"):
        with open(path, encoding="utf-8") as f:
            results.append(json.load(f))
    results.sort(key=lambda r: _log_sort_key(r["log_file"]))
    return results


def ground_truth_disease(log_name: str) -> str:
    m = re.match(r"(D\d+)", log_name)
    if not m:
        raise ValueError(f"Cannot extract disease ID from '{log_name}'")
    return m.group(1)


def _names_to_ids(names: list[str], name2id: dict[str, str]) -> set[str]:
    ids = set()
    for n in names:
        did = name2id.get(n.lower().strip())
        if did:
            ids.add(did)
    return ids


# ── Main evaluation ──────────────────────────────────────────────────────────

def evaluate() -> tuple[list[dict], dict, int]:
    criteria    = load_criteria()
    name2id     = _name_to_id(criteria)
    all_symptoms = load_all_symptoms()
    n_classes   = len(criteria)

    results = load_results()
    if not results:
        print("No result files found.", file=sys.stderr)
        sys.exit(1)

    max_turn = max(r["total_turns"] for r in results)
    turn_stats = defaultdict(lambda: {
        "tp": 0, "fp": 0, "fn": 0, "tn": 0, "n": 0,
        "total_pred": 0, "total_truth": 0,
    })
    sample_turns: list[dict] = []
    skipped = 0

    for r in results:
        log_name = r["log_file"]
        gt = ground_truth_disease(log_name)
        log_file = LOGS_DIR / f"{log_name}.txt"
        if not log_file.exists():
            skipped += 1
            continue

        pairs, doctor_cands = parse_dialogue(log_file)
        n_turns = len(r["turns"])

        if len(doctor_cands) < n_turns or len(pairs) < n_turns:
            print(
                f"  [warn] {log_name}: dialogue pairs={len(pairs)}, "
                f"doctor_cands={len(doctor_cands)}, patient_turns={n_turns} — skipping",
                file=sys.stderr,
            )
            skipped += 1
            continue

        # LLM denial extraction (cached per log)
        denials_per_turn = extract_denials_for_log(log_name, pairs, all_symptoms)

        denied_cumulative: set[str] = set()
        confirmed_cumulative: set[str] = set()
        prev_truth_set: "set[str] | None" = None

        for turn in r["turns"]:
            t = turn["turn"]
            turn_idx = t - 1

            # Accumulate denials and confirmed symptoms up to this turn
            denied_cumulative |= set(denials_per_turn.get(t, []))
            new_confirmed = set(turn.get("identified_symptoms", [])) - confirmed_cumulative
            confirmed_cumulative |= new_confirmed

            # Doctor predictions for this turn
            if turn_idx < len(doctor_cands):
                preds = _names_to_ids(doctor_cands[turn_idx], name2id)
                raw_candidates = doctor_cands[turn_idx]
            else:
                preds = set()
                raw_candidates = []

            # Intersection-based truth set: narrow from prev_truth_set
            truth_set = method_b_truth_set(
                gt, new_confirmed, denied_cumulative, criteria, prev_truth_set
            )
            prev_truth_set = truth_set

            tp = len(preds & truth_set)
            fp = len(preds - truth_set)
            fn = len(truth_set - preds)
            tn = n_classes - len(preds | truth_set)

            stats = turn_stats[t]
            stats["tp"] += tp
            stats["fp"] += fp
            stats["fn"] += fn
            stats["tn"] += tn
            stats["n"] += 1
            stats["total_pred"] += len(preds)
            stats["total_truth"] += len(truth_set)

            prec = tp / len(preds) if preds else 0.0
            rec = tp / len(truth_set) if truth_set else 0.0
            acc = (tp + tn) / n_classes

            sample_turns.append({
                "log_file": log_name,
                "turn": t,
                "patient_response": turn["patient_response"],
                "identified_symptoms": turn["identified_symptoms"],
                "new_confirmed_this_turn": sorted(new_confirmed),
                "denied_symptoms_this_turn": sorted(denials_per_turn.get(t, [])),
                "denied_cumulative": sorted(denied_cumulative),
                "confirmed_cumulative": sorted(confirmed_cumulative),
                "ground_truth": gt,
                "truth_set": sorted(truth_set),
                "predicted": sorted(preds),
                "predicted_names": raw_candidates,
                "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                "precision": round(prec, 4),
                "recall":    round(rec, 4),
                "accuracy":  round(acc, 4),
            })

    # ── Print table ────────────────────────────────────────────────────────
    header = (
        f"{'Turn':>5}  {'N':>5}  {'Acc(TN)':>9}  {'Prec':>8}  {'Recall':>8}  "
        f"{'|Truth|':>8}  {'TP':>5}  {'FP':>5}  {'FN':>5}"
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)

    for t in range(1, max_turn + 1):
        s = turn_stats[t]
        n = s["n"]
        if n == 0:
            continue
        denom = s["tp"] + s["fp"] + s["fn"] + s["tn"]
        acc = (s["tp"] + s["tn"]) / denom if denom else 0.0
        prec = s["tp"] / s["total_pred"] if s["total_pred"] > 0 else 0.0
        rec = s["tp"] / s["total_truth"] if s["total_truth"] > 0 else 0.0
        avg_truth = s["total_truth"] / n
        print(
            f"{t:>5}  {n:>5}  {acc:>9.4f}  {prec:>8.4f}  {rec:>8.4f}  "
            f"{avg_truth:>8.2f}  {s['tp']:>5}  {s['fp']:>5}  {s['fn']:>5}"
        )
    print(sep)

    all_tp = sum(s["tp"] for s in turn_stats.values())
    all_fp = sum(s["fp"] for s in turn_stats.values())
    all_fn = sum(s["fn"] for s in turn_stats.values())
    all_tn = sum(s["tn"] for s in turn_stats.values())
    all_n  = sum(s["n"]  for s in turn_stats.values())
    all_pred = sum(s["total_pred"] for s in turn_stats.values())
    all_truth = sum(s["total_truth"] for s in turn_stats.values())
    denom = all_tp + all_fp + all_fn + all_tn
    overall_acc = (all_tp + all_tn) / denom if denom else 0.0
    overall_prec = all_tp / all_pred if all_pred else 0.0
    overall_rec = all_tp / all_truth if all_truth else 0.0
    print(
        f"{'ALL':>5}  {all_n:>5}  {overall_acc:>9.4f}  {overall_prec:>8.4f}  "
        f"{overall_rec:>8.4f}  {all_truth/max(all_n,1):>8.2f}  "
        f"{all_tp:>5}  {all_fp:>5}  {all_fn:>5}"
    )
    print(sep)
    if skipped:
        print(f"\n({skipped} sample(s) skipped)")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "turn_eval_strict.json"
    out_path.write_text(json.dumps(sample_turns, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(sample_turns)} sample-turn entries to {out_path}")

    return sample_turns, criteria, n_classes


# ── Plotting ─────────────────────────────────────────────────────────────────

def plot(sample_turns: list[dict], criteria: dict) -> None:
    id2name = {did: v["name"] for did, v in criteria.items()}

    stats: dict = defaultdict(lambda: defaultdict(lambda: {"acc": [], "prec": [], "recall": []}))
    case_series: dict = defaultdict(lambda: defaultdict(list))
    for e in sample_turns:
        m = re.match(r"(D\d+)", e["log_file"])
        did = m.group(1)
        t = e["turn"]
        stats[did][t]["acc"].append(e["accuracy"])
        stats[did][t]["prec"].append(e["precision"])
        stats[did][t]["recall"].append(e["recall"])
        case_series[did][e["log_file"]].append((t, e["accuracy"], e["precision"], e["recall"]))

    disease_ids = sorted(stats.keys(), key=lambda x: int(x[1:]))

    overall: dict = defaultdict(lambda: {"acc": [], "prec": [], "recall": []})
    overall_series: dict = defaultdict(list)
    for e in sample_turns:
        t = e["turn"]
        overall[t]["acc"].append(e["accuracy"])
        overall[t]["prec"].append(e["precision"])
        overall[t]["recall"].append(e["recall"])
        overall_series[e["log_file"]].append((t, e["accuracy"], e["precision"], e["recall"]))

    colors  = {"acc": "#1f77b4", "prec": "#ff7f0e", "recall": "#2ca02c"}
    markers = {"acc": "o",       "prec": "s",        "recall": "^"}
    n_dis   = len(disease_ids)
    n_cols  = 6
    n_rows  = (n_dis + 1 + n_cols - 1) // n_cols

    def _case_lines(ax, series, metric, color):
        """각 case(log_file)의 turn별 점수를 연한 실선으로 연결."""
        key_idx = {"acc": 1, "prec": 2, "recall": 3}[metric]
        for pts in series.values():
            pts_s = sorted(pts, key=lambda x: x[0])
            if len(pts_s) < 2:
                continue
            ax.plot([p[0] for p in pts_s], [p[key_idx] for p in pts_s],
                    color=color, alpha=0.3, linewidth=0.7, zorder=1)

    def _scatter(ax, turn_data, metric, color, marker):
        for t in sorted(turn_data.keys()):
            vals = turn_data[t][metric]
            n = len(vals)
            xs = np.linspace(t - 0.2, t + 0.2, n) if n > 1 else np.array([float(t)])
            ax.scatter(xs, vals, color=color, alpha=0.4, s=18, marker=marker, zorder=2)

    def plot_one(ax, turn_data, series, title):
        turns = sorted(turn_data.keys())
        mean_acc  = [np.mean(turn_data[t]["acc"])    for t in turns]
        mean_prec = [np.mean(turn_data[t]["prec"])   for t in turns]
        mean_rec  = [np.mean(turn_data[t]["recall"]) for t in turns]
        counts    = [len(turn_data[t]["acc"])         for t in turns]

        ax2 = ax.twinx()
        ax2.bar(turns, counts, color="gray", alpha=0.25, width=0.7, zorder=1, label="#Samples")
        ax2.set_ylim(0, max(counts) * 1.15 if counts else 1)
        ax2.set_ylabel("# Samples", fontsize=8, color="gray")
        ax2.tick_params(axis="y", labelsize=7, colors="gray")
        for t, c in zip(turns, counts):
            ax2.text(t, c, str(c), ha="center", va="bottom", fontsize=7, color="gray", alpha=0.9)

        for key in ("acc", "prec", "recall"):
            _case_lines(ax, series, key, colors[key])
            _scatter(ax, turn_data, key, colors[key], markers[key])

        ax.plot(turns, mean_acc,  color=colors["acc"],    marker=markers["acc"],
                label="Accuracy (TN)", linewidth=1.5, markersize=5, zorder=3)
        ax.plot(turns, mean_prec, color=colors["prec"],   marker=markers["prec"],
                label="Precision",     linewidth=1.5, markersize=5, zorder=3)
        ax.plot(turns, mean_rec,  color=colors["recall"], marker=markers["recall"],
                label="Recall",        linewidth=1.5, markersize=5, zorder=3)

        ax.set_ylim(0.0, 1.1)
        ax.set_yticks(np.arange(0.0, 1.2, 0.2))
        for y in np.arange(0.0, 1.2, 0.2):
            ax.axhline(y=y, color="gray", linestyle="--", linewidth=0.5, alpha=0.6, zorder=0)
        ax.set_xlim(left=0.5)
        ax.set_xticks(turns)
        ax.set_xlabel("Turn")
        ax.set_ylabel("Score")
        ax.set_title(title, fontsize=9, fontweight="bold")
        ax.set_zorder(ax2.get_zorder() + 1)
        ax.patch.set_visible(False)
        ax.legend(loc="lower left", fontsize=7)

    def plot_metric(ax, turn_data, series, title, metric, color, marker, label):
        turns = sorted(turn_data.keys())
        means = [np.mean(turn_data[t][metric]) for t in turns]
        _case_lines(ax, series, metric, color)
        _scatter(ax, turn_data, metric, color, marker)
        ax.plot(turns, means, color=color, marker=marker, label=label,
                linewidth=2.0, markersize=6, zorder=3)
        ax.set_ylim(0.0, 1.1)
        ax.set_yticks(np.arange(0.0, 1.2, 0.2))
        for y in np.arange(0.0, 1.2, 0.2):
            ax.axhline(y=y, color="gray", linestyle="--", linewidth=0.5, alpha=0.6, zorder=0)
        ax.set_xlim(left=0.5)
        ax.set_xticks(turns)
        ax.set_xlabel("Turn")
        ax.set_ylabel(label)
        ax.set_title(title, fontsize=9, fontweight="bold")
        ax.legend(loc="lower left", fontsize=7)

    def _iter_subplots(fn):
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 5, n_rows * 4.5))
        axes_flat = np.asarray(axes).flatten()
        for i, did in enumerate(disease_ids):
            short = id2name.get(did, did)
            if len(short) > 40:
                short = short[:37] + "..."
            fn(axes_flat[i], stats[did], case_series[did], f"{did}: {short}")
        fn(axes_flat[n_dis], overall, overall_series, "Overall Average")
        for j in range(n_dis + 1, len(axes_flat)):
            axes_flat[j].set_visible(False)
        plt.tight_layout()
        return fig

    # ── Combined plot (all three metrics + individual dots) ──
    fig = _iter_subplots(plot_one)
    out_png = RESULTS_DIR / "turn_eval_plot_strict.png"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved plot to {out_png}")

    # ── Per-metric plots ──
    metric_cfgs = [
        ("acc",    "#1f77b4", "o", "Accuracy (TN)", "turn_eval_plot_strict_accuracy.png"),
        ("prec",   "#ff7f0e", "s", "Precision",     "turn_eval_plot_strict_precision.png"),
        ("recall", "#2ca02c", "^", "Recall",        "turn_eval_plot_strict_recall.png"),
    ]
    for metric_key, color, marker, label, out_name in metric_cfgs:
        def _fn(ax, td, ser, title, _m=metric_key, _c=color, _mk=marker, _l=label):
            plot_metric(ax, td, ser, title, _m, _c, _mk, _l)
        fig = _iter_subplots(_fn)
        out_png = RESULTS_DIR / out_name
        fig.savefig(out_png, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved plot to {out_png}")


if __name__ == "__main__":
    sample_turns, criteria, n_classes = evaluate()
    print(f"\n[info] N_classes (total diseases) = {n_classes}")
    plot(sample_turns, criteria)
