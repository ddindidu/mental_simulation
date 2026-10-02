#!/usr/bin/env python3
"""
Diagnostic Efficiency Summary (evaluation_v5.md §3)
Reads efficiency_eval.json and writes analysis/<run_dir>/efficiency/efficiency_summary.txt:
a per-disorder table of Total Turns, 1st-Confidence Turn, Overcommitment
Turns and Final Accuracy. (The per-disorder figure is
reporting/plot_efficiency_eval.py.)

Usage:
  python summarize_efficiency.py          # uses get_run_dir() to auto-detect path
  python summarize_efficiency.py path/to/efficiency_eval.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
from utils.paths import ANALYSIS_ROOT, LOGS_ROOT, RESULTS_ROOT


def _log_sort_key(name: str) -> tuple[int, int]:
    m = re.match(r"D(\d+)_(\d+)", name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def load_efficiency(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def group_by_disorder(entries: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in sorted(entries, key=lambda x: _log_sort_key(x["log_file"])):
        did = re.match(r"(D\d+)", e["log_file"]).group(1)
        groups[did].append(e)
    return dict(sorted(groups.items(), key=lambda x: int(x[0][1:])))


TTFIN = "time_to_first_confident_narrowing"


def _stats(runs: list[dict]) -> dict:
    """Headline efficiency metrics (+ final accuracy) over `runs`. The
    1st-Confidence Turn mean is over episodes that reached it (its sentinel
    T+1 is excluded); `reached` is that share."""
    reached = [r[TTFIN] for r in runs if r[TTFIN] <= r["turn_count"]]
    return {
        "n":                   len(runs),
        "accuracy":            float(np.mean([r["final_accuracy"] for r in runs])),
        "turn_count":          float(np.mean([r["turn_count"] for r in runs])),
        "turn_count_std":      float(np.std([r["turn_count"] for r in runs])),
        "first_confident":     float(np.mean(reached)) if reached else float("nan"),
        "reached":             len(reached) / len(runs),
        "overcommitment_conf": float(np.mean([r["overcommitment_conf"] for r in runs])),
    }


# ── Text summary ─────────────────────────────────────────────────────────────

def _row(label: str, s: dict, name: str = "") -> str:
    return (
        f"{label:<6}  {s['n']:>4}  {s['turn_count']:>6.2f}  {s['turn_count_std']:>5.2f}  "
        f"{s['first_confident']:>7.2f}  {s['reached']:>7.1%}  {s['overcommitment_conf']:>7.2f}  "
        f"{s['accuracy']:>6.1%}  {name}"
    )


def write_summary(groups: dict[str, list[dict]], out_path: Path) -> None:
    SEP = "=" * 110
    HDR = "-" * 110
    header = (
        f"{'Code':<6}  {'N':>4}  {'Turns':>6}  {'±':>5}  "
        f"{'1stConf':>7}  {'Reached':>7}  {'OvCom':>7}  {'Acc':>6}  Disease Name"
    )
    lines = [SEP, "Diagnostic Efficiency Summary (evaluation_v5.md §3) + Final Accuracy", SEP, header, HDR]

    all_runs: list[dict] = []
    for did, runs in groups.items():
        all_runs.extend(runs)
        lines.append(_row(did, _stats(runs), runs[0]["ground_truth_name"]))
    lines.append(HDR)
    lines.append(_row("TOTAL", _stats(all_runs)))
    lines += [
        SEP,
        "",
        "Column descriptions:",
        "  Turns   : Total Turns — mean patient turns per episode (± = std)",
        "  1stConf : 1st-Confidence Turn — mean first turn at which the KG reference",
        "            candidate set == {doctor's final diagnosis}, over episodes that reached it",
        "  Reached : share of episodes that reached the 1st-confidence turn",
        "  OvCom   : Overcommitment Turns — mean (Total − 1st-Confidence), 0 if never reached",
        "  Acc     : Final Accuracy",
        SEP,
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:4 + len(groups) + 3]))
    print(f"Saved summary  → {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("json", nargs="?", type=Path, default=None,
                        help="Path to efficiency_eval.json (default: auto via get_run_dir)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Directory to write outputs (default: analysis/<run_dir>)")
    args = parser.parse_args()

    if args.json is None:
        from utils.llm import get_run_dir as _get_run_dir
        run_dir = _get_run_dir()
        args.json = RESULTS_ROOT / run_dir / "efficiency_eval.json"

    if not args.json.exists():
        print(f"[error] File not found: {args.json}", file=sys.stderr)
        sys.exit(1)

    if args.output is None:
        # Infer run_dir from json path: results/<run_dir>/efficiency_eval.json
        try:
            rel = args.json.resolve().parent.relative_to((RESULTS_ROOT).resolve())
            args.output = ANALYSIS_ROOT / rel
        except ValueError:
            args.output = args.json.parent

    args.output = args.output / "efficiency"
    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Input JSON : {args.json}")
    print(f"Output dir : {args.output}")

    entries = load_efficiency(args.json)
    groups  = group_by_disorder(entries)

    write_summary(groups, args.output / "efficiency_summary.txt")
    # Figure: reporting/plot_efficiency_eval.py (same output dir).


if __name__ == "__main__":
    main()
