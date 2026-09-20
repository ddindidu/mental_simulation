#!/usr/bin/env python3
"""
Pinned-at-1 vs. Narrowing — Variable-Width ("Marimekko") Bars, by Judge Model

Alternative to plot_overcommitment_and_ratio_combined.py's two-row layout:
puts the ratio AND the turn-count breakdown into ONE bar pair per doctor,
one panel per judge, doctors along the y-axis:

  Each doctor gets one slot holding two stacked-vertically bars:
    Top    ("pinned@1"):  height = pinned@1 episode share of that doctor's
                                    episodes (never runs a differential)
                           length (x) = mean turn_count over those episodes
                           (single color, not stacked — there's no
                           "narrowing then overcommitting" phase to split)
    Bottom ("narrowing"): height = narrowing episode share (starts >1,
                                    narrows down)
                           length (x) = STACKED, same as
                                    plot_overcommitment_by_judge.py:
                                      turn to 1st confident (|predicted|==1)
                                    + overcommitment (turns after that)
                                    = that group's mean turn_count

So bar HEIGHT reads the population split (item 1) and bar LENGTH (with the
bottom bar's stack) reads the confidence-timing breakdown (item 2) — both in
one glyph per doctor instead of two stacked panels.

Usage:
  python reporting/plot_overcommitment_marimekko.py [--style plain] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_overcommitment_marimekko.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from utils.paths import ANALYSIS_ROOT, RUN_ROOT
from reporting.plot_overcommitment_by_judge import COLOR_CONFIDENT, COLOR_OVERCOMMIT, _order_rank
from reporting.plot_pinned_at_1_turn_counts import COLOR_PINNED, turn_counts_by_group
from reporting.plot_v4_radar_by_judge import DOCTOR_NAME_CANONICAL

SLOT_WIDTH = 0.86   # total height per doctor's bar pair (< 1.0 leaves a gap)
SLOT_GAP = 1.0       # y-distance between slot centers


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

    # Filter to doctors with usable data (at least one of the two groups
    # non-empty and its mean(s) present) and fix a shared doctor order:
    # gpt-5.4, gemini-3.8-flash, claude-sonnet-5, qwen3-235b, llama-3.3-70b-instruct
    # (MODEL_ORDER's ascending rank already matches this).
    panels: list[tuple[str, list[tuple[str, dict]]]] = []
    for judge in judges:
        rows = [
            (d, s) for d, s in by_judge[judge]
            if (s["pinned_n"] or s["real_n"]) and (s["pinned_mean"] is not None or s["real_t1c_mean"] is not None)
        ]
        rows.sort(key=lambda x: _order_rank(x[0]))
        panels.append((judge, rows))

    ymax = max(
        (s["pinned_mean"] or 0) for _j, rows in panels for _d, s in rows
    )
    ymax = max(ymax, max(
        (s["real_t1c_mean"] or 0) + (s["real_oc_mean"] or 0) for _j, rows in panels for _d, s in rows
    )) * 1.18

    for judge, rows in panels:
        fig, ax = plt.subplots(figsize=(8.5, 1.1 * len(rows) + 1.8))

        n_rows = len(rows)
        for i, (doctor, s) in enumerate(rows):
            # First row in `rows` (gpt-5.4, ...) plotted at the top.
            slot_bottom = (n_rows - 1 - i) * SLOT_GAP

            total_n = s["pinned_n"] + s["real_n"]
            pinned_frac = s["pinned_n"] / total_n if total_n else 0.0
            narrow_frac = 1.0 - pinned_frac

            pinned_h = pinned_frac * SLOT_WIDTH
            narrow_h = narrow_frac * SLOT_WIDTH

            pinned_mean = s["pinned_mean"] or 0.0
            t1c = s["real_t1c_mean"] or 0.0
            oc = s["real_oc_mean"] or 0.0

            if pinned_h > 0:
                ax.barh(slot_bottom, pinned_mean, height=pinned_h, align="edge",
                        color=COLOR_PINNED, edgecolor="white", linewidth=0.6, zorder=3)
                if pinned_h > 0.06:
                    ax.text(pinned_mean + ymax * 0.012, slot_bottom + pinned_h / 2,
                            f"{pinned_mean:.1f}", ha="left", va="center", 
                            fontsize=12,
                              color=COLOR_PINNED)

            if narrow_h > 0:
                ax.barh(slot_bottom + pinned_h, t1c, height=narrow_h, align="edge",
                        color=COLOR_CONFIDENT, edgecolor="white", linewidth=0.6, zorder=3)
                ax.barh(slot_bottom + pinned_h, oc, height=narrow_h, align="edge", left=t1c,
                        color=COLOR_OVERCOMMIT, edgecolor="white", linewidth=0.6, zorder=3)
                # turn-to-1st-confident value, centered in its own segment
                # (matches plot_overcommitment_by_judge.py's labeling)
                if narrow_h > 0.10 and t1c > ymax * 0.04:
                    ax.text(t1c - 1, slot_bottom + pinned_h + narrow_h / 2,
                            f"{t1c:.1f}", ha="center", va="center", fontsize=12, color="white", fontweight="bold")
                # overcommitment (turns after 1st confident) value, centered
                # in its own segment — same convention as the t1c label above.
                if narrow_h > 0.10 and oc > ymax * 0.04:
                    ax.text(t1c + oc / 2, slot_bottom + pinned_h + narrow_h / 2,
                            f"+{oc:.1f}", ha="center", va="center", fontsize=12,
                            color="white", fontweight="bold")
                if narrow_h > 0.06:
                    ax.text(t1c + oc + ymax * 0.012, slot_bottom + pinned_h + narrow_h / 2,
                            f"{t1c + oc:.1f}", ha="left", va="center", fontsize=12, color="#1C2333")

            # share labels inside the base of each bar (white, small) rather
            # than past the bar's end, which would collide with the value
            # label placed there.
            if pinned_h > 0.10 and pinned_mean > ymax * 0.04:
                ax.text(ymax * 0.012, slot_bottom + pinned_h / 2, f"{pinned_frac*100:.0f}%",
                        ha="left", va="center", fontsize=12, color="white", fontweight="bold")
            if narrow_h > 0.10 and (t1c + oc) > ymax * 0.04:
                ax.text(ymax * 0.012, slot_bottom + pinned_h + narrow_h / 2, f"{narrow_frac*100:.0f}%",
                        ha="left", va="center", fontsize=12, color="white", fontweight="bold")

        ax.set_yticks([(n_rows - 1 - i) * SLOT_GAP + SLOT_WIDTH / 2 for i in range(n_rows)])
        ax.set_yticklabels([DOCTOR_NAME_CANONICAL.get(d, d) for d, _s in rows], fontsize=14)
        legend_band = 0.15
        ax.set_ylim(-0.08, (n_rows - 1) * SLOT_GAP + SLOT_WIDTH + legend_band)
        ax.set_xlim(0, ymax)
        # ax.set_title(f"Judge: {judge}", fontsize=12.5, fontweight="bold", pad=10)
        ax.grid(axis="x", color="#E4EBF5", linewidth=0.8, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlabel("Mean turn count", fontsize=14)
        ax.tick_params(axis="x", labelsize=12)

        handles = [
            plt.Rectangle((0, 0), 1, 1, color=COLOR_PINNED,
                          label="Single fixed candidate\n" + r"(non-narrowing case; $\hat{C}_{1,\dots}=1$)"),
            plt.Rectangle((0, 0), 1, 1, color=COLOR_CONFIDENT,
                          label="Turns to convergence\n" + r"(narrowing case; $\hat{C}_t > 1$)"),
            plt.Rectangle((0, 0), 1, 1, color=COLOR_OVERCOMMIT,
                          label="Extended inquiry\n" + r"(narrowing case; $\hat{C}_t = 1$)"),
        ]
        ax.legend(handles=handles, fontsize=11, loc="center right",
                  bbox_to_anchor=(0.9, 0.6), borderaxespad=0.0,
                  frameon=False)

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
