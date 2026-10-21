#!/usr/bin/env python3
"""
Pinned-at-1 vs. Narrowing — Variable-Width ("Marimekko") Bars, by Judge Model

Alternative to plot_overcommitment_and_ratio_combined.py's two-row layout:
puts the ratio AND the turn-count breakdown into ONE bar pair per doctor,
one panel per judge, doctors along the y-axis:

  Each doctor gets one full-width bar (narrowing episodes only — the
  no-narrowing/pinned@1 group is excluded from this plot), STACKED same as
  plot_overcommitment_by_judge.py:
    turn to 1st confident (|predicted|==1) + overcommitment (turns after that)
    = that group's mean turn_count

Usage:
  python reporting/plot_overcommitment_marimekko.py [--style plain] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_overcommitment_marimekko.py
"""
from __future__ import annotations

import argparse
import os
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.paths import ANALYSIS_ROOT, RUN_ROOT
from reporting.cross_model.plot_v4_radar_by_judge import DOCTOR_NAME_CANONICAL

COLOR_CONFIDENT = "#2F6FD6"
COLOR_OVERCOMMIT = "#9FC2F2"

SLOT_WIDTH = 0.86   # total height per doctor's bar pair (< 1.0 leaves a gap)
SLOT_GAP = 1.0       # y-distance between slot centers

# Fixed display order (top of each panel to bottom); models not listed here
# fall to the bottom, alphabetically among themselves.
MODEL_ORDER = [
    "gpt-5.4", "gpt-5.6-luna",
    "gemini-3.8-flash", "gemini-3.1-flash-lite",
    "claude-sonnet-5", "claude-haiku-4.5",
    "qwen3-235b",
    "llama-3.3-70b-instruct",
]
EXCLUDE_DOCTORS = {"gpt-5.6-luna", "gemini-3.1-flash-lite", "claude-haiku-4.5"}

# Local model order for this chart only (GPT, Gemini, Claude, Llama, Qwen —
# swaps qwen3-235b <-> llama-3.3-70b-instruct relative to
# plot_overcommitment_by_judge.MODEL_ORDER, which other v4 figures still use
# as-is — not shared, to avoid reordering every other consumer of it).
_LOCAL_MODEL_ORDER = list(MODEL_ORDER)
_i, _j = _LOCAL_MODEL_ORDER.index("qwen3-235b"), _LOCAL_MODEL_ORDER.index("llama-3.3-70b-instruct")
_LOCAL_MODEL_ORDER[_i], _LOCAL_MODEL_ORDER[_j] = _LOCAL_MODEL_ORDER[_j], _LOCAL_MODEL_ORDER[_i]
_LOCAL_ORDER_RANK = {name: i for i, name in enumerate(_LOCAL_MODEL_ORDER)}


def _order_rank(doctor: str) -> int:
    return _LOCAL_ORDER_RANK.get(doctor, len(_LOCAL_MODEL_ORDER))

def discover_turn_eval_combos() -> list[tuple[str, str, str, Path]]:
    combos = []
    for te_path in sorted(ANALYSIS_ROOT.rglob("turn_eval.json")):
        combo_dir = te_path.parent
        rel = combo_dir.relative_to(ANALYSIS_ROOT)
        if len(rel.parts) != 3:
            continue
        patient, judge, doctor = rel.parts
        combos.append((patient, judge, doctor, te_path))
    return combos


def predicted_sizes_per_episode(path: Path, style: str | None) -> list[list[int]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    if style:
        data = [row for row in data if str(row.get("log_file", "")).endswith(f"_{style}")]
    by_episode: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in data:
        log_file, turn = row.get("log_file"), row.get("turn")
        if log_file is None or turn is None:
            continue
        by_episode[log_file].append((turn, len(row.get("predicted") or [])))
    episodes = []
    for turn_sizes in by_episode.values():
        turn_sizes.sort(key=lambda t: t[0])
        episodes.append([size for _t, size in turn_sizes])
    return episodes


def predicted_t1c_overcommit(sizes: list[int]) -> tuple[float, float]:
    """Turn to 1st confident (|predicted|==1) and overcommitment (turns
    spent after that before the episode ends), using the same sentinel
    convention as eval/evaluate_efficiency.py's reference-based version."""
    T = len(sizes)
    ttfin = T + 1
    for i, size in enumerate(sizes):
        if size == 1:
            ttfin = i + 1
            break
    overcommit = 0 if ttfin > T else T - ttfin
    return float(ttfin), float(overcommit)


def turn_counts_by_group(style: str | None) -> dict[str, list[tuple[str, dict]]]:
    """panels[judge] = list of (doctor, stats). stats:
      pinned_mean/pinned_n           mean turn_count over pinned@1 episodes
      real_t1c_mean/real_oc_mean     mean turn-to-1st-confident / overcommitment
                                      over real-differential episodes (their
                                      sum is that group's mean turn_count)
      real_n
    """
    combos = discover_turn_eval_combos()
    by_judge: dict[str, list[tuple[str, dict]]] = {}
    for patient, judge, doctor, path in combos:
        if doctor.lower() in EXCLUDE_DOCTORS:
            continue
        episodes = predicted_sizes_per_episode(path, style)
        if not episodes:
            continue
        pinned_lens = [len(sizes) for sizes in episodes if sizes and sizes[0] <= 1]
        real_episodes = [sizes for sizes in episodes if sizes and sizes[0] > 1]
        if not pinned_lens and not real_episodes:
            continue
        real_t1cs, real_ocs = [], []
        for sizes in real_episodes:
            t1c, oc = predicted_t1c_overcommit(sizes)
            real_t1cs.append(t1c)
            real_ocs.append(oc)
        stats = {
            "pinned_mean": float(np.mean(pinned_lens)) if pinned_lens else None,
            "pinned_n": len(pinned_lens),
            "real_t1c_mean": float(np.mean(real_t1cs)) if real_t1cs else None,
            "real_oc_mean": float(np.mean(real_ocs)) if real_ocs else None,
            "real_n": len(real_episodes),
        }
        by_judge.setdefault(judge, []).append((doctor, stats))
    return by_judge

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--style", default="plain",
        help="Only include episodes whose log filename ends in _<style> "
             "(default: plain). Pass '' for all styles.",
    )
    parser.add_argument(
        "-o", "--out-prefix", default=None,
        help="Output PNG path prefix, one file per judge: <prefix><judge>.png "
             "(default: analysis/<run>/overcommitment_marimekko_)",
    )
    args = parser.parse_args()
    style = args.style or None

    out_prefix = Path(args.out_prefix) if args.out_prefix else ANALYSIS_ROOT / "overcommitment_marimekko_"

    by_judge = turn_counts_by_group(style)
    if not by_judge:
        print("No judge panel has predicted-differential episode data.")
        return

    judges = sorted(by_judge)

    # Filter to doctors with usable data and fix a shared doctor order:
    # gpt-5.4, gemini-3.8-flash, claude-sonnet-5, qwen3-235b, llama-3.3-70b-instruct
    # (MODEL_ORDER's ascending rank already matches this).
    panels: list[tuple[str, list[tuple[str, dict]]]] = []
    for judge in judges:
        rows = [
            (d, s) for d, s in by_judge[judge]
            if s["real_n"] and s["real_t1c_mean"] is not None
        ]
        rows.sort(key=lambda x: _order_rank(x[0]))
        panels.append((judge, rows))

    ymax = max(
        (s["real_t1c_mean"] or 0) + (s["real_oc_mean"] or 0) for _j, rows in panels for _d, s in rows
    ) * 1.06

    for judge, rows in panels:
        fig, ax = plt.subplots(figsize=(11.5, 1.1 * len(rows) + 1.8))

        n_rows = len(rows)
        for i, (doctor, s) in enumerate(rows):
            # First row in `rows` (gpt-5.4, ...) plotted at the top.
            slot_bottom = (n_rows - 1 - i) * SLOT_GAP

            t1c = s["real_t1c_mean"] or 0.0
            oc = s["real_oc_mean"] or 0.0

            ax.barh(slot_bottom, t1c, height=SLOT_WIDTH, align="edge",
                    color=COLOR_CONFIDENT, edgecolor="white", linewidth=0.6, zorder=3)
            ax.barh(slot_bottom, oc, height=SLOT_WIDTH, align="edge", left=t1c,
                    color=COLOR_OVERCOMMIT, edgecolor="white", linewidth=0.6, zorder=3)
            # turn-to-1st-confident value, centered in its own segment
            # (matches plot_overcommitment_by_judge.py's labeling)
            if t1c > ymax * 0.04:
                ax.text(t1c - 1, slot_bottom + SLOT_WIDTH / 2,
                        f"{t1c:.1f}", ha="center", va="center", fontsize=16, color="white", fontweight="bold")
            # overcommitment (turns after 1st confident) value, centered
            # in its own segment — same convention as the t1c label above.
            if oc > ymax * 0.04:
                ax.text(t1c + oc / 2, slot_bottom + SLOT_WIDTH / 2,
                        f"+{oc:.1f}", ha="center", va="center", fontsize=16,
                        color="white", fontweight="bold")
            ax.text(t1c + oc + ymax * 0.012, slot_bottom + SLOT_WIDTH / 2,
                    f"{t1c + oc:.1f}", ha="left", va="center", fontsize=16, fontweight="bold", color="#1C2333")

        # Break each canonical name onto two lines (before the last word) so
        # long names don't force extra left margin on the y-axis.
        def _break_name(name: str) -> str:
            parts = name.split(" ")
            return "\n".join(parts)

        ax.set_yticks([(n_rows - 1 - i) * SLOT_GAP + SLOT_WIDTH / 2 for i in range(n_rows)])
        ax.set_yticklabels(
            [_break_name(DOCTOR_NAME_CANONICAL.get(d, d)) for d, _s in rows], fontsize=16
        )
        legend_band = 0.15
        ax.set_ylim(-0.08, (n_rows - 1) * SLOT_GAP + SLOT_WIDTH + legend_band)
        ax.set_xlim(0, ymax)
        ax.set_xticks(np.arange(0, ymax, 5))
        # ax.set_title(f"Judge: {judge}", fontsize=12.5, fontweight="bold", pad=10)
        ax.grid(axis="x", color="#E4EBF5", linewidth=0.8, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlabel("Mean turn count", fontsize=18)
        ax.tick_params(axis="both", labelsize=18)

        handles = [
            plt.Rectangle((0, 0), 1, 1, color=COLOR_CONFIDENT,
                          label="Before convergence"),
            plt.Rectangle((0, 0), 1, 1, color=COLOR_OVERCOMMIT,
                          label="After convergence"),
        ]
        ax.legend(handles=handles, fontsize=18, loc="center right",
                  bbox_to_anchor=(1, 0.5), borderaxespad=0.0,
                )#frameon=False)

        style_note = f"style={style}" if style else "all styles"
        # fig.suptitle(
        #     f"Pinned-at-1 vs. narrowing episodes — variable-width bars, judge: {judge}\n"
        #     f"(bar width = episode share; bar height = mean turn count; {style_note}; {RUN_ROOT.name})",
        #     fontsize=13.5, fontweight="bold", y=1.14,
        # )

        fig.tight_layout()
        out_path = Path(f"{out_prefix}{judge}.png")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.35)
        plt.close(fig)
        print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
