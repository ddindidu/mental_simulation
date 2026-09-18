#!/usr/bin/env python3
"""
Narrowing Progress (%) vs. Relative Turn Progress (%) — by Judge Model
(doctor's self-reported / predicted candidate list, NOT the judge/KG
reference candidate_set)

  narrowing_progress(t) = 100 * (|P_t| - 1) / (|P_1| - 1)

|P_t| is the SIZE OF THE DOCTOR'S OWN STATED DIFFERENTIAL at turn t — the
`predicted` list eval/evaluate_turns.py already saves per turn in
analysis/<patient>/<judge>/<doctor>/turn_eval.json. This is what the doctor
model itself believes/reports as still-plausible diseases; it is NOT the
KG-deterministic reference candidate_set (high_likely|moderate_likely|
low_likely) that eval/symptom_diagnosis.py computes independently from
confirmed/denied symptoms — see plot_candidate_narrowing.py /
plot_narrowing_progress_reference.py for that version. The two can disagree:
a doctor can report a shrinking differential while the KG reference set is
still large (overconfidence), or vice versa (appropriate caution).

This metric reframes |P_t| as "% of the doctor's own narrowing task (from
its first-turn differential down to a single diagnosis) still left to do":

  - 100% at the first turn (nothing narrowed yet, by the doctor's own report)
  -   0% once the doctor's own stated list has collapsed to exactly 1
  -  50% once half the *distance* from |P_1| down to 1 has been covered

Each line is also labeled with the model's mean Information Acquisition
Score (IAS, from question_eval.json's llm_judge.mean_ias — see
evaluation_v4.md §2) for that judge, so narrowing behavior and question
quality can be read off the same legend.

Each episode is resampled onto a common 0-100% grid via linear interpolation
over its own (turn, |P_t|) trace before averaging, so every episode
contributes at every x position (no survivorship-bias tail from truncating
at raw turn numbers).

Usage:
  python reporting/plot_narrowing_progress.py [--style plain] [--doctors ...] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_narrowing_progress.py
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT, RUN_ROOT

DEFAULT_DOCTORS = [
    "gpt-5.4",
    "gemini-3.8-flash",
    "claude-sonnet-5",
    "llama-3.3-70b-instruct",
    "qwen3-235b",
]

PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
           "#56B4E9", "#999999", "#000000", "#F0E442"]

N_GRID = 11
GRID = np.linspace(0.0, 1.0, N_GRID)


def discover_combos() -> list[tuple[str, str, str, Path]]:
    combos = []
    for te_path in sorted(ANALYSIS_ROOT.rglob("turn_eval.json")):
        combo_dir = te_path.parent
        rel = combo_dir.relative_to(ANALYSIS_ROOT)
        if len(rel.parts) != 3:
            continue
        patient, judge, doctor = rel.parts
        combos.append((patient, judge, doctor, te_path))
    return combos


def load_predicted_sizes_per_episode(path: Path, style: str | None) -> list[list[float]]:
    """Group turn_eval.json's per-turn rows by log_file, sort by turn number,
    and return one list-of-|predicted| per episode."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    if style:
        data = [row for row in data if str(row.get("log_file", "")).endswith(f"_{style}")]

    by_episode: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in data:
        log_file = row.get("log_file")
        turn = row.get("turn")
        predicted = row.get("predicted") or []
        if log_file is None or turn is None:
            continue
        by_episode[log_file].append((turn, len(predicted)))

    episodes = []
    for log_file, turn_sizes in by_episode.items():
        turn_sizes.sort(key=lambda t: t[0])
        episodes.append([size for _t, size in turn_sizes])
    return episodes


def load_mean_ias(patient: str, judge: str, doctor: str, style: str | None) -> float | None:
    path = RESULTS_ROOT / patient / judge / doctor / "question_eval.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return None
    if style:
        data = [ep for ep in data if str(ep.get("log_file", "")).endswith(f"_{style}")]
    ias_vals = []
    for ep in data:
        v = (ep.get("episode_metrics") or {}).get("llm_judge", {}).get("mean_ias")
        if v is not None:
            ias_vals.append(v)
    return float(np.mean(ias_vals)) if ias_vals else None


def resample_episode(sizes: list[float]) -> np.ndarray | None:
    if not sizes:
        return None
    if len(sizes) == 1:
        return np.full(N_GRID, sizes[0], dtype=float)
    x = np.linspace(0.0, 1.0, len(sizes))
    return np.interp(GRID, x, sizes)


def narrowing_progress_matrix(episodes: list[list[float]]) -> tuple[np.ndarray, int] | None:
    """Rows = episodes, cols = GRID points; value = 100*(|P_t|-1)/(|P_1|-1),
    clipped at 0 — a doctor reporting an empty differential (|P_t|=0, seen
    on ~10-20% of final turns) would otherwise register as *negative*
    progress, but there's no narrower state than "fully narrowed" so 0% is
    the floor. Episodes that start already at a single prediction
    (|P_1|<=1) are dropped — there's no narrowing *task* left to measure
    progress on."""
    rows = []
    for sizes in episodes:
        resampled = resample_episode(sizes)
        if resampled is None:
            continue
        p1 = resampled[0]
        if p1 <= 1:
            continue
        rows.append(np.clip(100.0 * (resampled - 1.0) / (p1 - 1.0), 0.0, None))
    if not rows:
        return None
    return np.array(rows), len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default="plain",
                         help="Only include episodes whose log filename ends in "
                              "_<style> (default: plain). Pass '' for all styles.")
    parser.add_argument("--doctors", nargs="+", default=DEFAULT_DOCTORS,
                         help=f"Doctor models to include (default: {DEFAULT_DOCTORS})")
    parser.add_argument("-o", "--out", default=None,
                         help="Output PNG path (default: analysis/<run>/narrowing_progress_predicted_by_judge.png)")
    args = parser.parse_args()
    style = args.style or None
    wanted = {d.lower() for d in args.doctors}

    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "narrowing_progress_predicted_by_judge.png"

    combos = [c for c in discover_combos() if c[2].lower() in wanted]
    if not combos:
        print(f"No turn_eval.json found under {ANALYSIS_ROOT} for doctors {sorted(wanted)}")
        return

    canonical_doctors = sorted({doctor.lower() for _p, _j, doctor, _pa in combos})
    color_of = {d: PALETTE[i % len(PALETTE)] for i, d in enumerate(canonical_doctors)}

    judges = sorted({j for _p, j, _d, _pa in combos})
    panels: dict[str, list[tuple[str, np.ndarray, int, float | None]]] = {}
    for patient, judge, doctor, path in combos:
        episodes = load_predicted_sizes_per_episode(path, style)
        result = narrowing_progress_matrix(episodes)
        if result is None:
            print(f"[{judge}] {doctor}: no usable episodes, skipped")
            continue
        mat, n = result
        ias = load_mean_ias(patient, judge, doctor, style)
        panels.setdefault(judge, []).append((doctor, mat, n, ias))

    judges = [j for j in judges if j in panels]
    if not judges:
        print("No judge panel produced a curve.")
        return

    x_pct = GRID * 100
    fig, axes = plt.subplots(1, len(judges), figsize=(7.5 * len(judges), 6.5), sharey=True)
    if len(judges) == 1:
        axes = [axes]

    for ax, judge in zip(axes, judges):
        curves = sorted(panels[judge], key=lambda c: DEFAULT_DOCTORS.index(c[0]) if c[0] in DEFAULT_DOCTORS else 99)

        for doctor, mat, n, ias in curves:
            color = color_of[doctor.lower()]
            mean = mat.mean(axis=0)
            ax.plot(x_pct, mean, color=color, linewidth=2.2, marker="o", markersize=4,
                     label=f"{doctor} (n={n})", zorder=3)

        # Stagger end-of-line annotations vertically (by rank of final value)
        # so labels don't overlap when several models finish near the same
        # value — a real occurrence here since many cluster near 0%.
        by_final = sorted(curves, key=lambda c: c[1].mean(axis=0)[-1])
        mid = (len(by_final) - 1) / 2
        for rank, (doctor, mat, n, ias) in enumerate(by_final):
            color = color_of[doctor.lower()]
            mean = mat.mean(axis=0)
            ias_str = f"{ias:.3f}" if ias is not None else "n/a"
            y_off = (rank - mid) * 15
            ax.annotate(f"{mean[-1]:.0f}%  (IAS={ias_str})", (x_pct[-1], mean[-1]),
                        textcoords="offset points", xytext=(8, y_off), fontsize=8.5,
                        color=color, va="center", fontweight="bold",
                        arrowprops=dict(arrowstyle="-", color=color, lw=0.8, alpha=0.6))

        ax.axhline(0, color="#BBBBBB", linewidth=0.8, zorder=0)
        ax.set_title(f"Judge: {judge}", fontsize=12.5, fontweight="bold", pad=10)
        ax.set_xlabel("Relative turn progress (%)", fontsize=10.5)
        ax.set_xlim(0, 125)
        ax.set_ylim(-15, 108)
        ax.grid(color="#E4EBF5", linewidth=0.8, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        # Per-panel legend: n differs by judge, so a legend shared across
        # panels would show only one (wrong for the other). IAS is written
        # next to each line's endpoint instead of in the legend.
        ax.legend(loc="lower left", fontsize=8, frameon=False)

    axes[0].set_ylabel("Narrowing progress remaining (%)\n(doctor's own predicted list; 100%=start, 0%=|P_t|=1)", fontsize=10.5)

    style_note = f"style={style}" if style else "all styles"
    fig.suptitle(
        "Narrowing Progress vs. Relative Turn Progress — by judge model (doctor-reported)\n"
        f"(100*(|P_t|-1)/(|P_1|-1), P_t = doctor's own stated differential size; "
        f"each episode resampled onto its own 0-100% timeline; {style_note}; {RUN_ROOT.name})",
        fontsize=12.5, fontweight="bold", y=1.06,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
