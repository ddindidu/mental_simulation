#!/usr/bin/env python3
"""
Efficiency Evaluation Summary
Reads efficiency_eval.json and outputs:
  - efficiency_summary.txt  : per-disorder table of all efficiency metrics
  - efficiency_eval_plot.png: grid visualization per disorder (similar to turn_eval_plot_strict.png)

Usage:
  python summarize_efficiency.py          # uses get_run_dir() to auto-detect path
  python summarize_efficiency.py path/to/efficiency_eval.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE_DIR = Path(__file__).parent


def _log_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def load_efficiency(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def group_by_disorder(entries: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in sorted(entries, key=lambda x: _log_sort_key(x["log_file"])):
        did = re.match(r"(D\d+)", e["log_file"]).group(1)
        groups[did].append(e)
    return dict(sorted(groups.items(), key=lambda x: int(x[0][1:])))


def _stats(runs: list[dict]) -> dict:
    def m(k): return float(np.mean([r[k] for r in runs]))
    def s(k): return float(np.std([r[k]  for r in runs]))
    return {
        "n":                            len(runs),
        "accuracy":                     m("final_accuracy"),
        "turn_count":                   m("turn_count"),
        "turn_count_std":               s("turn_count"),
        "cssr":                         m("cssr"),
        "cssr_std":                     s("cssr"),
        "time_to_first_correct":        m("time_to_first_correct_narrowing"),
        "monotonicity_violations":      m("monotonicity_violations"),
        "redundant_turn_ratio":         m("redundant_turn_ratio"),
        "overcommitment_turns":         m("overcommitment_turns"),
    }


# ── Text summary ─────────────────────────────────────────────────────────────

def write_summary(groups: dict[str, list[dict]], out_path: Path) -> None:
    COL = 55
    SEP = "=" * (COL + 70)
    HDR = "-" * (COL + 70)

    header = (
        f"{'Code':<6}  {'Acc':>6}  {'Turns':>6}  {'CSSR':>7}  "
        f"{'T-1st':>6}  {'MonoV':>6}  {'RedRat':>7}  {'OvCom':>6}  Disease Name"
    )

    lines = [
        SEP,
        "Efficiency Evaluation Summary",
        SEP,
        header,
        HDR,
    ]

    all_runs: list[dict] = []
    for did, runs in groups.items():
        name = runs[0]["ground_truth_name"]
        s = _stats(runs)
        all_runs.extend(runs)
        lines.append(
            f"{did:<6}  {s['accuracy']:>6.1%}  {s['turn_count']:>6.2f}  "
            f"{s['cssr']:>+7.4f}  {s['time_to_first_correct']:>6.2f}  "
            f"{s['monotonicity_violations']:>6.2f}  {s['redundant_turn_ratio']:>7.4f}  "
            f"{s['overcommitment_turns']:>6.2f}  {name}"
        )

    lines.append(HDR)

    s = _stats(all_runs)
    lines.append(
        f"{'TOTAL':<6}  {s['accuracy']:>6.1%}  {s['turn_count']:>6.2f}  "
        f"{s['cssr']:>+7.4f}  {s['time_to_first_correct']:>6.2f}  "
        f"{s['monotonicity_violations']:>6.2f}  {s['redundant_turn_ratio']:>7.4f}  "
        f"{s['overcommitment_turns']:>6.2f}"
    )
    lines += [
        SEP,
        "",
        "Column descriptions:",
        "  Acc     : Final diagnosis accuracy (mean across runs)",
        "  Turns   : Mean turn count per episode",
        "  CSSR    : Candidate Set Shrink Rate = (size[0] − size[T-1]) / T  (higher = faster)",
        "  T-1st   : Mean turn of first correct single-candidate narrowing",
        "  MonoV   : Mean monotonicity violations (candidate set grew between turns)",
        "  RedRat  : Mean redundant turn ratio (turns with no candidate-set change)",
        "  OvCom   : Mean overcommitment turns (continued after candidate size=1)",
        SEP,
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved summary  → {out_path}")


# ── Visualization ─────────────────────────────────────────────────────────────

COLORS = {
    "final_accuracy":      "#1f77b4",
    "cssr":                "#ff7f0e",
    "redundant_turn_ratio":"#2ca02c",
    "monotonicity_violations": "#9467bd",
    "overcommitment_turns":    "#d62728",
}
MARKERS = {
    "final_accuracy":      "o",
    "cssr":                "s",
    "redundant_turn_ratio":"^",
    "monotonicity_violations": "D",
    "overcommitment_turns":    "v",
}
LABELS = {
    "final_accuracy":      "Accuracy",
    "cssr":                "CSSR",
    "redundant_turn_ratio":"Redund. Ratio",
    "monotonicity_violations": "Mono. Viol.",
    "overcommitment_turns":    "Overcommit",
}


def _plot_one(ax: plt.Axes, runs: list[dict], title: str) -> None:
    run_nums = list(range(1, len(runs) + 1))
    turn_counts = [r["turn_count"] for r in runs]

    # Background bars: turn count (right y-axis)
    ax2 = ax.twinx()
    ax2.bar(run_nums, turn_counts, color="gray", alpha=0.18, width=0.7, zorder=1)
    ax2.set_ylabel("# Turns", fontsize=8, color="gray")
    ax2.tick_params(axis="y", labelsize=7, colors="gray")
    max_turns = max(turn_counts) if turn_counts else 1
    ax2.set_ylim(0, max_turns * 1.4)
    for x, tc in zip(run_nums, turn_counts):
        ax2.text(x, tc + max_turns * 0.02, str(tc),
                 ha="center", va="bottom", fontsize=6, color="gray")

    # Per-metric scatter + mean line
    for key in ("final_accuracy", "cssr", "redundant_turn_ratio",
                "monotonicity_violations", "overcommitment_turns"):
        vals = np.array([r[key] for r in runs], dtype=float)
        mean_val = float(vals.mean())
        color  = COLORS[key]
        marker = MARKERS[key]
        label  = f"{LABELS[key]} (μ={mean_val:+.3f})"

        ax.scatter(run_nums, vals, color=color, alpha=0.65, s=30,
                   marker=marker, zorder=4)
        ax.axhline(mean_val, color=color, linewidth=1.3,
                   linestyle="--", alpha=0.75, zorder=3, label=label)

    # Horizontal reference lines
    for y in np.arange(-2.5, 3.0, 0.5):
        ax.axhline(y, color="gray", linestyle=":", linewidth=0.4, alpha=0.4, zorder=0)
    ax.axhline(0.0, color="black", linewidth=0.6, alpha=0.5, zorder=1)
    ax.axhline(1.0, color="black", linewidth=0.6, alpha=0.5, linestyle="--", zorder=1)

    ax.set_xlim(0.5, len(runs) + 0.5)
    ax.set_xticks(run_nums)
    ax.set_xlabel("Run", fontsize=8)
    ax.set_ylabel("Metric Value", fontsize=8)
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.tick_params(labelsize=7)
    ax.legend(loc="upper right", fontsize=6.5, framealpha=0.75, ncol=1)
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)


def plot_efficiency(groups: dict[str, list[dict]], out_path: Path) -> None:
    disease_ids = list(groups.keys())
    n_dis  = len(disease_ids)
    n_cols = 6
    n_rows = (n_dis + 1 + n_cols - 1) // n_cols

    all_runs = [r for runs in groups.values() for r in runs]

    # Build overall-per-run aggregates
    overall_by_run: dict[int, list[dict]] = defaultdict(list)
    for r in all_runs:
        run_num = int(re.search(r"_(\d+)$", r["log_file"]).group(1))
        overall_by_run[run_num].append(r)

    overall_agg = []
    for run_num in sorted(overall_by_run.keys()):
        entries = overall_by_run[run_num]
        def avg(k): return float(np.mean([e[k] for e in entries]))
        overall_agg.append({
            "turn_count":                    avg("turn_count"),
            "final_accuracy":                avg("final_accuracy"),
            "cssr":                          avg("cssr"),
            "time_to_first_correct_narrowing": avg("time_to_first_correct_narrowing"),
            "monotonicity_violations":       avg("monotonicity_violations"),
            "redundant_turn_ratio":          avg("redundant_turn_ratio"),
            "overcommitment_turns":          avg("overcommitment_turns"),
        })

    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(n_cols * 5.2, n_rows * 4.2),
                             squeeze=False)
    axes_flat = axes.flatten()

    for i, did in enumerate(disease_ids):
        runs = groups[did]
        name = runs[0]["ground_truth_name"]
        short = name if len(name) <= 42 else name[:39] + "..."
        _plot_one(axes_flat[i], runs, f"{did}: {short}")

    _plot_one(axes_flat[n_dis], overall_agg, "Overall Average")

    for j in range(n_dis + 1, len(axes_flat)):
        axes_flat[j].set_visible(False)

    fig.suptitle("Efficiency Metrics per Disorder (per run)",
                 fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved plot     → {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("json", nargs="?", type=Path, default=None,
                        help="Path to efficiency_eval.json (default: auto via get_run_dir)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Directory to write outputs (default: analysis/<run_dir>)")
    args = parser.parse_args()

    if args.json is None:
        from utils.llm import get_run_dir as _get_run_dir
        run_dir = _get_run_dir()
        args.json = BASE_DIR / "results" / run_dir / "efficiency_eval.json"

    if not args.json.exists():
        print(f"[error] File not found: {args.json}", file=sys.stderr)
        sys.exit(1)

    if args.output is None:
        # Infer run_dir from json path: results/<run_dir>/efficiency_eval.json
        try:
            rel = args.json.resolve().parent.relative_to((BASE_DIR / "results").resolve())
            args.output = BASE_DIR / "analysis" / rel
        except ValueError:
            args.output = args.json.parent

    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Input JSON : {args.json}")
    print(f"Output dir : {args.output}")

    entries = load_efficiency(args.json)
    groups  = group_by_disorder(entries)

    write_summary(groups, args.output / "efficiency_summary.txt")
    plot_efficiency(groups, args.output / "efficiency_eval_plot.png")


if __name__ == "__main__":
    main()
