#!/usr/bin/env python3
"""
evaluation_v4.md — IAS Components: Diagnostic Relevance vs. Redundancy Penalty

IAS (Information Acquisition Score, §2 of evaluation_v4.md) decomposes as:

    IAS = DRS x (1 - RP)

  DRS (diagnostic relevance)  = |S(q_t) ∩ I_t| / |S(q_t)|   — mean per episode,
                                  over all llm_judge-scored turns
  RP  (redundancy penalty)    = |S(q_t) ∩ resolved| / |S(q_t)| — mean per episode
                                  (episode_metrics.llm_judge.mean_redundancy)

This script scatters one point per (judge, doctor) combo: x = mean DRS,
y = mean (1 - RP) so both axes point "higher = better" and the up-right
corner is the ideal quadrant; point color encodes mean IAS on a sequential
ramp (the product of the two axes, approximately — episode-level averaging
means it isn't an exact identity, see module docstring above). Marker shape
distinguishes judge.

Reads question_eval.json directly (DRS isn't in the summarize_v4_metrics_csv.py
CSV — only the composite IAS is), filtered to the same style as the run's
v4_metrics_summary CSV.

Usage:
  python reporting/plot_v4_ias_components.py [--style plain] [-o OUT.png]

  MS_RUN=run_batch_20260912 python reporting/plot_v4_ias_components.py --style plain
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MS_RUN", "run_batch_20260912")

from utils.paths import ANALYSIS_ROOT, RESULTS_ROOT

MARKERS = ["o", "^", "s", "D", "P", "X"]

SELECTED_DOCTORS = {
    "gpt-5.4",
    "gemini-3.8-flash",
    "claude-sonnet-5",
    "llama-3.3-70b-instruct",
    "qwen3-235b",
}


def load_components(style: str | None) -> dict[tuple[str, str], dict]:
    by_key: dict[tuple[str, str], dict] = defaultdict(lambda: {"drs": [], "rp": [], "ias": []})

    for qe_path in sorted(RESULTS_ROOT.glob("*/*/*/question_eval.json")):
        judge, doctor = qe_path.parts[-3], qe_path.parts[-2]
        if doctor.lower() not in SELECTED_DOCTORS:
            continue
        episodes = json.loads(qe_path.read_text(encoding="utf-8"))
        for ep in episodes:
            if style and not str(ep.get("log_file", "")).endswith(f"_{style}"):
                continue
            jm = (ep.get("episode_metrics") or {}).get("llm_judge") or {}
            if jm.get("mean_ias") is None:
                continue
            drs_vals = [
                sbm["llm_judge"]["diagnostic_relevance"]
                for t in ep.get("turns", [])
                if (sbm := t.get("scores_by_mapper", {})).get("llm_judge", {}).get("diagnostic_relevance") is not None
            ]
            if not drs_vals:
                continue
            k = (judge, doctor)
            by_key[k]["drs"].append(float(np.mean(drs_vals)))
            by_key[k]["rp"].append(jm["mean_redundancy"])
            by_key[k]["ias"].append(jm["mean_ias"])

    out = {}
    for k, v in by_key.items():
        out[k] = {
            "n": len(v["drs"]),
            "drs": float(np.mean(v["drs"])),
            "rp": float(np.mean(v["rp"])),
            "ias": float(np.mean(v["ias"])),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default=None, help="Filter episodes by log filename suffix (e.g. 'plain').")
    parser.add_argument("-o", "--out", default=None, help="Output PNG path.")
    args = parser.parse_args()

    data = load_components(args.style)
    if not data:
        print("No question_eval.json data found (with llm_judge scores).")
        return

    judges = sorted({j for j, _d in data})
    marker_of = {j: MARKERS[i % len(MARKERS)] for i, j in enumerate(judges)}

    xs = [v["drs"] for v in data.values()]
    ys = [1 - v["rp"] for v in data.values()]
    cs = [v["ias"] for v in data.values()]

    fig, ax = plt.subplots(figsize=(8.5, 7))
    sc = None
    for (judge, doctor), v in data.items():
        sc = ax.scatter(
            v["drs"], 1 - v["rp"], c=[v["ias"]], cmap="Blues", vmin=min(cs), vmax=max(cs),
            s=170, marker=marker_of[judge], edgecolors="#0d366b", linewidths=0.8, zorder=3,
        )
        ax.annotate(
            doctor, (v["drs"], 1 - v["rp"]), textcoords="offset points", xytext=(7, 6),
            fontsize=8.5, color="#3a3a38",
        )

    x_pad = (max(xs) - min(xs)) * 0.22 or 0.02
    y_pad = (max(ys) - min(ys)) * 0.12 or 0.02
    ax.set_xlim(min(xs) - x_pad * 0.4, max(xs) + x_pad)
    ax.set_ylim(min(ys) - y_pad, max(ys) + y_pad)

    ax.set_xlabel("Diagnostic Relevance (DRS) — mean per episode, higher = better", fontsize=10, color="#52514e")
    ax.set_ylabel("1 − Redundancy Penalty — mean per episode, higher = better", fontsize=10, color="#52514e")
    # ax.set_title(
    #     "evaluation_v4.md §2 — IAS decomposition: Diagnostic Relevance vs. Non-Redundancy\n"
    #     "(point color = mean IAS; marker shape = judge)",
    #     fontsize=12, fontweight="bold",
    # )
    ax.grid(color="#e1e0d9", linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Mean IAS", fontsize=9.5, color="#52514e")

    judge_handles = [
        plt.Line2D([0], [0], marker=marker_of[j], color="w", markerfacecolor="#6da7ec",
                   markeredgecolor="#0d366b", markersize=10, label=j)
        for j in judges
    ]
    ax.legend(handles=judge_handles, title="Judge", loc="lower right", fontsize=9, frameon=False)

    fig.tight_layout()
    out_path = Path(args.out) if args.out else ANALYSIS_ROOT / "v4_ias_components.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    print(f"[saved] {out_path}")


if __name__ == "__main__":
    main()
