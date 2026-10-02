#!/usr/bin/env python3
"""
Our automated metrics vs. gpt-6-luna LLM-as-judge — correlation.

Same 3 matched-dimension design as
human_validation/judge/plot_expert_vs_llm_correlation.py, but the "expert"
side is replaced by llm_judge_scores.json (this dir's own LLM-as-judge
output) instead of human expert xlsx ratings:

  jaccard_rigid (ours, turn_eval.json)              <-> h  (LLM-judge, Diagnostic Hypothesis Quality)
  ias (ours, question_eval.json)                    <-> q  (LLM-judge, Diagnostic Question Quality, turn>=2)
  diagnostic_evidence_sufficiency_pred (ours, dr json) <-> evidence_sufficiency (LLM-judge, episode-level)

Usage:
  python human_validation/judge/llm_response_2/correlate_llm_judge.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scipy.stats as scipy_stats


def _qts(d: dict, new_key: str, old_key: str):
    """QTS was renamed from IAS; read the new key, fall back to the old one."""
    return d.get(new_key, d.get(old_key))

THIS_DIR = Path(__file__).resolve().parent
JUDGE_DIR = THIS_DIR.parent
REPO_ROOT = JUDGE_DIR.parent.parent

SCORES_PATH = THIS_DIR / "llm_judge_scores.json"
RESULTS_BASE = REPO_ROOT / "saved" / "run_batch_20260912" / "results" / "gpt-5.6-terra" / "gpt-5.6-terra"
ANALYSIS_BASE = REPO_ROOT / "saved" / "run_batch_20260912" / "analysis" / "gpt-5.6-terra" / "gpt-5.6-terra"
CSV_OUT_PATH = THIS_DIR / "llm_judge_vs_metrics.csv"


def _mean(vals) -> float | None:
    vals = [v for v in vals if v is not None]
    return float(np.mean(vals)) if vals else None


def pearson(xs: list, ys: list) -> tuple[float | None, int]:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return None, n
    xa = np.array([p[0] for p in pairs]); ya = np.array([p[1] for p in pairs])
    if np.std(xa) == 0 or np.std(ya) == 0:
        return None, n
    return float(np.corrcoef(xa, ya)[0, 1]), n


def spearman(xs: list, ys: list) -> tuple[float | None, int]:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return None, n
    xa = np.array([p[0] for p in pairs]); ya = np.array([p[1] for p in pairs])
    if np.std(xa) == 0 or np.std(ya) == 0:
        return None, n
    rho, _ = scipy_stats.spearmanr(xa, ya)
    return float(rho), n


# ── per-case automated metrics, straight from source (not the stale xlsx) ──

_dr_cache: dict[str, dict[str, dict]] = {}
_turn_eval_cache: dict[str, dict[str, list[dict]]] = {}
_qeval_cache: dict[str, dict[str, dict]] = {}


def _dr_entry(doctor: str, log_file: str) -> dict | None:
    if doctor not in _dr_cache:
        path = RESULTS_BASE / doctor / "diagnostic_reasoning_eval.json"
        _dr_cache[doctor] = {e["log_file"]: e for e in json.loads(path.read_text(encoding="utf-8"))}
    return _dr_cache[doctor].get(log_file)


def _turn_rows(doctor: str, log_file: str) -> list[dict]:
    if doctor not in _turn_eval_cache:
        path = ANALYSIS_BASE / doctor / "turn_eval.json"
        by_log: dict[str, list[dict]] = {}
        for row in json.loads(path.read_text(encoding="utf-8")):
            by_log.setdefault(row["log_file"], []).append(row)
        _turn_eval_cache[doctor] = by_log
    return _turn_eval_cache[doctor].get(log_file, [])


def _qeval_entry(doctor: str, log_file: str) -> dict | None:
    if doctor not in _qeval_cache:
        path = RESULTS_BASE / doctor / "question_eval.json"
        _qeval_cache[doctor] = {e["log_file"]: e for e in json.loads(path.read_text(encoding="utf-8"))}
    return _qeval_cache[doctor].get(log_file)


def our_metrics(doctor: str, profile_id: str) -> dict:
    log_file = f"{profile_id}_plain"
    dr = _dr_entry(doctor, log_file) or {}
    turn_rows = sorted(_turn_rows(doctor, log_file), key=lambda r: r.get("turn", 0))
    qe = _qeval_entry(doctor, log_file) or {}
    turn_ias = {t.get("turn"): _qts((t.get("scores_by_mapper") or {}).get("llm_judge", {}), "qts", "ias")
                for t in qe.get("turns", [])}

    jaccard_by_turn = {r.get("turn"): r.get("jaccard_rigid") for r in turn_rows}
    ias_mean = _qts((qe.get("episode_metrics") or {}).get("llm_judge", {}), "mean_qts", "mean_ias")

    return {
        "jaccard_rigid_mean": _mean(r.get("jaccard_rigid") for r in turn_rows),
        "jaccard_rigid_by_turn": jaccard_by_turn,
        "ias_mean": ias_mean,
        "ias_by_turn": turn_ias,
        "evidence_sufficiency_pred": dr.get("overall_score_pred"),
    }


def main() -> None:
    cases = json.loads(SCORES_PATH.read_text(encoding="utf-8"))
    print(f"Loaded {len(cases)} LLM-as-judge cases")

    rows = []
    turn_h_pairs: list[tuple[float, float]] = []
    turn_q_pairs: list[tuple[float, float]] = []

    for c in cases:
        parsed = c.get("parsed")
        if not parsed:
            continue
        doctor, profile_id = c["doctor"], c["profile_id"]
        m = our_metrics(doctor, profile_id)

        turns = parsed.get("turns") or []
        h_vals = [t.get("h") for t in turns if t.get("h") is not None]
        q_vals = [t.get("q") for t in turns if t.get("q") is not None]
        mean_h = _mean(h_vals)
        mean_q = _mean(q_vals)
        llm_evidence = parsed.get("evidence_sufficiency")

        for t in turns:
            tn = t.get("t")
            if t.get("h") is not None and m["jaccard_rigid_by_turn"].get(tn) is not None:
                turn_h_pairs.append((m["jaccard_rigid_by_turn"][tn], t["h"]))
            if t.get("q") is not None and m["ias_by_turn"].get(tn) is not None:
                turn_q_pairs.append((m["ias_by_turn"][tn], t["q"]))

        rows.append({
            "sheet": c["sheet"], "profile_id": profile_id, "doctor": doctor,
            "jaccard_rigid_mean": m["jaccard_rigid_mean"], "llm_mean_h": mean_h,
            "ias_mean": m["ias_mean"], "llm_mean_q": mean_q,
            "evidence_sufficiency_pred": m["evidence_sufficiency_pred"], "llm_evidence_sufficiency": llm_evidence,
        })

    import csv
    with open(CSV_OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[saved] {CSV_OUT_PATH}")

    print(f"\n=== Episode-level: our metrics vs. gpt-6-luna LLM-as-judge (n={len(rows)}) ===")
    headline = [
        ("jaccard_rigid_mean", "llm_mean_h", "Jaccard(rigid) <-> h (Hypothesis Quality)"),
        ("ias_mean", "llm_mean_q", "IAS <-> q (Question Quality)"),
        ("evidence_sufficiency_pred", "llm_evidence_sufficiency", "Evidence Sufficiency(pred) <-> evidence_sufficiency"),
    ]
    for ours_key, llm_key, label in headline:
        xs = [r[ours_key] for r in rows]
        ys = [r[llm_key] for r in rows]
        r, n = pearson(xs, ys)
        rho, _ = spearman(xs, ys)
        r_s = f"{r:.3f}" if r is not None else "n/a"
        rho_s = f"{rho:.3f}" if rho is not None else "n/a"
        print(f"  {label:50s} Pearson r={r_s}  Spearman ρ={rho_s}  (n={n})")

    print(f"\n=== Turn-level (pooled, each rated turn = one point) ===")
    for label, pairs in (("jaccard_rigid(turn) <-> h(turn)", turn_h_pairs),
                          ("ias(turn) <-> q(turn, t>=2)", turn_q_pairs)):
        xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
        r, n = pearson(xs, ys)
        rho, _ = spearman(xs, ys)
        r_s = f"{r:.3f}" if r is not None else "n/a"
        rho_s = f"{rho:.3f}" if rho is not None else "n/a"
        print(f"  {label:38s} Pearson r={r_s}  Spearman ρ={rho_s}  (n={n})")


if __name__ == "__main__":
    main()
