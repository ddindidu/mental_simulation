#!/usr/bin/env python3
"""
Doctor-/setting-controlled regression version of
plot_early_turn_quality_vs_efficiency.py's quartile plots.

Same data (episode-level, T > EARLY_N, early-window metric from turns 1-3
vs. remaining_turns = turn_count - EARLY_N), but instead of a doctor-collapsed
quartile trend, fits:

jaccard/precision/recall here are already episode-mean metrics: each is the
mean of that one episode's own turns 1-3 (jaccard_rigid / precision_rigid /
recall_rigid), not a cross-episode pooled value — the turn-weighted-pooled
vs. episode-mean distinction from evaluation_v5.md's combo-level aggregation
doesn't apply within a single episode.

  (1) per-correctness regression, doctor + setting fixed effects:
        remaining_turns_i = b0 + b1 * X_i + Doctor_FE + Judge_FE + e_i
      run separately on the correct (final_accuracy=1) and wrong subsets.

  (2) pooled regression with a Correct x X interaction, doctor + setting FE:
        remaining_turns_i = b0 + b1*X_i + b2*Correct_i + b3*(X_i*Correct_i)
                            + Doctor_FE + Judge_FE + e_i
      b1 = slope of X on remaining_turns among wrong cases (Correct=0 baseline)
      b1+b3 = slope among correct cases
      b3's p-value tests whether the two slopes actually differ.

Standard errors are clustered by doctor (5 clusters) to account for
within-doctor correlation across episodes.

Usage:
  MS_RUN=run_batch_20260912 python reporting/analyze_early_quality_regression.py
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from reporting.cross_model.plot_early_turn_quality_vs_efficiency import collect  # noqa: E402

METRICS = ["early_jaccard", "early_precision", "early_recall", "early_qts"]


def main() -> None:
    rows = collect()
    df = pd.DataFrame(rows)
    df["correct"] = (df["final_accuracy"] == 1.0).astype(int)
    df["doctor"] = df["doctor"].astype("category")
    df["judge"] = df["judge"].astype("category")
    print(f"n episodes: {len(df)}  (correct={df['correct'].sum()}, wrong={(1 - df['correct']).sum()})\n")

    print("=== (1) Per-correctness: remaining_turns ~ X + Doctor FE + Judge FE ===")
    print("(SE clustered by doctor; n=5 clusters, so treat p-values as indicative, not exact)\n")
    header = f"{'metric':<18}{'subset':<10}{'coef':>10}{'se':>10}{'p':>12}{'n':>7}{'R2':>8}"
    print(header)
    print("-" * len(header))
    for metric in METRICS:
        for subset_name, subset_val in [("correct", 1), ("wrong", 0)]:
            d = df[df["correct"] == subset_val]
            model = smf.ols(f"remaining_turns ~ {metric} + C(doctor) + C(judge)", data=d)
            fit = model.fit(cov_type="cluster", cov_kwds={"groups": d["doctor"]})
            b, se, p = fit.params[metric], fit.bse[metric], fit.pvalues[metric]
            print(f"{metric:<18}{subset_name:<10}{b:>10.3f}{se:>10.3f}{p:>12.2g}{len(d):>7}{fit.rsquared:>8.3f}")
        print()

    print("=== (2) Pooled with Correct x X interaction, Doctor FE + Judge FE ===\n")
    header2 = f"{'metric':<18}{'term':<22}{'coef':>10}{'se':>10}{'p':>12}"
    print(header2)
    print("-" * len(header2))
    for metric in METRICS:
        formula = f"remaining_turns ~ {metric} * correct + C(doctor) + C(judge)"
        model = smf.ols(formula, data=df)
        fit = model.fit(cov_type="cluster", cov_kwds={"groups": df["doctor"]})
        for term in [metric, "correct", f"{metric}:correct"]:
            b, se, p = fit.params[term], fit.bse[term], fit.pvalues[term]
            print(f"{metric:<18}{term:<22}{b:>10.3f}{se:>10.3f}{p:>12.2g}")
        print(f"  (n={len(df)}, R2={fit.rsquared:.3f})\n")


if __name__ == "__main__":
    main()
