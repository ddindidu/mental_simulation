#!/usr/bin/env python3
"""
Diagnostic Question Quality plotter — QTS (evaluation_v5.md §2)

Reads results/<run_dir>/question_eval.json (written by eval/evaluate_question.py,
llm_judge mapper) and plots per-turn QTS and its two components:
  QTS = DRS × (1 − RP)
  DRS = diagnostic relevance, RP = redundancy penalty

Outputs (analysis/<run_dir>/question_eval/):
  question_eval_plot.png              QTS + DRS + RP combined
  question_eval_plot_qts.png
  question_eval_plot_relevance.png
  question_eval_plot_redundancy.png

Previously this script re-scored questions with SemanticSimilarityMapper and
wrote question_eval_semantic.json; that mapper almost never fired (~99.5% of
turns scored 0), so it is no longer used.

Usage:
  python plot_question_eval.py --results results/path/to/combo
  python plot_question_eval.py   # auto via get_run_dir()
"""
from __future__ import annotations

import argparse
import json
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
from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT
from utils.metric_compat import turn_qts

MAPPER = "llm_judge"


def load_episodes(results_dir: Path) -> list[dict]:
    """question_eval.json -> [{log_file, ground_truth, turns: [{turn, qts,
    diagnostic_relevance, redundancy_penalty} | {turn, skipped}]}]."""
    path = results_dir / "question_eval.json"
    if not path.exists():
        print(f"[error] {path} not found — run eval/evaluate_question.py first", file=sys.stderr)
        sys.exit(1)
    episodes = []
    for ep in json.loads(path.read_text(encoding="utf-8")):
        turns = []
        for t in ep.get("turns", []):
            sc = (t.get("scores_by_mapper") or {}).get(MAPPER)
            if sc is None:
                turns.append({"turn": t["turn"], "skipped": True})
                continue
            turns.append({
                "turn":                 t["turn"],
                "qts":                  turn_qts(sc),
                "diagnostic_relevance": sc.get("diagnostic_relevance"),
                "redundancy_penalty":   sc.get("redundancy_penalty"),
            })
        episodes.append({"log_file": ep["log_file"], "ground_truth": ep["ground_truth"], "turns": turns})
    return episodes


# ── Build per-disorder stats ────────────────────────────────────────────────────

QMETRICS = ("qts", "diagnostic_relevance", "redundancy_penalty")

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
    "qts":                  "#1f77b4",
    "diagnostic_relevance": "#17becf",
    "redundancy_penalty":   "#d62728",
}
MARKERS = {
    "qts": "o", "diagnostic_relevance": "D", "redundancy_penalty": "v",
}
YLABELS = {
    "qts":                  "QTS",
    "diagnostic_relevance": "Diagnostic Relevance (DRS)",
    "redundancy_penalty":   "Redundancy Penalty (RP)",
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
    counts = [len([v for v in turn_data[t]["qts"] if not np.isnan(v)]) for t in turns]
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
        "qts":                  "qts",
        "diagnostic_relevance": "relevance",
        "redundancy_penalty":   "redundancy",
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
    for ep in episodes:
        for turn in ep["turns"]:
            if turn.get("skipped"):
                continue
            for m in QMETRICS:
                v = turn.get(m)
                if v is not None:
                    stats[m].append(float(v))

    print(f"\n=== Question Metrics Summary ({MAPPER} mapper, per scored turn) ===")
    hdr = f"{'Metric':<28} {'Mean':>8}  {'Std':>8}  {'N':>6}"
    print(hdr)
    print("-" * len(hdr))
    for m in QMETRICS:
        vals = stats[m]
        if vals:
            print(f"{YLABELS[m]:<28} {np.mean(vals):>8.4f}  {np.std(vals):>8.4f}  {len(vals):>6}")


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=None,
                        help="Dir containing question_eval.json (default: results/<run_dir>)")
    parser.add_argument("--output",  type=Path, default=None,
                        help="Directory to write outputs (default: analysis/<run_dir>)")
    args = parser.parse_args()

    if args.results is None:
        from utils.llm import get_run_dir as _get_run_dir
        args.results = RESULTS_ROOT / _get_run_dir()
    if args.output is None:
        try:
            rel = args.results.resolve().relative_to((RESULTS_ROOT).resolve())
            args.output = ANALYSIS_ROOT / rel
        except ValueError:
            args.output = ANALYSIS_ROOT / args.results.name

    episodes = load_episodes(args.results)
    print_summary(episodes)
    plots_dir = args.output / "question_eval"
    plots_dir.mkdir(parents=True, exist_ok=True)
    plot_all(episodes, plots_dir)
    print("Done.")


if __name__ == "__main__":
    main()
