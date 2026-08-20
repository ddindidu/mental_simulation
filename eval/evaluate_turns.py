#!/usr/bin/env python3
"""
Turn-level evaluation: accuracy, precision, recall based on doctor's
per-turn candidate diagnoses parsed from simulation logs.

Ground truth : disease ID extracted from log filename (e.g. D001_3.txt → D001)
Predicted set: doctor's inference candidates (ICD-10 codes) after each patient turn
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

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

import matplotlib.pyplot as plt
import numpy as np

BASE_DIR    = Path(__file__).resolve().parent.parent

from utils.llm import get_run_dir as _get_run_dir
_RUN_DIR    = _get_run_dir()
RESULTS_DIR  = BASE_DIR / "results"  / _RUN_DIR
LOGS_DIR     = BASE_DIR / "logs"     / _RUN_DIR
ANALYSIS_DIR = BASE_DIR / "analysis" / _RUN_DIR
PLOTS_DIR    = ANALYSIS_DIR / "turn_eval"
CRITERIA_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "diagnostic_criteria.json"
DISORDER_ICD10_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "disorder_icd10.json"


# ── ICD-10 code ↔ ID mapping ─────────────────────────────────────────────────

def _build_code_to_id() -> dict[str, str]:
    """Return {icd10_code: disease_id} from disorder_icd10.json."""
    with open(DISORDER_ICD10_FILE, encoding="utf-8") as f:
        mapping = json.load(f)
    code2id: dict[str, str] = {}
    for k, v in mapping.items():
        for code in v.get("icd10_accepted_codes") or [v["icd10_code"]]:
            code2id[code.strip().upper()] = k
    return code2id


# ── Log parsing: extract doctor candidates per turn ──────────────────────────

def extract_doctor_candidates_per_turn(
    log_file: Path,
) -> tuple[list[list[str]], list[str] | None]:
    """
    Parse a simulation log and return:
      - per_turn : inference candidates (ICD-10 codes) per patient turn
      - final_cands: candidates from the final diagnosis block, if present

    Inference block: {"candidates", "note"} without "diagnosis".
    Final diagnosis block: {"diagnosis", "candidates", "reason"}.
    """
    text = log_file.read_text(encoding="utf-8")
    blocks = re.findall(
        r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}",
        text,
        re.DOTALL,
    )
    per_turn: list[list[str]] = []
    final_cands: list[str] | None = None
    for b in blocks:
        b = b.strip()
        try:
            parsed = json.loads(b)
            if not isinstance(parsed, dict) or "candidates" not in parsed:
                continue
            if "diagnosis" in parsed:
                final_cands = parsed["candidates"]
            elif "note" in parsed:
                per_turn.append(parsed["candidates"])
        except (json.JSONDecodeError, ValueError):
            continue
    return per_turn, final_cands


def _codes_to_ids(codes: list[str], code2id: dict[str, str]) -> set[str]:
    """Map a list of ICD-10 codes to their disease IDs. Skip unknown codes."""
    ids = set()
    for code in codes:
        did = code2id.get(str(code).strip().upper())
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
    code2id = _build_code_to_id()
    results = load_results()
    if not results:
        print("No result files found.", file=sys.stderr)
        sys.exit(1)

    max_turn = max(r["total_turns"] for r in results)

    # turn_stats now tracks weighted_recall numerators/denominators separately
    turn_stats = defaultdict(lambda: {
        "tp": 0, "fp": 0, "fn": 0, "n": 0, "total_pred": 0,
        "strict_acc_sum": 0.0,
        "jaccard_sum": 0.0,
        "wr_penalty": 0, "wr_max_penalty": 0,
    })
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

        doctor_cands, final_cands = extract_doctor_candidates_per_turn(log_file)
        n_turns = len(r["turns"])

        # Allow off-by-one: doctor skipped the last intermediate inference and
        # went straight to a final diagnosis (i.e. early confident conclusion).
        # In that case, use the final diagnosis candidates for the missing turn.
        if len(doctor_cands) == n_turns - 1 and final_cands is not None:
            doctor_cands = doctor_cands + [final_cands]
        elif len(doctor_cands) < n_turns:
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
                preds = _codes_to_ids(doctor_cands[turn_idx], code2id)
                raw_candidates = doctor_cands[turn_idx]
            else:
                preds = set()
                raw_candidates = []

            # Candidate tiers from candidate_set (preferred) or disease_matches fallback
            cs = turn.get("candidate_set", {})
            dm = turn["disease_matches"]
            if cs:
                high_likely     = set(cs.get("high_likely",    []))
                moderate_likely = set(cs.get("moderate_likely", []))
                low_likely      = set(cs.get("low_likely",      []))
            else:
                high_likely     = {d["disease_id"] for d in dm.get("fully_met",   [])}
                moderate_likely = {d["disease_id"] for d in dm.get("top_partial", [])}
                low_likely      = set()

            high_likely.add(gt)
            moderate_likely -= high_likely
            low_likely      -= high_likely | moderate_likely

            strong_candidates = high_likely | moderate_likely
            all_candidates    = strong_candidates | low_likely
            truth_set         = all_candidates

            intersection = preds & truth_set
            tp = len(intersection)
            fp = len(preds - truth_set)
            fn = len(truth_set - preds)
            n_truth = len(truth_set)

            # spec §4.3 metrics
            precision = tp / len(preds) if preds else 0.0
            recall = tp / n_truth if n_truth else 0.0
            accuracy = 1.0 if preds == truth_set else 0.0
            union = preds | truth_set
            jaccard = tp / len(union) if union else 1.0
            # weighted recall: high=2×, moderate=1×, low=0.5× — spec §4.3
            missed_high = high_likely - preds
            missed_mod  = moderate_likely - preds
            missed_low  = low_likely - preds
            wr_penalty  = 2 * len(missed_high) + 1 * len(missed_mod) + 0.5 * len(missed_low)
            wr_max      = 2 * len(high_likely) + 1 * len(moderate_likely) + 0.5 * len(low_likely)
            weighted_recall = 1.0 - wr_penalty / wr_max if wr_max else 1.0

            stats = turn_stats[t]
            stats["tp"] += tp
            stats["fp"] += fp
            stats["fn"] += fn
            stats["n"] += 1
            stats["total_pred"] += len(preds)
            stats["strict_acc_sum"] += accuracy
            stats["jaccard_sum"] += jaccard
            stats["wr_penalty"] += wr_penalty
            stats["wr_max_penalty"] += wr_max

            sample_turns.append({
                "log_file":          log_name,
                "turn":              t,
                "patient_response":  turn["patient_response"],
                "symptom_reasoning": turn.get("symptom_reasoning", {}),
                "ground_truth":      gt,
                "predicted":         sorted(preds),
                "predicted_codes":   raw_candidates,
                "high_likely":       sorted(high_likely),
                "moderate_likely":   sorted(moderate_likely),
                "low_likely":        sorted(low_likely),
                "strong_candidates": sorted(strong_candidates),
                "all_candidates":    sorted(all_candidates),
                "truth_set":         sorted(truth_set),
                "tp": tp, "fp": fp, "fn": fn,
                "precision":        round(precision, 4),
                "recall":           round(recall, 4),
                "accuracy":         round(accuracy, 4),
                "jaccard":          round(jaccard, 4),
                "weighted_recall":  round(weighted_recall, 4),
            })

    # Print table
    header = (
        f"{'Turn':>5}  {'N':>5}  {'Acc':>6}  {'Prec':>8}  {'Recall':>8}  "
        f"{'Jaccard':>8}  {'WtdRec':>8}  {'TP':>5}  {'FP':>5}  {'FN':>5}"
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
        prec = s["tp"] / s["total_pred"] if s["total_pred"] > 0 else 0.0
        rec = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) > 0 else 0.0
        acc = s["strict_acc_sum"] / n
        jac = s["jaccard_sum"] / n
        wr = 1.0 - s["wr_penalty"] / s["wr_max_penalty"] if s["wr_max_penalty"] else 1.0
        print(
            f"{t:>5}  {n:>5}  {acc:>6.3f}  {prec:>8.4f}  {rec:>8.4f}  "
            f"{jac:>8.4f}  {wr:>8.4f}  {s['tp']:>5}  {s['fp']:>5}  {s['fn']:>5}"
        )

    print(sep)

    all_tp = sum(s["tp"] for s in turn_stats.values())
    all_fp = sum(s["fp"] for s in turn_stats.values())
    all_fn = sum(s["fn"] for s in turn_stats.values())
    all_n = sum(s["n"] for s in turn_stats.values())
    all_pred = sum(s["total_pred"] for s in turn_stats.values())
    all_acc = sum(s["strict_acc_sum"] for s in turn_stats.values())
    all_jac = sum(s["jaccard_sum"] for s in turn_stats.values())
    all_wr_pen = sum(s["wr_penalty"] for s in turn_stats.values())
    all_wr_max = sum(s["wr_max_penalty"] for s in turn_stats.values())

    overall_prec = all_tp / all_pred if all_pred else 0
    overall_rec = all_tp / (all_tp + all_fn) if (all_tp + all_fn) else 0
    overall_acc = all_acc / all_n if all_n else 0
    overall_jac = all_jac / all_n if all_n else 0
    overall_wr = 1.0 - all_wr_pen / all_wr_max if all_wr_max else 1.0
    print(
        f"{'ALL':>5}  {all_n:>5}  {overall_acc:>6.3f}  {overall_prec:>8.4f}  {overall_rec:>8.4f}  "
        f"{overall_jac:>8.4f}  {overall_wr:>8.4f}  {all_tp:>5}  {all_fp:>5}  {all_fn:>5}"
    )
    print(sep)
    if skipped:
        print(f"\n({skipped} log files not found, skipped)")

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ANALYSIS_DIR / "turn_eval.json"
    out_path.write_text(json.dumps(sample_turns, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(sample_turns)} sample-turn entries to {out_path}")
    return sample_turns


def plot(sample_turns: list[dict]) -> None:
    try:
        with open(CRITERIA_FILE, encoding="utf-8") as f:
            criteria = json.load(f)
        id2name = {did: v["name"] for did, v in criteria.items()}
    except Exception:
        id2name = {}

    stats: dict = defaultdict(lambda: defaultdict(lambda: {
        "acc": [], "prec": [], "recall": [], "jaccard": [], "weighted_recall": [],
    }))
    case_series: dict = defaultdict(lambda: defaultdict(list))
    for e in sample_turns:
        m = re.match(r"(D\d+)", e["log_file"])
        if not m:
            continue
        did = m.group(1)
        t = e["turn"]
        stats[did][t]["acc"].append(e["accuracy"])
        stats[did][t]["prec"].append(e["precision"])
        stats[did][t]["recall"].append(e["recall"])
        stats[did][t]["jaccard"].append(e["jaccard"])
        stats[did][t]["weighted_recall"].append(e["weighted_recall"])
        case_series[did][e["log_file"]].append(
            (t, e["accuracy"], e["precision"], e["recall"], e["jaccard"], e["weighted_recall"])
        )

    disease_ids = sorted(stats.keys(), key=lambda x: int(x[1:]))

    overall: dict = defaultdict(lambda: {
        "acc": [], "prec": [], "recall": [], "jaccard": [], "weighted_recall": [],
    })
    overall_series: dict = defaultdict(list)
    for e in sample_turns:
        t = e["turn"]
        overall[t]["acc"].append(e["accuracy"])
        overall[t]["prec"].append(e["precision"])
        overall[t]["recall"].append(e["recall"])
        overall[t]["jaccard"].append(e["jaccard"])
        overall[t]["weighted_recall"].append(e["weighted_recall"])
        overall_series[e["log_file"]].append(
            (t, e["accuracy"], e["precision"], e["recall"], e["jaccard"], e["weighted_recall"])
        )

    colors   = {"acc": "#1f77b4", "prec": "#ff7f0e", "recall": "#2ca02c",
                "jaccard": "#9467bd", "weighted_recall": "#8c564b"}
    markers  = {"acc": "o",       "prec": "s",        "recall": "^",
                "jaccard": "D",    "weighted_recall": "v"}
    n_dis    = len(disease_ids)
    n_cols   = 6
    n_rows   = (n_dis + 1 + n_cols - 1) // n_cols

    def _case_lines(ax, series, metric, color):
        """각 case(log_file)의 turn별 점수를 연한 실선으로 연결."""
        key_idx = {"acc": 1, "prec": 2, "recall": 3}[metric]
        for pts in series.values():
            pts_s = sorted(pts, key=lambda x: x[0])
            if len(pts_s) < 2:
                continue
            ax.plot([p[0] for p in pts_s], [p[key_idx] for p in pts_s],
                    color=color, alpha=0.15, linewidth=0.7, zorder=1)

    def _scatter(ax, turn_data, metric, color, marker):
        for t in sorted(turn_data.keys()):
            vals = turn_data[t][metric]
            n = len(vals)
            xs = np.linspace(t - 0.2, t + 0.2, n) if n > 1 else np.array([float(t)])
            ax.scatter(xs, vals, color=color, alpha=0.4, s=18, marker=marker, zorder=2)

    def _plot_combined(ax, turn_data, series, title):
        turns = sorted(turn_data.keys())
        if not turns:
            ax.set_title(title, fontsize=9)
            return
        mean_acc  = [np.mean(turn_data[t]["acc"])             for t in turns]
        mean_prec = [np.mean(turn_data[t]["prec"])            for t in turns]
        mean_rec  = [np.mean(turn_data[t]["recall"])          for t in turns]
        mean_jac  = [np.mean(turn_data[t]["jaccard"])         for t in turns]
        mean_wr   = [np.mean(turn_data[t]["weighted_recall"]) for t in turns]
        counts    = [len(turn_data[t]["acc"])                  for t in turns]

        ax2 = ax.twinx()
        ax2.bar(turns, counts, color="gray", alpha=0.25, width=0.7, zorder=1)
        ax2.set_ylim(0, max(counts) * 1.15 if counts else 1)
        ax2.set_ylabel("# Samples", fontsize=8, color="gray")
        ax2.tick_params(axis="y", labelsize=7, colors="gray")
        for t, c in zip(turns, counts):
            ax2.text(t, c, str(c), ha="center", va="bottom", fontsize=7, color="gray", alpha=0.9)

        ax.plot(turns, mean_acc,  color=colors["acc"],             marker=markers["acc"],
                label="Accuracy (strict)", linewidth=1.5, markersize=5, zorder=3)
        ax.plot(turns, mean_prec, color=colors["prec"],            marker=markers["prec"],
                label="Precision",         linewidth=1.5, markersize=5, zorder=3)
        ax.plot(turns, mean_rec,  color=colors["recall"],          marker=markers["recall"],
                label="Recall",            linewidth=1.5, markersize=5, zorder=3)
        ax.plot(turns, mean_jac,  color=colors["jaccard"],         marker=markers["jaccard"],
                label="Jaccard",           linewidth=1.5, markersize=5, zorder=3, linestyle="--")
        ax.plot(turns, mean_wr,   color=colors["weighted_recall"], marker=markers["weighted_recall"],
                label="Wtd Recall",        linewidth=1.5, markersize=5, zorder=3, linestyle="--")

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

    def _plot_metric(ax, turn_data, series, title, metric, color, marker, label):
        turns = sorted(turn_data.keys())
        if not turns:
            ax.set_title(title, fontsize=9)
            return
        means = [np.mean(turn_data[t][metric]) for t in turns]
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

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Combined plot (all three metrics + individual dots) ──
    fig = _iter_subplots(_plot_combined)
    out_png = PLOTS_DIR / "turn_eval_plot.png"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved plot to {out_png}")

    # ── Per-metric plots ──
    metric_cfgs = [
        ("acc",             "#1f77b4", "o", "Accuracy (strict)", "turn_eval_plot_accuracy.png"),
        ("prec",            "#ff7f0e", "s", "Precision",         "turn_eval_plot_precision.png"),
        ("recall",          "#2ca02c", "^", "Recall",            "turn_eval_plot_recall.png"),
        ("jaccard",         "#9467bd", "D", "Jaccard",           "turn_eval_plot_jaccard.png"),
        ("weighted_recall", "#8c564b", "v", "Weighted Recall",   "turn_eval_plot_weighted_recall.png"),
    ]
    for metric_key, color, marker, label, out_name in metric_cfgs:
        def _fn(ax, td, ser, title, _m=metric_key, _c=color, _mk=marker, _l=label):
            _plot_metric(ax, td, ser, title, _m, _c, _mk, _l)
        fig = _iter_subplots(_fn)
        out_png = PLOTS_DIR / out_name
        fig.savefig(out_png, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved plot to {out_png}")


if __name__ == "__main__":
    sample_turns = evaluate()
    plot(sample_turns)
