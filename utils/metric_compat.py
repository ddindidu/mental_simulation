"""Readers for evaluation outputs that span the IAS -> QTS rename.

question_eval.json written before the rename stores `ias` / `mean_ias`;
newer files store `qts` / `mean_qts`. Prefer the new key, fall back to the old.
"""
from __future__ import annotations


def turn_qts(scores: dict) -> float | None:
    """One turn's scores_by_mapper[<mapper>] dict -> QTS."""
    return scores.get("qts", scores.get("ias"))


def episode_mean_qts(entry: dict, mapper: str = "llm_judge") -> float | None:
    """One question_eval.json episode entry -> episode mean QTS for `mapper`."""
    em = (entry.get("episode_metrics") or {}).get(mapper) or {}
    return em.get("mean_qts", em.get("mean_ias"))


def csv_qts(row: dict) -> str | None:
    """A v4_metrics_summary CSV row -> QTS cell (column renamed ias -> qts)."""
    return row.get("qts", row.get("ias"))


def csv_hypothesis(row: dict, name: str) -> str | None:
    """A v4_metrics_summary CSV row -> jaccard / precision / recall cell.

    CSVs written before the refactor carry both `<name>` (union reference
    set, now deactivated) and `<name>_rigid` (tier-priority, the headline);
    newer CSVs carry only `<name>` (tier-priority). Prefer `_rigid` when present.
    """
    return row.get(f"{name}_rigid", row.get(name))
