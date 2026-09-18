#!/usr/bin/env python3
"""
Turns to Confidence vs. Turns Spent Confirming It — by Judge Model

Stacked horizontal bar chart, one panel per judge, one bar per doctor model:

  Turn to 1st confident        (mean)
  Overcommitment (confidence-based)   (mean)

These two are true complements: turn_count == turn_to_1st_confident +
overcommitment_conf whenever the confident-narrowing point is reached, so
the bar's total length is (close to) mean turn_count. Bars within each
panel follow a fixed provider-grouped order (MODEL_ORDER below), top to
bottom.

Two data sources (--source):
  reference (default)  time_to_first_confident_narrowing / overcommitment_conf
                        from eval/evaluate_efficiency.py, via the CSV
                        summarize_v4_metrics_csv.py produces. "Confident" here
                        means the JUDGE/KG reference candidate_set (high|
                        moderate|low) has collapsed to exactly the doctor's
                        final diagnosis — independent of what the doctor
                        itself believes turn-by-turn.
  predicted             recomputed directly from analysis/<run>/turn_eval.json's
                        per-turn `predicted` field — the doctor's OWN stated
                        differential list. "Confident" here means the doctor
                        itself reported exactly one candidate. Turn to 1st
                        confident = first turn where |predicted|==1 (sentinel
                        turn_count+1 if never reached); overcommitment =
                        turns spent after that before the episode ends.
                        These two can disagree a lot with the reference
                        version — see plot_narrowing_progress.py's finding
                        that doctors report narrowing much faster than the
                        KG reference set actually does.

                        Excludes episodes with |P_1|<=1 (predicted already
                        has 0-1 candidates on turn 1 — most such episodes
                        stay pinned at exactly 1 candidate for the whole
                        conversation, e.g. llama-3.3-70b does this on ~44%
                        of episodes vs. ~4-14% for other models). These are
                        a fixed single guess, not narrowing behavior, and
                        plot_narrowing_progress.py already excludes them for
                        the same reason — without this exclusion here too, a
                        model that does this a lot would look like it
                        "converges instantly" in THIS chart while looking
                        like it narrows slowly in narrowing_progress.py; not
                        a real contradiction, just two charts computed over
                        different episode populations. Each bar's y-tick
                        label reports what fraction was excluded.

Usage:
  python reporting/plot_overcommitment_by_judge.py [--source reference|predicted]
      [--csv PATH] [--style plain] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_overcommitment_by_judge.py --source predicted
"""
from __future__ import annotations

import argparse
import csv as csv_mod
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from utils.paths import ANALYSIS_ROOT, RUN_ROOT

COLOR_CONFIDENT = "#2F6FD6"
COLOR_OVERCOMMIT = "#9FC2F2"

# Fixed display order (top of each panel to bottom); models not listed here
# fall to the bottom, alphabetically among themselves.
MODEL_ORDER = [
    "gpt-5.4", "gpt-5.6-luna",
    "gemini-3.8-flash", "gemini-3.1-flash-lite",
    "claude-sonnet-5", "claude-haiku-4.5",
    "qwen3-235b",
    "llama-3.3-70b-instruct",
]
_ORDER_RANK = {name: i for i, name in enumerate(MODEL_ORDER)}

# Smaller/secondary variants dropped from these charts to keep the panels to
# one clear representative per provider family.
EXCLUDE_DOCTORS = {"gpt-5.6-luna", "gemini-3.1-flash-lite", "claude-haiku-4.5"}


def _order_rank(doctor: str) -> int:
    return _ORDER_RANK.get(doctor, len(MODEL_ORDER))


def _to_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_rows(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8") as f:
        return list(csv_mod.DictReader(f))


def panels_from_reference(csv_path: Path) -> list[tuple[str, list[tuple[str, float, float]]]]:
    rows = load_rows(csv_path)
    if not rows:
        print(f"No rows in {csv_path}")
        return []

    judges = sorted({r["judge"] for r in rows})
    panels = []
    for judge in judges:
        judge_rows = []
        for r in rows:
            if r["judge"] != judge or r["doctor"].lower() in EXCLUDE_DOCTORS:
                continue
            t1c = _to_float(r["turn_to_1st_confident"])
            oc = _to_float(r["overcommitment_conf"])
            if t1c is None or oc is None:
                print(f"[{judge}] {r['doctor']}: missing turn_to_1st_confident/overcommitment_conf, skipped")
                continue
            judge_rows.append((r["doctor"], t1c, oc))
        judge_rows.sort(key=lambda x: -_order_rank(x[0]))
        if judge_rows:
            panels.append((judge, judge_rows))
    return panels


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


def panels_from_predicted(
    style: str | None,
) -> tuple[list[tuple[str, list[tuple[str, float, float]]]], dict[tuple[str, str], float]]:
    """Excludes episodes with |P_1|<=1 (doctor never actually reports more
    than one candidate, most turns pinned at 1 — no narrowing behavior
    happens, it's a fixed single guess from the start) — same convention as
    plot_narrowing_progress.py's narrowing_progress_matrix(), so both charts
    are computed over the same population. Without this, a model that
    frequently starts (and stays) at |P_1|=1 looks like it "converges
    instantly" here while plot_narrowing_progress.py (which excludes exactly
    these episodes) shows it narrowing slowly on the episodes where it does
    maintain a differential — same model, two populations, not a real
    contradiction. pinned_rate[(judge, doctor)] reports how much of each
    bar's population that exclusion removed, so it can be annotated."""
    combos = discover_turn_eval_combos()
    if not combos:
        print(f"No turn_eval.json found under {ANALYSIS_ROOT}")
        return [], {}

    by_judge: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    pinned_rate: dict[tuple[str, str], float] = {}
    for patient, judge, doctor, path in combos:
        if doctor.lower() in EXCLUDE_DOCTORS:
            continue
        episodes = predicted_sizes_per_episode(path, style)
        if not episodes:
            print(f"[{judge}] {doctor}: no episodes, skipped")
            continue
        total = len(episodes)
        t1cs, ocs, pinned = [], [], 0
        for sizes in episodes:
            if not sizes:
                continue
            if sizes[0] <= 1:
                pinned += 1
                continue
            t1c, oc = predicted_t1c_overcommit(sizes)
            t1cs.append(t1c)
            ocs.append(oc)
        if not t1cs:
            continue
        by_judge[judge].append((doctor, float(np.mean(t1cs)), float(np.mean(ocs))))
        pinned_rate[(judge, doctor)] = pinned / total

    panels = []
    for judge in sorted(by_judge):
        judge_rows = sorted(by_judge[judge], key=lambda x: -_order_rank(x[0]))
        panels.append((judge, judge_rows))
    return panels, pinned_rate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", choices=["reference", "predicted"], default="reference",
        help="reference = judge/KG candidate_set (default, from the CSV); "
             "predicted = doctor's own stated differential (recomputed from turn_eval.json)",
    )
    parser.add_argument(
        "--csv", default=None,
        help="Input CSV from summarize_v4_metrics_csv.py, used only for --source reference "
             "(default: analysis/<run>/v4_metrics_summary_plain.csv)",
    )
    parser.add_argument(
        "--style", default="plain",
        help="--source predicted only: only include episodes whose log filename "
             "ends in _<style> (default: plain). Pass '' for all styles.",
    )
    parser.add_argument(
        "-o", "--out", default=None,
        help="Output PNG path (default: analysis/<run>/overcommitment_by_judge.png)",
    )
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "overcommitment_by_judge.png"

    pinned_rate: dict[tuple[str, str], float] = {}
    if args.source == "predicted":
        panels, pinned_rate = panels_from_predicted(args.style or None)
        confident_label = "Turn to 1st confident (predicted |P_t|=1)"
        overcommit_label = "Overcommitment (predicted-confidence-based)"
    else:
        csv_path = Path(args.csv) if args.csv else ANALYSIS_ROOT / "v4_metrics_summary_plain.csv"
        panels = panels_from_reference(csv_path)
        confident_label = "Turn to 1st confident"
        overcommit_label = "Overcommitment (confidence-based)"

    if not panels:
        print("No judge panel has complete turn_to_1st_confident/overcommitment data.")
        return

    fig, axes = plt.subplots(1, len(panels), figsize=(9.5 * len(panels), 0.6 * max(len(p[1]) for p in panels) + 2.2))
    if len(panels) == 1:
        axes = [axes]

    xmax = max(t1c + oc for _j, rows_ in panels for _d, t1c, oc in rows_) * 1.12

    for ax, (judge, judge_rows) in zip(axes, panels):
        doctors = [d for d, _t1c, _oc in judge_rows]
        t1cs = [t1c for _d, t1c, _oc in judge_rows]
        ocs = [oc for _d, _t1c, oc in judge_rows]
        ys = np.arange(len(doctors))

        ax.barh(ys, t1cs, color=COLOR_CONFIDENT, label=confident_label, zorder=3)
        ax.barh(ys, ocs, left=t1cs, color=COLOR_OVERCOMMIT, label=overcommit_label, zorder=3)

        for yi, (t1c, oc) in enumerate(zip(t1cs, ocs)):
            ax.text(t1c / 2, yi, f"{t1c:.1f}", ha="center", va="center", fontsize=10, color="white", fontweight="bold")
            ax.text(t1c + oc + xmax * 0.01, yi, f"{t1c + oc:.1f}", ha="left", va="center", fontsize=10, color="#1C2333")
            ax.text(t1c + oc / 2, yi + 0.32, f"+{oc:.1f}", ha="center", va="bottom", fontsize=8.5, color="#4B7FC2")

        ax.set_yticks(ys)
        if pinned_rate:
            ytick_labels = []
            for d in doctors:
                rate = pinned_rate.get((judge, d))
                note = f"  [excl. {rate*100:.0f}% pinned@1]" if rate is not None and rate > 0 else ""
                ytick_labels.append(f"{d}{note}")
            ax.set_yticklabels(ytick_labels, fontsize=9)
        else:
            ax.set_yticklabels(doctors, fontsize=10)
        ax.set_xlim(0, xmax)
        ax.set_xlabel("Turns", fontsize=9.5)
        ax.set_title(f"Judge: {judge}", fontsize=12.5, fontweight="bold", pad=10)
        ax.grid(axis="x", color="#E4EBF5", linewidth=0.8, zorder=0)
        ax.spines[["top", "right", "left"]].set_visible(False)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, fontsize=10.5,
               frameon=False, bbox_to_anchor=(0.5, 1.04))
    source_note = ("doctor's own predicted differential" if args.source == "predicted"
                    else "judge/KG reference candidate_set")
    fig.suptitle(
        "Turns to confidence vs. turns spent confirming it — by judge model\n"
        f"(\"confident\" = {source_note}; {RUN_ROOT.name})",
        fontsize=14.5, fontweight="bold", y=1.14,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
