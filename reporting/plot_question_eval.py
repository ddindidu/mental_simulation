#!/usr/bin/env python3
"""
Question Metrics Evaluation Plotter  (spec §4.4)

Reads *_result.json + log .txt files, runs SemanticSimilarityMapper (no LLM needed),
computes per-turn question scores, and generates visualisations:
  - question_eval_semantic.json                  (saved directly under --output)
  - question_eval/question_eval_plot.png         (DCS + composite + mandatory_first + redundancy + IG combined)
  - question_eval/question_eval_plot_dcs.png
  - question_eval/question_eval_plot_composite.png
  - question_eval/question_eval_plot_mandatory.png
  - question_eval/question_eval_plot_redundancy.png
  - question_eval/question_eval_plot_ig.png

For LLM-based mappers (llm_judge / hybrid), run evaluate_question.py separately;
this script is intentionally LLM-free for reproducible offline analysis.

Usage:
  python plot_question_eval.py --results results/path/dir --logs logs/path/dir
  python plot_question_eval.py   # auto via get_run_dir()
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
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
DISORDER_ICD10_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "disorder_icd10.json"

from eval.question_score import (
    SemanticSimilarityMapper,
    load_all_symptoms,
    load_criteria,
    load_differential_edges,
    score_dcs,
    score_edge_alignment,
    mandatory_first_compliance,
    redundancy_penalty,
    composite_question_score,
    score_information_gain,
    safety_screening_compliance,
)


# ── Log parsing: questions & inference candidates per turn ─────────────────────

def _extract_questions_and_candidates(log_file: Path) -> list[tuple[str, list[str]]]:
    text = log_file.read_text(encoding="utf-8")
    blocks = re.findall(r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}", text, re.DOTALL)

    questions: list[str] = []
    cands_per_turn: list[list[str]] = []

    for b in blocks:
        b = b.strip()
        try:
            p = json.loads(b)
            if isinstance(p, dict) and "question" in p and "category" in p:
                questions.append(p["question"])
            elif isinstance(p, dict) and "candidates" in p and "note" in p and "diagnosis" not in p:
                cands_per_turn.append(p.get("candidates", []))
        except (json.JSONDecodeError, ValueError):
            continue

    follow_ups = questions[1:] if len(questions) > 1 else []
    return list(zip(follow_ups, cands_per_turn))


def _log_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _build_code_to_id() -> dict[str, str]:
    """Return {icd10_code: disease_id} from disorder_icd10.json."""
    with open(DISORDER_ICD10_FILE, encoding="utf-8") as f:
        mapping = json.load(f)
    code2id: dict[str, str] = {}
    for k, v in mapping.items():
        for code in v.get("icd10_accepted_codes") or [v["icd10_code"]]:
            code2id[code.strip().upper()] = k
    return code2id


# ── Metric computation ─────────────────────────────────────────────────────────

def compute_question_metrics(results_dir: Path, logs_dir: Path) -> list[dict]:
    all_symptoms = load_all_symptoms()
    criteria     = load_criteria()
    diff_edges   = load_differential_edges()
    code2id      = _build_code_to_id()
    mapper       = SemanticSimilarityMapper()

    result_paths = sorted(results_dir.glob("*_result.json"),
                          key=lambda p: _log_sort_key(p.stem.replace("_result", "")))
    if not result_paths:
        print(f"[error] No *_result.json found in {results_dir}", file=sys.stderr)
        sys.exit(1)

    all_episodes: list[dict] = []
    skipped = 0

    for res_path in result_paths:
        result   = json.loads(res_path.read_text(encoding="utf-8"))
        log_name = result["log_file"]
        gt_m = re.match(r"(D\d+)", log_name)
        if not gt_m:
            continue
        gt = gt_m.group(1)

        log_file = logs_dir / f"{log_name}.txt"
        if not log_file.exists():
            skipped += 1
            continue

        q_and_cands = _extract_questions_and_candidates(log_file)
        turns_data  = result.get("turns", [])

        turns_out: list[dict] = []
        asked_per_turn: list[set[str]] = []

        for i, turn_data in enumerate(turns_data):
            t = turn_data["turn"]
            cumulative_confirmed = set(turn_data.get("cumulative_confirmed", []))
            cumulative_denied    = set(turn_data.get("cumulative_denied", []))

            if i >= len(q_and_cands):
                turns_out.append({"turn": t, "skipped": True})
                asked_per_turn.append(set())
                continue

            question, raw_cands = q_and_cands[i]
            candidate_ids = [
                code2id[c.strip().upper()]
                for c in raw_cands
                if code2id.get(c.strip().upper())
            ]

            q_syms     = mapper.map(question, all_symptoms)
            dcs, kg_fr = score_dcs(q_syms, candidate_ids, criteria, diff_edges)
            edge_align = score_edge_alignment(q_syms, candidate_ids, diff_edges)
            mand_first = mandatory_first_compliance(
                q_syms, candidate_ids, cumulative_confirmed, cumulative_denied, criteria)
            redund     = redundancy_penalty(q_syms, cumulative_confirmed, cumulative_denied)
            composite  = composite_question_score(dcs, edge_align, mand_first, redund)

            # KG-based Information Gain: how much does this question narrow |C_t|?
            cs = turn_data.get("candidate_set", {})
            current_size = (
                len(set(cs.get("high_likely", []))
                    | set(cs.get("moderate_likely", []))
                    | set(cs.get("low_likely", [])))
                if cs else 0
            )
            ig = score_information_gain(
                q_syms, cumulative_confirmed, cumulative_denied, criteria, current_size
            )

            asked_per_turn.append(set(q_syms))
            turns_out.append({
                "turn":                       t,
                "question":                   question,
                "candidate_ids":              candidate_ids,
                "targeted_symptoms":          q_syms,
                "dcs":                        dcs,
                "kg_edge_fraction":           round(kg_fr, 4),
                "edge_alignment":             edge_align,
                "mandatory_first_compliance": mand_first,
                "redundancy_penalty":         redund,
                "composite_score":            composite,
                "information_gain":           ig,
                "candidate_size_before":      current_size,
            })

        safety = safety_screening_compliance(asked_per_turn)
        all_episodes.append({
            "log_file":                    log_name,
            "ground_truth":                gt,
            "safety_screening_compliance": safety,
            "turns":                       turns_out,
        })

    if skipped:
        print(f"  [{skipped} episodes skipped — log missing]")
    return all_episodes


# ── Build per-disorder stats ────────────────────────────────────────────────────

QMETRICS = ("dcs", "composite_score", "mandatory_first_compliance", "redundancy_penalty", "information_gain")

def build_stats(episodes: list[dict]):
    stats_by_dis: dict = defaultdict(lambda: defaultdict(lambda: {m: [] for m in QMETRICS}))
    case_series:  dict = defaultdict(lambda: defaultdict(list))

    for ep in episodes:
        did = ep["ground_truth"]
        log = ep["log_file"]
        for turn in ep["turns"]:
            if turn.get("skipped"):
                continue
            t = turn["turn"]
            for m in QMETRICS:
                v = turn.get(m)
                if v is not None:
                    stats_by_dis[did][t][m].append(float(v))
            case_series[did][log].append((t,) + tuple(
                float(turn[m]) if turn.get(m) is not None else float("nan")
                for m in QMETRICS
            ))

    overall_stats:  dict = defaultdict(lambda: {m: [] for m in QMETRICS})
    overall_series: dict = defaultdict(list)
    for ep in episodes:
        log = ep["log_file"]
        for turn in ep["turns"]:
            if turn.get("skipped"):
                continue
            t = turn["turn"]
            for m in QMETRICS:
                v = turn.get(m)
                if v is not None:
                    overall_stats[t][m].append(float(v))
            overall_series[log].append((t,) + tuple(
                float(turn[m]) if turn.get(m) is not None else float("nan")
                for m in QMETRICS
            ))

    return stats_by_dis, case_series, overall_stats, overall_series


# ── Plotting ───────────────────────────────────────────────────────────────────

METRIC_IDX = {m: i + 1 for i, m in enumerate(QMETRICS)}
COLORS  = {
    "dcs":                        "#1f77b4",
    "composite_score":            "#ff7f0e",
    "mandatory_first_compliance": "#2ca02c",
    "redundancy_penalty":         "#d62728",
    "information_gain":           "#17becf",
}
MARKERS = {
    "dcs": "o", "composite_score": "s",
    "mandatory_first_compliance": "^", "redundancy_penalty": "v",
    "information_gain": "D",
}
YLABELS = {
    "dcs":                        "DCS",
    "composite_score":            "Composite",
    "mandatory_first_compliance": "Mandatory First",
    "redundancy_penalty":         "Redundancy Penalty",
    "information_gain":           "Information Gain",
}


def _case_lines(ax, series: dict, metric: str, color: str):
    idx = METRIC_IDX[metric]
    for pts in series.values():
        pts_s = sorted(pts, key=lambda x: x[0])
        if len(pts_s) < 2:
            continue
        xs = [p[0] for p in pts_s]
        ys = [p[idx] for p in pts_s]
        if all(np.isnan(y) for y in ys):
            continue
        ax.plot(xs, ys, color=color, alpha=0.18, linewidth=0.8, zorder=1)


def _scatter(ax, turn_data: dict, metric: str, color: str, marker: str):
    for t in sorted(turn_data.keys()):
        vals = [v for v in turn_data[t][metric] if not np.isnan(v)]
        if not vals:
            continue
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

    means = []
    valid_turns = []
    for t in turns:
        vals = [v for v in turn_data[t][metric] if not np.isnan(v)]
        if vals:
            means.append(float(np.mean(vals)))
            valid_turns.append(t)

    _case_lines(ax, series, metric, color)
    _scatter(ax, turn_data, metric, color, marker)
    if valid_turns:
        ax.plot(valid_turns, means, color=color, marker=marker, label=label,
                linewidth=2.2, markersize=6, zorder=3)

    ax.set_ylim(-0.05, 1.1)
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

    for metric in QMETRICS:
        color  = COLORS[metric]
        marker = MARKERS[metric]
        valid_turns, means = [], []
        for t in turns:
            vals = [v for v in turn_data[t][metric] if not np.isnan(v)]
            if vals:
                valid_turns.append(t)
                means.append(float(np.mean(vals)))
        _case_lines(ax, series, metric, color)
        _scatter(ax, turn_data, metric, color, marker)
        if valid_turns:
            ls = "--" if metric == "redundancy_penalty" else "-"
            ax.plot(valid_turns, means, color=color, marker=marker,
                    label=YLABELS[metric], linewidth=1.8, markersize=5,
                    zorder=3, linestyle=ls)

    ax2 = ax.twinx()
    counts = [len([v for v in turn_data[t]["dcs"] if not np.isnan(v)]) for t in turns]
    ax2.bar(turns, counts, color="gray", alpha=0.15, width=0.7, zorder=0)
    ax2.set_ylabel("# Samples", fontsize=7, color="gray")
    ax2.tick_params(axis="y", labelsize=6, colors="gray")
    ax2.set_ylim(0, max(counts) * 1.3 if counts else 1)
    for t, c in zip(turns, counts):
        ax2.text(t, c + max(counts) * 0.02, str(c),
                 ha="center", va="bottom", fontsize=6, color="gray")

    ax.set_ylim(-0.05, 1.1)
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
    ax.legend(loc="upper right", fontsize=6.5, ncol=2)


def _iter_subplots(disease_ids, stats_by_dis, case_series, overall_stats, overall_series,
                   id2name, draw_fn):
    n_dis  = len(disease_ids)
    n_cols = 6
    n_rows = (n_dis + 1 + n_cols - 1) // n_cols
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


def plot_all(episodes: list[dict], results_dir: Path) -> None:
    with open(CRITERIA_FILE_PATH, encoding="utf-8") as f:
        criteria = json.load(f)
    id2name = {k: v["name"] for k, v in criteria.items()}

    stats_by_dis, case_series, overall_stats, overall_series = build_stats(episodes)
    disease_ids = sorted(stats_by_dis.keys(), key=lambda x: int(x[1:]))

    def _save(fig, name):
        p = results_dir / name
        fig.savefig(p, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved → {p}")

    # Combined
    fig = _iter_subplots(disease_ids, stats_by_dis, case_series,
                         overall_stats, overall_series, id2name, _draw_combined)
    _save(fig, "question_eval_plot.png")

    # Per-metric
    metric_names = {
        "dcs":                        "dcs",
        "composite_score":            "composite",
        "mandatory_first_compliance": "mandatory",
        "redundancy_penalty":         "redundancy",
        "information_gain":           "ig",
    }
    for metric, fname_suffix in metric_names.items():
        def _fn(ax, td, ser, title, _m=metric):
            _draw_metric(ax, td, ser, title, _m)
        fig = _iter_subplots(disease_ids, stats_by_dis, case_series,
                             overall_stats, overall_series, id2name, _fn)
        _save(fig, f"question_eval_plot_{fname_suffix}.png")


CRITERIA_FILE_PATH = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "diagnostic_criteria.json"


# ── Summary table ───────────────────────────────────────────────────────────────

def print_summary(episodes: list[dict]) -> None:
    stats: dict[str, list] = {m: [] for m in QMETRICS}
    safety_covered = []
    for ep in episodes:
        safety_covered.append(ep["safety_screening_compliance"].get("all_covered", False))
        for turn in ep["turns"]:
            if turn.get("skipped"):
                continue
            for m in QMETRICS:
                v = turn.get(m)
                if v is not None:
                    stats[m].append(float(v))

    print("\n=== Question Metrics Summary (Semantic Mapper) ===")
    hdr = f"{'Metric':<28} {'Mean':>8}  {'Std':>8}  {'N':>6}"
    print(hdr)
    print("-" * len(hdr))
    for m in QMETRICS:
        vals = stats[m]
        if vals:
            print(f"{YLABELS[m]:<28} {np.mean(vals):>8.4f}  {np.std(vals):>8.4f}  {len(vals):>6}")
    rate = sum(safety_covered) / len(safety_covered) if safety_covered else 0.0
    print(f"\nSafety-critical coverage: {rate:.1%} of episodes")


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=None)
    parser.add_argument("--logs",    type=Path, default=None)
    parser.add_argument("--output",  type=Path, default=None,
                        help="Directory to write outputs (default: analysis/<run_dir>)")
    args = parser.parse_args()

    if args.results is None or args.logs is None:
        from utils.llm import get_run_dir as _get_run_dir
        run_dir = _get_run_dir()
        if args.results is None:
            args.results = BASE_DIR / "results" / run_dir
        if args.logs is None:
            args.logs = BASE_DIR / "logs" / run_dir

    if args.output is None:
        try:
            rel = args.results.resolve().relative_to((BASE_DIR / "results").resolve())
            args.output = BASE_DIR / "analysis" / rel
        except ValueError:
            args.output = BASE_DIR / "analysis" / args.results.name

    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Results dir : {args.results}")
    print(f"Logs dir    : {args.logs}")
    print(f"Output dir  : {args.output}")
    print("Running SemanticSimilarityMapper (no LLM calls)...")

    episodes = compute_question_metrics(args.results, args.logs)
    if not episodes:
        print("[error] No data computed.", file=sys.stderr)
        sys.exit(1)

    out_json = args.output / "question_eval_semantic.json"
    out_json.write_text(json.dumps(episodes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved → {out_json}")

    print_summary(episodes)
    print("\nGenerating plots...")
    plots_dir = args.output / "question_eval"
    plots_dir.mkdir(parents=True, exist_ok=True)
    plot_all(episodes, plots_dir)
    print("Done.")


if __name__ == "__main__":
    main()
