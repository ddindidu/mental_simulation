#!/usr/bin/env python3
"""
Doctor inference confusion analysis

FP definition: set(predicted) − set(truth_set)
When GT = X, which wrong diseases appear in the doctor's predicted set?

Outputs (saved to --output/confusion/, default --input/confusion/):
  confusion_heatmap_overall.png   — 23×23 aggregated FP-rate heatmap
  confusion_heatmap_per_turn.png  — grid of per-turn 23×23 heatmaps
  confusion_trajectory.png        — top-K confused FP diseases per GT over turns

Usage:
  python plot_confusion.py --input analysis/gemini-3.5-flash/gemini-3.5-flash/gemini-3.5-flash
  python plot_confusion.py          # auto via get_run_dir()
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

import matplotlib.pyplot as plt
import numpy as np

BASE_DIR      = Path(__file__).resolve().parent.parent
CRITERIA_FILE = BASE_DIR / "mentalbench/resources/knowledge_graph/EN/diagnostic_criteria.json"
TOP_K         = 5
TRAJ_COLORS   = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _id2name() -> dict[str, str]:
    data = json.loads(CRITERIA_FILE.read_text(encoding="utf-8"))
    return {k: v["name"] for k, v in data.items()}


def _abbrev(name: str, n: int = 20) -> str:
    return name if len(name) <= n else name[:n - 1] + "…"


# ── data ──────────────────────────────────────────────────────────────────────

def _build_fp_data(entries: list[dict]):
    """
    fp_at[gt][fp_did][turn] = # of times fp_did appeared as FP when GT=gt, turn=turn
    n_at[gt][turn]          = # of (episode, turn) pairs for GT=gt at turn
    """
    fp_at = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    n_at  = defaultdict(lambda: defaultdict(int))
    max_t = 0
    for e in entries:
        gt = e["ground_truth"]
        t  = e["turn"]
        fp = set(e["predicted"]) - set(e["truth_set"])
        n_at[gt][t] += 1
        max_t = max(max_t, t)
        for d in fp:
            fp_at[gt][d][t] += 1
    return fp_at, n_at, max_t


def _rate_matrix(fp_at, n_at, dids, turn=None) -> np.ndarray:
    """
    Returns (n, n) FP-rate matrix.  turn=None aggregates across all turns.
    row = GT index, col = FP disease index.
    """
    idx = {d: i for i, d in enumerate(dids)}
    mat = np.zeros((len(dids), len(dids)))
    for gt in dids:
        gi = idx[gt]
        if turn is None:
            denom = sum(n_at.get(gt, {}).values())
        else:
            denom = n_at.get(gt, {}).get(turn, 0)
        if denom == 0:
            continue
        for fp_did in dids:
            fi = idx[fp_did]
            if turn is None:
                num = sum(fp_at.get(gt, {}).get(fp_did, {}).values())
            else:
                num = fp_at.get(gt, {}).get(fp_did, {}).get(turn, 0)
            mat[gi, fi] = num / denom
    return mat


# ── A1: overall heatmap ───────────────────────────────────────────────────────

def _draw_heatmap(ax, mat, dids, id2name, title, vmax, show_names_y=True):
    y_labels = (
        [f"{d}  {_abbrev(id2name.get(d,''), 25)}" for d in dids]
        if show_names_y else dids
    )
    im = ax.imshow(mat, aspect="auto", cmap="YlOrRd", vmin=0, vmax=vmax)
    ax.set_title(title, fontsize=9, fontweight="bold", pad=4)
    ax.set_xticks(range(len(dids)))
    ax.set_xticklabels(dids, fontsize=6, rotation=90)
    ax.set_yticks(range(len(dids)))
    ax.set_yticklabels(y_labels, fontsize=6)
    ax.set_xlabel("FP disease (wrongly included)", fontsize=7)
    ax.set_ylabel("Ground Truth", fontsize=7)
    return im


def plot_overall_heatmap(mat, dids, id2name, out_path):
    vmax = float(mat.max()) or 1.0
    fig, ax = plt.subplots(figsize=(11, 10))
    im = _draw_heatmap(ax, mat, dids, id2name,
                       "Overall FP-Rate Confusion  (row=GT, col=wrongly included FP disease)",
                       vmax=vmax, show_names_y=True)
    # annotate cells with value > threshold
    thresh = vmax * 0.15
    for i in range(len(dids)):
        for j in range(len(dids)):
            v = mat[i, j]
            if v >= thresh:
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                        fontsize=5.5,
                        color="white" if v > vmax * 0.65 else "black")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="FP rate")
    plt.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ── A2: per-turn heatmap grid ─────────────────────────────────────────────────

def plot_per_turn_heatmaps(fp_at, n_at, dids, id2name, max_turn, out_path):
    turns = list(range(1, max_turn + 1))
    mats  = [_rate_matrix(fp_at, n_at, dids, t) for t in turns]
    vmax  = max((m.max() for m in mats), default=1.0) or 1.0

    ncols = 5
    nrows = (len(turns) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(ncols * 4.2, nrows * 4.2),
                             squeeze=False)
    flat = axes.flatten()

    for i, (t, mat) in enumerate(zip(turns, mats)):
        ax = flat[i]
        n_total = sum(n_at.get(gt, {}).get(t, 0) for gt in dids)
        im = _draw_heatmap(ax, mat, dids, id2name,
                           f"Turn {t}  (N={n_total})",
                           vmax=vmax, show_names_y=False)
    for j in range(len(turns), len(flat)):
        flat[j].set_visible(False)

    fig.subplots_adjust(right=0.87)
    cax = fig.add_axes([0.89, 0.15, 0.015, 0.7])
    sm  = plt.cm.ScalarMappable(cmap="YlOrRd",
                                norm=plt.Normalize(vmin=0, vmax=vmax))
    sm.set_array([])
    fig.colorbar(sm, cax=cax, label="FP rate")
    fig.suptitle("Per-Turn FP Confusion  (row=GT, col=wrongly included FP disease)",
                 fontsize=12, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 0.87, 0.97])
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ── B: per-disorder trajectory ────────────────────────────────────────────────

def _top_fp_for_gt(gt, fp_at, n_at, dids, k=TOP_K) -> list[tuple[float, str]]:
    total = sum(n_at.get(gt, {}).values())
    if total == 0:
        return []
    rows = []
    for fp_did in dids:
        if fp_did == gt:
            continue
        cnt = sum(fp_at.get(gt, {}).get(fp_did, {}).values())
        if cnt > 0:
            rows.append((cnt / total, fp_did))
    rows.sort(reverse=True)
    return rows[:k]


def plot_trajectory(fp_at, n_at, dids, id2name, max_turn, out_path):
    turns = list(range(1, max_turn + 1))
    ncols = 6
    nrows = (len(dids) + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(ncols * 4.8, nrows * 3.8),
                             squeeze=False)
    flat = axes.flatten()

    for i, gt in enumerate(dids):
        ax   = flat[i]
        name = id2name.get(gt, gt)
        top  = _top_fp_for_gt(gt, fp_at, n_at, dids)

        if not top:
            ax.set_title(f"{gt}: {_abbrev(name, 28)}", fontsize=8, fontweight="bold")
            ax.text(0.5, 0.5, "No FP confusion", ha="center", va="center",
                    transform=ax.transAxes, fontsize=9, color="gray")
            ax.set_axis_off()
            continue

        for j, (rate_overall, fp_did) in enumerate(top):
            ys = []
            ns = []
            for t in turns:
                n   = n_at.get(gt, {}).get(t, 0)
                cnt = fp_at.get(gt, {}).get(fp_did, {}).get(t, 0)
                ys.append(cnt / n if n > 0 else float("nan"))
                ns.append(n)
            color    = TRAJ_COLORS[j % len(TRAJ_COLORS)]
            fp_name  = _abbrev(id2name.get(fp_did, fp_did), 22)
            ax.plot(turns, ys, color=color, marker="o", markersize=4,
                    linewidth=1.8,
                    label=f"{fp_did}: {fp_name}  (avg {rate_overall:.2f})")

        # N annotation on twin axis
        ax2 = ax.twinx()
        n_series = [n_at.get(gt, {}).get(t, 0) for t in turns]
        ax2.bar(turns, n_series, color="gray", alpha=0.12, width=0.7, zorder=0)
        ax2.set_ylabel("N", fontsize=6, color="gray")
        ax2.tick_params(axis="y", labelsize=5.5, colors="gray")
        mx = max(n_series) if n_series else 1
        ax2.set_ylim(0, mx * 1.5)
        for t, n in zip(turns, n_series):
            if n > 0:
                ax2.text(t, n + mx * 0.02, str(n),
                         ha="center", va="bottom", fontsize=5, color="gray")

        for y in np.arange(0.0, 1.2, 0.2):
            ax.axhline(y, color="lightgray", linewidth=0.4, zorder=0)
        ax.set_xlim(0.5, max_turn + 0.5)
        ax.set_xticks(turns)
        ax.set_ylim(-0.05, 1.05)
        ax.tick_params(labelsize=6.5)
        ax.set_xlabel("Turn", fontsize=7)
        ax.set_ylabel("FP rate", fontsize=7)
        ax.set_title(f"{gt}: {_abbrev(name, 28)}", fontsize=8, fontweight="bold")
        ax.legend(loc="upper right", fontsize=5.5, framealpha=0.75)
        ax.set_zorder(ax2.get_zorder() + 1)
        ax.patch.set_visible(False)

    for j in range(len(dids), len(flat)):
        flat[j].set_visible(False)

    fig.suptitle(f"Top-{TOP_K} Confused FP Diseases per GT — FP Rate over Turns",
                 fontsize=13, fontweight="bold", y=1.005)
    plt.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=None,
                        help="Directory containing turn_eval.json "
                             "(default: analysis/<run_dir> via get_run_dir())")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output directory (default: same as --input)")
    args = parser.parse_args()

    if args.input is None:
        from utils.llm import get_run_dir as _grd
        args.input = BASE_DIR / "analysis" / _grd()
    if args.output is None:
        args.output = args.input
    args.output = args.output / "confusion"
    args.output.mkdir(parents=True, exist_ok=True)

    json_path = args.input / "turn_eval.json"
    if not json_path.exists():
        import sys
        print(f"[error] {json_path} not found", file=sys.stderr)
        sys.exit(1)

    id2name = _id2name()
    entries = json.loads(json_path.read_text(encoding="utf-8"))
    print(f"Input  : {args.input}")
    print(f"Output : {args.output}")
    print(f"Loaded {len(entries)} turn entries")

    dids = sorted({e["ground_truth"] for e in entries}, key=lambda x: int(x[1:]))
    if not dids:
        print("[warn] No turn entries with a ground_truth — nothing to plot.")
        return
    fp_at, n_at, max_turn = _build_fp_data(entries)
    print(f"GT diseases: {len(dids)},  max turn: {max_turn}")

    # count total FP occurrences for a quick sanity check
    total_fp = sum(
        sum(fp_at[gt][fp_did][t]
            for fp_did in fp_at.get(gt, {})
            for t in fp_at[gt][fp_did])
        for gt in dids
    )
    print(f"Total FP occurrences: {total_fp}")

    mat_overall = _rate_matrix(fp_at, n_at, dids, turn=None)

    print("\nGenerating A1: overall heatmap …")
    plot_overall_heatmap(mat_overall, dids, id2name,
                         args.output / "confusion_heatmap_overall.png")

    print("Generating A2: per-turn heatmaps …")
    plot_per_turn_heatmaps(fp_at, n_at, dids, id2name, max_turn,
                           args.output / "confusion_heatmap_per_turn.png")

    print("Generating B: confusion trajectories …")
    plot_trajectory(fp_at, n_at, dids, id2name, max_turn,
                    args.output / "confusion_trajectory.png")

    print("\nDone.")


if __name__ == "__main__":
    main()
