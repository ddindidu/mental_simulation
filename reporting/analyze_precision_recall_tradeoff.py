#!/usr/bin/env python3
"""
Does "high precision, low recall" come with a cost?

For each episode (plain style, 5 headline doctors, both judge/patient
buckets), computes:
  precision, recall       = mean-over-turns of precision_rigid / recall_rigid
                             (turn_eval.json — same definition as
                             plot_v4_precision_vs_recall.py)
  gap                      = precision - recall (positive = "high precision,
                             low recall" relative to that episode's own pair)
  turn_count, final_accuracy  from efficiency_eval.json

Then:
  1. Pearson/Spearman of gap vs. turn_count, and gap vs. final_accuracy
     (point-biserial, since final_accuracy is 0/1).
  2. Tercile split on gap: compare mean turn_count and accuracy rate between
     the top tercile (precision >> recall) and bottom tercile (recall >= precision).
  3. Scatter of recall vs. precision, colored by turn_count, with the
     diagonal marked, to visualize where the high-precision/low-recall
     episodes sit and what their turn counts look like.

Usage:
  MS_RUN=run_batch_20260912 python reporting/analyze_precision_recall_tradeoff.py
"""
from __future__ import annotations

import json
import os
import sys as _sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as scipy_stats

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT  # noqa: E402
from reporting.plot_v4_radar_by_judge import DOCTOR_NAME_CANONICAL  # noqa: E402

STYLE = "plain"
SELECTED_DOCTORS = {
    "gpt-5.4", "gemini-3.8-flash", "claude-sonnet-5",
    "llama-3.3-70b-instruct", "qwen3-235b",
}


def _load(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def collect_episodes() -> list[dict]:
    rows = []
    for te_path in sorted(ANALYSIS_ROOT.rglob("turn_eval.json")):
        combo = te_path.parent
        rel = combo.relative_to(ANALYSIS_ROOT)
        if len(rel.parts) != 3:
            continue
        patient, judge, doctor = rel.parts
        if doctor.lower() not in SELECTED_DOCTORS:
            continue

        per_ep: dict[str, dict[str, list[float]]] = {}
        for row in _load(te_path):
            lf = row.get("log_file", "")
            if not lf.endswith(f"_{STYLE}"):
                continue
            p, r = row.get("precision_rigid"), row.get("recall_rigid")
            d = per_ep.setdefault(lf, {"p": [], "r": []})
            if p is not None:
                d["p"].append(float(p))
            if r is not None:
                d["r"].append(float(r))

        eff_path = RESULTS_ROOT / patient / judge / doctor / "efficiency_eval.json"
        eff_by_log = {e["log_file"]: e for e in _load(eff_path) if e.get("log_file")}

        for lf, d in per_ep.items():
            if not d["p"] or not d["r"]:
                continue
            eff = eff_by_log.get(lf)
            if eff is None:
                continue
            tc = eff.get("turn_count")
            acc = eff.get("final_accuracy")
            if tc is None or acc is None:
                continue
            precision, recall = float(np.mean(d["p"])), float(np.mean(d["r"]))
            rows.append({
                "judge": judge, "doctor": doctor, "log_file": lf,
                "precision": precision, "recall": recall,
                "gap": precision - recall,
                "turn_count": float(tc), "final_accuracy": float(acc),
            })
    return rows


def main() -> None:
    rows = collect_episodes()
    print(f"Episodes: {len(rows)} across doctors {sorted({r['doctor'] for r in rows})}, "
          f"judges {sorted({r['judge'] for r in rows})}\n")

    gap = np.array([r["gap"] for r in rows])
    tc = np.array([r["turn_count"] for r in rows])
    acc = np.array([r["final_accuracy"] for r in rows])

    r1, p1 = scipy_stats.pearsonr(gap, tc)
    rho1, prho1 = scipy_stats.spearmanr(gap, tc)
    print(f"gap (precision - recall) vs. turn_count:   Pearson r={r1:.3f} (p={p1:.4f})  "
          f"Spearman rho={rho1:.3f} (p={prho1:.4f})  n={len(rows)}")

    r2, p2 = scipy_stats.pointbiserialr(acc, gap)
    print(f"gap (precision - recall) vs. final_accuracy (point-biserial): r={r2:.3f} (p={p2:.4f})  n={len(rows)}")

    # tercile split on gap
    q1, q2 = np.percentile(gap, [100 / 3, 200 / 3])
    low = [r for r in rows if r["gap"] <= q1]       # recall >= precision (or small gap)
    high = [r for r in rows if r["gap"] >= q2]       # precision >> recall
    print(f"\nTercile split on gap (n={len(low)} low-gap vs n={len(high)} high-gap, "
          f"cutoffs q1={q1:.3f} q2={q2:.3f}):")

    def _summ(group, label):
        tcs = [g["turn_count"] for g in group]
        accs = [g["final_accuracy"] for g in group]
        print(f"  {label:30s} mean turn_count={np.mean(tcs):.2f} (sd={np.std(tcs):.2f})   "
              f"accuracy={np.mean(accs):.3f}  (n={len(group)})")
        return tcs, accs

    low_tc, low_acc = _summ(low, "low-gap (recall>=precision)")
    high_tc, high_acc = _summ(high, "high-gap (precision>>recall)")

    t_tc, p_tc = scipy_stats.ttest_ind(high_tc, low_tc, equal_var=False)
    print(f"  turn_count: Welch t={t_tc:.3f}, p={p_tc:.4f} (high-gap vs. low-gap)")

    tab = np.array([
        [sum(high_acc), len(high_acc) - sum(high_acc)],
        [sum(low_acc), len(low_acc) - sum(low_acc)],
    ])
    chi2, p_acc, _, _ = scipy_stats.chi2_contingency(tab)
    print(f"  final_accuracy: chi2={chi2:.3f}, p={p_acc:.4f} (high-gap vs. low-gap, 2x2)")

    # per-doctor breakdown, for context
    print("\nPer-doctor mean gap / turn_count / accuracy:")
    for doctor in sorted({r["doctor"] for r in rows}):
        d_rows = [r for r in rows if r["doctor"] == doctor]
        g = np.mean([r["gap"] for r in d_rows])
        t = np.mean([r["turn_count"] for r in d_rows])
        a = np.mean([r["final_accuracy"] for r in d_rows])
        print(f"  {DOCTOR_NAME_CANONICAL.get(doctor, doctor):<20} gap={g:+.3f}  turn_count={t:.2f}  accuracy={a:.3f}  (n={len(d_rows)})")

    # scatter
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    precision = np.array([r["precision"] for r in rows])
    recall = np.array([r["recall"] for r in rows])
    sca = ax.scatter(recall, precision, c=tc, cmap="viridis_r", s=36, alpha=0.75,
                      edgecolors="white", linewidths=0.4, zorder=3)
    ax.plot([0, 1], [0, 1], color="#999999", linewidth=1.2, linestyle=":", zorder=1)
    ax.set_xlabel("Recall (rigid, mean over turns)", fontsize=13)
    ax.set_ylabel("Precision (rigid, mean over turns)", fontsize=13)
    ax.grid(color="#E4EBF5", linewidth=0.8, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    cbar = fig.colorbar(sca, ax=ax)
    cbar.set_label("Turn count", fontsize=12)
    ax.set_title("Precision vs. recall per episode, colored by turn count", fontsize=12)
    fig.tight_layout()
    out = ANALYSIS_ROOT / "precision_recall_tradeoff_scatter.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n[saved] {out}")


if __name__ == "__main__":
    main()
