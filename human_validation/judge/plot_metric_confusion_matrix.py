#!/usr/bin/env python3
"""
Confusion-matrix-style heatmap of correlations between our metrics and human/
LLM ratings:

  rows = {jaccard (rigid), qts}
  cols = {진단 가설 품질, 질문 품질}
  cell = Pearson r / Spearman rho (both shown)

4 panels: {episode level, turn level} x {expert (mean of 2,3), claude-sonnet-4.6
judge}. Off-diagonal cells (e.g. jaccard vs. 질문 품질) are included, not just
the matched pairs.

Usage:
  MS_RUN=run_batch_20260912 python human_validation/judge/plot_metric_confusion_matrix.py
"""
from __future__ import annotations

import json
import sys as _sys
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as scipy_stats

JUDGE_DIR = Path(__file__).resolve().parent
LLM_DIR = JUDGE_DIR / "llm_response_2"
REPO_ROOT = JUDGE_DIR.parent.parent
for p in (REPO_ROOT, JUDGE_DIR, LLM_DIR):
    if str(p) not in _sys.path:
        _sys.path.insert(0, str(p))

from utils.turn_policy import OPENING_TURN  # noqa: E402
from plot_expert_vs_llm_correlation import (  # noqa: E402
    doctor_from_kor_path,
    find_kor_file,
    turn_ias,
    turn_jaccard_rigid,
)
from correlate_expert_3 import EXPERT_FILES, automated_metrics, expert_turn_ratings, parse_expert  # noqa: E402
import correlate_llm_judge as clj  # noqa: E402

ROWS = ["jaccard", "ias"]
ROW_LABELS = {"jaccard": "Jaccard (rigid)", "ias": "QTS"}
COLS = ["hyp", "qst"]  # display order
COL_LABELS = {"hyp": "진단 가설 품질", "qst": "질문 품질"}
# parse_expert() (episode-level) keys its dict by these instead of hyp/qst
EPISODE_DIM_KEY = {"hyp": "hypothesis", "qst": "question"}
CLAUDE_SCORES = LLM_DIR / "claude-sonnet-4.6" / "llm_judge_scores.json"


def pearson_rho(xs: list[float], ys: list[float]) -> tuple[float | None, float | None, float | None, float | None, int]:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None, None, None, None, n
    xa = np.array([p[0] for p in pairs])
    ya = np.array([p[1] for p in pairs])
    if xa.std() == 0 or ya.std() == 0:
        return None, None, None, None, n
    r, r_p = scipy_stats.pearsonr(xa, ya)
    rho, rho_p = scipy_stats.spearmanr(xa, ya)
    return float(r), float(r_p), float(rho), float(rho_p), n


# ── Expert (mean of Expert 2 & 3) ───────────────────────────────────────────

def expert_episode_grid() -> np.ndarray:
    experts = [parse_expert(p) for p in EXPERT_FILES]
    common = sorted(set(experts[0]) & set(experts[1]))
    auto = {pid: automated_metrics(pid) for pid in common}

    grid = np.empty((len(ROWS), len(COLS)), dtype=object)
    for i, metric in enumerate(ROWS):
        for j, dim in enumerate(COLS):
            xs, ys = [], []
            ekey = EPISODE_DIM_KEY[dim]
            for pid in common:
                a = auto[pid].get(metric)
                vals = [experts[0][pid][ekey], experts[1][pid][ekey]]
                vals = [v for v in vals if v is not None]
                e = float(np.mean(vals)) if vals else None
                if a is None or e is None:
                    continue
                xs.append(a)
                ys.append(e)
            grid[i, j] = pearson_rho(xs, ys)
    return grid


def expert_turn_grid() -> np.ndarray:
    per_expert = [expert_turn_ratings(p) for p in EXPERT_FILES]
    common = sorted(set(per_expert[0]) & set(per_expert[1]))
    getters = {"jaccard": turn_jaccard_rigid, "ias": turn_ias}

    grid = np.empty((len(ROWS), len(COLS)), dtype=object)
    for i, metric in enumerate(ROWS):
        getter = getters[metric]
        for j, dim in enumerate(COLS):
            xs, ys = [], []
            for pid in common:
                kor = find_kor_file(pid)
                if kor is None:
                    continue
                doctor = doctor_from_kor_path(kor)
                for t, a in getter(doctor, pid).items():
                    vals = [e[pid][dim].get(t) for e in per_expert if pid in e]
                    vals = [v for v in vals if v is not None]
                    if not vals:
                        continue
                    xs.append(a)
                    ys.append(float(np.mean(vals)))
            grid[i, j] = pearson_rho(xs, ys)
    return grid


# ── Claude-sonnet-4.6 LLM-as-judge ──────────────────────────────────────────

def _load_claude_cases() -> list[dict]:
    return json.loads(CLAUDE_SCORES.read_text(encoding="utf-8"))


def _q_turn(c: dict, t: dict) -> int | None:
    tn = t.get("t")
    if tn is None:
        return None
    legacy = c.get("turn_numbering") != "policy"
    from utils.turn_policy import preceding_question_turn_to_policy
    return preceding_question_turn_to_policy(tn) if legacy else tn


def claude_episode_grid() -> np.ndarray:
    cases = _load_claude_cases()
    grid = np.empty((len(ROWS), len(COLS)), dtype=object)
    cache = {}
    for i, metric in enumerate(ROWS):
        for j, dim in enumerate(COLS):
            xs, ys = [], []
            for c in cases:
                parsed = c.get("parsed")
                if not parsed:
                    continue
                key = (c["doctor"], c["profile_id"])
                if key not in cache:
                    cache[key] = clj.our_metrics(c["doctor"], c["profile_id"])
                m = cache[key]
                a = m["jaccard_rigid_mean"] if metric == "jaccard" else m["ias_mean"]
                turns = parsed.get("turns") or []
                if dim == "hyp":
                    vals = [t.get("h") for t in turns if t.get("h") is not None]
                else:
                    vals = [t.get("q") for t in turns
                            if t.get("q") is not None and _q_turn(c, t) != OPENING_TURN]
                e = float(np.mean(vals)) if vals else None
                if a is None or e is None:
                    continue
                xs.append(a)
                ys.append(e)
            grid[i, j] = pearson_rho(xs, ys)
    return grid


def claude_turn_grid() -> np.ndarray:
    cases = _load_claude_cases()
    grid = np.empty((len(ROWS), len(COLS)), dtype=object)
    cache = {}
    for i, metric in enumerate(ROWS):
        for j, dim in enumerate(COLS):
            xs, ys = [], []
            for c in cases:
                parsed = c.get("parsed")
                if not parsed:
                    continue
                key = (c["doctor"], c["profile_id"])
                if key not in cache:
                    cache[key] = clj.our_metrics(c["doctor"], c["profile_id"])
                m = cache[key]
                by_turn = m["jaccard_rigid_by_turn"] if metric == "jaccard" else m["ias_by_turn"]
                for t in parsed.get("turns") or []:
                    if dim == "hyp":
                        if t.get("h") is None:
                            continue
                        turn_key, e = t.get("t"), t["h"]
                    else:
                        qt = _q_turn(c, t)
                        if t.get("q") is None or qt == OPENING_TURN:
                            continue
                        turn_key, e = qt, t["q"]
                    a = by_turn.get(turn_key)
                    if a is None:
                        continue
                    xs.append(a)
                    ys.append(e)
            grid[i, j] = pearson_rho(xs, ys)
    return grid


def draw_panel(ax, grid: np.ndarray, title: str) -> None:
    r_grid = np.array([[(c[0] if c[0] is not None else np.nan) for c in row] for row in grid])
    im = ax.imshow(r_grid, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(COLS)))
    ax.set_xticklabels([COL_LABELS[c] for c in COLS], fontsize=11)
    ax.set_yticks(range(len(ROWS)))
    ax.set_yticklabels([ROW_LABELS[r] for r in ROWS], fontsize=11)

    def _p(v: float) -> str:
        return "p<0.001" if v < 0.001 else f"p={v:.3f}"

    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            r, r_p, rho, rho_p, n = grid[i, j]
            if r is None:
                txt, color = "n/a", "#1C2333"
            else:
                txt = f"r={r:.2f} ({_p(r_p)})\nρ={rho:.2f} ({_p(rho_p)})\n(n={n})"
                color = "white" if abs(r) > 0.55 else "#1C2333"
            ax.text(j, i, txt, ha="center", va="center", fontsize=9, color=color)
    ax.set_title(title, fontsize=12)
    return im


def main() -> None:
    cjk = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    fm.fontManager.addfont(cjk)
    plt.rcParams["font.family"] = [fm.FontProperties(fname=cjk).get_name(), "DejaVu Sans"]

    panels = [
        ("Expert (mean 2,3) — episode level", expert_episode_grid()),
        ("Claude-sonnet-4.6 judge — episode level", claude_episode_grid()),
        ("Expert (mean 2,3) — turn level", expert_turn_grid()),
        ("Claude-sonnet-4.6 judge — turn level", claude_turn_grid()),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(11, 9.5))
    im = None
    for ax, (title, grid) in zip(axes.flat, panels):
        im = draw_panel(ax, grid, title)

    fig.suptitle("Our metrics vs. expert / LLM-as-judge ratings (Pearson r / Spearman ρ)",
                 fontsize=13, y=1.0)
    cbar = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.03)
    cbar.set_label("Pearson r", fontsize=11)
    out = JUDGE_DIR / "metric_confusion_matrix.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out}")


if __name__ == "__main__":
    main()
