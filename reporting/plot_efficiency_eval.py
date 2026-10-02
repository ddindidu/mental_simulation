#!/usr/bin/env python3
"""
Diagnostic Efficiency Plotter (evaluation_v5.md §3, + Final Accuracy §4.1)
Reads efficiency_eval.json and generates per-disorder subplots (one point per
episode, x = episode index within that disorder) plus an "Overall" panel
(one point per disorder = that disorder's episode mean).

Outputs saved to analysis/<run_dir>/efficiency/:
  efficiency_eval_plot.png                combined: per-episode stacked bar
                                          (1st-Confidence Turn | Overcommitment
                                          Turns) = Total Turns; red edge = wrong dx
  efficiency_eval_plot_turns.png          Total Turns
  efficiency_eval_plot_first_confident.png 1st-Confidence Turn (reached episodes only)
  efficiency_eval_plot_overcommit.png     Overcommitment Turns
  efficiency_eval_plot_accuracy.png       Final Accuracy

Usage:
  python plot_efficiency_eval.py results/.../efficiency_eval.json
  python plot_efficiency_eval.py              # auto via get_run_dir()
  python plot_efficiency_eval.py results/.../efficiency_eval.json --output analysis/custom/
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

BASE_DIR       = Path(__file__).resolve().parent.parent
from utils.paths import ANALYSIS_ROOT, LOGS_ROOT, RESULTS_ROOT
CRITERIA_FILE  = BASE_DIR / "mentalbench" / "resources" / "knowledge_graph" / "EN" / "diagnostic_criteria.json"

N_COLS = 6


# ── Helpers ────────────────────────────────────────────────────────────────────

def _id2name() -> dict[str, str]:
    data = json.loads(CRITERIA_FILE.read_text(encoding="utf-8"))
    return {k: v["name"] for k, v in data.items()}


def _log_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def load_and_group(json_path: Path) -> dict[str, list[dict]]:
    entries = json.loads(json_path.read_text(encoding="utf-8"))
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in sorted(entries, key=lambda x: _log_sort_key(x["log_file"])):
        did = re.match(r"(D\d+)", e["log_file"]).group(1)
        groups[did].append(e)
    return dict(sorted(groups.items(), key=lambda x: int(x[0][1:])))


# ── Metric config ──────────────────────────────────────────────────────────────

METRICS = [
    # (key, label, color, marker, higher_is_better, y_center_zero)
    ("turn_count",                        "Total Turns",          "#8c564b", "D", False, False),
    ("time_to_first_confident_narrowing", "1st-Confidence Turn",  "#9467bd", "^", False, False),
    ("overcommitment_conf",               "Overcommitment Turns", "#d62728", "X", False, False),
    ("final_accuracy",                    "Final Accuracy",       "#1f77b4", "o", True,  False),
]
METRIC_KEYS    = [m[0] for m in METRICS]
METRIC_LABELS  = {m[0]: m[1] for m in METRICS}
METRIC_COLORS  = {m[0]: m[2] for m in METRICS}
METRIC_MARKERS = {m[0]: m[3] for m in METRICS}

TTFIN = "time_to_first_confident_narrowing"


def _metric_value(r: dict, metric: str) -> float | None:
    """Per-episode value; the 1st-Confidence Turn sentinel (T+1 = never
    reached) is treated as missing rather than plotted as a turn number."""
    v = r.get(metric)
    if metric == TTFIN and v is not None and v > r.get("turn_count", v):
        return None
    return v


# ── Per-disorder subplot ───────────────────────────────────────────────────────

def _run_nums(runs: list[dict]) -> list[int]:
    """x position: 1-based episode index within the panel."""
    return list(range(1, len(runs) + 1))


def _draw_single_metric(ax, runs: list[dict], title: str, metric: str,
                         color: str, marker: str, label: str, center_zero: bool):
    pts = [(x, v) for x, r in zip(_run_nums(runs), runs) if (v := _metric_value(r, metric)) is not None]
    if not pts:
        ax.set_title(title, fontsize=9, fontweight="bold")
        return
    run_nums = [x for x, _ in pts]
    vals     = [v for _, v in pts]
    mean_val = float(np.mean(vals))

    ax.scatter(run_nums, vals, color=color, alpha=0.7, s=35, marker=marker, zorder=3)
    ax.axhline(mean_val, color=color, linewidth=1.6, linestyle="--", alpha=0.85,
               zorder=2, label=f"μ = {mean_val:+.3f}" if center_zero else f"μ = {mean_val:.3f}")

    # Y-axis range
    all_min, all_max = min(vals), max(vals)
    pad = max((all_max - all_min) * 0.15, 0.05)
    if metric == "final_accuracy":
        ax.set_ylim(-0.05, 1.1)
        ax.set_yticks([0, 0.5, 1.0])
    elif center_zero:
        bound = max(abs(all_min - pad), abs(all_max + pad), 0.5)
        ax.set_ylim(-bound, bound)
        ax.axhline(0, color="black", linewidth=0.6, alpha=0.4, zorder=1)
    else:
        ax.set_ylim(max(0, all_min - pad), all_max + pad)

    for y in ax.get_yticks():
        ax.axhline(y, color="lightgray", linewidth=0.4, zorder=0)

    ax.set_xlim(0.3, len(runs) + 0.7)
    ax.tick_params(labelsize=7)
    ax.set_xlabel("Episode", fontsize=8)
    ax.set_ylabel(label, fontsize=8)
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.legend(loc="upper right", fontsize=7.5)


def _draw_combined(ax, runs: list[dict], title: str):
    """Stacked bar per episode: 1st-Confidence Turn (bottom) + Overcommitment
    Turns (top) = Total Turns. Episodes that never reached the 1st-confidence
    turn are drawn as a single hatched Total-Turns bar. Bar edge red = the
    final diagnosis was wrong."""
    xs = _run_nums(runs)
    for x, r in zip(xs, runs):
        T = r["turn_count"]
        t1 = _metric_value(r, TTFIN)
        edge = "#d62728" if r.get("final_accuracy", 0.0) < 1.0 else "none"
        if t1 is None:
            ax.bar(x, T, color="#cfcfcf", hatch="//", edgecolor=edge, linewidth=0.8, width=0.75)
        else:
            ax.bar(x, t1, color=METRIC_COLORS[TTFIN], edgecolor=edge, linewidth=0.8, width=0.75)
            ax.bar(x, T - t1, bottom=t1, color=METRIC_COLORS["overcommitment_conf"],
                   edgecolor=edge, linewidth=0.8, width=0.75)

    acc = float(np.mean([r.get("final_accuracy", 0.0) for r in runs]))
    mean_t = float(np.mean([r["turn_count"] for r in runs]))
    ax.text(0.98, 0.97, f"Total μ={mean_t:.1f}  Acc={acc:.0%}", transform=ax.transAxes,
            ha="right", va="top", fontsize=7.5)
    ax.set_xlim(0.3, len(runs) + 0.7)
    ax.tick_params(labelsize=7)
    ax.set_xlabel("Episode", fontsize=8)
    ax.set_ylabel("Turns", fontsize=8)
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.grid(axis="y", color="lightgray", linewidth=0.4)
    ax.set_axisbelow(True)


# ── Overall-panel helper ───────────────────────────────────────────────────────

def _overall_runs(groups: dict[str, list[dict]]) -> list[dict]:
    """One entry per disorder holding that disorder's episode means (the
    1st-Confidence Turn mean is over reached episodes only)."""
    overall = []
    for did, runs in groups.items():
        agg: dict = {"log_file": did}
        for k in METRIC_KEYS:
            vals = [v for r in runs if (v := _metric_value(r, k)) is not None]
            agg[k] = float(np.mean(vals)) if vals else None
        if agg[TTFIN] is None:
            agg[TTFIN] = agg["turn_count"] + 1  # keep the "never reached" sentinel
        overall.append(agg)
    return overall


# ── Build figure grid ──────────────────────────────────────────────────────────

def _make_fig(n_dis: int) -> tuple[plt.Figure, list[plt.Axes]]:
    n_rows = (n_dis + 1 + N_COLS - 1) // N_COLS
    fig, axes = plt.subplots(n_rows, N_COLS, figsize=(N_COLS * 5.2, n_rows * 4.2))
    return fig, np.asarray(axes).flatten().tolist()


def _hide_extra(axes: list, used: int):
    for ax in axes[used:]:
        ax.set_visible(False)


# ── Public plot functions ──────────────────────────────────────────────────────

def plot_combined(groups: dict[str, list[dict]], out_path: Path,
                  id2name: dict[str, str], overall: list[dict]) -> None:
    disease_ids = list(groups.keys())
    n_dis = len(disease_ids)
    fig, axes = _make_fig(n_dis)

    for i, did in enumerate(disease_ids):
        name  = id2name.get(did, did)
        short = name[:40] + "..." if len(name) > 40 else name
        _draw_combined(axes[i], groups[did], f"{did}: {short}")

    _draw_combined(axes[n_dis], overall, "Overall (one bar per disorder mean)")
    _hide_extra(axes, n_dis + 1)

    fig.suptitle("Diagnostic Efficiency — 1st-Confidence Turn (purple) + Overcommitment Turns (red) "
                 "= Total Turns; hatched = never reached; red edge = wrong final dx",
                 fontsize=13, fontweight="bold", y=1.005)
    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path}")


def plot_metric(groups: dict[str, list[dict]], metric: str, out_path: Path,
                id2name: dict[str, str], overall: list[dict]) -> None:
    _, __, color, marker, _hib, center_zero = next(m for m in METRICS if m[0] == metric)
    label = METRIC_LABELS[metric]

    disease_ids = list(groups.keys())
    n_dis = len(disease_ids)
    fig, axes = _make_fig(n_dis)

    for i, did in enumerate(disease_ids):
        name  = id2name.get(did, did)
        short = name[:40] + "..." if len(name) > 40 else name
        _draw_single_metric(axes[i], groups[did], f"{did}: {short}",
                            metric, color, marker, label, center_zero)

    _draw_single_metric(axes[n_dis], overall, "Overall (per-disorder means)",
                        metric, color, marker, label, center_zero)
    _hide_extra(axes, n_dis + 1)

    fig.suptitle(f"Diagnostic Efficiency — {label}", fontsize=13, fontweight="bold", y=1.005)
    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json", nargs="?", type=Path, default=None,
                        help="Path to efficiency_eval.json")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output directory (default: analysis/<run_dir>)")
    args = parser.parse_args()

    if args.json is None:
        from utils.llm import get_run_dir as _get_run_dir
        run_dir = _get_run_dir()
        args.json = RESULTS_ROOT / run_dir / "efficiency_eval.json"

    if not args.json.exists():
        print(f"[error] File not found: {args.json}", file=sys.stderr)
        sys.exit(1)

    if args.output is None:
        try:
            rel = args.json.resolve().parent.relative_to((RESULTS_ROOT).resolve())
            args.output = ANALYSIS_ROOT / rel
        except ValueError:
            args.output = args.json.parent

    args.output = args.output / "efficiency"
    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Input JSON : {args.json}")
    print(f"Output dir : {args.output}")

    id2name = _id2name()
    groups  = load_and_group(args.json)
    overall = _overall_runs(groups)

    print("Generating plots...")
    plot_combined(groups, args.output / "efficiency_eval_plot.png", id2name, overall)

    fname_map = {
        "turn_count":                        "turns",
        "time_to_first_confident_narrowing": "first_confident",
        "overcommitment_conf":               "overcommit",
        "final_accuracy":                    "accuracy",
    }
    for metric, fname in fname_map.items():
        plot_metric(groups, metric,
                    args.output / f"efficiency_eval_plot_{fname}.png",
                    id2name, overall)

    print("Done.")


if __name__ == "__main__":
    main()
