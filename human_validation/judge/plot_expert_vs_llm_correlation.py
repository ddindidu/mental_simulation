#!/usr/bin/env python3
"""
Human Expert Validation — Expert vs. LLM-as-Judge Correlation

Compares 2 clinicians' manual ratings (human_validation/judge/expert_response/
doctor_전문가평가_{1,2}.xlsx, 46 cases each, same 46 cases for both experts) against
the automated LLM-as-judge metrics baked into the matching
human_validation/judge/kor/judge_<profile_id>__<doctor>_kor.xlsx sheet
("자동 평가 지표" section).

Expert xlsx layout (per sheet, one sheet per case): column D holds a 1-5
"감별진단 능력" (differential-diagnosis ability) rating entered at every
differential-diagnosis-turn row, column E holds a 1-5 "정보 습득 능력"
(information-acquisition ability) rating entered at every question-turn row,
and column F holds a single 1-5 "진단 근거 충분성" (evidence sufficiency)
rating entered once somewhere in the sheet (row position varies by expert).
Per-case expert score = mean of whatever non-empty values were found in each
column (order-independent, so this doesn't care exactly which row each rating
landed on).

NOTE on "judge model" splits: every one of the 92 kor xlsx (and hence all 46
expert-scored cases) comes from the run_batch_20260912 gpt-5.6-terra
patient/judge bucket only (human_validation/judge/generate_judge_xlsx.py
pins PATIENT_ROOT = "gpt-5.6-terra"); gemini-3.1-pro-preview-bucket episodes
were never sampled for expert scoring. So there is only one judge-model group
in this dataset — a per-judge split is not computable from what exists here.

NOTE on IAS: the kor/en xlsx's own "IAS (mean over turns)" cell was originally
sourced (by generate_judge_xlsx.py) from analysis/.../question_eval_semantic.json,
whose SemanticSimilarityMapper (tau=0.7 word-overlap threshold) almost never
fires — ~99.5% of turns got ias=0.0 there. Those source files have since been
corrected in place, and the xlsx IAS cells re-patched. This script now also
independently re-derives IAS straight from
results/gpt-5.6-terra/gpt-5.6-terra/<doctor>/question_eval.json's
episode_metrics.llm_judge.mean_ias (the authoritative source used throughout
reporting/plot_v4_*.py) rather than trusting the xlsx cell, as a second layer
of defense against this class of bug.

NOTE on Jaccard/Precision/Recall: same issue as IAS — the xlsx cell was built
from turn_eval.json's non-'_rigid' (loose, union-tier) fields, while every
other v4 figure in this repo (plot_v4_precision_vs_recall.py,
plot_metric_correlation_heatmap.py, ...) uses the '_rigid' (tier-priority
reference-candidate) fields. This script re-derives jaccard/precision/recall
as the mean-over-turns of *_rigid straight from turn_eval.json to match.

Usage:
  python human_validation/judge/plot_expert_vs_llm_correlation.py
"""
from __future__ import annotations

import csv
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import scipy.stats as scipy_stats

_CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
fm.fontManager.addfont(_CJK_FONT)
plt.rcParams["font.family"] = [fm.FontProperties(fname=_CJK_FONT).get_name(), "DejaVu Sans"]

import sys as _sys
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from utils.metric_compat import episode_mean_qts, turn_qts
from utils.turn_policy import OPENING_TURN, preceding_question_turn_to_policy
from reporting.ias_variants import IAS_VARIANT_KEYS, IAS_VARIANT_LABELS, episode_ias_variants
from reporting.plot_v4_radar_by_judge import DOCTOR_NAME_CANONICAL, PALETTE

_DOCTOR_MODEL_ORDER = ["gpt-5.4", "gemini-3.8-flash", "claude-sonnet-5", "qwen3-235b", "llama-3.3-70b-instruct"]


def _doctor_order_rank(doctor: str) -> int:
    d = doctor.lower()
    return _DOCTOR_MODEL_ORDER.index(d) if d in _DOCTOR_MODEL_ORDER else len(_DOCTOR_MODEL_ORDER)

EXPERT_DIR = _THIS_DIR / "expert_response"
KOR_DIR = _THIS_DIR / "kor"
RESULTS_BASE = _REPO_ROOT / "saved" / "run_batch_20260912" / "results" / "gpt-5.6-terra" / "gpt-5.6-terra"
ANALYSIS_BASE = _REPO_ROOT / "saved" / "run_batch_20260912" / "analysis" / "gpt-5.6-terra" / "gpt-5.6-terra"
OUT_PATH = _THIS_DIR / "expert_vs_llm_correlation.png"
SPEARMAN_OUT_PATH = _THIS_DIR / "expert_vs_llm_correlation_spearman.png"
IAS_NONZERO_OUT_PATH = _THIS_DIR / "expert_vs_llm_correlation_ias_nonzero.png"
IAS_VARIANTS_SCATTER_OUT_PATH = _THIS_DIR / "expert_vs_llm_ias_variants_scatter.png"
SCATTER_OUT_PATH = _THIS_DIR / "expert_vs_llm_scatter.png"
TERNARY_SCATTER_OUT_PATH = _THIS_DIR / "expert_vs_llm_scatter_ternary.png"
DOCTOR_TURN_BOXPLOT_OUT_PATH = _THIS_DIR / "expert_turn_ratings_by_doctor.png"
EXPERT_RADAR_OUT_PATH = _THIS_DIR / "expert_ratings_radar_by_doctor.png"
TURN_SCATTER_OUT_PATH = _THIS_DIR / "expert_vs_llm_scatter_turn_level.png"
CSV_OUT_PATH = _THIS_DIR / "expert_vs_llm_responses.csv"

LLM_METRIC_KEYS = [
    "jaccard", "precision", "recall", "ias", "ecr", "turn_count",
    "turn_to_1st_confident", "final_accuracy", "diagnostic_evidence_sufficiency_pred",
] + IAS_VARIANT_KEYS

EXPERT_DIMS = ["diff_diag", "info_acq", "evidence_suff"]
EXPERT_DIM_LABELS = {
    "diff_diag": "감별진단능력\n(Differential Dx)",
    "info_acq": "정보습득능력\n(Info. Acquisition)",
    "evidence_suff": "진단근거충분성\n(Evidence Sufficiency)",
}

AUTO_METRICS = ["jaccard", "ias", "diagnostic_evidence_sufficiency_pred"]
AUTO_METRIC_LABELS = {
    "jaccard": "Jaccard (rigid)\n(자카드 유사도)",
    "ias": "IAS\n(정보습득점수)",
    "diagnostic_evidence_sufficiency_pred": "Evidence Sufficiency (pred)\n(진단 근거 충분성(자동, doctor 진단 기준))",
}

KOR_LABEL_TO_KEY = {
    "자카드 유사도 (턴 평균)": "jaccard",
    "정밀도 (턴 평균)": "precision",
    "재현율 (턴 평균)": "recall",
    "정보습득점수 IAS (턴 평균)": "ias",
    "후보축소기대값 ECR (턴 평균)": "ecr",
    "총 턴 수": "turn_count",
    "첫 확신적 후보 축소까지의 턴 수": "turn_to_1st_confident",
    "최종 진단 정확도": "final_accuracy",
    # NOTE: this must match the literal label text already baked into the
    # existing kor/*.xlsx cells (generate_judge_xlsx_kor.py's label was
    # renamed going forward, but the 92 already-generated files on disk
    # still say the old Korean text — not regenerated as part of this rename).
    "진단적 추론 능력 (overall_score)": "diagnostic_evidence_sufficiency_gt",
}


_TURN_RE = re.compile(r"(\d+)번째\s*턴")


def _sheet_uses_policy_numbering(ws) -> bool:
    """Sheets generated under utils/turn_policy.py start the transcript with a
    '[0번째 턴 · 의사 첫 질문]' row. The expert_response/ sheets predate that
    and number each question with the patient response that FOLLOWS it."""
    for row in ws.iter_rows(values_only=True):
        text = row[2] if len(row) > 2 else None
        if isinstance(text, str) and (m := _TURN_RE.search(text)) and int(m.group(1)) == OPENING_TURN:
            return True
    return False


def _row_turn(text, policy_numbering: bool) -> int | None:
    """Policy turn of a transcript row (utils/turn_policy.py), or None if the
    row isn't a transcript row. Question rows in old-layout sheets are
    shifted onto the policy (sheet 'N번째 턴 · 의사 질문' -> turn N − 1)."""
    if not isinstance(text, str) or not (m := _TURN_RE.search(text)):
        return None
    turn = int(m.group(1))
    if "의사 질문" in text and not policy_numbering:
        turn = preceding_question_turn_to_policy(turn)
    return turn


def parse_expert_file(path: Path) -> dict[str, dict[str, float]]:
    """sheet -> {profile_id, diff_diag, info_acq, evidence_suff}.

    info_acq excludes any rating on the opening question (turn 0 is not a
    turn under utils/turn_policy.py — QTS never scores it either)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    out = {}
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        header = ws.cell(row=1, column=2).value
        if not header or "/" not in str(header):
            continue
        profile_id = str(header).split("/")[0].strip()

        policy_numbering = _sheet_uses_policy_numbering(ws)
        diff_vals, info_vals, evid_vals = [], [], []
        for row in ws.iter_rows(min_row=1, values_only=True):
            if len(row) > 3 and isinstance(row[3], (int, float)):
                diff_vals.append(float(row[3]))
            if (len(row) > 4 and isinstance(row[4], (int, float))
                    and _row_turn(row[2] if len(row) > 2 else None, policy_numbering) != OPENING_TURN):
                info_vals.append(float(row[4]))
            if len(row) > 5 and isinstance(row[5], (int, float)):
                evid_vals.append(float(row[5]))

        if not (diff_vals or info_vals or evid_vals):
            continue
        out[profile_id] = {
            "diff_diag": float(np.mean(diff_vals)) if diff_vals else None,
            "info_acq": float(np.mean(info_vals)) if info_vals else None,
            "evidence_suff": float(np.mean(evid_vals)) if evid_vals else None,
        }
    return out


def parse_expert_turns(path: Path) -> dict[str, dict[str, dict[int, float]]]:
    """sheet -> {profile_id, diff_diag: {turn: value}, info_acq: {turn: value}}.

    Turns follow utils/turn_policy.py (turn t = patient response t, the
    differential after it, and the doctor's next question; the opening
    question is turn 0 and is dropped). Parsed from the Doctor-column text
    ("[N번째 턴 · ...]"): 감별진단 ratings (col D) live on '...의사의 감별진단'
    rows, 정보습득 ratings (col E) on '...의사 질문' rows — in old-layout sheets
    a question row labelled N is the question of turn N − 1 (see _row_turn), so
    it lines up with QTS at turn N − 1. 진단근거충분성 (col F) has no turn."""
    wb = openpyxl.load_workbook(path, data_only=True)
    out: dict[str, dict[str, dict[int, float]]] = {}
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        header = ws.cell(row=1, column=2).value
        if not header or "/" not in str(header):
            continue
        profile_id = str(header).split("/")[0].strip()

        policy_numbering = _sheet_uses_policy_numbering(ws)
        diff_by_turn: dict[int, float] = {}
        info_by_turn: dict[int, float] = {}
        for row in ws.iter_rows(min_row=1, values_only=True):
            turn = _row_turn(row[2] if len(row) > 2 else None, policy_numbering)
            if turn is None:
                continue
            if len(row) > 3 and isinstance(row[3], (int, float)):
                diff_by_turn[turn] = float(row[3])
            if len(row) > 4 and isinstance(row[4], (int, float)) and turn != OPENING_TURN:
                info_by_turn[turn] = float(row[4])

        if diff_by_turn or info_by_turn:
            out[profile_id] = {"diff_diag": diff_by_turn, "info_acq": info_by_turn}
    return out


def parse_kor_metrics(path: Path) -> dict[str, float]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    out = {}
    for row in ws.iter_rows(min_row=1, max_row=13, values_only=True):
        label = row[0]
        if label in KOR_LABEL_TO_KEY and isinstance(row[1], (int, float)):
            out[KOR_LABEL_TO_KEY[label]] = float(row[1])
    return out


def find_kor_file(profile_id: str) -> Path | None:
    matches = sorted(KOR_DIR.glob(f"judge_{profile_id}__*_kor.xlsx"))
    return matches[0] if matches else None


def doctor_from_kor_path(path: Path) -> str:
    # judge_<profile_id>__<doctor>_kor.xlsx
    stem = path.stem  # judge_<profile_id>__<doctor>_kor
    return stem.rsplit("__", 1)[1].removesuffix("_kor")


_mean_ias_cache: dict[str, dict[str, float]] = {}


def authoritative_mean_ias(doctor: str, profile_id: str) -> float | None:
    """episode_metrics.llm_judge.mean_ias from results/.../question_eval.json —
    the source used throughout reporting/plot_v4_*.py, not the (previously
    broken) question_eval_semantic.json the xlsx IAS cell was derived from."""
    if doctor not in _mean_ias_cache:
        path = RESULTS_BASE / doctor / "question_eval.json"
        by_log = {}
        if path.exists():
            for entry in json.loads(path.read_text(encoding="utf-8")):
                lf = entry.get("log_file")
                v = episode_mean_qts(entry)
                if lf is not None:
                    by_log[lf] = v
        _mean_ias_cache[doctor] = by_log
    return _mean_ias_cache[doctor].get(f"{profile_id}_plain")


_ias_variant_cache: dict[str, dict[str, dict[str, float]]] = {}


def authoritative_ias_variants(doctor: str, profile_id: str) -> dict[str, float] | None:
    """Episode-mean IAS under the 3 informative-set definitions in
    reporting/ias_variants.py (disc-only / +mandatory [current] / +optional),
    from results/.../question_eval.json — same source as authoritative_mean_ias."""
    if doctor not in _ias_variant_cache:
        path = RESULTS_BASE / doctor / "question_eval.json"
        by_log: dict[str, dict[str, float]] = {}
        if path.exists():
            for entry in json.loads(path.read_text(encoding="utf-8")):
                lf = entry.get("log_file")
                if lf is None:
                    continue
                means = episode_ias_variants(entry, mapper="llm_judge")
                if means is not None:
                    by_log[lf] = means
        _ias_variant_cache[doctor] = by_log
    return _ias_variant_cache[doctor].get(f"{profile_id}_plain")


_pred_score_cache: dict[str, dict[str, float]] = {}


def authoritative_overall_score_pred(doctor: str, profile_id: str) -> float | None:
    """overall_score_pred from results/.../diagnostic_reasoning_eval.json — the
    doctor's-own-final-diagnosis-based evidence sufficiency score (as opposed
    to overall_score_gt, which the kor xlsx cell / KOR_LABEL_TO_KEY bakes in).
    Not present in any existing xlsx, so always re-derived from source here."""
    if doctor not in _pred_score_cache:
        path = RESULTS_BASE / doctor / "diagnostic_reasoning_eval.json"
        by_log: dict[str, float] = {}
        if path.exists():
            for entry in json.loads(path.read_text(encoding="utf-8")):
                lf = entry.get("log_file")
                v = entry.get("overall_score_pred")
                if lf is not None and v is not None:
                    by_log[lf] = float(v)
        _pred_score_cache[doctor] = by_log
    return _pred_score_cache[doctor].get(f"{profile_id}_plain")


_rigid_cache: dict[str, dict[str, dict[str, list[float]]]] = {}


def authoritative_rigid_means(doctor: str, profile_id: str) -> dict[str, float | None]:
    """Mean-over-turns of jaccard_rigid/precision_rigid/recall_rigid from
    analysis/.../turn_eval.json — the tier-priority reference-candidate
    definition used throughout reporting/plot_v4_precision_vs_recall.py and
    plot_metric_correlation_heatmap.py, in place of the non-'_rigid' (loose,
    union-tier) fields generate_judge_xlsx.py's scores_table() actually reads
    (t.get('jaccard') / t.get('precision') / t.get('recall'))."""
    if doctor not in _rigid_cache:
        path = ANALYSIS_BASE / doctor / "turn_eval.json"
        by_log: dict[str, dict[str, list[float]]] = {}
        if path.exists():
            for row in json.loads(path.read_text(encoding="utf-8")):
                lf = row.get("log_file")
                if lf is None:
                    continue
                entry = by_log.setdefault(lf, {"jaccard": [], "precision": [], "recall": []})
                for key, rigid_key in (("jaccard", "jaccard_rigid"),
                                        ("precision", "precision_rigid"),
                                        ("recall", "recall_rigid")):
                    v = row.get(rigid_key)
                    if v is not None:
                        entry[key].append(float(v))
        _rigid_cache[doctor] = by_log
    per_turn = _rigid_cache[doctor].get(f"{profile_id}_plain", {})
    return {
        k: (float(np.mean(vals)) if vals else None)
        for k, vals in per_turn.items()
    } if per_turn else {"jaccard": None, "precision": None, "recall": None}


_turn_rigid_cache: dict[tuple[str, str], dict[str, dict[int, float]]] = {}


def turn_rigid_field(doctor: str, profile_id: str, field: str) -> dict[int, float]:
    """turn -> <field> (e.g. 'jaccard_rigid', 'precision_rigid', 'recall_rigid'),
    from analysis/.../turn_eval.json (per-turn, not averaged) — for turn-level
    correlation against the expert's per-turn 감별진단능력 rating."""
    cache_key = (doctor, field)
    if cache_key not in _turn_rigid_cache:
        path = ANALYSIS_BASE / doctor / "turn_eval.json"
        by_log: dict[str, dict[int, float]] = {}
        if path.exists():
            for row in json.loads(path.read_text(encoding="utf-8")):
                lf = row.get("log_file")
                turn = row.get("turn")
                v = row.get(field)
                if lf is not None and turn is not None and v is not None:
                    by_log.setdefault(lf, {})[int(turn)] = float(v)
        _turn_rigid_cache[cache_key] = by_log
    return _turn_rigid_cache[cache_key].get(f"{profile_id}_plain", {})


def turn_jaccard_rigid(doctor: str, profile_id: str) -> dict[int, float]:
    return turn_rigid_field(doctor, profile_id, "jaccard_rigid")


_turn_ias_cache: dict[str, dict[str, dict[int, float]]] = {}


def turn_ias(doctor: str, profile_id: str) -> dict[int, float]:
    """turn -> ias (llm_judge mapper), from results/.../question_eval.json
    (per-turn, not averaged) — for turn-level correlation against the
    expert's per-turn 정보습득능력 rating."""
    if doctor not in _turn_ias_cache:
        path = RESULTS_BASE / doctor / "question_eval.json"
        by_log: dict[str, dict[int, float]] = {}
        if path.exists():
            for entry in json.loads(path.read_text(encoding="utf-8")):
                lf = entry.get("log_file")
                if lf is None:
                    continue
                per_turn = {}
                for t in entry.get("turns", []):
                    turn = t.get("turn")
                    v = turn_qts((t.get("scores_by_mapper") or {}).get("llm_judge", {}))
                    if turn is not None and v is not None:
                        per_turn[int(turn)] = float(v)
                by_log[lf] = per_turn
        _turn_ias_cache[doctor] = by_log
    return _turn_ias_cache[doctor].get(f"{profile_id}_plain", {})


def pearson(xs: list[float], ys: list[float]) -> tuple[float | None, int]:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return None, n
    xa = np.array([p[0] for p in pairs])
    ya = np.array([p[1] for p in pairs])
    if np.std(xa) == 0 or np.std(ya) == 0:
        return None, n
    return float(np.corrcoef(xa, ya)[0, 1]), n


def spearman(xs: list[float], ys: list[float]) -> tuple[float | None, int]:
    """Rank correlation — more appropriate than Pearson here since expert
    ratings are an ordinal 1-5 Likert scale (heavily tied) and automated
    metrics are often piled up at 0/1; Spearman only assumes a monotonic
    relationship, not linear-on-the-raw-scale."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return None, n
    xa = np.array([p[0] for p in pairs])
    ya = np.array([p[1] for p in pairs])
    if np.std(xa) == 0 or np.std(ya) == 0:
        return None, n
    rho, _p = scipy_stats.spearmanr(xa, ya)
    return float(rho), n


def icc_2_1(xs: list[float], ys: list[float]) -> tuple[float | None, int]:
    """ICC(2,1): two-way random-effects, single-rater, absolute-agreement
    intraclass correlation (Shrout & Fleiss, 1979) between two raters sharing
    the SAME scale — i.e. only meaningful for expert1-vs-expert2 IAA (both
    1-5 Likert). Automated metrics (0-1) and expert ratings (1-5) are on
    different scales, so ICC between them would conflate "different scale"
    with "different judgment" and is not reported here; use Spearman for
    that comparison instead."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return None, n
    data = np.array(pairs)  # (n, 2): columns = the 2 raters
    k = 2
    subj_means = data.mean(axis=1)
    rater_means = data.mean(axis=0)
    grand_mean = data.mean()

    ss_total = np.sum((data - grand_mean) ** 2)
    ss_rows = k * np.sum((subj_means - grand_mean) ** 2)          # between-subjects
    ss_cols = n * np.sum((rater_means - grand_mean) ** 2)          # between-raters
    ss_error = ss_total - ss_rows - ss_cols

    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))

    denom = ms_rows + (k - 1) * ms_error + (k / n) * (ms_cols - ms_error)
    if denom == 0:
        return None, n
    icc = (ms_rows - ms_error) / denom
    return float(icc), n


# ── Binary / ternary discretization of the 1-5 expert rating ──────────────
# Cut points as specified: binary bad=[1,3) good=[3,5]; ternary
# bad=[1,2.5) neutral=[2.5,3.5] good=(3.5,5].
def label_binary(v: float | None) -> int | None:
    if v is None:
        return None
    return 1 if v >= 3.0 else 0


def tercile_cuts(values: list[float]) -> tuple[float, float]:
    """Data-driven ternary cut points: the 33rd/66th percentile of the actual
    per-dimension distribution, instead of the fixed [2.5, 3.5] cut — used
    because diff_diag's ratings cluster tightly around 2.5-3.5 (29/45 land in
    'neutral' under the fixed cut, only 3 in 'good'), which starves the
    ternary label of variance regardless of how well the automated metric
    actually tracks it. Each dimension gets its own cuts since their
    distributions differ (info_acq and evidence_suff are not as degenerate
    under the fixed cut)."""
    vals = [v for v in values if v is not None]
    lo, hi = np.percentile(vals, [100 / 3, 200 / 3])
    return float(lo), float(hi)


def label_ternary(v: float | None, lo: float, hi: float) -> int | None:
    if v is None:
        return None
    if v < lo:
        return 0  # bad
    if v <= hi:
        return 1  # neutral
    return 2  # good


def auroc(scores: list[float], labels: list[int]) -> tuple[float | None, int, int]:
    """AUROC of `scores` as a predictor of the binary `labels` (1=good), via
    the rank-sum formula (equivalent to Mann-Whitney U / n_pos / n_neg) —
    no sklearn dependency needed."""
    pairs = [(s, l) for s, l in zip(scores, labels) if s is not None and l is not None]
    if not pairs:
        return None, 0, 0
    s_arr = np.array([p[0] for p in pairs])
    l_arr = np.array([p[1] for p in pairs])
    n_pos = int(np.sum(l_arr == 1))
    n_neg = int(np.sum(l_arr == 0))
    if n_pos == 0 or n_neg == 0:
        return None, n_pos, n_neg
    ranks = scipy_stats.rankdata(s_arr)
    rank_sum_pos = ranks[l_arr == 1].sum()
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2
    return float(u / (n_pos * n_neg)), n_pos, n_neg


def draw_heatmap(matrix: np.ndarray, row_labels: list[str], col_labels: list[str],
                  title: str, out_path: Path, n: int, cbar_label: str = "Pearson correlation (r)") -> None:
    cmap = plt.get_cmap("RdBu").copy()
    fig, ax = plt.subplots(figsize=(7.2, 5.6))
    im = ax.imshow(matrix, cmap=cmap, vmin=-1, vmax=1, aspect="equal")

    for a in range(matrix.shape[0]):
        for b in range(matrix.shape[1]):
            v = matrix[a, b]
            text = "n/a" if np.isnan(v) else f"{v:.2f}"
            color = "white" if (not np.isnan(v) and abs(v) > 0.6) else "#2a2a28"
            ax.text(b, a, text, ha="center", va="center", fontsize=13, color=color)

    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=11)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=11)
    ax.set_xticks(np.arange(-0.5, len(col_labels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(row_labels), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5)
    ax.tick_params(which="minor", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(cbar_label, fontsize=11)
    cbar.ax.tick_params(labelsize=9)

    ax.set_title(f"{title}\n(n = {n} cases)", fontsize=12.5, fontweight="bold", pad=12)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"[saved] {out_path}")


SCATTER_PAIRS = [
    ("jaccard", "diff_diag", "Jaccard (rigid)", "감별진단능력\n(Differential Dx)"),
    ("ias", "info_acq", "IAS", "정보습득능력\n(Info. Acquisition)"),
    ("diagnostic_evidence_sufficiency_pred", "evidence_suff",
     "Diagnostic Evidence Sufficiency\n(overall_score_pred)", "진단근거충분성\n(Evidence Sufficiency)"),
]


def draw_scatter(joined_ids: list[str], llm_metrics: dict[str, dict[str, float]],
                  avg_expert: dict[str, dict[str, float]], out_path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, (auto_key, dim, x_label, y_label) in zip(axes, SCATTER_PAIRS):
        xs = [llm_metrics[i].get(auto_key) for i in joined_ids]
        ys = [avg_expert[i][dim] for i in joined_ids]
        pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
        xa = np.array([p[0] for p in pairs])
        ya = np.array([p[1] for p in pairs])

        ax.scatter(xa, ya, color="#0072B2", alpha=0.6, s=60,
                   edgecolors="white", linewidths=0.6, zorder=3)

        r, n = pearson(list(xa), list(ya))
        if n >= 2 and np.std(xa) > 0:
            slope, intercept = np.polyfit(xa, ya, 1)
            x_line = np.linspace(xa.min(), xa.max(), 100)
            ax.plot(x_line, slope * x_line + intercept, color="#D55E00",
                    linewidth=1.8, zorder=2)
        r_str = f"{r:.3f}" if r is not None else "n/a"
        ax.text(0.05, 0.95, f"r = {r_str}\nn = {n}", transform=ax.transAxes,
                fontsize=12, va="top", ha="left",
                bbox=dict(boxstyle="round", facecolor="white", edgecolor="#cccccc", alpha=0.9))

        ax.set_xlabel(x_label, fontsize=12)
        ax.set_ylabel(y_label, fontsize=12)
        ax.tick_params(axis="both", labelsize=10)
        ax.grid(color="#e1e0d9", linewidth=1, zorder=0)
        ax.set_axisbelow(True)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

    fig.suptitle("Automated Metric vs. Expert Rating (matched dimensions)",
                  fontsize=14, fontweight="bold")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"[saved] {out_path}")


TERNARY_COLORS = {0: "#D55E00", 1: "#999999", 2: "#009E73"}  # bad / neutral / good
TERNARY_LABELS_KO = {0: "Bad", 1: "Neutral", 2: "Good"}


RADAR_AXES = [
    ("감별진단능력\n(turn-level mean)", "diff_diag"),
    ("정보습득능력\n(turn-level mean)", "info_acq"),
    ("진단근거충분성\n(episode-level mean)", "evidence_suff"),
]


def draw_expert_radar(by_doctor: dict[str, dict[str, float]], out_path: Path) -> None:
    """by_doctor[doctor] = {'diff_diag': mean, 'info_acq': mean, 'evidence_suff': mean}
    — z-scored per axis across the doctors shown (same convention as
    reporting/plot_v4_radar_by_judge.py), one polygon per doctor. All 3 axes
    are "higher = better" expert ratings, so no sign-flip is needed."""
    doctors = sorted(by_doctor, key=_doctor_order_rank)
    raw = np.array([[by_doctor[d][key] for d in doctors] for _label, key in RADAR_AXES])  # axes x doctors

    mean = raw.mean(axis=1, keepdims=True)
    std = raw.std(axis=1, keepdims=True)
    std[std == 0] = 1.0
    z = (raw - mean) / std

    n_axes = len(RADAR_AXES)
    angles = np.linspace(0, 2 * np.pi, n_axes, endpoint=False).tolist()
    angles += angles[:1]
    zlim = max(0.5, np.ceil(np.abs(z).max() * 2) / 2)

    fig, ax = plt.subplots(figsize=(7.5, 7.5), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([label for label, _key in RADAR_AXES], fontsize=13)
    ax.set_ylim(-zlim, zlim)
    yticks = np.linspace(-zlim, zlim, 5)
    ax.set_yticks(yticks)
    ax.set_yticklabels([f"{t:+.1f}σ" for t in yticks], fontsize=9, color="gray")
    ax.grid(color="lightgray", linewidth=0.7)
    ax.spines["polar"].set_color("lightgray")

    for j, doctor in enumerate(doctors):
        vals = z[:, j].tolist()
        vals += vals[:1]
        color = PALETTE[_doctor_order_rank(doctor) % len(PALETTE)]
        label = DOCTOR_NAME_CANONICAL.get(doctor, doctor)
        ax.plot(angles, vals, color=color, linewidth=2, label=label)
        ax.fill(angles, vals, color=color, alpha=0.08)
        ax.scatter(angles[:-1], vals[:-1], color=color, s=28, zorder=3)

    ax.legend(loc="upper right", bbox_to_anchor=(1.32, 1.1), fontsize=10, frameon=False)
    fig.suptitle("Expert Ratings by Doctor Model (z-score across models)",
                  fontsize=13, fontweight="bold", y=0.98)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"[saved] {out_path}")


def draw_doctor_turn_boxplot(diff_diag_turns_by_doctor: dict[str, list[float]],
                              info_acq_turns_by_doctor: dict[str, list[float]],
                              out_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5))
    panels = [
        (axes[0], diff_diag_turns_by_doctor, "감별진단능력 (turn-level)\n(Differential Dx)"),
        (axes[1], info_acq_turns_by_doctor, "정보습득능력 (turn-level)\n(Info. Acquisition)"),
    ]
    for ax, by_doctor, y_label in panels:
        doctors = sorted(by_doctor, key=_doctor_order_rank)
        data = [by_doctor[d] for d in doctors]
        labels = [DOCTOR_NAME_CANONICAL.get(d, d) for d in doctors]
        bp = ax.boxplot(data, labels=labels, patch_artist=True, showmeans=True,
                         medianprops=dict(color="#1C2333", linewidth=1.5),
                         meanprops=dict(marker="D", markerfacecolor="#D55E00",
                                        markeredgecolor="white", markersize=6))
        for patch in bp["boxes"]:
            patch.set_facecolor("#A6CEE3")
            patch.set_alpha(0.8)
        for i, d in enumerate(doctors):
            n = len(by_doctor[d])
            ax.text(i + 1, ax.get_ylim()[0], f"n={n}", ha="center", va="bottom",
                    fontsize=9, color="#666666")
        ax.set_ylabel(y_label, fontsize=12)
        ax.tick_params(axis="x", labelsize=10, rotation=20)
        ax.tick_params(axis="y", labelsize=10)
        ax.grid(axis="y", color="#e1e0d9", linewidth=1, zorder=0)
        ax.set_axisbelow(True)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

    fig.suptitle("Expert Turn-Level Ratings by Doctor Model", fontsize=14, fontweight="bold")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"[saved] {out_path}")


def draw_ternary_scatter(joined_ids: list[str], llm_metrics: dict[str, dict[str, float]],
                          avg_expert: dict[str, dict[str, float]],
                          ternary_labels_by_pid: dict[str, dict[str, int | None]],
                          ternary_cuts_by_dim: dict[str, tuple[float, float]],
                          out_path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, (auto_key, dim, x_label, y_label) in zip(axes, SCATTER_PAIRS):
        lo, hi = ternary_cuts_by_dim[dim]
        for cat in (0, 1, 2):
            xs = [llm_metrics[i].get(auto_key) for i in joined_ids
                  if ternary_labels_by_pid[i][dim] == cat]
            ys = [avg_expert[i][dim] for i in joined_ids
                  if ternary_labels_by_pid[i][dim] == cat]
            pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
            if not pairs:
                continue
            ax.scatter([p[0] for p in pairs], [p[1] for p in pairs],
                       color=TERNARY_COLORS[cat], alpha=0.75, s=65,
                       edgecolors="white", linewidths=0.6, zorder=3,
                       label=f"{TERNARY_LABELS_KO[cat]} (n={len(pairs)})")

        ax.axhline(lo, color="#999999", linestyle="--", linewidth=1, zorder=1)
        ax.axhline(hi, color="#999999", linestyle="--", linewidth=1, zorder=1)

        all_xs = [llm_metrics[i].get(auto_key) for i in joined_ids]
        all_ys = [avg_expert[i][dim] for i in joined_ids]
        rho, n = spearman(
            all_xs,
            [float(ternary_labels_by_pid[i][dim]) if ternary_labels_by_pid[i][dim] is not None else None
             for i in joined_ids],
        )
        rho_str = f"{rho:.3f}" if rho is not None else "n/a"
        ax.text(0.05, 0.95, f"Spearman ρ (vs. tercile label) = {rho_str}\nn = {n}",
                transform=ax.transAxes, fontsize=11, va="top", ha="left",
                bbox=dict(boxstyle="round", facecolor="white", edgecolor="#cccccc", alpha=0.9))

        ax.set_xlabel(x_label, fontsize=12)
        ax.set_ylabel(y_label, fontsize=12)
        ax.tick_params(axis="both", labelsize=10)
        ax.grid(color="#e1e0d9", linewidth=1, zorder=0)
        ax.set_axisbelow(True)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        ax.legend(fontsize=9, loc="lower right")

    fig.suptitle("Automated Metric vs. Expert Rating, colored by data-driven tercile "
                  "(bad / neutral / good)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"[saved] {out_path}")


TURN_SCATTER_PANELS = [
    ("jaccard_rigid (turn)", "감별진단능력 (turn)\n(Differential Dx)"),
    ("IAS (turn)", "정보습득능력 (turn)\n(Info. Acquisition)"),
]


def draw_turn_scatter(turn_jaccard_pairs: list[tuple[float, float]],
                       turn_ias_pairs: list[tuple[float, float]],
                       out_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2))
    rng = np.random.default_rng(0)

    for ax, pairs, (x_label, y_label) in zip(
        axes, (turn_jaccard_pairs, turn_ias_pairs), TURN_SCATTER_PANELS
    ):
        xa = np.array([p[0] for p in pairs])
        ya = np.array([p[1] for p in pairs])
        # y is a discrete 1-5 rating averaged over <=2 experts (so still
        # heavily tied) with hundreds of points — jitter for visibility only,
        # the fit line and r use the unjittered values.
        y_jitter = ya + rng.uniform(-0.06, 0.06, size=len(ya))

        ax.scatter(xa, y_jitter, color="#0072B2", alpha=0.35, s=28,
                   edgecolors="none", zorder=3)

        r, n = pearson(list(xa), list(ya))
        if n >= 2 and np.std(xa) > 0:
            slope, intercept = np.polyfit(xa, ya, 1)
            x_line = np.linspace(xa.min(), xa.max(), 100)
            ax.plot(x_line, slope * x_line + intercept, color="#D55E00",
                    linewidth=2.0, zorder=4)
        r_str = f"{r:.3f}" if r is not None else "n/a"
        ax.text(0.05, 0.95, f"r = {r_str}\nn = {n}", transform=ax.transAxes,
                fontsize=12, va="top", ha="left",
                bbox=dict(boxstyle="round", facecolor="white", edgecolor="#cccccc", alpha=0.9))

        ax.set_xlabel(x_label, fontsize=12)
        ax.set_ylabel(y_label, fontsize=12)
        ax.tick_params(axis="both", labelsize=10)
        ax.grid(color="#e1e0d9", linewidth=1, zorder=0)
        ax.set_axisbelow(True)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

    fig.suptitle("Turn-level: Automated Metric vs. Expert Rating\n"
                  "(one point per rated turn, not per case; y jittered for visibility)",
                  fontsize=13, fontweight="bold")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"[saved] {out_path}")


def draw_ias_variant_scatter(joined_ids: list[str], llm_metrics: dict[str, dict[str, float]],
                              avg_expert: dict[str, dict[str, float]], out_path: Path) -> None:
    fig, axes = plt.subplots(1, len(IAS_VARIANT_KEYS), figsize=(5.2 * len(IAS_VARIANT_KEYS), 5))
    for ax, k in zip(axes, IAS_VARIANT_KEYS):
        xs = [llm_metrics[i].get(k) for i in joined_ids]
        ys = [avg_expert[i]["info_acq"] for i in joined_ids]
        pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
        xa = np.array([p[0] for p in pairs])
        ya = np.array([p[1] for p in pairs])

        ax.scatter(xa, ya, color="#009E73", alpha=0.6, s=60,
                   edgecolors="white", linewidths=0.6, zorder=3)

        r, n = pearson(list(xa), list(ya))
        rho, _ = spearman(list(xa), list(ya))
        if n >= 2 and np.std(xa) > 0:
            slope, intercept = np.polyfit(xa, ya, 1)
            x_line = np.linspace(xa.min(), xa.max(), 100)
            ax.plot(x_line, slope * x_line + intercept, color="#D55E00", linewidth=1.8, zorder=2)
        r_str = f"{r:.3f}" if r is not None else "n/a"
        rho_str = f"{rho:.3f}" if rho is not None else "n/a"
        ax.text(0.05, 0.95, f"Pearson r = {r_str}\nSpearman ρ = {rho_str}\nn = {n}",
                transform=ax.transAxes, fontsize=11, va="top", ha="left",
                bbox=dict(boxstyle="round", facecolor="white", edgecolor="#cccccc", alpha=0.9))

        ax.set_xlabel(IAS_VARIANT_LABELS[k], fontsize=11)
        ax.set_ylabel("정보습득능력\n(Info. Acquisition)", fontsize=12)
        ax.tick_params(axis="both", labelsize=10)
        ax.grid(color="#e1e0d9", linewidth=1, zorder=0)
        ax.set_axisbelow(True)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

    fig.suptitle("IAS Variants vs. Expert 정보습득능력 (episode-level)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"[saved] {out_path}")


def main() -> None:
    expert_paths = sorted(EXPERT_DIR.glob("*_1.xlsx")) + sorted(EXPERT_DIR.glob("*_2.xlsx"))
    if len(expert_paths) != 2:
        raise SystemExit(f"Expected 2 expert files, found {len(expert_paths)}: {expert_paths}")

    expert1 = parse_expert_file(expert_paths[0])
    expert2 = parse_expert_file(expert_paths[1])
    print(f"Expert 1 ({expert_paths[0].name}): {len(expert1)} cases")
    print(f"Expert 2 ({expert_paths[1].name}): {len(expert2)} cases")

    common_ids = sorted(set(expert1) & set(expert2))
    print(f"Common cases (both experts): {len(common_ids)}")

    expert1_turns = parse_expert_turns(expert_paths[0])
    expert2_turns = parse_expert_turns(expert_paths[1])

    # ── IAA between the two experts ─────────────────────────────────────
    # Both experts use the same 1-5 scale, so ICC(2,1) (absolute agreement)
    # is reported here as well as Pearson/Spearman.
    print("\n=== Inter-Annotator Agreement (Expert 1 vs Expert 2) ===")
    for dim in EXPERT_DIMS:
        xs = [expert1[i][dim] for i in common_ids]
        ys = [expert2[i][dim] for i in common_ids]
        r, n = pearson(xs, ys)
        rho, _ = spearman(xs, ys)
        icc, _ = icc_2_1(xs, ys)
        r_str = f"{r:.3f}" if r is not None else "n/a"
        rho_str = f"{rho:.3f}" if rho is not None else "n/a"
        icc_str = f"{icc:.3f}" if icc is not None else "n/a"
        print(f"  {dim:15s} Pearson r={r_str}  Spearman ρ={rho_str}  ICC(2,1)={icc_str}  (n={n})")

    # ── average expert score per case ───────────────────────────────────
    avg_expert: dict[str, dict[str, float]] = {}
    for pid in common_ids:
        avg_expert[pid] = {}
        for dim in EXPERT_DIMS:
            v1, v2 = expert1[pid][dim], expert2[pid][dim]
            vals = [v for v in (v1, v2) if v is not None]
            avg_expert[pid][dim] = float(np.mean(vals)) if vals else None

    # ── join with LLM-as-judge automated metrics ────────────────────────
    llm_metrics: dict[str, dict[str, float]] = {}
    doctor_of: dict[str, str] = {}
    missing = []
    for pid in common_ids:
        kor_path = find_kor_file(pid)
        if kor_path is None:
            missing.append(pid)
            continue
        metrics = parse_kor_metrics(kor_path)
        doctor = doctor_from_kor_path(kor_path)
        correct_ias = authoritative_mean_ias(doctor, pid)
        if correct_ias is not None:
            metrics["ias"] = correct_ias
        ias_variants = authoritative_ias_variants(doctor, pid)
        if ias_variants is not None:
            metrics.update(ias_variants)
        rigid = authoritative_rigid_means(doctor, pid)
        for k, v in rigid.items():
            if v is not None:
                metrics[k] = v
        pred_score = authoritative_overall_score_pred(doctor, pid)
        if pred_score is not None:
            metrics["diagnostic_evidence_sufficiency_pred"] = pred_score
        else:
            metrics.pop("diagnostic_evidence_sufficiency_pred", None)
        llm_metrics[pid] = metrics
        doctor_of[pid] = doctor
    if missing:
        print(f"\n[warn] No kor xlsx found for {len(missing)} cases: {missing}", file=_sys.stderr)

    # ── turn-level correlation (pool every rated turn across all cases,
    # instead of collapsing each case to one episode-mean point first) ──
    turn_jaccard_pairs: list[tuple[float, float]] = []
    turn_precision_pairs: list[tuple[float, float]] = []
    turn_recall_pairs: list[tuple[float, float]] = []
    turn_ias_pairs: list[tuple[float, float]] = []
    # per-doctor raw expert turn ratings, for the by-model statistics below
    diff_diag_turns_by_doctor: dict[str, list[float]] = defaultdict(list)
    info_acq_turns_by_doctor: dict[str, list[float]] = defaultdict(list)
    for pid in common_ids:
        doctor = doctor_of.get(pid)
        if doctor is None:
            continue
        j_by_turn = turn_jaccard_rigid(doctor, pid)
        p_by_turn = turn_rigid_field(doctor, pid, "precision_rigid")
        rc_by_turn = turn_rigid_field(doctor, pid, "recall_rigid")
        ias_by_turn = turn_ias(doctor, pid)

        diff_by_turn: dict[int, list[float]] = {}
        info_by_turn: dict[int, list[float]] = {}
        for turns_dict in (expert1_turns.get(pid, {}), expert2_turns.get(pid, {})):
            for turn, v in turns_dict.get("diff_diag", {}).items():
                diff_by_turn.setdefault(turn, []).append(v)
            for turn, v in turns_dict.get("info_acq", {}).items():
                info_by_turn.setdefault(turn, []).append(v)

        for turn, vals in diff_by_turn.items():
            turn_mean = float(np.mean(vals))
            diff_diag_turns_by_doctor[doctor].append(turn_mean)
            if turn in j_by_turn:
                turn_jaccard_pairs.append((j_by_turn[turn], turn_mean))
            if turn in p_by_turn:
                turn_precision_pairs.append((p_by_turn[turn], turn_mean))
            if turn in rc_by_turn:
                turn_recall_pairs.append((rc_by_turn[turn], turn_mean))
        for turn, vals in info_by_turn.items():
            turn_mean = float(np.mean(vals))
            info_acq_turns_by_doctor[doctor].append(turn_mean)
            if turn in ias_by_turn:
                turn_ias_pairs.append((ias_by_turn[turn], turn_mean))

    # ── expert turn-level ratings by doctor model ───────────────────────
    print(f"\n=== Expert turn-level ratings by doctor model "
          f"({len(diff_diag_turns_by_doctor)} models) ===")

    def _print_doctor_stats(label: str, by_doctor: dict[str, list[float]]) -> None:
        print(f"  -- {label} --")
        header = f"    {'doctor':24s} {'n':>5s} {'mean':>7s} {'std':>7s} {'median':>7s} {'min':>6s} {'max':>6s}"
        print(header)
        for doctor in sorted(by_doctor, key=_doctor_order_rank):
            vals = np.array(by_doctor[doctor])
            name = DOCTOR_NAME_CANONICAL.get(doctor, doctor)
            print(f"    {name:24s} {len(vals):5d} {vals.mean():7.3f} {vals.std(ddof=1):7.3f} "
                  f"{np.median(vals):7.3f} {vals.min():6.2f} {vals.max():6.2f}")

    _print_doctor_stats("감별진단능력 (turn-level)", diff_diag_turns_by_doctor)
    _print_doctor_stats("정보습득능력 (turn-level)", info_acq_turns_by_doctor)

    draw_doctor_turn_boxplot(diff_diag_turns_by_doctor, info_acq_turns_by_doctor,
                              DOCTOR_TURN_BOXPLOT_OUT_PATH)

    evidence_suff_by_doctor: dict[str, list[float]] = defaultdict(list)
    for pid in common_ids:
        doctor = doctor_of.get(pid)
        v = avg_expert[pid]["evidence_suff"]
        if doctor is not None and v is not None:
            evidence_suff_by_doctor[doctor].append(v)

    radar_means = {
        d: {
            "diff_diag": float(np.mean(diff_diag_turns_by_doctor[d])),
            "info_acq": float(np.mean(info_acq_turns_by_doctor[d])),
            "evidence_suff": float(np.mean(evidence_suff_by_doctor[d])),
        }
        for d in diff_diag_turns_by_doctor
        if d in info_acq_turns_by_doctor and d in evidence_suff_by_doctor
    }
    draw_expert_radar(radar_means, EXPERT_RADAR_OUT_PATH)

    print("\n=== Turn-level correlation (each rated turn is one point, not one case) ===")

    def _print_turn_pair(label: str, pairs: list[tuple[float, float]]) -> None:
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        r, n = pearson(xs, ys)
        rho, _ = spearman(xs, ys)
        r_s = f"{r:.3f}" if r is not None else "n/a"
        rho_s = f"{rho:.3f}" if rho is not None else "n/a"
        print(f"  {label:34s} Pearson r={r_s}  Spearman ρ={rho_s}  (n={n})")

    _print_turn_pair("jaccard_rigid (turn) x diff_diag", turn_jaccard_pairs)
    _print_turn_pair("precision_rigid (turn) x diff_diag", turn_precision_pairs)
    _print_turn_pair("recall_rigid (turn) x diff_diag", turn_recall_pairs)
    _print_turn_pair("ias (turn) x info_acq", turn_ias_pairs)
    print("  (ICC not reported here: automated metrics (0-1) and expert ratings (1-5) "
          "are on different scales — ICC assumes a shared scale, use Spearman instead)")
    print("  (compare against the episode-aggregated 'Headline pairs' printed below)")

    # ── per-case CSV: profile_id, doctor, expert1/expert2/avg ratings, all LLM metrics ──
    csv_fields = (
        ["profile_id", "doctor"]
        + [f"expert1_{d}" for d in EXPERT_DIMS]
        + [f"expert2_{d}" for d in EXPERT_DIMS]
        + [f"expert_avg_{d}" for d in EXPERT_DIMS]
        + [f"llm_{k}" for k in LLM_METRIC_KEYS]
    )
    with open(CSV_OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for pid in common_ids:
            row = {"profile_id": pid, "doctor": doctor_of.get(pid, "")}
            for d in EXPERT_DIMS:
                v1, v2 = expert1[pid][d], expert2[pid][d]
                row[f"expert1_{d}"] = round(v1, 4) if v1 is not None else None
                row[f"expert2_{d}"] = round(v2, 4) if v2 is not None else None
                vals = [v for v in (v1, v2) if v is not None]
                row[f"expert_avg_{d}"] = round(float(np.mean(vals)), 4) if vals else None
            case_llm = llm_metrics.get(pid, {})
            for k in LLM_METRIC_KEYS:
                v = case_llm.get(k)
                row[f"llm_{k}"] = round(v, 4) if isinstance(v, float) else v
            writer.writerow(row)
    print(f"[saved] {CSV_OUT_PATH}")

    joined_ids = sorted(set(avg_expert) & set(llm_metrics))
    print(f"\nJoined cases (expert avg + LLM-judge metrics): {len(joined_ids)}")
    print("NOTE: all joined cases come from the single 'gpt-5.6-terra' "
          "patient/judge bucket (see module docstring) — no second judge-model "
          "group exists in this human-validation sample to split against.")

    # ── per-expert breakdown (Expert 1 alone vs. Expert 2 alone, not the
    # averaged rating) — episode-level and turn-level, for every metric ──
    METRIC_DIM_PAIRS = [
        ("jaccard", "diff_diag", turn_jaccard_rigid),
        ("precision", "diff_diag", lambda d, p: turn_rigid_field(d, p, "precision_rigid")),
        ("recall", "diff_diag", lambda d, p: turn_rigid_field(d, p, "recall_rigid")),
        ("ias", "info_acq", turn_ias),
    ]

    print("\n=== Per-expert breakdown: Expert 1 alone vs. Expert 2 alone "
          "(not the averaged rating) ===")
    for expert_dict, expert_label in ((expert1, "Expert 1"), (expert2, "Expert 2")):
        print(f"\n  -- {expert_label} --")
        print(f"    {'metric x dim':38s} {'episode-level':>28s} {'turn-level':>28s}")
        for auto_key, dim, turn_lookup in METRIC_DIM_PAIRS:
            # episode-level: this expert's own rating (not avg_expert)
            xs_ep = [llm_metrics[i].get(auto_key) for i in joined_ids]
            ys_ep = [expert_dict[i][dim] for i in joined_ids]
            r_ep, n_ep = pearson(xs_ep, ys_ep)
            rho_ep, _ = spearman(xs_ep, ys_ep)
            r_ep_s = f"r={r_ep:.3f}" if r_ep is not None else "r=n/a"
            rho_ep_s = f"ρ={rho_ep:.3f}" if rho_ep is not None else "ρ=n/a"

            # turn-level: this expert's own per-turn ratings (not the
            # 2-expert-averaged turn_*_pairs computed above)
            expert_turns = expert1_turns if expert_dict is expert1 else expert2_turns
            turn_pairs = []
            for pid in common_ids:
                doctor = doctor_of.get(pid)
                if doctor is None:
                    continue
                by_turn = turn_lookup(doctor, pid)
                for turn, v in expert_turns.get(pid, {}).get(dim, {}).items():
                    if turn in by_turn:
                        turn_pairs.append((by_turn[turn], v))
            r_tn, n_tn = pearson([p[0] for p in turn_pairs], [p[1] for p in turn_pairs])
            rho_tn, _ = spearman([p[0] for p in turn_pairs], [p[1] for p in turn_pairs])
            r_tn_s = f"r={r_tn:.3f}" if r_tn is not None else "r=n/a"
            rho_tn_s = f"ρ={rho_tn:.3f}" if rho_tn is not None else "ρ=n/a"

            ep_str = f"{r_ep_s} {rho_ep_s} (n={n_ep})"
            tn_str = f"{r_tn_s} {rho_tn_s} (n={n_tn})"
            print(f"    {auto_key + ' x ' + dim:38s} {ep_str:>28s} {tn_str:>28s}")

    # ── 3x3 confusion matrix: automated metrics (rows) x expert dims (cols) ──
    matrix = np.full((len(AUTO_METRICS), len(EXPERT_DIMS)), np.nan)
    matrix_sp = np.full((len(AUTO_METRICS), len(EXPERT_DIMS)), np.nan)
    print("\n=== Expert vs. LLM-as-Judge correlation (n=%d) ===" % len(joined_ids))
    for ai, auto_key in enumerate(AUTO_METRICS):
        for di, dim in enumerate(EXPERT_DIMS):
            xs = [llm_metrics[i].get(auto_key) for i in joined_ids]
            ys = [avg_expert[i][dim] for i in joined_ids]
            r, n = pearson(xs, ys)
            rho, _ = spearman(xs, ys)
            matrix[ai, di] = r if r is not None else np.nan
            matrix_sp[ai, di] = rho if rho is not None else np.nan
            r_str = f"{r:.3f}" if r is not None else "n/a"
            rho_str = f"{rho:.3f}" if rho is not None else "n/a"
            print(f"  {auto_key:32s} x {dim:15s} Pearson r={r_str}  Spearman ρ={rho_str}  (n={n})")

    draw_heatmap(
        matrix,
        row_labels=[AUTO_METRIC_LABELS[k] for k in AUTO_METRICS],
        col_labels=[EXPERT_DIM_LABELS[k] for k in EXPERT_DIMS],
        title="Automated Metrics vs. Human Expert Ratings (Pearson r)",
        out_path=OUT_PATH,
        n=len(joined_ids),
    )
    draw_heatmap(
        matrix_sp,
        row_labels=[AUTO_METRIC_LABELS[k] for k in AUTO_METRICS],
        col_labels=[EXPERT_DIM_LABELS[k] for k in EXPERT_DIMS],
        title="Automated Metrics vs. Human Expert Ratings (Spearman ρ)",
        out_path=SPEARMAN_OUT_PATH,
        n=len(joined_ids),
        cbar_label="Spearman correlation (ρ)",
    )

    draw_scatter(joined_ids, llm_metrics, avg_expert, SCATTER_OUT_PATH)
    draw_turn_scatter(turn_jaccard_pairs, turn_ias_pairs, TURN_SCATTER_OUT_PATH)

    # ── headline diagonal correlations (task 4: "the" expert-vs-judge corr) ──
    print("\n=== Headline pairs (matched dimensions) ===")
    diag_pairs = list(zip(AUTO_METRICS, EXPERT_DIMS))
    for auto_key, dim in diag_pairs:
        xs = [llm_metrics[i].get(auto_key) for i in joined_ids]
        ys = [avg_expert[i][dim] for i in joined_ids]
        r, n = pearson(xs, ys)
        rho, _ = spearman(xs, ys)
        r_str = f"{r:.3f}" if r is not None else "n/a"
        rho_str = f"{rho:.3f}" if rho is not None else "n/a"
        print(f"  {auto_key} <-> {dim}: Pearson r={r_str}  Spearman ρ={rho_str} (n={n})")

    print("\n=== precision_rigid / recall_rigid vs. diff_diag, episode-level ===")
    for auto_key in ("precision", "recall"):
        xs = [llm_metrics[i].get(auto_key) for i in joined_ids]
        ys = [avg_expert[i]["diff_diag"] for i in joined_ids]
        r, n = pearson(xs, ys)
        rho, _ = spearman(xs, ys)
        r_str = f"{r:.3f}" if r is not None else "n/a"
        rho_str = f"{rho:.3f}" if rho is not None else "n/a"
        print(f"  {auto_key}_rigid <-> diff_diag: Pearson r={r_str}  Spearman ρ={rho_str} (n={n})")

    # ── discretized expert rating: binary (bad [1,3) / good [3,5]) and
    # ternary (bad [1,2.5) / neutral [2.5,3.5] / good (3.5,5]) cut points ──
    binary_pairs = [
        ("jaccard", "diff_diag"), ("precision", "diff_diag"), ("recall", "diff_diag"),
        ("ias", "info_acq"),
        ("diagnostic_evidence_sufficiency_pred", "evidence_suff"),
    ]
    print("\n=== Binary expert rating (bad [1,3) / good [3,5]) — "
          "point-biserial r + AUROC ===")
    for auto_key, dim in binary_pairs:
        xs = [llm_metrics[i].get(auto_key) for i in joined_ids]
        raw = [avg_expert[i][dim] for i in joined_ids]
        labels = [label_binary(v) for v in raw]
        r, n = pearson(xs, [float(l) if l is not None else None for l in labels])
        auc, n_pos, n_neg = auroc(xs, labels)
        r_str = f"{r:.3f}" if r is not None else "n/a"
        auc_str = f"{auc:.3f}" if auc is not None else "n/a"
        print(f"  {auto_key:32s} x {dim:15s} point-biserial r={r_str}  AUROC={auc_str}  "
              f"(good n={n_pos}, bad n={n_neg})")

    print("\n=== Ternary expert rating (data-driven per-dimension terciles, "
          "not the fixed [2.5, 3.5] cut) — Spearman ρ vs. ordinal label ===")
    ternary_cuts_by_dim: dict[str, tuple[float, float]] = {}
    ternary_labels_by_pid: dict[str, dict[str, int | None]] = {i: {} for i in joined_ids}
    for dim in EXPERT_DIMS:
        lo, hi = tercile_cuts([avg_expert[i][dim] for i in joined_ids])
        ternary_cuts_by_dim[dim] = (lo, hi)
        for i in joined_ids:
            ternary_labels_by_pid[i][dim] = label_ternary(avg_expert[i][dim], lo, hi)
    for dim in EXPERT_DIMS:
        lo, hi = ternary_cuts_by_dim[dim]
        print(f"  [{dim}] cuts: bad < {lo:.2f} <= neutral <= {hi:.2f} < good")
    print()
    for auto_key, dim in binary_pairs:
        xs = [llm_metrics[i].get(auto_key) for i in joined_ids]
        labels = [ternary_labels_by_pid[i][dim] for i in joined_ids]
        rho, n = spearman(xs, [float(l) if l is not None else None for l in labels])
        counts = {c: sum(1 for l in labels if l == c) for c in (0, 1, 2)}
        rho_str = f"{rho:.3f}" if rho is not None else "n/a"
        print(f"  {auto_key:32s} x {dim:15s} Spearman ρ={rho_str}  (n={n}; "
              f"bad={counts[0]}, neutral={counts[1]}, good={counts[2]})")

    draw_ternary_scatter(joined_ids, llm_metrics, avg_expert,
                          ternary_labels_by_pid, ternary_cuts_by_dim,
                          TERNARY_SCATTER_OUT_PATH)

    # ── sensitivity check: same 3x3 matrix, dropping ias==0 cases ──
    # IAS=0 means the automated question->symptom mapper found zero targets
    # for every question in that episode (see module docstring) — it isn't
    # necessarily a "the doctor asked nothing informative" case, it can also
    # be a mapper miss, so it's worth checking whether those cases are
    # dragging the ias correlations down (or, since jaccard/reasoning are
    # computed on the SAME reduced case set here, whether they change too).
    ias_nonzero_ids = [i for i in joined_ids if (llm_metrics[i].get("ias") or 0) != 0]
    n_dropped = len(joined_ids) - len(ias_nonzero_ids)
    print(f"\n=== Same matrix, excluding {n_dropped} case(s) with automated ias == 0 "
          f"(n={len(ias_nonzero_ids)}) ===")
    matrix_nz = np.full((len(AUTO_METRICS), len(EXPERT_DIMS)), np.nan)
    for ai, auto_key in enumerate(AUTO_METRICS):
        for di, dim in enumerate(EXPERT_DIMS):
            xs = [llm_metrics[i].get(auto_key) for i in ias_nonzero_ids]
            ys = [avg_expert[i][dim] for i in ias_nonzero_ids]
            r, n = pearson(xs, ys)
            rho, _ = spearman(xs, ys)
            matrix_nz[ai, di] = r if r is not None else np.nan
            r_str = f"{r:.3f}" if r is not None else "n/a"
            rho_str = f"{rho:.3f}" if rho is not None else "n/a"
            print(f"  {auto_key:32s} x {dim:15s} Pearson r={r_str}  Spearman ρ={rho_str}  (n={n})")

    draw_heatmap(
        matrix_nz,
        row_labels=[AUTO_METRIC_LABELS[k] for k in AUTO_METRICS],
        col_labels=[EXPERT_DIM_LABELS[k] for k in EXPERT_DIMS],
        title=f"Automated Metrics vs. Human Expert Ratings (excluding ias==0, {n_dropped} dropped)",
        out_path=IAS_NONZERO_OUT_PATH,
        n=len(ias_nonzero_ids),
    )

    # ── IAS variants vs. 정보습득능력 (info_acq): which informative-set
    # definition aligns best with the clinicians' rating? ──
    print("\n=== IAS variants vs. expert 정보습득능력 (info_acq), episode-level ===")
    for k in IAS_VARIANT_KEYS:
        xs = [llm_metrics[i].get(k) for i in joined_ids]
        ys = [avg_expert[i]["info_acq"] for i in joined_ids]
        r, n = pearson(xs, ys)
        rho, _ = spearman(xs, ys)
        r_str = f"{r:.3f}" if r is not None else "n/a"
        rho_str = f"{rho:.3f}" if rho is not None else "n/a"
        tag = "  <- current production IAS" if k == "ias_disc_mand" else ""
        print(f"  {IAS_VARIANT_LABELS[k]:52s} Pearson r={r_str}  Spearman ρ={rho_str}  (n={n}){tag}")

    draw_ias_variant_scatter(joined_ids, llm_metrics, avg_expert, IAS_VARIANTS_SCATTER_OUT_PATH)


if __name__ == "__main__":
    main()
