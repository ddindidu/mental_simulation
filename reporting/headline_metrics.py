#!/usr/bin/env python3
"""
Shared loader for the evaluation_v5.md headline metrics, per episode.

load_combo(patient, judge, doctor, style) joins the four eval outputs of one
(patient, judge, doctor) combo by log_file and returns one dict per episode:

  Diagnostic Hypothesis Quality  jaccard, precision, recall, weighted_recall
                                 (per-episode mean over turns; *_sum / n_turns
                                 are kept so callers can pool over turns)
  Diagnostic Question Quality    qts
  Diagnostic Efficiency          turn_count, first_confident (None if never
                                 reached), overcommitment_conf
  Diagnostic Decision Quality    final_accuracy, evidence_sufficiency (None if
                                 the final dx is unresolved / not scored)

pooled_means(episodes) aggregates them the same way
reporting/summarize_v4_metrics_csv.py does: episode-mean throughout — each
episode counts once (hypothesis metrics are already turn-averaged per episode
in load_combo; everything else is already one value per episode) — rather
than a flat mean over all (episode, turn) rows, which would weight episodes
with more turns more heavily.
"""
from __future__ import annotations

import json
from pathlib import Path

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT
from utils.metric_compat import episode_mean_qts

HYPOTHESIS = ("jaccard", "precision", "recall", "weighted_recall")

# (key, label, dimension, lower_is_better)
HEADLINE: list[tuple[str, str, str, bool]] = [
    ("jaccard",              "Jaccard",               "Hypothesis", False),
    ("precision",            "Precision",             "Hypothesis", False),
    ("recall",               "Recall",                "Hypothesis", False),
    ("weighted_recall",      "Weighted Recall",       "Hypothesis", False),
    ("qts",                  "QTS",                   "Question",   False),
    ("turn_count",           "Total Turns",           "Efficiency", True),
    ("first_confident",      "1st-Confidence Turn",   "Efficiency", True),
    ("overcommitment_conf",  "Overcommitment Turns",  "Efficiency", True),
    ("final_accuracy",       "Final Accuracy",        "Decision",   False),
    ("evidence_sufficiency", "Evidence Sufficiency",  "Decision",   False),
]
HEADLINE_KEYS = [k for k, *_ in HEADLINE]
DIMENSION_NAMES = {
    "Hypothesis": "Diagnostic Hypothesis Quality",
    "Question":   "Diagnostic Question Quality",
    "Efficiency": "Diagnostic Efficiency",
    "Decision":   "Diagnostic Decision Quality",
}


def _load_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _style_ok(log_file: str, style: str | None) -> bool:
    return not style or log_file.endswith(f"_{style}")


def discover_combos() -> list[tuple[str, str, str]]:
    """(patient, judge, doctor) for every combo with an efficiency_eval.json."""
    return sorted(
        (p.parts[-4], p.parts[-3], p.parts[-2])
        for p in RESULTS_ROOT.glob("*/*/*/efficiency_eval.json")
    )


def load_combo(patient: str, judge: str, doctor: str, style: str | None = "plain") -> list[dict]:
    rdir = RESULTS_ROOT / patient / judge / doctor
    adir = ANALYSIS_ROOT / patient / judge / doctor

    episodes: dict[str, dict] = {}
    for e in _load_list(rdir / "efficiency_eval.json"):
        lf = e["log_file"]
        if not _style_ok(lf, style):
            continue
        t1 = e.get("time_to_first_confident_narrowing")
        episodes[lf] = {
            "log_file":            lf,
            "ground_truth":        e.get("ground_truth"),
            "turn_count":          e.get("turn_count"),
            "first_confident":     t1 if t1 is not None and t1 <= e.get("turn_count", 0) else None,
            "overcommitment_conf": e.get("overcommitment_conf"),
            "final_accuracy":      e.get("final_accuracy"),
            "qts":                 None,
            "evidence_sufficiency": None,
            "n_turns":             0,
            **{f"{m}_sum": 0.0 for m in HYPOTHESIS},
            **{m: None for m in HYPOTHESIS},
        }

    for row in _load_list(adir / "turn_eval.json"):
        ep = episodes.get(row["log_file"])
        if ep is None:
            continue
        ep["n_turns"] += 1
        for m in HYPOTHESIS:
            # *_rigid holds the headline (tier-priority) value in pre- and post-v5 files.
            ep[f"{m}_sum"] += row.get(f"{m}_rigid", row[m])
    for ep in episodes.values():
        if ep["n_turns"]:
            for m in HYPOTHESIS:
                ep[m] = ep[f"{m}_sum"] / ep["n_turns"]

    for q in _load_list(rdir / "question_eval.json"):
        if q["log_file"] in episodes:
            episodes[q["log_file"]]["qts"] = episode_mean_qts(q)

    for d in _load_list(rdir / "diagnostic_reasoning_eval.json"):
        if d["log_file"] in episodes:
            episodes[d["log_file"]]["evidence_sufficiency"] = d.get("overall_score_pred")

    return list(episodes.values())


def pooled_means(episodes: list[dict]) -> dict[str, float | None]:
    """Episode-mean: hypothesis metrics use each episode's own per-episode
    mean (`e[m]`, already turn-averaged within the episode in load_combo),
    averaged again across episodes — every episode counts equally regardless
    of its turn count. Everything else is already one value per episode, so
    it's a plain mean over episodes with a value."""
    out: dict[str, float | None] = {}
    for m in HYPOTHESIS:
        vals = [e[m] for e in episodes if e.get(m) is not None]
        out[m] = sum(vals) / len(vals) if vals else None
    for k in HEADLINE_KEYS:
        if k in HYPOTHESIS:
            continue
        vals = [e[k] for e in episodes if e.get(k) is not None]
        out[k] = sum(vals) / len(vals) if vals else None
    out["n_episodes"] = len(episodes)
    return out
