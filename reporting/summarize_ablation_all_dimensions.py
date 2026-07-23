#!/usr/bin/env python3
"""
Outcome-Stratification Ablation — All 4 Evaluation Dimensions  (spec §4.4.7)

Splits episodes into:
  correct   — ground_truth ∈ all_candidates() at the final turn (_result.json)
  incorrect — ground_truth ∉ all_candidates()

For each dimension, applies macro-mean aggregation per stratum.

Data sources:
  Inference Quality   : analysis/<j>/<j>/<m>/turn_eval.json            (per-turn rows)
  Question Quality    : results/<j>/<j>/<m>/question_eval.json          (per-episode, per-mapper)
  Efficiency          : results/<j>/<j>/<m>/efficiency_eval.json        (per-episode)
  Diagnostic Reasoning: results/<j>/<j>/<m>/diagnostic_reasoning_eval.json (per-episode)

Outputs:
  analysis/<j>/<j>/comparison/outcome_stratified/
    ablation_inference_quality.{json,csv}
    ablation_question_quality.{json,csv}   (cosine mapper)
    ablation_efficiency.{json,csv}
    ablation_diagnostic_reasoning.{json,csv}
    ablation_all_summary.json              (unified cross-dimension view)
    ablation_all_dimensions.png            (4-panel bar chart)
    ablation_delta_heatmap.png             (model × metric Δ heatmap)
"""
from __future__ import annotations

import csv
import json
import os
import re
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

warnings.filterwarnings("ignore")

BASE_DIR  = Path(__file__).resolve().parent.parent
JUDGE     = "gemini-3.5-flash"
RB        = BASE_DIR / "results"  / JUDGE / JUDGE   # results base
AB        = BASE_DIR / "analysis" / JUDGE / JUDGE   # analysis base
OUT_DIR   = AB / "comparison" / "outcome_stratified"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gpt-5.4",
    "gpt-5.4-mini-2026-03-17",
    "llama-3.3-70b-instruct",
    "qwen3-235b-a22b-2507",
]
MODEL_LABELS = {
    "gemini-3.1-flash-lite":      "Gemini 3.1 Lite",
    "gemini-3.5-flash":           "Gemini 3.5 Flash",
    "gpt-5.4":                    "GPT-5.4",
    "gpt-5.4-mini-2026-03-17":    "GPT-5.4 Mini",
    "llama-3.3-70b-instruct":     "Llama 3.3 70B",
    "qwen3-235b-a22b-2507":       "Qwen3 235B",
}
MODEL_COLORS = ["#4580C4", "#F07C35", "#C94040", "#3AA89C", "#5BA04E", "#9B6ABE"]

STRATA = ("correct", "incorrect", "all")


# ─── Outcome determination ────────────────────────────────────────────────────

def load_outcomes(model: str) -> dict[str, bool]:
    """
    Returns {log_file_stem: is_correct} from _result.json files.
    correct = ground_truth ∈ all_candidates() at final turn.
    """
    res_dir = RB / model
    outcomes: dict[str, bool] = {}
    for p in res_dir.glob("*_result.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            log_name = d.get("log_file", p.stem.replace("_result", ""))
            gt_m = re.match(r"(D\d+)", log_name)
            gt = gt_m.group(1) if gt_m else d.get("ground_truth", "")
            turns = d.get("turns", [])
            if not turns or not gt:
                continue
            last = max(turns, key=lambda t: t.get("turn", 0))
            cs = last.get("candidate_set", {})
            all_cands = (cs.get("high_likely", [])
                         + cs.get("moderate_likely", [])
                         + cs.get("low_likely", []))
            outcomes[log_name] = gt in all_cands
        except Exception:
            continue
    return outcomes


def _mean(vals: list) -> float | None:
    clean = [v for v in vals if v is not None]
    return float(np.mean(clean)) if clean else None


def _std(vals: list) -> float | None:
    clean = [v for v in vals if v is not None]
    return float(np.std(clean)) if len(clean) > 1 else None


# ─── Dimension 1: Inference Quality ──────────────────────────────────────────

INF_METRICS = ["accuracy", "precision", "recall", "jaccard", "weighted_recall"]


def _load_inference_episodes(model: str) -> list[dict]:
    """
    From turn_eval.json: group by log_file, compute macro-mean over turns per episode.
    Returns list of {log_file, ground_truth, <metric>: mean_over_turns, ...}
    """
    path = AB / model / "turn_eval.json"
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    by_ep: dict[str, list] = defaultdict(list)
    for r in rows:
        by_ep[r["log_file"]].append(r)
    episodes = []
    for lf, turn_rows in by_ep.items():
        gt = turn_rows[0].get("ground_truth", "")
        ep: dict[str, Any] = {"log_file": lf, "ground_truth": gt}
        for m in INF_METRICS:
            vals = [r.get(m) for r in turn_rows if r.get(m) is not None]
            ep[m] = float(np.mean(vals)) if vals else None
        episodes.append(ep)
    return episodes


def ablate_inference(outcomes: dict[str, bool], episodes: list[dict]) -> dict:
    strata_eps: dict[str, list] = {"correct": [], "incorrect": [], "all": []}
    for ep in episodes:
        out = outcomes.get(ep["log_file"])
        if out is None:
            continue
        key = "correct" if out else "incorrect"
        strata_eps[key].append(ep)
        strata_eps["all"].append(ep)

    result: dict[str, Any] = {}
    for s, eps in strata_eps.items():
        agg: dict[str, Any] = {"n": len(eps)}
        for m in INF_METRICS:
            vals = [ep[m] for ep in eps if ep.get(m) is not None]
            agg[m] = {"mean": _mean(vals), "std": _std(vals)}
        result[s] = agg
    return result


# ─── Dimension 2: Question Quality ───────────────────────────────────────────

Q_METRICS = [
    "conditional_mean_composite", "conditional_mean_ig",
    "ig_positive_rate", "discriminating_q_rate",
    "mean_composite", "mean_dcs", "redundancy_rate",
    "early_ig_mean", "active_turn_count",
]
Q_MAPPERS = ("cosine", "llm_judge")


def _load_question_episodes(model: str) -> list[dict]:
    path = RB / model / "question_eval.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def ablate_question(outcomes: dict[str, bool], episodes: list[dict]) -> dict:
    strata_eps: dict[str, list] = {"correct": [], "incorrect": [], "all": []}
    for ep in episodes:
        out = outcomes.get(ep.get("log_file", ""))
        if out is None:
            continue
        key = "correct" if out else "incorrect"
        strata_eps[key].append(ep)
        strata_eps["all"].append(ep)

    result: dict[str, Any] = {}
    for s, eps in strata_eps.items():
        agg: dict[str, Any] = {"n": len(eps), "by_mapper": {}}
        for mapper in Q_MAPPERS:
            magg: dict[str, Any] = {}
            for metric in Q_METRICS:
                vals = [
                    ep.get("episode_metrics", {}).get(mapper, {}).get(metric)
                    for ep in eps
                ]
                vals = [v for v in vals if v is not None]
                magg[metric] = {"mean": _mean(vals), "std": _std(vals)}
            agg["by_mapper"][mapper] = magg
        result[s] = agg
    return result


# ─── Dimension 3: Efficiency ──────────────────────────────────────────────────

EFF_METRICS = [
    "final_accuracy", "turn_count", "cssr",
    "time_to_first_correct_narrowing",
    "monotonicity_violations", "redundant_turn_ratio", "overcommitment_turns",
]
# lower-is-better metrics (for sign annotation in Δ)
EFF_LOWER_BETTER = {
    "turn_count", "time_to_first_correct_narrowing",
    "monotonicity_violations", "redundant_turn_ratio", "overcommitment_turns",
}


def _load_efficiency_episodes(model: str) -> list[dict]:
    path = RB / model / "efficiency_eval.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def ablate_efficiency(outcomes: dict[str, bool], episodes: list[dict]) -> dict:
    strata_eps: dict[str, list] = {"correct": [], "incorrect": [], "all": []}
    for ep in episodes:
        out = outcomes.get(ep.get("log_file", ""))
        if out is None:
            continue
        key = "correct" if out else "incorrect"
        strata_eps[key].append(ep)
        strata_eps["all"].append(ep)

    result: dict[str, Any] = {}
    for s, eps in strata_eps.items():
        agg: dict[str, Any] = {"n": len(eps)}
        for m in EFF_METRICS:
            vals = [ep.get(m) for ep in eps if ep.get(m) is not None]
            agg[m] = {"mean": _mean(vals), "std": _std(vals)}
        result[s] = agg
    return result


# ─── Dimension 4: Diagnostic Reasoning ───────────────────────────────────────

DR_METRICS = [
    "overall_score", "symptom_satisfaction_score", "duration_score",
    "functional_impairment_score", "traumatic_stressor_score",
    "psychosocial_stressor_score", "additional_requirements_score",
]


def _load_dr_episodes(model: str) -> list[dict]:
    path = RB / model / "diagnostic_reasoning_eval.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def ablate_dr(outcomes: dict[str, bool], episodes: list[dict]) -> dict:
    strata_eps: dict[str, list] = {"correct": [], "incorrect": [], "all": []}
    for ep in episodes:
        out = outcomes.get(ep.get("log_file", ""))
        if out is None:
            continue
        key = "correct" if out else "incorrect"
        strata_eps[key].append(ep)
        strata_eps["all"].append(ep)

    result: dict[str, Any] = {}
    for s, eps in strata_eps.items():
        agg: dict[str, Any] = {"n": len(eps)}
        for m in DR_METRICS:
            vals = [ep.get(m) for ep in eps if ep.get(m) is not None]
            agg[m] = {"mean": _mean(vals), "std": _std(vals)}
        result[s] = agg
    return result


# ─── Save helpers ─────────────────────────────────────────────────────────────

def _save_json(data: Any, path: Path) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[saved] {path}")


def _save_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[saved] {path}")


def _flatten_agg(model: str, dim: str, agg_by_stratum: dict, metrics: list[str],
                 mapper: str | None = None) -> list[dict]:
    rows = []
    for s in STRATA:
        s_agg = agg_by_stratum.get(s, {})
        if mapper:
            metric_agg = s_agg.get("by_mapper", {}).get(mapper, {})
        else:
            metric_agg = s_agg
        row: dict[str, Any] = {
            "model": model, "dimension": dim, "stratum": s,
            "n": s_agg.get("n", 0),
        }
        if mapper:
            row["mapper"] = mapper
        for m in metrics:
            v = (metric_agg.get(m) or {}).get("mean")
            row[m] = round(v, 6) if v is not None else None
        rows.append(row)
    return rows


# ─── Visualisation ────────────────────────────────────────────────────────────

def _plot_all(all_results: dict[str, dict]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("[skip] matplotlib not available")
        return

    n_models = len(MODELS)
    short_labels = [MODEL_LABELS[m].replace(" ", "\n") for m in MODELS]
    colors = MODEL_COLORS
    ok_color   = "#0EA472"
    fail_color = "#E04545"
    alpha_ok   = 0.85
    alpha_fail = 0.45

    # ── Figure 1: 4-panel bar chart (one per dimension) ──────────────────────
    DIM_CONFIGS = [
        ("inference",  "Inference Quality",  ["accuracy", "recall", "precision", "jaccard"],
         ["Accuracy\n(exact match)", "Recall\n(truth coverage)", "Precision", "Jaccard"]),
        ("question",   "Question Quality\n(cosine mapper)",
         ["conditional_mean_composite", "discriminating_q_rate", "ig_positive_rate", "conditional_mean_ig"],
         ["Cond. Mean\nComposite", "Discriminating-Q\nRate", "IG-Positive\nRate", "Cond. Mean IG"]),
        ("efficiency", "Efficiency",
         ["cssr", "redundant_turn_ratio", "monotonicity_violations", "turn_count"],
         ["CSSR\n(↑ better)", "Redundant Turn\nRatio (↓ better)", "Monotonicity\nViolations (↓)", "Turn Count\n(↓ better)"]),
        ("dr",         "Diagnostic Reasoning",
         ["overall_score", "duration_score", "functional_impairment_score", "additional_requirements_score"],
         ["Overall Score", "Duration\nScore", "Functional\nImpairment", "Additional\nRequirements"]),
    ]

    fig, axes = plt.subplots(4, 4, figsize=(20, 18))
    fig.patch.set_facecolor("#F1F4F9")

    for row_i, (dim_key, dim_label, metrics, metric_labels) in enumerate(DIM_CONFIGS):
        for col_i, (metric, m_label) in enumerate(zip(metrics, metric_labels)):
            ax = axes[row_i][col_i]
            ax.set_facecolor("#FFFFFF")

            xs      = np.arange(n_models)
            bar_w   = 0.32
            vals_ok = []
            vals_fail = []

            for model in MODELS:
                mdata = all_results.get(model, {}).get(dim_key, {})
                if dim_key == "question":
                    ok_v   = (mdata.get("correct",   {}).get("by_mapper", {})
                              .get("cosine", {}).get(metric, {}) or {}).get("mean")
                    fail_v = (mdata.get("incorrect", {}).get("by_mapper", {})
                              .get("cosine", {}).get(metric, {}) or {}).get("mean")
                else:
                    ok_v   = (mdata.get("correct",   {}).get(metric) or {}).get("mean")
                    fail_v = (mdata.get("incorrect", {}).get(metric) or {}).get("mean")
                vals_ok.append(ok_v if ok_v is not None else 0)
                vals_fail.append(fail_v if fail_v is not None else 0)

            bars_ok   = ax.bar(xs - bar_w/2, vals_ok,   bar_w, color=ok_color,   alpha=alpha_ok,   label="correct",   zorder=3)
            bars_fail = ax.bar(xs + bar_w/2, vals_fail, bar_w, color=fail_color, alpha=alpha_fail, label="incorrect", zorder=3)

            # Model-color top border
            for xi, col in zip(xs, colors):
                ax.bar(xi, ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 1,
                       bar_w * 2.1, bottom=0, color=col, alpha=0.06, zorder=1)

            ax.set_xticks(xs)
            ax.set_xticklabels(short_labels, fontsize=6.5, ha="center")
            ax.tick_params(axis="y", labelsize=7)
            ax.set_title(m_label, fontsize=8, fontweight="bold", pad=4)
            ax.grid(axis="y", color="#E4EBF5", linewidth=0.8, zorder=0)
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.spines["bottom"].set_color("#DDE3EF")

            if col_i == 0:
                ax.set_ylabel(dim_label, fontsize=8, color="#6B7A99", fontweight="bold")

    # Legend
    patch_ok   = mpatches.Patch(color=ok_color,   alpha=alpha_ok,   label="Correct episodes")
    patch_fail = mpatches.Patch(color=fail_color, alpha=alpha_fail, label="Incorrect episodes")
    fig.legend(handles=[patch_ok, patch_fail], loc="upper right", fontsize=9,
               framealpha=0.9, edgecolor="#DDE3EF", bbox_to_anchor=(0.99, 0.99))

    fig.suptitle("Outcome-Stratification Ablation — All Evaluation Dimensions",
                 fontsize=13, fontweight="bold", y=1.003, color="#1C2333")
    plt.tight_layout(rect=[0, 0, 1, 1])
    out1 = OUT_DIR / "ablation_all_dimensions.png"
    fig.savefig(out1, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[saved] {out1}")

    # ── Figure 2: Δ heatmap (model × metric) ────────────────────────────────
    HEATMAP_METRICS = [
        ("inference", "accuracy",                      "Inf: Accuracy",       False),
        ("inference", "recall",                        "Inf: Recall",         False),
        ("inference", "precision",                     "Inf: Precision",      False),
        ("question",  "conditional_mean_composite",    "Q: Cond Composite",   False),
        ("question",  "discriminating_q_rate",         "Q: Disc-Q Rate",      False),
        ("question",  "ig_positive_rate",              "Q: IG-Pos Rate",      False),
        ("efficiency","cssr",                          "Eff: CSSR",           False),
        ("efficiency","redundant_turn_ratio",          "Eff: Redund Ratio",   True),
        ("efficiency","turn_count",                    "Eff: Turn Count",     True),
        ("dr",        "overall_score",                 "DR: Overall",         False),
        ("dr",        "duration_score",                "DR: Duration",        False),
        ("dr",        "functional_impairment_score",   "DR: Func.Impairment", False),
    ]

    delta_matrix = np.full((n_models, len(HEATMAP_METRICS)), np.nan)
    for mi, model in enumerate(MODELS):
        mdata = all_results.get(model, {})
        for ci, (dim, metric, _, lower_better) in enumerate(HEATMAP_METRICS):
            if dim == "question":
                ok_v   = (mdata.get(dim, {}).get("correct",   {}).get("by_mapper", {})
                          .get("cosine", {}).get(metric, {}) or {}).get("mean")
                fail_v = (mdata.get(dim, {}).get("incorrect", {}).get("by_mapper", {})
                          .get("cosine", {}).get(metric, {}) or {}).get("mean")
            else:
                ok_v   = (mdata.get(dim, {}).get("correct",   {}).get(metric) or {}).get("mean")
                fail_v = (mdata.get(dim, {}).get("incorrect", {}).get(metric) or {}).get("mean")
            if ok_v is not None and fail_v is not None:
                raw_delta = ok_v - fail_v
                # For lower-better metrics, flip sign so green always = "more confounded toward correct"
                delta_matrix[mi, ci] = -raw_delta if lower_better else raw_delta

    col_labels = [h[2] for h in HEATMAP_METRICS]
    row_labels  = [MODEL_LABELS[m] for m in MODELS]

    vmax = np.nanpercentile(np.abs(delta_matrix), 95)
    vmax = max(vmax, 0.05)

    fig2, ax2 = plt.subplots(figsize=(15, 5))
    fig2.patch.set_facecolor("#F1F4F9")
    ax2.set_facecolor("#F1F4F9")

    from matplotlib.colors import TwoSlopeNorm
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
    cmap = plt.cm.RdYlGn

    im = ax2.imshow(delta_matrix, cmap=cmap, norm=norm, aspect="auto")

    ax2.set_xticks(range(len(col_labels)))
    ax2.set_xticklabels(col_labels, rotation=35, ha="right", fontsize=8)
    ax2.set_yticks(range(len(row_labels)))
    ax2.set_yticklabels(row_labels, fontsize=9)

    # Add model-color left stripe
    for yi, col in enumerate(colors):
        ax2.add_patch(plt.Rectangle((-0.55 - 0.35, yi - 0.5), 0.35, 1,
                                     color=col, transform=ax2.transData, clip_on=False))

    # Cell text
    for ri in range(n_models):
        for ci in range(len(HEATMAP_METRICS)):
            v = delta_matrix[ri, ci]
            if not np.isnan(v):
                sign = "+" if v >= 0 else ""
                text_color = "white" if abs(v) > vmax * 0.55 else "#1C2333"
                ax2.text(ci, ri, f"{sign}{v:.3f}", ha="center", va="center",
                         fontsize=6.5, color=text_color, fontweight="bold")

    # Dividers between dimensions
    dim_boundaries = [3, 6, 9]  # after inf(3), q(3), eff(3)
    for b in dim_boundaries:
        ax2.axvline(b - 0.5, color="white", linewidth=2)

    # Dimension labels on top
    dim_spans = [("Inference\nQuality", 0, 2), ("Question Quality\n(cosine)", 3, 5),
                 ("Efficiency", 6, 8), ("Diagnostic\nReasoning", 9, 11)]
    ax2_top = ax2.secondary_xaxis("top")
    ax2_top.set_xticks([])
    for label, start, end in dim_spans:
        mid = (start + end) / 2
        ax2.text(mid, -1.1, label, ha="center", va="bottom", fontsize=8,
                 fontweight="bold", color="#4C6EF5", transform=ax2.transData)

    cbar = fig2.colorbar(im, ax=ax2, shrink=0.7, pad=0.02)
    cbar.set_label("Δ correct − incorrect\n(green = correct episodes score higher)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    ax2.set_title(
        "Outcome-Stratification Δ Heatmap  (Δ = correct − incorrect, lower-better metrics sign-flipped)",
        fontsize=10, fontweight="bold", color="#1C2333", pad=28,
    )
    plt.tight_layout()
    out2 = OUT_DIR / "ablation_delta_heatmap.png"
    fig2.savefig(out2, dpi=150, bbox_inches="tight", facecolor=fig2.get_facecolor())
    plt.close(fig2)
    print(f"[saved] {out2}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    all_results: dict[str, dict] = {}
    dim_rows: dict[str, list[dict]] = {
        "inference": [], "question": [], "efficiency": [], "dr": [],
    }

    for model in MODELS:
        if not (RB / model).exists():
            print(f"[skip] {model}: results dir not found")
            continue

        outcomes = load_outcomes(model)
        n_correct   = sum(v for v in outcomes.values())
        n_incorrect = sum(1 for v in outcomes.values() if not v)
        rate = n_correct / max(len(outcomes), 1)
        print(f"\n{model}: correct={n_correct}, incorrect={n_incorrect} ({rate:.1%})")

        mdata: dict[str, Any] = {}

        # 1. Inference Quality
        inf_eps = _load_inference_episodes(model)
        mdata["inference"] = ablate_inference(outcomes, inf_eps)
        dim_rows["inference"] += _flatten_agg(model, "inference",
                                               mdata["inference"], INF_METRICS)

        # 2. Question Quality
        q_eps = _load_question_episodes(model)
        if q_eps and "episode_metrics" in q_eps[0]:
            mdata["question"] = ablate_question(outcomes, q_eps)
            for mapper in Q_MAPPERS:
                dim_rows["question"] += _flatten_agg(model, "question",
                                                      mdata["question"], Q_METRICS, mapper)
        else:
            mdata["question"] = {}

        # 3. Efficiency
        eff_eps = _load_efficiency_episodes(model)
        mdata["efficiency"] = ablate_efficiency(outcomes, eff_eps)
        dim_rows["efficiency"] += _flatten_agg(model, "efficiency",
                                                mdata["efficiency"], EFF_METRICS)

        # 4. Diagnostic Reasoning
        dr_eps = _load_dr_episodes(model)
        mdata["dr"] = ablate_dr(outcomes, dr_eps)
        dim_rows["dr"] += _flatten_agg(model, "dr", mdata["dr"], DR_METRICS)

        all_results[model] = mdata

    # Print per-dimension summaries
    for dim_key, dim_label, metrics in [
        ("inference",  "INFERENCE QUALITY",    INF_METRICS),
        ("efficiency", "EFFICIENCY",            EFF_METRICS[:4]),
        ("dr",         "DIAGNOSTIC REASONING",  DR_METRICS[:4]),
    ]:
        print(f"\n{'='*70}\n  {dim_label}\n{'='*70}")
        hdr = f"  {'Model':<24}"
        for m in metrics:
            hdr += f"  {m[:10]:>10}"
        print(hdr + "  (correct|incorrect)")
        print("  " + "-" * 62)
        for model in MODELS:
            mdata = all_results.get(model, {}).get(dim_key, {})
            c_agg = mdata.get("correct", {})
            i_agg = mdata.get("incorrect", {})
            row = f"  {MODEL_LABELS[model]:<24}"
            for m in metrics:
                cv = (c_agg.get(m) or {}).get("mean")
                iv = (i_agg.get(m) or {}).get("mean")
                cs = f"{cv:.3f}" if cv is not None else "  N/A"
                is_ = f"{iv:.3f}" if iv is not None else "  N/A"
                row += f"  {cs}|{is_}"
            print(row)

    # Save JSONs + CSVs
    dim_map = {
        "inference":  ("ablation_inference_quality",     INF_METRICS),
        "efficiency": ("ablation_efficiency",            EFF_METRICS),
        "dr":         ("ablation_diagnostic_reasoning",  DR_METRICS),
    }
    for dim_key, (fname, _) in dim_map.items():
        _save_json({m: all_results[m].get(dim_key, {}) for m in all_results},
                   OUT_DIR / f"{fname}.json")
        _save_csv(dim_rows[dim_key], OUT_DIR / f"{fname}.csv")

    # Question quality JSON + CSV (cosine mapper only for CSV)
    _save_json({m: all_results[m].get("question", {}) for m in all_results},
               OUT_DIR / "ablation_question_quality.json")
    _save_csv([r for r in dim_rows["question"] if r.get("mapper") == "cosine"],
              OUT_DIR / "ablation_question_quality_cosine.csv")
    _save_csv([r for r in dim_rows["question"] if r.get("mapper") == "llm_judge"],
              OUT_DIR / "ablation_question_quality_llm.csv")

    # Unified summary
    _save_json(all_results, OUT_DIR / "ablation_all_summary.json")

    # Plots
    _plot_all(all_results)


if __name__ == "__main__":
    main()
