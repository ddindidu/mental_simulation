#!/usr/bin/env python3
"""
Diagnostic Hypothesis Quality — per-turn plotter (evaluation_v5.md §1)

Reads analysis/<run_dir>/turn_eval.json (written by eval/evaluate_turns.py —
this script no longer computes or writes turn metrics itself) and draws, per
disorder + overall: thin per-episode lines, jittered per-turn scatter, and a
bold per-turn mean line.

Outputs (analysis/<run_dir>/turn_eval/):
  turn_eval_cases_plot.png                     Jaccard + Precision + Recall + Weighted Recall
  turn_eval_cases_plot_<metric>.png            one per metric

(eval/evaluate_turns.py's own turn_eval_plot*.png are the mean-only versions.)

Usage:
  python plot_turn_eval.py --input analysis/path/to/combo
  python plot_turn_eval.py   # uses get_run_dir() paths if no args
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
from utils.paths import ANALYSIS_ROOT
CRITERIA_FILE = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "diagnostic_criteria.json"

METRICS = ("jaccard", "precision", "recall", "weighted_recall")


def _build_id_to_name() -> dict[str, str]:
    data = json.loads(CRITERIA_FILE.read_text(encoding="utf-8"))
    return {k: v["name"] for k, v in data.items()}


def _turn_value(e: dict, metric: str) -> float:
    # turn_eval.json written before evaluation_v5 holds union-reference values
    # under the unsuffixed keys; *_rigid is the headline value in both versions.
    if metric in ("jaccard", "precision", "recall"):
        return e.get(f"{metric}_rigid", e[metric])
    return e[metric]


# ── Build per-disorder stats ────────────────────────────────────────────────────

def build_stats(sample_turns: list[dict]):
    """Return (stats_by_disease, case_series_by_disease, overall_stats, overall_series)."""
    stats_by_dis: dict = defaultdict(lambda: defaultdict(lambda: {m: [] for m in METRICS}))
    case_series:  dict = defaultdict(lambda: defaultdict(list))

    for e in sample_turns:
        m = re.match(r"(D\d+)", e["log_file"])
        if not m:
            continue
        did = m.group(1)
        t   = e["turn"]
        for met in METRICS:
            stats_by_dis[did][t][met].append(_turn_value(e, met))
        case_series[did][e["log_file"]].append((t,) + tuple(_turn_value(e, met) for met in METRICS))

    overall_stats:  dict = defaultdict(lambda: {m: [] for m in METRICS})
    overall_series: dict = defaultdict(list)
    for e in sample_turns:
        t = e["turn"]
        for met in METRICS:
            overall_stats[t][met].append(_turn_value(e, met))
        overall_series[e["log_file"]].append((t,) + tuple(_turn_value(e, met) for met in METRICS))

    return stats_by_dis, case_series, overall_stats, overall_series


# ── Plotting helpers ───────────────────────────────────────────────────────────

METRIC_IDX = {m: i + 1 for i, m in enumerate(METRICS)}
COLORS  = {"precision": "#ff7f0e", "recall": "#2ca02c",
           "jaccard": "#9467bd", "weighted_recall": "#8c564b"}
MARKERS = {"precision": "s", "recall": "^", "jaccard": "D", "weighted_recall": "v"}
YLABELS = {"precision": "Precision", "recall": "Recall",
           "jaccard": "Jaccard", "weighted_recall": "Weighted Recall"}


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

    for metric in METRICS:
        color  = COLORS[metric]
        marker = MARKERS[metric]
        means  = [np.mean(turn_data[t][metric]) for t in turns]
        _case_lines(ax, series, metric, color)
        _scatter(ax, turn_data, metric, color, marker)
        ax.plot(turns, means, color=color, marker=marker, label=YLABELS[metric],
                linewidth=2.0, markersize=5, zorder=3)

    ax2 = ax.twinx()
    counts = [len(turn_data[t]["jaccard"]) for t in turns]
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

    fig = _iter_subplots(disease_ids, stats_by_dis, case_series,
                         overall_stats, overall_series, id2name, _draw_combined)
    _save(fig, "turn_eval_cases_plot.png")

    for metric in METRICS:
        def _fn(ax, td, ser, title, _m=metric):
            _draw_metric(ax, td, ser, title, _m)
        fig = _iter_subplots(disease_ids, stats_by_dis, case_series,
                             overall_stats, overall_series, id2name, _fn)
        _save(fig, f"turn_eval_cases_plot_{metric}.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=None,
                        help="Analysis dir containing turn_eval.json (default: analysis/<run_dir>)")
    args = parser.parse_args()

    if args.input is None:
        from utils.llm import get_run_dir as _get_run_dir
        args.input = ANALYSIS_ROOT / _get_run_dir()

    json_path = args.input / "turn_eval.json"
    if not json_path.exists():
        print(f"[error] {json_path} not found — run eval/evaluate_turns.py first", file=sys.stderr)
        sys.exit(1)
    sample_turns = json.loads(json_path.read_text(encoding="utf-8"))
    print(f"Input : {json_path} ({len(sample_turns)} entries)")

    plots_dir = args.input / "turn_eval"
    plots_dir.mkdir(parents=True, exist_ok=True)
    plot_all(sample_turns, plots_dir)
    print("Done.")


if __name__ == "__main__":
    main()
