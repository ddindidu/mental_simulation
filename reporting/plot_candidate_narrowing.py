#!/usr/bin/env python3
"""
Candidate-Set Narrowing Curve — by Judge Model

Recommended metric for "did the doctor actually narrow the candidate set
down to 1 before committing to a final diagnosis, or did it decide anyway
while several diseases were still plausible?":

  Mean reference candidate-set size |C_t| across episodes, and the
  Narrowing Ratio |C_t| / |C_1| (how much of the starting candidate pool is
  still alive), both plotted against *relative* turn progress (0-100% of
  each episode's own length) rather than raw turn number.

|C_t| is the reference candidate set (evaluation_v4.md's high_likely ∪
moderate_likely ∪ low_likely — every disease still consistent with
confirmed/denied symptoms so far), ground-truth-deterministic and
independent of what the doctor believes. It's eval/evaluate_efficiency.py's
per-episode `candidate_sizes` array.

Why relative progress instead of raw turn number (first version of this
chart used raw turn number, truncating each line once <5 episodes had that
many turns — this produced a spurious upward trend at high turn numbers):
at turn 18, only the slowest ~10% of episodes are even still running, and
those are disproportionately the hardest cases (large starting candidate
set, slow narrowing) — the mean at that point isn't "how models behave
late in a conversation", it's "how models behave on hard cases", and the
apparent uptick was that composition shift, not real backsliding.
Reindexing each episode onto a common 0-100% grid via linear interpolation
over its own (turn, |C_t|) trace means EVERY episode contributes at EVERY
point on the x-axis, at a constant sample size (no survivorship bias, no
shrinking-n tail). The Narrowing Ratio row additionally normalizes out each
episode's own starting difficulty (a case that starts with 10 candidates
isn't penalized for not looking like a case that starts with 3), which is
the more apples-to-apples version of "how much actual narrowing happened".

Two files are produced:
  candidate_narrowing_by_judge.png           mean lines only (both rows above),
                                              for cross-model comparison
  candidate_narrowing_by_judge_variance.png  Narrowing Ratio, one small
                                              subplot per (doctor, judge) with
                                              its own mean ±1 SD band — with
                                              7-8 models the bands are wide
                                              enough (episodes range from ~3
                                              to ~14 starting candidates) that
                                              overlaying them on one axes
                                              washes out into an unreadable
                                              gray smear, so spread is shown
                                              per-model instead.

Reads efficiency_eval.json directly (results/<patient>/<judge>/<doctor>/) —
not the summarize_v4_metrics_csv.py CSV, since candidate_sizes is a per-turn
array that summary intentionally collapses away.

Usage:
  python reporting/plot_candidate_narrowing.py [--style plain] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_candidate_narrowing.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT, RUN_ROOT

# Colorblind-safe qualitative palette (Okabe-Ito), assigned per canonical
# (lower-cased) doctor name so a model keeps its color across judges.
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
           "#56B4E9", "#999999", "#000000", "#F0E442"]

N_GRID = 11  # 0%, 10%, ..., 100%
GRID = np.linspace(0.0, 1.0, N_GRID)


def discover_combos() -> list[tuple[str, str, str, Path]]:
    combos = []
    for eff_path in sorted(RESULTS_ROOT.rglob("efficiency_eval.json")):
        combo_dir = eff_path.parent
        rel = combo_dir.relative_to(RESULTS_ROOT)
        if len(rel.parts) != 3:
            continue
        patient, judge, doctor = rel.parts
        combos.append((patient, judge, doctor, eff_path))
    return combos


def load_episodes(path: Path, style: str | None) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    if style:
        data = [ep for ep in data if str(ep.get("log_file", "")).endswith(f"_{style}")]
    return data


def resample_episode(sizes: list[float]) -> np.ndarray | None:
    """Linearly interpolate one episode's (turn, |C_t|) trace onto GRID
    (0-100% of its own length). None if the episode has no turns."""
    if not sizes:
        return None
    if len(sizes) == 1:
        return np.full(N_GRID, sizes[0], dtype=float)
    x = np.linspace(0.0, 1.0, len(sizes))
    return np.interp(GRID, x, sizes)


def doctor_curves(episodes: list[dict]) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (abs_matrix, ratio_matrix), each shape (n_episodes, N_GRID)."""
    abs_rows, ratio_rows = [], []
    for ep in episodes:
        sizes = ep.get("candidate_sizes") or []
        resampled = resample_episode(sizes)
        if resampled is None:
            continue
        c1 = resampled[0]
        if c1 <= 0:
            continue
        abs_rows.append(resampled)
        ratio_rows.append(resampled / c1)
    if not abs_rows:
        return None
    return np.array(abs_rows), np.array(ratio_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default="plain",
                         help="Only include episodes whose log filename ends in "
                              "_<style> (default: plain). Pass '' for all styles.")
    parser.add_argument("-o", "--out", default=None,
                         help="Output PNG path (default: analysis/<run>/candidate_narrowing_by_judge.png)")
    args = parser.parse_args()
    style = args.style or None

    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "candidate_narrowing_by_judge.png"

    combos = discover_combos()
    if not combos:
        print(f"No efficiency_eval.json found under {RESULTS_ROOT}")
        return

    canonical_doctors = sorted({doctor.lower() for _p, _j, doctor, _pa in combos})
    color_of = {d: PALETTE[i % len(PALETTE)] for i, d in enumerate(canonical_doctors)}

    judges = sorted({j for _p, j, _d, _pa in combos})
    # panels[judge] = list of (doctor, abs_matrix, ratio_matrix, n_episodes)
    panels: dict[str, list[tuple[str, np.ndarray, np.ndarray, int]]] = {}
    for patient, judge, doctor, path in combos:
        episodes = load_episodes(path, style)
        result = doctor_curves(episodes)
        if result is None:
            print(f"[{judge}] {doctor}: no usable episodes, skipped")
            continue
        abs_mat, ratio_mat = result
        panels.setdefault(judge, []).append((doctor, abs_mat, ratio_mat, len(abs_mat)))

    judges = [j for j in judges if j in panels]
    if not judges:
        print("No judge panel produced a curve.")
        return

    x_pct = GRID * 100

    fig, axes = plt.subplots(2, len(judges), figsize=(7.5 * len(judges), 10.5), sharex=True)
    if len(judges) == 1:
        axes = axes.reshape(2, 1)

    abs_ymax = max(
        abs_mat.mean(axis=0).max()
        for curves in panels.values()
        for _d, abs_mat, _r, _n in curves
    ) * 1.15
    ratio_ymax = max(
        ratio_mat.mean(axis=0).max()
        for curves in panels.values()
        for _d, _a, ratio_mat, _n in curves
    ) * 1.15

    for col, judge in enumerate(judges):
        curves = panels[judge]

        ax_abs = axes[0][col]
        for doctor, abs_mat, _ratio_mat, n in curves:
            color = color_of[doctor.lower()]
            mean = abs_mat.mean(axis=0)
            ax_abs.plot(x_pct, mean, color=color, linewidth=2, marker="o", markersize=3.5, label=doctor)
            ax_abs.annotate(f"{mean[-1]:.1f}", (x_pct[-1], mean[-1]), textcoords="offset points",
                             xytext=(6, 0), fontsize=8.5, color=color, va="center", fontweight="bold")
        ax_abs.axhline(1.0, color="dimgray", linestyle="--", linewidth=1.2, zorder=1)
        ax_abs.text(0.98, 1.0, " fully narrowed (|C|=1)", transform=ax_abs.get_yaxis_transform(),
                    ha="right", va="bottom", fontsize=8, color="dimgray")
        ax_abs.set_title(f"Judge: {judge}", fontsize=12.5, fontweight="bold", pad=10)
        ax_abs.set_ylim(0, abs_ymax)
        ax_abs.grid(color="#E4EBF5", linewidth=0.8, zorder=0)
        ax_abs.spines[["top", "right"]].set_visible(False)

        ax_ratio = axes[1][col]
        for doctor, _abs_mat, ratio_mat, n in curves:
            color = color_of[doctor.lower()]
            mean = ratio_mat.mean(axis=0)
            ax_ratio.plot(x_pct, mean, color=color, linewidth=2, marker="o", markersize=3.5, label=f"{doctor} (n={n})")
            ax_ratio.annotate(f"{mean[-1]:.2f}", (x_pct[-1], mean[-1]), textcoords="offset points",
                               xytext=(6, 0), fontsize=8.5, color=color, va="center", fontweight="bold")
        ax_ratio.axhline(1.0, color="dimgray", linestyle="--", linewidth=1.2, zorder=1)
        ax_ratio.text(0.98, 1.0, " no narrowing (ratio=1)", transform=ax_ratio.get_yaxis_transform(),
                      ha="right", va="bottom", fontsize=8, color="dimgray")
        ax_ratio.set_xlabel("Relative turn progress (%)", fontsize=10.5)
        ax_ratio.set_ylim(0, ratio_ymax)
        ax_ratio.grid(color="#E4EBF5", linewidth=0.8, zorder=0)
        ax_ratio.spines[["top", "right"]].set_visible(False)

    axes[0][0].set_ylabel("Mean |C_t|", fontsize=10.5)
    axes[1][0].set_ylabel("Narrowing ratio |C_t| / |C_1|", fontsize=10.5)

    handles, labels = [], []
    for row in axes:
        for ax in row:
            h, l = ax.get_legend_handles_labels()
            for hi, li in zip(h, l):
                base = li.split(" (n=")[0]
                if base not in [lb.split(" (n=")[0] for lb in labels]:
                    handles.append(hi)
                    labels.append(li)
    fig.legend(handles, labels, loc="upper center", ncol=min(len(labels), 4),
               fontsize=9.5, frameon=False, bbox_to_anchor=(0.5, 1.09))

    style_note = f"style={style}" if style else "all styles"
    fig.suptitle(
        "Candidate-Set Narrowing vs. Relative Turn Progress — by judge model\n"
        f"(each episode resampled onto its own 0-100% timeline, no truncation bias; {style_note}; {RUN_ROOT.name})",
        fontsize=13.5, fontweight="bold", y=1.15,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.90])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    print(f"[saved] {out_path}")

    variance_path = out_path.with_name(out_path.stem + "_variance.png")
    plot_variance_small_multiples(panels, judges, color_of, x_pct, style, variance_path)


def plot_variance_small_multiples(panels, judges, color_of, x_pct, style, out_path: Path) -> None:
    """One subplot per (doctor, judge) showing the Narrowing Ratio's mean ±1 SD
    band in isolation — the combined chart's bands overlap so heavily across
    7-8 models that they wash out into an unreadable gray smear; small
    multiples keep each model's spread legible."""
    all_doctors = sorted({d for curves in panels.values() for d, *_ in curves},
                          key=lambda d: d.lower())

    ncols = len(judges)
    nrows = len(all_doctors)
    fig, axes = plt.subplots(nrows, ncols, figsize=(5.5 * ncols, 2.3 * nrows), sharex=True, sharey=True)
    if nrows == 1:
        axes = axes.reshape(1, ncols)
    if ncols == 1:
        axes = axes.reshape(nrows, 1)

    for row, doctor in enumerate(all_doctors):
        for col, judge in enumerate(judges):
            ax = axes[row][col]
            if row == 0:
                ax.set_title(f"Judge: {judge}", fontsize=10.5, fontweight="bold")
            if col == 0:
                ax.set_ylabel(f"{doctor}", fontsize=8.5)
            if row == nrows - 1:
                ax.set_xlabel("Relative turn\nprogress (%)", fontsize=8.5)

            match = next((c for c in panels.get(judge, []) if c[0] == doctor), None)
            if match is None:
                ax.text(0.5, 0.5, "no data", ha="center", va="center",
                        fontsize=9, color="gray", transform=ax.transAxes)
                ax.set_xticks([])
                ax.set_yticks([])
                for spine in ax.spines.values():
                    spine.set_visible(False)
                continue
            _doctor, _abs_mat, ratio_mat, n = match
            color = color_of[doctor.lower()]
            mean = ratio_mat.mean(axis=0)
            std = ratio_mat.std(axis=0)
            ax.plot(x_pct, mean, color=color, linewidth=2)
            ax.fill_between(x_pct, mean - std, mean + std, color=color, alpha=0.22, linewidth=0)
            ax.axhline(1.0, color="dimgray", linestyle="--", linewidth=1.0, zorder=1)
            ax.set_ylim(0, 4)
            ax.grid(color="#E4EBF5", linewidth=0.7, zorder=0)
            ax.spines[["top", "right"]].set_visible(False)
            if col == 0:
                ax.set_ylabel(f"{doctor}\n(n={n})", fontsize=8.5)

    fig.suptitle(
        "Narrowing Ratio — per-model spread (mean ± 1 SD)\n"
        f"(style={style or 'all'}; {RUN_ROOT.name})",
        fontsize=13, fontweight="bold", y=1.0,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
