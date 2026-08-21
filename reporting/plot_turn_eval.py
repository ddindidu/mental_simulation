#!/usr/bin/env python3
"""
Turn-level Inference Evaluation Plotter
Reads *_result.json + log .txt files and generates:
  - turn_eval.json                        (saved directly under --output)
  - turn_eval/turn_eval_plot.png          (accuracy + precision + recall combined)
  - turn_eval/turn_eval_plot_accuracy.png
  - turn_eval/turn_eval_plot_precision.png
  - turn_eval/turn_eval_plot_recall.png

Usage:
  python plot_turn_eval.py --results results/path/to/dir --logs logs/path/to/dir
  python plot_turn_eval.py   # uses get_run_dir() paths if no args

Style matches v2_result reference plots:
  thin case lines + jittered scatter + bold mean line (no background bars).
"""
from __future__ import annotations

import argparse
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
import matplotlib.gridspec as gridspec
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
from utils.paths import ANALYSIS_ROOT, LOGS_ROOT, RESULTS_ROOT
CRITERIA_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "diagnostic_criteria.json"
DISORDER_ICD10_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "disorder_icd10.json"


# ── ICD-10 code → ID mapping ─────────────────────────────────────────────────

def _build_code_to_id() -> dict[str, str]:
    """Return {icd10_code: disease_id} from disorder_icd10.json."""
    with open(DISORDER_ICD10_FILE, encoding="utf-8") as f:
        mapping = json.load(f)
    code2id: dict[str, str] = {}
    for k, v in mapping.items():
        for code in v.get("icd10_accepted_codes") or [v["icd10_code"]]:
            code2id[code.strip().upper()] = k
    return code2id


def _build_id_to_name() -> dict[str, str]:
    with open(CRITERIA_FILE, encoding="utf-8") as f:
        criteria = json.load(f)
    return {k: v["name"] for k, v in criteria.items()}


# ── Log parsing: doctor candidates per turn ─────────────────────────────────

def extract_doctor_candidates(log_file: Path) -> tuple[list[list[str]], list[str] | None]:
    text = log_file.read_text(encoding="utf-8")
    blocks = re.findall(r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}", text, re.DOTALL)
    per_turn: list[list[str]] = []
    final_cands: list[str] | None = None
    for b in blocks:
        b = b.strip()
        try:
            p = json.loads(b)
            if not isinstance(p, dict) or "candidates" not in p:
                continue
            if "diagnosis" in p:
                final_cands = p["candidates"]
            elif "note" in p:
                per_turn.append(p["candidates"])
        except (json.JSONDecodeError, ValueError):
            continue
    return per_turn, final_cands


def _codes_to_ids(codes: list[str], code2id: dict[str, str]) -> set[str]:
    ids = set()
    for code in codes:
        did = code2id.get(str(code).strip().upper())
        if did:
            ids.add(did)
    return ids


def _log_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


# ── Metric computation ─────────────────────────────────────────────────────────

def compute_turn_metrics(results_dir: Path, logs_dir: Path) -> list[dict]:
    code2id = _build_code_to_id()
    result_paths = sorted(results_dir.glob("*_result.json"),
                          key=lambda p: _log_sort_key(p.stem.replace("_result", "")))
    if not result_paths:
        print(f"[error] No *_result.json found in {results_dir}", file=sys.stderr)
        sys.exit(1)

    sample_turns: list[dict] = []
    skipped = 0

    for res_path in result_paths:
        result = json.loads(res_path.read_text(encoding="utf-8"))
        log_name = result["log_file"]
        gt_m = re.match(r"(D\d+)", log_name)
        if not gt_m:
            continue
        gt = gt_m.group(1)

        log_file = logs_dir / f"{log_name}.txt"
        if not log_file.exists():
            skipped += 1
            continue

        doctor_cands, final_cands = extract_doctor_candidates(log_file)
        n_turns = len(result["turns"])

        if len(doctor_cands) == n_turns - 1 and final_cands is not None:
            doctor_cands = doctor_cands + [final_cands]
        elif len(doctor_cands) < n_turns:
            skipped += 1
            continue

        for turn in result["turns"]:
            t = turn["turn"]
            turn_idx = t - 1

            preds = _codes_to_ids(doctor_cands[turn_idx], code2id) if turn_idx < len(doctor_cands) else set()

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

            # gt is always a known positive; ensure it lands in the right tier
            high_likely.add(gt)
            moderate_likely -= high_likely
            low_likely      -= high_likely | moderate_likely

            strong_candidates = high_likely | moderate_likely
            all_candidates    = strong_candidates | low_likely
            truth_set         = all_candidates          # default: include optional-evidence tier

            intersection = preds & truth_set
            tp = len(intersection)
            fp = len(preds - truth_set)
            fn = len(truth_set - preds)

            precision = tp / len(preds) if preds else 0.0
            recall    = tp / len(truth_set) if truth_set else 0.0
            accuracy  = 1.0 if preds == truth_set else 0.0
            union = preds | truth_set
            jaccard = tp / len(union) if union else 1.0

            # weighted recall: high_likely miss=2, moderate_likely miss=1, low_likely miss=0.5
            missed_high = high_likely - preds
            missed_mod  = moderate_likely - preds
            missed_low  = low_likely - preds
            wr_penalty  = 2 * len(missed_high) + 1 * len(missed_mod) + 0.5 * len(missed_low)
            wr_max      = 2 * len(high_likely) + 1 * len(moderate_likely) + 0.5 * len(low_likely)
            weighted_recall = 1.0 - wr_penalty / wr_max if wr_max else 1.0

            sample_turns.append({
                "log_file":          log_name,
                "turn":              t,
                "ground_truth":      gt,
                "predicted":         sorted(preds),
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

    if skipped:
        print(f"  [{skipped} episodes skipped — log file missing or mismatched turns]")
    return sample_turns


# ── Build per-disorder stats ────────────────────────────────────────────────────

def build_stats(sample_turns: list[dict]):
    """Return (stats_by_disease, case_series_by_disease, overall_stats, overall_series)."""
    METRICS = ("accuracy", "precision", "recall", "jaccard", "weighted_recall")

    stats_by_dis: dict = defaultdict(lambda: defaultdict(lambda: {m: [] for m in METRICS}))
    case_series:  dict = defaultdict(lambda: defaultdict(list))

    for e in sample_turns:
        m = re.match(r"(D\d+)", e["log_file"])
        if not m:
            continue
        did = m.group(1)
        t   = e["turn"]
        for met in METRICS:
            stats_by_dis[did][t][met].append(e[met])
        case_series[did][e["log_file"]].append((t,) + tuple(e[met] for met in METRICS))

    overall_stats:  dict = defaultdict(lambda: {m: [] for m in METRICS})
    overall_series: dict = defaultdict(list)
    for e in sample_turns:
        t = e["turn"]
        for met in METRICS:
            overall_stats[t][met].append(e[met])
        overall_series[e["log_file"]].append((t,) + tuple(e[met] for met in METRICS))

    return stats_by_dis, case_series, overall_stats, overall_series


# ── Plotting helpers ───────────────────────────────────────────────────────────

METRIC_IDX = {"accuracy": 1, "precision": 2, "recall": 3, "jaccard": 4, "weighted_recall": 5}
COLORS  = {"accuracy": "#1f77b4", "precision": "#ff7f0e", "recall": "#2ca02c",
           "jaccard": "#9467bd", "weighted_recall": "#8c564b"}
MARKERS = {"accuracy": "o", "precision": "s", "recall": "^",
           "jaccard": "D", "weighted_recall": "v"}
YLABELS = {"accuracy": "Accuracy (strict)", "precision": "Precision",
           "recall": "Recall", "jaccard": "Jaccard", "weighted_recall": "Weighted Recall"}


def _case_lines(ax, series: dict, metric: str, color: str):
    idx = METRIC_IDX[metric]
    for pts in series.values():
        pts_s = sorted(pts, key=lambda x: x[0])
        if len(pts_s) < 2:
            continue
        ax.plot([p[0] for p in pts_s], [p[idx] for p in pts_s],
                color=color, alpha=0.18, linewidth=0.8, zorder=1)


def _scatter(ax, turn_data: dict, metric: str, color: str, marker: str):
    for t in sorted(turn_data.keys()):
        vals = turn_data[t][metric]
        n = len(vals)
        xs = np.linspace(t - 0.22, t + 0.22, n) if n > 1 else np.array([float(t)])
        ax.scatter(xs, vals, color=color, alpha=0.35, s=16, marker=marker, zorder=2)


def _draw_metric(ax, turn_data: dict, series: dict, title: str, metric: str):
    color  = COLORS[metric]
    marker = MARKERS[metric]
    label  = YLABELS[metric]
    turns  = sorted(turn_data.keys())
    if not turns:
        ax.set_title(title, fontsize=9)
        return

    means = [np.mean(turn_data[t][metric]) for t in turns]

    _case_lines(ax, series, metric, color)
    _scatter(ax, turn_data, metric, color, marker)
    ax.plot(turns, means, color=color, marker=marker, label=label,
            linewidth=2.2, markersize=6, zorder=3)

    ax.set_ylim(0.0, 1.05)
    ax.set_yticks(np.arange(0.0, 1.2, 0.2))
    for y in np.arange(0.0, 1.2, 0.2):
        ax.axhline(y, color="lightgray", linewidth=0.5, zorder=0)
    ax.set_xlim(left=0.5)
    ax.set_xticks(turns)
    ax.tick_params(labelsize=7)
    ax.set_xlabel("Turn", fontsize=8)
    ax.set_ylabel(label, fontsize=8)
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.legend(loc="lower left", fontsize=7.5)


def _draw_combined(ax, turn_data: dict, series: dict, title: str):
    turns = sorted(turn_data.keys())
    if not turns:
        ax.set_title(title, fontsize=9)
        return

    for metric in ("accuracy", "precision", "recall"):
        color  = COLORS[metric]
        marker = MARKERS[metric]
        means  = [np.mean(turn_data[t][metric]) for t in turns]
        _case_lines(ax, series, metric, color)
        _scatter(ax, turn_data, metric, color, marker)
        ax.plot(turns, means, color=color, marker=marker, label=YLABELS[metric],
                linewidth=2.0, markersize=5, zorder=3)

    ax2 = ax.twinx()
    counts = [len(turn_data[t]["accuracy"]) for t in turns]
    ax2.bar(turns, counts, color="gray", alpha=0.18, width=0.7, zorder=0)
    ax2.set_ylabel("# Samples", fontsize=7, color="gray")
    ax2.tick_params(axis="y", labelsize=6, colors="gray")
    ax2.set_ylim(0, max(counts) * 1.3 if counts else 1)
    for t, c in zip(turns, counts):
        ax2.text(t, c + max(counts) * 0.02, str(c),
                 ha="center", va="bottom", fontsize=6, color="gray")

    ax.set_ylim(0.0, 1.05)
    ax.set_yticks(np.arange(0.0, 1.2, 0.2))
    for y in np.arange(0.0, 1.2, 0.2):
        ax.axhline(y, color="lightgray", linewidth=0.5, zorder=0)
    ax.set_xlim(left=0.5)
    ax.set_xticks(turns)
    ax.tick_params(labelsize=7)
    ax.set_xlabel("Turn", fontsize=8)
    ax.set_ylabel("Score", fontsize=8)
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    ax.legend(loc="lower left", fontsize=7)


def _make_grid(disease_ids, id2name) -> tuple[int, int]:
    n_dis  = len(disease_ids)
    n_cols = 6
    n_rows = (n_dis + 1 + n_cols - 1) // n_cols
    return n_rows, n_cols


def _iter_subplots(disease_ids, stats_by_dis, case_series, overall_stats, overall_series,
                   id2name, draw_fn):
    n_rows, n_cols = _make_grid(disease_ids, id2name)
    n_dis = len(disease_ids)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 5, n_rows * 4.5))
    axes_flat = np.asarray(axes).flatten()

    for i, did in enumerate(disease_ids):
        name  = id2name.get(did, did)
        short = name if len(name) <= 40 else name[:37] + "..."
        draw_fn(axes_flat[i], stats_by_dis[did], case_series[did], f"{did}: {short}")

    draw_fn(axes_flat[n_dis], overall_stats, overall_series, "Overall Average")

    for j in range(n_dis + 1, len(axes_flat)):
        axes_flat[j].set_visible(False)

    plt.tight_layout()
    return fig


# ── Main ───────────────────────────────────────────────────────────────────────

def plot_all(sample_turns: list[dict], results_dir: Path) -> None:
    id2name = _build_id_to_name()
    stats_by_dis, case_series, overall_stats, overall_series = build_stats(sample_turns)
    disease_ids = sorted(stats_by_dis.keys(), key=lambda x: int(x[1:]))

    def _save(fig, name):
        p = results_dir / name
        fig.savefig(p, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved → {p}")

    # Combined: accuracy + precision + recall
    fig = _iter_subplots(disease_ids, stats_by_dis, case_series,
                         overall_stats, overall_series, id2name, _draw_combined)
    _save(fig, "turn_eval_plot.png")

    # Per-metric
    for metric in ("accuracy", "precision", "recall"):
        def _fn(ax, td, ser, title, _m=metric):
            _draw_metric(ax, td, ser, title, _m)
        fig = _iter_subplots(disease_ids, stats_by_dis, case_series,
                             overall_stats, overall_series, id2name, _fn)
        _save(fig, f"turn_eval_plot_{metric}.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=None,
                        help="Path to results directory (input; default: auto via get_run_dir)")
    parser.add_argument("--logs", type=Path, default=None,
                        help="Path to logs directory (input; default: auto via get_run_dir)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Directory to write outputs (default: analysis/<run_dir>)")
    args = parser.parse_args()

    if args.results is None or args.logs is None:
        from utils.llm import get_run_dir as _get_run_dir
        run_dir = _get_run_dir()
        if args.results is None:
            args.results = RESULTS_ROOT / run_dir
        if args.logs is None:
            args.logs = LOGS_ROOT / run_dir

    if args.output is None:
        try:
            rel = args.results.resolve().relative_to((RESULTS_ROOT).resolve())
            args.output = ANALYSIS_ROOT / rel
        except ValueError:
            args.output = ANALYSIS_ROOT / args.results.name

    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Results dir : {args.results}")
    print(f"Logs dir    : {args.logs}")
    print(f"Output dir  : {args.output}")

    sample_turns = compute_turn_metrics(args.results, args.logs)
    if not sample_turns:
        print("[error] No turn data computed.", file=sys.stderr)
        sys.exit(1)

    out_json = args.output / "turn_eval.json"
    out_json.write_text(json.dumps(sample_turns, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved → {out_json}  ({len(sample_turns)} entries)")

    print("Generating plots...")
    plots_dir = args.output / "turn_eval"
    plots_dir.mkdir(parents=True, exist_ok=True)
    plot_all(sample_turns, plots_dir)
    print("Done.")


if __name__ == "__main__":
    main()
