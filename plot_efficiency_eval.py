#!/usr/bin/env python3
"""
Efficiency Metrics Plotter  (spec §4.5)
Reads efficiency_eval.json and generates per-disorder subplots for each
efficiency metric — matching the grid style of turn_eval / question_eval plots.

Outputs saved to analysis/<run_dir>/efficiency/:
  efficiency_eval_plot.png            combined (accuracy + cssr + redundant_ratio)
  efficiency_eval_plot_accuracy.png
  efficiency_eval_plot_cssr.png
  efficiency_eval_plot_turns.png
  efficiency_eval_plot_tfirst.png
  efficiency_eval_plot_monotonicity.png
  efficiency_eval_plot_redundancy.png
  efficiency_eval_plot_overcommit.png

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

import matplotlib.pyplot as plt
import numpy as np

BASE_DIR       = Path(__file__).parent
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
    ("final_accuracy",                "Accuracy",          "#1f77b4", "o",  True,  False),
    ("cssr",                          "CSSR",              "#ff7f0e", "s",  True,  True),
    ("turn_count",                    "Turn Count",        "#8c564b", "D",  False, False),
    ("time_to_first_correct_narrowing","T-First",          "#9467bd", "^",  False, False),
    ("monotonicity_violations",       "Mono. Violations",  "#e377c2", "v",  False, False),
    ("redundant_turn_ratio",          "Redundant Ratio",   "#2ca02c", "P",  False, False),
    ("overcommitment_turns",          "Overcommit Turns",  "#d62728", "X",  False, False),
]
METRIC_KEYS    = [m[0] for m in METRICS]
METRIC_LABELS  = {m[0]: m[1] for m in METRICS}
METRIC_COLORS  = {m[0]: m[2] for m in METRICS}
METRIC_MARKERS = {m[0]: m[3] for m in METRICS}

# Metrics shown in the combined plot (0-1 or near-0-1 range)
COMBINED_METRICS = ("final_accuracy", "cssr", "redundant_turn_ratio")


# ── Per-disorder subplot ───────────────────────────────────────────────────────

def _run_nums(runs: list[dict]) -> list[int]:
    nums = []
    for r in runs:
        m = re.search(r"_(\d+)$", r["log_file"])
        nums.append(int(m.group(1)) if m else len(nums) + 1)
    return nums


def _draw_single_metric(ax, runs: list[dict], title: str, metric: str,
                         color: str, marker: str, label: str, center_zero: bool):
    run_nums = _run_nums(runs)
    vals     = [r[metric] for r in runs]
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

    ax.set_xlim(min(run_nums) - 0.7, max(run_nums) + 0.7)
    ax.set_xticks(run_nums)
    ax.tick_params(labelsize=7)
    ax.set_xlabel("Run", fontsize=8)
    ax.set_ylabel(label, fontsize=8)
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.legend(loc="upper right", fontsize=7.5)


def _draw_combined(ax, runs: list[dict], title: str):
    run_nums = _run_nums(runs)

    # Right axis: turn_count bars
    ax2 = ax.twinx()
    turn_counts = [r["turn_count"] for r in runs]
    ax2.bar(run_nums, turn_counts, color="gray", alpha=0.15, width=0.7, zorder=0)
    ax2.set_ylabel("Turn Count", fontsize=7, color="gray")
    ax2.tick_params(axis="y", labelsize=6, colors="gray")
    max_tc = max(turn_counts)
    ax2.set_ylim(0, max_tc * 1.5)
    for x, tc in zip(run_nums, turn_counts):
        ax2.text(x, tc + max_tc * 0.03, str(tc),
                 ha="center", va="bottom", fontsize=6, color="gray")

    # Left axis: 0-1 bounded metrics
    for metric in COMBINED_METRICS:
        vals     = [r[metric] for r in runs]
        mean_val = float(np.mean(vals))
        color    = METRIC_COLORS[metric]
        marker   = METRIC_MARKERS[metric]
        lbl      = f"{METRIC_LABELS[metric]} (μ={mean_val:+.2f})"
        ax.scatter(run_nums, vals, color=color, alpha=0.6, s=28, marker=marker, zorder=3)
        ax.axhline(mean_val, color=color, linewidth=1.4, linestyle="--", alpha=0.8,
                   zorder=2, label=lbl)

    # Reference lines
    ax.axhline(0, color="black", linewidth=0.5, alpha=0.35, zorder=1)
    ax.axhline(1, color="black", linewidth=0.5, alpha=0.35, linestyle=":", zorder=1)

    all_vals = [r[m] for r in runs for m in COMBINED_METRICS]
    lo = min(min(all_vals) - 0.15, -0.1)
    hi = max(max(all_vals) + 0.15,  1.1)
    ax.set_ylim(lo, hi)
    for y in np.arange(round(lo, 1), hi + 0.05, 0.2):
        ax.axhline(y, color="lightgray", linewidth=0.4, zorder=0)

    ax.set_xlim(min(run_nums) - 0.7, max(run_nums) + 0.7)
    ax.set_xticks(run_nums)
    ax.tick_params(labelsize=7)
    ax.set_xlabel("Run", fontsize=8)
    ax.set_ylabel("Score / Rate", fontsize=8)
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    ax.legend(loc="upper right", fontsize=6.5, ncol=1, framealpha=0.75)


# ── Overall-panel helper ───────────────────────────────────────────────────────

def _overall_runs(groups: dict[str, list[dict]]) -> list[dict]:
    """Aggregate per-disorder means into per-run-index overall entries."""
    by_run: dict[int, list[dict]] = defaultdict(list)
    for runs in groups.values():
        for r in runs:
            m = re.search(r"_(\d+)$", r["log_file"])
            rn = int(m.group(1)) if m else 0
            by_run[rn].append(r)

    overall = []
    for rn in sorted(by_run.keys()):
        entries = by_run[rn]
        agg = {k: float(np.mean([e[k] for e in entries])) for k in METRIC_KEYS}
        agg["log_file"] = f"OVERALL_{rn}"
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

    _draw_combined(axes[n_dis], overall, "Overall Average")
    _hide_extra(axes, n_dis + 1)

    fig.suptitle("Efficiency Metrics — Combined View (Accuracy / CSSR / Redundant Ratio)",
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

    _draw_single_metric(axes[n_dis], overall, "Overall Average",
                        metric, color, marker, label, center_zero)
    _hide_extra(axes, n_dis + 1)

    fig.suptitle(f"Efficiency — {label}", fontsize=13, fontweight="bold", y=1.005)
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
        args.json = BASE_DIR / "results" / run_dir / "efficiency_eval.json"

    if not args.json.exists():
        print(f"[error] File not found: {args.json}", file=sys.stderr)
        sys.exit(1)

    if args.output is None:
        try:
            rel = args.json.resolve().parent.relative_to((BASE_DIR / "results").resolve())
            args.output = BASE_DIR / "analysis" / rel
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
        "final_accuracy":                 "accuracy",
        "cssr":                           "cssr",
        "turn_count":                     "turns",
        "time_to_first_correct_narrowing":"tfirst",
        "monotonicity_violations":        "monotonicity",
        "redundant_turn_ratio":           "redundancy",
        "overcommitment_turns":           "overcommit",
    }
    for metric, fname in fname_map.items():
        plot_metric(groups, metric,
                    args.output / f"efficiency_eval_plot_{fname}.png",
                    id2name, overall)

    print("Done.")


if __name__ == "__main__":
    main()
