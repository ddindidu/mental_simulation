#!/usr/bin/env python3
"""
Relative progress bin visualization  (spec §4.3 + §4.4)

Maps each episode's turn sequence onto 5 progress bins:
  [0% | 25% | 50% | 75% | 100%]
where 0% = first turn, 100% = final turn of that episode.
The turn index closest to each percentile is selected; values are then
averaged across episodes so the x-axis reflects *diagnostic progress*
regardless of each case's absolute length.

Reads pre-computed JSON files from analysis/<run_dir>/:
  - turn_eval.json               → inference metrics
  - question_eval_semantic.json  → question metrics

Outputs (saved under --output/turn_rel/):
  turn_rel_inference.png
  turn_rel_inference_accuracy.png
  turn_rel_inference_precision.png
  turn_rel_inference_recall.png
  turn_rel_question.png
  turn_rel_question_dcs.png
  turn_rel_question_composite.png
  turn_rel_question_mandatory.png
  turn_rel_question_redundancy.png

Usage:
  python plot_turn_rel.py --input analysis/gemini-3.5-flash/gemini-3.5-flash/gemini-3.1-flash-lite
  python plot_turn_rel.py          # auto via get_run_dir()
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

BASE_DIR      = Path(__file__).parent
CRITERIA_FILE = BASE_DIR / "mentalbench/resources/knowledge_graph/EN/diagnostic_criteria.json"
N_COLS        = 6

BINS       = [0.0, 0.25, 0.5, 0.75, 1.0]
BIN_LABELS = ["0%\n(start)", "25%", "50%", "75%", "100%\n(end)"]

INF_METRICS = ("accuracy", "precision", "recall", "jaccard", "weighted_recall")
Q_METRICS   = ("dcs", "composite_score", "mandatory_first_compliance", "redundancy_penalty")

INF_COLORS  = {"accuracy": "#1f77b4", "precision": "#ff7f0e", "recall": "#2ca02c",
               "jaccard": "#9467bd", "weighted_recall": "#8c564b"}
INF_MARKERS = {"accuracy": "o", "precision": "s", "recall": "^",
               "jaccard": "D", "weighted_recall": "v"}
INF_LABELS  = {"accuracy": "Accuracy", "precision": "Precision", "recall": "Recall",
               "jaccard": "Jaccard", "weighted_recall": "Weighted Recall"}

Q_COLORS    = {"dcs": "#1f77b4", "composite_score": "#ff7f0e",
               "mandatory_first_compliance": "#2ca02c", "redundancy_penalty": "#d62728"}
Q_MARKERS   = {"dcs": "o", "composite_score": "s",
               "mandatory_first_compliance": "^", "redundancy_penalty": "v"}
Q_LABELS    = {"dcs": "DCS", "composite_score": "Composite",
               "mandatory_first_compliance": "Mandatory First",
               "redundancy_penalty": "Redundancy Penalty"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _id2name() -> dict[str, str]:
    data = json.loads(CRITERIA_FILE.read_text(encoding="utf-8"))
    return {k: v["name"] for k, v in data.items()}


def _lsort(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _met_idx(metrics: tuple) -> dict[str, int]:
    return {m: i + 1 for i, m in enumerate(metrics)}


def _nan(v) -> bool:
    return isinstance(v, float) and np.isnan(v)


# ── Bin assignment ─────────────────────────────────────────────────────────────

def _assign_bins(per_metric: dict[str, list]) -> dict[int, dict[str, float]]:
    """
    per_metric: {metric: [val_t1, val_t2, ...]}  aligned, sorted by turn
    Returns: {bin_idx: {metric: value}}
    Single-turn episodes map the same turn to all bins.
    """
    n = next((len(v) for v in per_metric.values()), 0)
    if n == 0:
        return {}
    result = {}
    for b_idx, frac in enumerate(BINS):
        t_idx = min(round(frac * (n - 1)), n - 1)
        result[b_idx] = {m: vals[t_idx] for m, vals in per_metric.items()}
    return result


# ── Data loading + binning ─────────────────────────────────────────────────────

def _bin_inf(entries: list[dict]):
    by_case: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_case[e["log_file"]].append(e)

    s_dis = defaultdict(lambda: defaultdict(lambda: {m: [] for m in INF_METRICS}))
    c_ser = defaultdict(lambda: defaultdict(list))
    s_ovr = defaultdict(lambda: {m: [] for m in INF_METRICS})
    c_ovr = defaultdict(list)

    for log, turns_data in sorted(by_case.items(), key=lambda x: _lsort(x[0])):
        m = re.match(r"(D\d+)", log)
        if not m:
            continue
        did      = m.group(1)
        turns_s  = sorted(turns_data, key=lambda x: x["turn"])
        per_met  = {met: [t[met] for t in turns_s] for met in INF_METRICS}
        binned   = _assign_bins(per_met)

        for b_idx, mvals in binned.items():
            for met, v in mvals.items():
                s_dis[did][b_idx][met].append(v)
                s_ovr[b_idx][met].append(v)
            row = (b_idx,) + tuple(mvals[met] for met in INF_METRICS)
            c_ser[did][log].append(row)
            c_ovr[log].append(row)

    return (dict(sorted(s_dis.items(), key=lambda x: int(x[0][1:]))),
            dict(c_ser), dict(s_ovr), dict(c_ovr))


def _bin_q(episodes: list[dict]):
    s_dis = defaultdict(lambda: defaultdict(lambda: {m: [] for m in Q_METRICS}))
    c_ser = defaultdict(lambda: defaultdict(list))
    s_ovr = defaultdict(lambda: {m: [] for m in Q_METRICS})
    c_ovr = defaultdict(list)

    for ep in episodes:
        did, log  = ep["ground_truth"], ep["log_file"]
        valid     = sorted((t for t in ep["turns"] if not t.get("skipped")),
                           key=lambda x: x["turn"])
        if not valid:
            continue
        per_met   = {met: [float(t[met]) if t.get(met) is not None else float("nan")
                           for t in valid]
                     for met in Q_METRICS}
        binned    = _assign_bins(per_met)

        for b_idx, mvals in binned.items():
            for met, v in mvals.items():
                if not _nan(v):
                    s_dis[did][b_idx][met].append(v)
                    s_ovr[b_idx][met].append(v)
            row = (b_idx,) + tuple(mvals[met] for met in Q_METRICS)
            c_ser[did][log].append(row)
            c_ovr[log].append(row)

    return (dict(sorted(s_dis.items(), key=lambda x: int(x[0][1:]))),
            dict(c_ser), dict(s_ovr), dict(c_ovr))


# ── Plotting primitives ────────────────────────────────────────────────────────

def _case_lines(ax, series, metric, color, midx):
    idx = midx[metric]
    for pts in series.values():
        pts_s = sorted(pts, key=lambda x: x[0])
        if len(pts_s) < 2:
            continue
        ys = [p[idx] for p in pts_s]
        if all(_nan(y) for y in ys):
            continue
        ax.plot([p[0] for p in pts_s], ys,
                color=color, alpha=0.18, linewidth=0.8, zorder=1)


def _scatter(ax, bin_data, metric, color, marker):
    for b in sorted(bin_data.keys()):
        vals = [v for v in bin_data[b][metric] if not _nan(v)]
        if not vals:
            continue
        n  = len(vals)
        xs = np.linspace(b - 0.14, b + 0.14, n) if n > 1 else np.array([float(b)])
        ax.scatter(xs, vals, color=color, alpha=0.35, s=18, marker=marker, zorder=2)


def _add_n_axis(ax, bin_data, ref_metric):
    bins   = sorted(bin_data.keys())
    counts = [len([v for v in bin_data[b][ref_metric] if not _nan(v)]) for b in bins]
    ax2    = ax.twinx()
    ax2.bar(bins, counts, color="gray", alpha=0.12, width=0.35, zorder=0)
    ax2.set_ylabel("N", fontsize=7, color="gray")
    ax2.tick_params(axis="y", labelsize=6, colors="gray")
    mx = max(counts) if counts else 1
    ax2.set_ylim(0, mx * 1.55)
    for b, c in zip(bins, counts):
        ax2.text(b, c + mx * 0.02, str(c),
                 ha="center", va="bottom", fontsize=5.5, color="gray")
    return ax2


def _setup_axes(ax, ax2, bins, title, ylabel):
    ax.set_ylim(-0.05, 1.1)
    ax.set_yticks(np.arange(0.0, 1.2, 0.2))
    for y in np.arange(0.0, 1.2, 0.2):
        ax.axhline(y, color="lightgray", linewidth=0.5, zorder=0)
    n = len(BINS)
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_xticks(list(range(n)))
    ax.set_xticklabels(BIN_LABELS, fontsize=6.5)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_xlabel("Diagnostic Progress", fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)


def _draw_single(ax, bin_data, series, title,
                 metric, colors, markers, labels, metrics_tuple):
    midx = _met_idx(metrics_tuple)
    bins = sorted(bin_data.keys())
    if not bins:
        ax.set_title(title, fontsize=9)
        return
    means, valid = [], []
    for b in bins:
        vals = [v for v in bin_data[b][metric] if not _nan(v)]
        if vals:
            valid.append(b)
            means.append(float(np.mean(vals)))
    ax2 = _add_n_axis(ax, bin_data, metric)
    _case_lines(ax, series, metric, colors[metric], midx)
    _scatter(ax, bin_data, metric, colors[metric], markers[metric])
    if valid:
        ax.plot(valid, means, color=colors[metric], marker=markers[metric],
                label=labels[metric], linewidth=2.2, markersize=6, zorder=4)
    _setup_axes(ax, ax2, bins, title, labels[metric])
    ax.legend(loc="lower left", fontsize=7.5)


def _draw_combined(ax, bin_data, series, title,
                   show_metrics, colors, markers, labels, metrics_tuple):
    midx = _met_idx(metrics_tuple)
    bins = sorted(bin_data.keys())
    if not bins:
        ax.set_title(title, fontsize=9)
        return
    ax2 = _add_n_axis(ax, bin_data, show_metrics[0])
    for met in show_metrics:
        means, valid = [], []
        for b in bins:
            vals = [v for v in bin_data[b][met] if not _nan(v)]
            if vals:
                valid.append(b)
                means.append(float(np.mean(vals)))
        _case_lines(ax, series, met, colors[met], midx)
        _scatter(ax, bin_data, met, colors[met], markers[met])
        if valid:
            ax.plot(valid, means, color=colors[met], marker=markers[met],
                    label=labels[met], linewidth=2.0, markersize=5, zorder=4)
    _setup_axes(ax, ax2, bins, title, "Score")
    ax.legend(loc="lower left", fontsize=7, ncol=2)


# ── Grid builder ───────────────────────────────────────────────────────────────

def _make_grid(n_dis):
    n_rows = (n_dis + 1 + N_COLS - 1) // N_COLS
    fig, axes = plt.subplots(n_rows, N_COLS, figsize=(N_COLS * 5, n_rows * 4.5))
    return fig, np.asarray(axes).flatten().tolist()


def _save_grid(disease_ids, stats_by_dis, case_series,
               overall_stats, overall_series,
               id2name, draw_fn, sup_title, out_path):
    n_dis = len(disease_ids)
    fig, flat = _make_grid(n_dis)
    for i, did in enumerate(disease_ids):
        name  = id2name.get(did, did)
        short = name if len(name) <= 40 else name[:37] + "..."
        draw_fn(flat[i], stats_by_dis[did], case_series.get(did, {}), f"{did}: {short}")
    draw_fn(flat[n_dis], overall_stats, overall_series, "Overall Average")
    for j in range(n_dis + 1, len(flat)):
        flat[j].set_visible(False)
    fig.suptitle(sup_title, fontsize=13, fontweight="bold", y=1.005)
    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=None,
                        help="analysis/<run_dir> directory (default: auto via get_run_dir)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output directory (default: same as --input)")
    args = parser.parse_args()

    if args.input is None:
        from utils.llm import get_run_dir as _grd
        args.input = BASE_DIR / "analysis" / _grd()
    if args.output is None:
        args.output = args.input
    args.output = args.output / "turn_rel"
    args.output.mkdir(parents=True, exist_ok=True)

    id2name = _id2name()
    print(f"Input  : {args.input}")
    print(f"Output : {args.output}")

    # ── Inference ──────────────────────────────────────────────────────────────
    inf_path = args.input / "turn_eval.json"
    if inf_path.exists():
        print(f"\nLoading {inf_path.name} …")
        inf_data = json.loads(inf_path.read_text(encoding="utf-8"))
        s_dis, c_ser, s_ovr, c_ovr = _bin_inf(inf_data)
        dids = list(s_dis.keys())

        def _inf_comb(ax, bd, ser, title):
            _draw_combined(ax, bd, ser, title,
                           ("accuracy", "precision", "recall"),
                           INF_COLORS, INF_MARKERS, INF_LABELS, INF_METRICS)
        _save_grid(dids, s_dis, c_ser, s_ovr, c_ovr, id2name, _inf_comb,
                   "Inference Metrics — Relative Progress  (Accuracy / Precision / Recall)",
                   args.output / "turn_rel_inference.png")

        for met in ("accuracy", "precision", "recall"):
            def _fn(ax, bd, ser, title, _m=met):
                _draw_single(ax, bd, ser, title, _m,
                             INF_COLORS, INF_MARKERS, INF_LABELS, INF_METRICS)
            _save_grid(dids, s_dis, c_ser, s_ovr, c_ovr, id2name, _fn,
                       f"Inference — {INF_LABELS[met]}  (Relative Progress)",
                       args.output / f"turn_rel_inference_{met}.png")
    else:
        print(f"[skip] {inf_path} not found — run plot_turn_eval.py first")

    # ── Question ───────────────────────────────────────────────────────────────
    q_path = args.input / "question_eval_semantic.json"
    if q_path.exists():
        print(f"\nLoading {q_path.name} …")
        q_data = json.loads(q_path.read_text(encoding="utf-8"))
        s_dis, c_ser, s_ovr, c_ovr = _bin_q(q_data)
        dids = list(s_dis.keys())

        def _q_comb(ax, bd, ser, title):
            _draw_combined(ax, bd, ser, title,
                           Q_METRICS,
                           Q_COLORS, Q_MARKERS, Q_LABELS, Q_METRICS)
        _save_grid(dids, s_dis, c_ser, s_ovr, c_ovr, id2name, _q_comb,
                   "Question Metrics — Relative Progress  (DCS / Composite / Mandatory / Redundancy)",
                   args.output / "turn_rel_question.png")

        fname_map = {"dcs": "dcs", "composite_score": "composite",
                     "mandatory_first_compliance": "mandatory",
                     "redundancy_penalty": "redundancy"}
        for met, fname in fname_map.items():
            def _fn(ax, bd, ser, title, _m=met):
                _draw_single(ax, bd, ser, title, _m,
                             Q_COLORS, Q_MARKERS, Q_LABELS, Q_METRICS)
            _save_grid(dids, s_dis, c_ser, s_ovr, c_ovr, id2name, _fn,
                       f"Question — {Q_LABELS[met]}  (Relative Progress)",
                       args.output / f"turn_rel_question_{fname}.png")
    else:
        print(f"[skip] {q_path} not found — run plot_question_eval.py first")

    print("\nDone.")


if __name__ == "__main__":
    main()
