#!/usr/bin/env python3
"""
Does bad early-turn reasoning quality predict a longer (less efficient)
remaining interview?

For each episode (plain style, 5 headline doctors), splits the dialogue into
an "early" window (turns 1-3) and the "remaining" turns (turn_count - 3), so
the predictor (early jaccard/precision/recall/QTS, rigid reference set) is
temporally prior to and non-overlapping with the outcome (remaining turn
count) — unlike a same-window correlation, this can't be explained by a long
transcript simply diluting its own average.

For each doctor separately, episodes are split into within-doctor quartiles
of the early metric (Q1 = that doctor's worst early quartile, Q4 = best), and
mean remaining-turn-count is computed per (doctor, quartile). Thin lines show
each doctor; the bold line is the cross-doctor average per quartile — this is
the doctor-controlled ("within-model") pattern reported alongside the pooled
Pearson r in reporting/analyze_precision_recall_tradeoff.py-style analyses.

Usage:
  MS_RUN=run_batch_20260912 python reporting/plot_early_turn_quality_vs_efficiency.py
"""
from __future__ import annotations

import json
import os
import sys as _sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as scipy_stats

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.metric_compat import turn_qts  # noqa: E402
from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT  # noqa: E402
from reporting.plot_v4_radar_by_judge import DOCTOR_NAME_CANONICAL  # noqa: E402

SELECTED_DOCTORS = ["gpt-5.4", "gemini-3.8-flash", "claude-sonnet-5",
                    "llama-3.3-70b-instruct", "qwen3-235b"]
STYLE = "plain"
EARLY_N = 3

PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00"]

METRICS = [
    ("early_jaccard", "Early Jaccard"),
    ("early_precision", "Early Precision"),
    ("early_recall", "Early Recall"),
    ("early_qts", "Early QTS"),
]


def _load(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def collect() -> list[dict]:
    rows = []
    for te_path in sorted(ANALYSIS_ROOT.rglob("turn_eval.json")):
        rel = te_path.parent.relative_to(ANALYSIS_ROOT)
        if len(rel.parts) != 3:
            continue
        patient, judge, doctor = rel.parts
        if doctor.lower() not in SELECTED_DOCTORS:
            continue

        by_ep: dict[str, dict[int, dict]] = defaultdict(dict)
        for row in _load(te_path):
            lf = row.get("log_file", "")
            if not lf.endswith(f"_{STYLE}"):
                continue
            t = row.get("turn")
            if t is None:
                continue
            by_ep[lf][t] = {
                "jac": row.get("jaccard_rigid"),
                "prec": row.get("precision_rigid"),
                "rec": row.get("recall_rigid"),
            }
        judge_name = judge

        eff_by_log = {e["log_file"]: e.get("final_accuracy")
                      for e in _load(RESULTS_ROOT / patient / judge / doctor / "efficiency_eval.json")
                      if e.get("log_file")}

        qts_by_log: dict[str, dict[int, float]] = {}
        for e in _load(RESULTS_ROOT / patient / judge / doctor / "question_eval.json"):
            lf = e.get("log_file")
            if lf is None:
                continue
            per_turn = {}
            for t in e.get("turns", []):
                turn = t.get("turn")
                v = turn_qts((t.get("scores_by_mapper") or {}).get("llm_judge", {}))
                if turn is not None and v is not None:
                    per_turn[turn] = v
            qts_by_log[lf] = per_turn

        for lf, turns in by_ep.items():
            T = max(turns.keys())
            if T <= EARLY_N:
                continue
            early_jac = [turns[t]["jac"] for t in range(1, EARLY_N + 1) if t in turns and turns[t]["jac"] is not None]
            early_prec = [turns[t]["prec"] for t in range(1, EARLY_N + 1) if t in turns and turns[t]["prec"] is not None]
            early_rec = [turns[t]["rec"] for t in range(1, EARLY_N + 1) if t in turns and turns[t]["rec"] is not None]
            qts_turns = qts_by_log.get(lf, {})
            early_qts = [qts_turns[t] for t in range(1, EARLY_N + 1) if t in qts_turns]
            acc = eff_by_log.get(lf)
            if not (early_jac and early_prec and early_rec and early_qts) or acc is None:
                continue
            rows.append({
                "doctor": doctor.lower(),
                "judge": judge_name,
                "early_jaccard": float(np.mean(early_jac)),
                "early_precision": float(np.mean(early_prec)),
                "early_recall": float(np.mean(early_rec)),
                "early_qts": float(np.mean(early_qts)),
                "remaining_turns": float(T - EARLY_N),
                "final_accuracy": float(acc),
            })
    return rows


def within_model_corr(rows: list[dict], metric: str) -> tuple[float, float, int]:
    doctors = sorted({r["doctor"] for r in rows})
    x = np.array([r[metric] for r in rows])
    y = np.array([r["remaining_turns"] for r in rows])
    di = np.array([doctors.index(r["doctor"]) for r in rows])
    xd, yd = x.copy(), y.copy()
    for d in range(len(doctors)):
        xd[di == d] -= x[di == d].mean()
        yd[di == d] -= y[di == d].mean()
    r, p = scipy_stats.pearsonr(xd, yd)
    return float(r), float(p), len(x)


def _quartile_means(rows: list[dict], doctors: list[str], metric: str,
                     bin_source: dict[str, np.ndarray]) -> dict[str, list[float]]:
    """Mean remaining_turns per within-doctor quartile of `metric`, using bin
    edges from `bin_source` (so correct/wrong share the same Q1-Q4 cutoffs
    per doctor) but computing the mean over only the rows passed in."""
    out = {d: [np.nan] * 4 for d in doctors}
    for d in doctors:
        d_rows = [r for r in rows if r["doctor"] == d]
        if not d_rows:
            continue
        vals = np.array([r[metric] for r in d_rows])
        remaining = np.array([r["remaining_turns"] for r in d_rows])
        qbins = bin_source[d]
        q_idx = np.digitize(vals, qbins[1:-1], right=True)
        # precision/recall pile up at the 1.0 ceiling, which can make q75
        # equal the max (1.0) and strand every tied score=1 row in Q3 with
        # Q4 left empty — a perfect score belongs in the best quartile
        # regardless of where the quantile edge landed, so force it there.
        q_idx[vals >= 1.0 - 1e-9] = 3
        for q in range(4):
            sel = q_idx == q
            if sel.sum() > 0:
                out[d][q] = float(remaining[sel].mean())
    return out


def _plot_skip_nan(ax, x: np.ndarray, y: list[float], **kwargs) -> None:
    """Plot x/y connecting only the non-NaN points directly (no interpolated
    value drawn for a missing quartile — the segment just skips over it)."""
    y = np.asarray(y, dtype=float)
    mask = ~np.isnan(y)
    ax.plot(x[mask], y[mask], **kwargs)


def draw(all_rows: list[dict], correct_rows: list[dict], wrong_rows: list[dict],
         out_path: Path, metrics: list[tuple[str, str]] = METRICS) -> None:
    doctors = sorted({r["doctor"] for r in all_rows})
    x = np.arange(1, 5)

    fig, axes = plt.subplots(len(metrics), 2, figsize=(8, 3.75 * len(metrics)))
    if len(metrics) == 1:
        axes = axes.reshape(1, 2)

    for row_i, (metric, label) in enumerate(metrics):
        bin_source = {}
        for d in doctors:
            vals = np.array([r[metric] for r in all_rows if r["doctor"] == d])
            qbins = np.quantile(vals, [0.0, 0.25, 0.5, 0.75, 1.0])
            qbins[0] -= 1e-9
            bin_source[d] = qbins

        qm_correct = _quartile_means(correct_rows, doctors, metric, bin_source)
        qm_wrong = _quartile_means(wrong_rows, doctors, metric, bin_source)
        avg_correct = np.nanmean(np.array([qm_correct[d] for d in doctors]), axis=0)
        avg_wrong = np.nanmean(np.array([qm_wrong[d] for d in doctors]), axis=0)

        all_y = [v for d in doctors for v in qm_correct[d] + qm_wrong[d] if not np.isnan(v)]
        y_lo, y_hi = min(all_y), max(all_y)
        pad = (y_hi - y_lo) * 0.08 or 1.0
        ylim = (y_lo - pad, y_hi + pad)

        for col_i, (qm, avg) in enumerate([(qm_correct, avg_correct), (qm_wrong, avg_wrong)]):
            ax = axes[row_i, col_i]
            for i, d in enumerate(doctors):
                _plot_skip_nan(ax, x, qm[d], color=PALETTE[i % len(PALETTE)], linewidth=1.3,
                               alpha=0.55, marker="o", markersize=5,
                               label=DOCTOR_NAME_CANONICAL.get(d, d))
            _plot_skip_nan(ax, x, avg, color="#1C2333", linewidth=3.2,
                           marker="o", markersize=8, zorder=5, label="Average (across doctors)")

            ax.set_xticks(x)
            ax.set_xticklabels(["Q1", "Q2", "Q3", "Q4"], fontsize=12)
            ax.set_ylim(ylim)
            ax.invert_yaxis()
            ax.tick_params(axis="y", labelsize=12)
            ax.grid(color="#E4EBF5", linewidth=0.8, zorder=0)
            ax.spines[["top", "right"]].set_visible(False)
            if col_i == 0:
                ax.set_ylabel("Efficiency (Total Turn Count)", fontsize=12)
            ax.set_xlabel(label, fontsize=14)

    fig.text(0.29, 1.0, "Correct cases", ha="center", fontsize=14, fontweight="bold")
    fig.text(0.78, 1.0, "Wrong cases", ha="center", fontsize=14, fontweight="bold")

    handles, labels = axes[0, 0].get_legend_handles_labels()
    # bbox_to_anchor is in figure-fraction units, so a fixed offset shrinks in
    # absolute terms as the figure gets shorter (fewer metric rows) — scale it
    # by the reference (4-row) figure's proportions to keep the same gap.
    legend_y = -0.035 * (4 / len(metrics))
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=12, frameon=False,
               bbox_to_anchor=(0.5, legend_y))
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out_path}")


JUDGES = ["gpt-5.6-terra", "gemini-3.1-pro-preview"]


def main() -> None:
    rows = collect()
    print(f"n episodes (T>{EARLY_N}): {len(rows)}")

    for judge in JUDGES:
        judge_rows = [r for r in rows if r["judge"] == judge]
        correct_rows = [r for r in judge_rows if r["final_accuracy"] == 1.0]
        wrong_rows = [r for r in judge_rows if r["final_accuracy"] != 1.0]
        print(f"  [{judge}] correct: {len(correct_rows)}   wrong: {len(wrong_rows)}")

        draw(judge_rows, correct_rows, wrong_rows,
             ANALYSIS_ROOT / f"early_turn_quality_vs_efficiency_{judge}.png")
        draw(judge_rows, correct_rows, wrong_rows,
             ANALYSIS_ROOT / f"early_turn_quality_vs_efficiency_jaccard_recall_{judge}.png",
             metrics=[METRICS[0], METRICS[2]])


if __name__ == "__main__":
    main()
