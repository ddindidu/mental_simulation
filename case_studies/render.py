#!/usr/bin/env python3
"""
Render self-contained HTML replay viewers for the case-study bundles in
case_studies/data/*.json, plus an index.html landing page.

Visual language reuses the palette from templates/index.html (the live
simulation playground): red = patient, blue = doctor, gold = final diagnosis.
"""
import html
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUT = BASE / "html"
OUT.mkdir(parents=True, exist_ok=True)

AXIS_META = {
    "diagnosis_precision": {
        "title": "Diagnosis Inference Precision",
        "blurb": "Per turn, does the doctor's own stated candidate list actually overlap the "
                 "knowledge-graph-derived reference candidate set (precision = |predicted ∩ truth| / |predicted|)?",
        "icon": "🎯", "higher_is_better": True,
    },
    "diagnosis_recall": {
        "title": "Diagnosis Inference Recall",
        "blurb": "Per turn, how much of the knowledge-graph-derived reference candidate set does the doctor's "
                 "own stated candidate list actually cover (recall = |predicted ∩ truth| / |truth|)?",
        "icon": "🧲", "higher_is_better": True,
    },
    "question_quality": {
        "title": "Information Acquisition",
        "blurb": "Per turn, does the doctor's question target diagnostically relevant, unresolved "
                 "information — discriminating symptoms or unconfirmed mandatory criteria (IAS) — while "
                 "also being expected to shrink the candidate set (ECR)?",
        "icon": "❓", "higher_is_better": True,
    },
    "ecr": {
        "title": "Expected Candidate Reduction",
        "blurb": "Mean expected candidate-set reduction per question (ECR = 1 − E[|C_t+1|] / |C_t|, "
                 "averaged per-target over unresolved question targets), conditioned on turns where the "
                 "candidate set had not yet collapsed to one.",
        "icon": "📉", "higher_is_better": True,
    },
    "ecr_positive_rate": {
        "title": "Positive ECR Rate",
        "blurb": "What fraction of a doctor's questions are expected to shrink the candidate set at all "
                 "(ECR > 0), versus questions that are redundant or off-target (ECR ≤ 0)?",
        "icon": "➕", "higher_is_better": True,
    },
    "mean_ias": {
        "title": "Mean Information Acquisition Score",
        "blurb": "Averaged over turns: IAS = diagnostic relevance × (1 − redundancy) — does the question "
                 "target diagnostically relevant, not-yet-resolved information for the current candidate set?",
        "icon": "🧭", "higher_is_better": True,
    },
    "diagnostic_reasoning": {
        "title": "Diagnostic Reasoning Coverage",
        "blurb": "Independent of whether the final diagnosis label was correct: does the doctor's final "
                 "diagnostic checklist actually cover the DSM-5-derived required criteria for the ground-truth disease?",
        "icon": "🧠", "higher_is_better": True,
    },
    "efficiency": {
        "title": "Interview Efficiency",
        "blurb": "How fast does the candidate set shrink per turn (CSSR), how often does it backtrack "
                 "(monotonicity violations), and how many turns are spent on questions that don't narrow anything "
                 "(redundant turns)?",
        "icon": "⏱️", "higher_is_better": True,
    },
    "avg_turn_count": {
        "title": "Interview Length",
        "blurb": "How many turns does the interview take? A short interview isn't automatically good "
                 "(it may mean premature closure) and a long one isn't automatically bad — read alongside "
                 "final accuracy and CSSR.",
        "icon": "📏", "higher_is_better": False,
    },
    "cssr": {
        "title": "Candidate-Set Shrink Rate (CSSR)",
        "blurb": "(|C_first| − |C_last|) / turn_count — the average number of candidates eliminated per turn "
                 "across the whole episode.",
        "icon": "📐", "higher_is_better": True,
    },
    "time_to_first_correct": {
        "title": "Turns to First Correct Narrowing",
        "blurb": "How many turns until the ground-truth disease first became the sole high-confidence "
                 "candidate? (sentinel = turn_count + 1 if this never happens.)",
        "icon": "⏳", "higher_is_better": False,
    },
    "redundant_turn_ratio": {
        "title": "Redundant Turn Ratio",
        "blurb": "What fraction of turns leave the reference candidate-set size completely unchanged from "
                 "the previous turn — i.e. contributed nothing to narrowing the diagnosis?",
        "icon": "🔁", "higher_is_better": False,
    },
    "overcommitment": {
        "title": "Overcommitment Turns",
        "blurb": "How many turns does the doctor keep interviewing after the candidate set has already "
                 "collapsed to a single disease, before finally committing to a final diagnosis?",
        "icon": "🐢", "higher_is_better": False,
    },
    "safety_compliance": {
        "title": "Safety-Critical Screening Compliance",
        "blurb": "Independent of diagnostic scoring, were the 6 safety-critical symptoms (delusions, "
                 "hallucinations, disorganized thinking/behavior, suicidal ideation, self-destructive behavior) "
                 "ever screened during the interview?",
        "icon": "🛡️", "higher_is_better": True,
    },
}

AXIS_ORDER = [
    "diagnosis_precision", "diagnosis_recall",
    "question_quality", "ecr", "ecr_positive_rate", "mean_ias",
    "diagnostic_reasoning",
    "efficiency", "avg_turn_count", "cssr", "time_to_first_correct", "redundant_turn_ratio", "overcommitment",
    "safety_compliance",
]

MODEL_LABELS = {
    "gpt-5.4": "GPT-5.4",
    "gpt-5.4-mini-2026-03-17": "GPT-5.4-mini",
    "gemini-3.5-flash": "Gemini-3.5-flash",
    "gemini-3.1-flash-lite": "Gemini-3.1-flash-lite",
    "qwen3-235b-a22b-2507": "Qwen3-235B",
    "llama-3.3-70b-instruct": "Llama-3.3-70B",
}

CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#f5f6f8; --surface:#ffffff; --elevated:#fafbfc; --border:#d8dde6; --border-bright:#c5ccd8;
  --p-hue:#c43d3d; --p-hue-dim:rgba(196,61,61,.10); --p-msg-bg:#fff5f5; --p-msg-border:#e8c4c4;
  --d-hue:#1a6fb5; --d-hue-dim:rgba(26,111,181,.10); --d-msg-bg:#f0f7fc; --d-msg-border:#b8d4ea;
  --dx-hue:#8a6d1a; --dx-bg:#fffbeb; --dx-border:#e8d48a;
  --good:#1a7a4a; --good-bg:#eafaf1; --good-border:#a9dfc2;
  --bad:#b3261e; --bad-bg:#fdecea; --bad-border:#f3b8b3;
  --text-primary:#1a1d24; --text-secondary:#3d4450; --text-muted:#5c6470; --text-code:#2a3140;
  --header-h:58px; --radius:10px;
}
html,body{background:var(--bg);color:var(--text-primary);font-family:'Inter','Noto Sans KR',sans-serif;font-size:15px;line-height:1.55}
body{padding:0 0 60px 0}
a{color:var(--d-hue)}
.wrap{max-width:960px;margin:0 auto;padding:0 20px}

/* ── Header — ported from templates/index.html (DSAIL playground) ────────── */
header{
  height:var(--header-h);display:flex;align-items:center;justify-content:space-between;
  padding:0 20px;background:var(--surface);border-bottom:1px solid var(--border);gap:16px;
  position:sticky;top:0;z-index:20;
}
.hd-brand{display:flex;align-items:center;gap:10px;flex:0 0 auto}
.hd-logo{font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;letter-spacing:.12em;
  color:var(--text-muted);background:var(--elevated);border:1px solid var(--border);padding:4px 10px;border-radius:4px}
.hd-title{font-size:16px;font-weight:600;color:var(--text-secondary);letter-spacing:.02em}
.hd-progress{flex:1;display:flex;flex-direction:column;align-items:center;gap:5px;max-width:480px}
.turn-dots{display:flex;gap:6px;flex-wrap:wrap;justify-content:center}
.turn-dot{width:16px;height:7px;border-radius:4px;background:var(--border)}
.turn-dot.patient{background:var(--p-hue)}
.turn-dot.doctor{background:var(--d-hue)}
.turn-dot.highlight{outline:2px solid var(--text-primary);outline-offset:1px}
.turn-label{font-size:12.5px;font-weight:500;color:var(--text-muted)}
.hd-model{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--text-muted);background:var(--elevated);
  border:1px solid var(--border);padding:6px 12px;border-radius:6px;white-space:nowrap;text-decoration:none}

/* ── Sub-header (case-study-specific: axis / level / rationale) ──────────── */
.subheader{background:var(--surface);border-bottom:1px solid var(--border);padding:18px 0}
.subheader .wrap{display:flex;flex-direction:column;gap:10px}
.crumbs{font-size:13px;color:var(--text-muted)}
.crumbs a{text-decoration:none}
.title-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
h1{font-size:21px;font-weight:800;letter-spacing:-.01em}
.badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.02em;text-transform:uppercase}
.badge.good{background:var(--good-bg);color:var(--good);border:1px solid var(--good-border)}
.badge.bad{background:var(--bad-bg);color:var(--bad);border:1px solid var(--bad-border)}
.badge.model{background:var(--elevated);color:var(--text-secondary);border:1px solid var(--border);font-family:'IBM Plex Mono',monospace;text-transform:none}
.badge.correct{background:var(--good-bg);color:var(--good);border:1px solid var(--good-border)}
.badge.incorrect{background:var(--bad-bg);color:var(--bad);border:1px solid var(--bad-border)}
.subtitle{color:var(--text-muted);font-size:13.5px;max-width:760px}

.page-body{padding-top:22px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px;margin-bottom:18px}
.card h2,.section-label{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin-bottom:12px}
.rationale{background:var(--elevated);border:1px solid var(--border);border-left:4px solid var(--d-hue);border-radius:8px;padding:14px 16px;font-size:14px;color:var(--text-secondary);margin-bottom:18px}

.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}
.metric{background:var(--elevated);border:1px solid var(--border);border-radius:8px;padding:10px 12px}
.metric .k{font-size:11px;text-transform:uppercase;letter-spacing:.03em;color:var(--text-muted);margin-bottom:4px}
.metric .v{font-size:19px;font-weight:800;color:var(--text-primary)}
.metric .v.good{color:var(--good)} .metric .v.bad{color:var(--bad)}

.modelbar-row{display:flex;align-items:center;gap:10px;margin:5px 0;font-size:12.5px}
.modelbar-row .name{width:150px;flex-shrink:0;color:var(--text-secondary);text-align:right}
.modelbar-row .track{flex:1;background:var(--elevated);border-radius:5px;height:14px;position:relative;overflow:hidden;border:1px solid var(--border)}
.modelbar-row .fill{position:absolute;left:0;top:0;bottom:0;background:var(--d-hue);border-radius:5px}
.modelbar-row.this .fill{background:var(--p-hue)}
.modelbar-row .val{width:52px;flex-shrink:0;font-variant-numeric:tabular-nums;color:var(--text-muted)}
.modelbar-row.this .name{font-weight:800;color:var(--p-hue)}

/* ── Chat feed — ported from templates/index.html (patient/doctor bubbles) ── */
.chat-section{border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);overflow:hidden;margin-bottom:18px}
.chat-top{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border);background:var(--elevated)}
.chat-top-label{font-size:13px;font-weight:600;letter-spacing:.04em;color:var(--text-muted);text-transform:uppercase}
.chat-feed{padding:22px 26px;display:flex;flex-direction:column;gap:10px}

.turn-sep{align-self:center;font-size:11.5px;font-weight:600;letter-spacing:.04em;color:var(--text-muted);
  padding:4px 14px;background:var(--elevated);border:1px solid var(--border);border-radius:24px;margin:6px 0 2px}
.turn-sep.highlighted{color:var(--p-hue);border-color:var(--p-msg-border);background:var(--p-hue-dim)}

.msg-wrapper{display:flex;flex-direction:column;max-width:78%}
.msg-wrapper.patient{align-self:flex-start}
.msg-wrapper.doctor{align-self:flex-end}
.msg-meta{display:flex;align-items:center;gap:6px;margin-bottom:6px}
.msg-wrapper.doctor .msg-meta{flex-direction:row-reverse}
.msg-role{font-size:12px;letter-spacing:.04em;font-weight:700;padding:3px 9px;border-radius:4px}
.msg-wrapper.patient .msg-role{background:var(--p-hue-dim);color:var(--p-hue);border:1px solid var(--p-msg-border)}
.msg-wrapper.doctor .msg-role{background:var(--d-hue-dim);color:var(--d-hue);border:1px solid var(--d-msg-border)}
.msg-bubble{padding:13px 17px;border-radius:var(--radius);font-size:15.5px;line-height:1.7;word-break:break-word}
.msg-wrapper.patient .msg-bubble{background:var(--p-msg-bg);border:1px solid var(--p-msg-border);border-radius:2px var(--radius) var(--radius) var(--radius)}
.msg-wrapper.doctor .msg-bubble{background:var(--d-msg-bg);border:1px solid var(--d-msg-border);border-radius:var(--radius) 2px var(--radius) var(--radius)}
.msg-bubble.skipped{opacity:.6;font-style:italic}

.qscores{display:flex;flex-wrap:wrap;gap:6px;margin-top:7px;justify-content:flex-end}
.msg-wrapper.patient .qscores{justify-content:flex-start}
.qchip{font-size:11px;padding:2px 8px;border-radius:999px;background:#fff;border:1px solid var(--d-msg-border);color:var(--d-hue);font-weight:700}

.turn-analysis{align-self:stretch;background:var(--elevated);border:1px solid var(--border);border-radius:var(--radius);
  margin:2px 0 4px;overflow:hidden}
.turn-analysis .ta-label{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted);
  padding:8px 14px;border-bottom:1px solid var(--border);background:var(--surface)}
.detail-row{display:grid;grid-template-columns:1fr 1fr;gap:0}
@media (max-width:640px){.detail-row{grid-template-columns:1fr}}
.detail-col{padding:11px 16px;font-size:12.5px}
.detail-col:first-child{border-right:1px solid var(--border)}
@media (max-width:640px){.detail-col:first-child{border-right:none;border-bottom:1px solid var(--border)}}
.detail-col .dl{font-size:10.5px;text-transform:uppercase;letter-spacing:.03em;color:var(--text-muted);font-weight:700;margin-bottom:6px}
.pill{display:inline-block;font-size:11.5px;padding:2px 8px;border-radius:999px;margin:2px 3px 2px 0;border:1px solid var(--border)}
.pill.high-likely{background:#fdecea;border-color:#f3b8b3;color:#b3261e}
.pill.moderate-likely{background:#fff6e0;border-color:#e8d48a;color:#8a6d1a}
.pill.low-likely{background:var(--elevated);border-color:var(--border);color:var(--text-muted)}
.pill.excluded{background:var(--elevated);border-color:var(--border);color:var(--text-muted);text-decoration:line-through}
.pill.confirmed{background:var(--good-bg);border-color:var(--good-border);color:var(--good)}
.pill.denied{background:var(--elevated);border-color:var(--border);color:var(--text-muted);text-decoration:line-through}
.pill.gt{outline:2px solid var(--p-hue);outline-offset:-1px}
.symptoms-line{margin-top:8px}
.stat-inline{color:var(--text-secondary);font-size:12.5px;margin-top:2px}
.stat-inline b{color:var(--text-primary)}

/* Diagnosis card — ported verbatim from templates/index.html (appears as the
   final item in the chat feed, exactly like the live simulation) */
.diagnosis-card{align-self:stretch;background:var(--dx-bg);border:1px solid var(--dx-border);border-radius:var(--radius);padding:16px 18px}
.dx-label{font-size:14px;font-weight:700;letter-spacing:.06em;color:var(--dx-hue);margin-bottom:10px;display:flex;align-items:center;gap:8px;text-transform:uppercase}
.dx-label::before,.dx-label::after{content:'';flex:1;height:1px;background:var(--dx-border)}
.dx-content{font-size:15px;line-height:1.75;color:var(--text-primary)}
.dx-content .verdict{font-weight:800;font-size:16px;margin-bottom:6px}
.dx-content .verdict.good{color:var(--good)} .dx-content .verdict.bad{color:var(--bad)}

.dx-box{background:var(--dx-bg);border:1px solid var(--dx-border);border-radius:var(--radius);padding:18px 20px;margin-bottom:18px}
.dx-box h2{color:var(--dx-hue)}
.dx-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:10px}
@media (max-width:640px){.dx-grid{grid-template-columns:1fr}}
.dx-cell .k{font-size:11px;text-transform:uppercase;color:#8a6d1a;font-weight:700;margin-bottom:3px}
.dx-cell .v{font-size:15px;font-weight:800}
.reason{font-size:13.5px;color:var(--text-secondary);margin-top:8px;line-height:1.6}
.checklist-group{margin-top:10px;padding-top:10px;border-top:1px solid var(--dx-border)}
.checklist-group .gname{font-size:12.5px;font-weight:800;color:var(--dx-hue);margin-bottom:4px}
.checklist-group ul{padding-left:18px;font-size:13px;color:var(--text-secondary)}

.judge-group{border-top:1px solid var(--border);padding:10px 0}
.judge-group:first-child{border-top:none;padding-top:0}
.judge-group .gname{font-weight:800;font-size:13px;margin-bottom:4px}
.judge-group .score{float:right;font-weight:800}
.judge-group .missing{color:var(--bad);font-size:12.5px}
.judge-group .matched{color:var(--good);font-size:12.5px}

.safety-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px}
.safety-item{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;border:1px solid var(--border);background:var(--elevated);font-size:13px}
.safety-item .dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.safety-item.covered .dot{background:var(--good)} .safety-item.covered{border-color:var(--good-border)}
.safety-item.missing .dot{background:var(--bad)} .safety-item.missing{border-color:var(--bad-border)}

footer{text-align:center;color:var(--text-muted);font-size:12.5px;padding:20px 0}
.back-link{display:inline-block;margin-bottom:14px;font-size:13px;text-decoration:none;color:var(--text-muted)}
.back-link:hover{color:var(--d-hue)}
"""


def polarity(axis: str, level: str) -> str:
    """'good' if this level represents the desirable extreme of the metric, else 'bad'."""
    hib = AXIS_META[axis].get("higher_is_better", True)
    is_high = level == "high"
    return "good" if (is_high == hib) else "bad"


def esc(x) -> str:
    if x is None:
        return ""
    return html.escape(str(x))


def fmt(x, digits=2):
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "Yes" if x else "No"
    if isinstance(x, (int, float)):
        if float(x).is_integer():
            return str(int(x))
        return f"{x:.{digits}f}"
    return str(x)


def pill_list(items, cls):
    if not items:
        return '<span style="color:var(--text-muted);font-size:12px">none</span>'
    return "".join(f'<span class="pill {cls}" title="{esc(it["id"])}">{esc(it["name"])}</span>' for it in items)


def sym_pill_list(items, cls, gt_ids=None):
    if not items:
        return '<span style="color:var(--text-muted);font-size:12px">none</span>'
    out = []
    for it in items:
        extra = " gt" if gt_ids and it["id"] in gt_ids else ""
        out.append(f'<span class="pill {cls}{extra}" title="{esc(it["id"])}">{esc(it["name"])}</span>')
    return "".join(out)


def render_turn(t: dict, highlighted_turn) -> str:
    """Render one turn as chat bubbles — same .msg-wrapper/.msg-role/.msg-bubble
    markup as the live simulation in templates/index.html (doctor right-aligned,
    patient left-aligned), plus a full-width analysis note for the score/
    candidate data the live app shows in its side panels instead."""
    hl = highlighted_turn is not None and t["turn"] == highlighted_turn
    sep_cls = " highlighted" if hl else ""
    parts = [f'<div class="turn-sep{sep_cls}">Turn {t["turn"]}'
             f'{" · opening question" if t.get("is_opening") else ""}'
             f'{" · ★ highlighted" if hl else ""}</div>']

    q = t.get("question")
    if q:
        qs = t.get("question_scores")
        chips = ""
        if qs:
            def chip(label, val, digits=2):
                return f'<span class="qchip">{label} {fmt(val, digits)}</span>'
            chips = '<div class="qscores">' + "".join([
                chip("IAS", qs.get("ias")),
                chip("relevance", qs.get("diagnostic_relevance")),
                chip("ECR", qs.get("ecr")),
                chip("redundant", qs.get("redundancy_penalty"), 0),
                chip("cand→" + fmt(qs.get("candidate_size_after"), 0), None) if qs.get("candidate_size_after") is not None else "",
            ]) + '</div>'
        parts.append(
            '<div class="msg-wrapper doctor">'
            '<div class="msg-meta"><span class="msg-role">Doctor</span></div>'
            f'<div class="msg-bubble">{esc(q)}</div>{chips}</div>'
        )
    elif t.get("question_skipped_reason"):
        parts.append(
            '<div class="msg-wrapper doctor">'
            '<div class="msg-meta"><span class="msg-role">Doctor</span></div>'
            f'<div class="msg-bubble skipped">[{esc(t["question_skipped_reason"])} — interview moved to final diagnosis]</div></div>'
        )

    conf = t.get("new_confirmed_symptoms") or []
    den = t.get("new_denied_symptoms") or []
    sym_chips = ""
    if conf or den:
        rows = []
        if conf:
            rows.append('<div style="margin-bottom:4px">' + sym_pill_list(conf, "confirmed") + '</div>')
        if den:
            rows.append('<div>' + sym_pill_list(den, "denied") + '</div>')
        sym_chips = '<div class="qscores" style="margin-top:9px">' + "".join(rows) + '</div>'
    parts.append(
        '<div class="msg-wrapper patient">'
        '<div class="msg-meta"><span class="msg-role">Patient</span></div>'
        f'<div class="msg-bubble">{esc(t["patient_response"])}</div>{sym_chips}</div>'
    )

    rc = t.get("reference_candidates") or {}
    ds = t.get("doctor_stated")
    parts.append('<div class="turn-analysis"><div class="ta-label">Turn analysis</div><div class="detail-row">')
    parts.append('<div class="detail-col"><div class="dl">Reference candidate set (KG symptom matching)</div>')
    parts.append(pill_list(rc.get("high_likely"), "high-likely"))
    parts.append(pill_list(rc.get("moderate_likely"), "moderate-likely"))
    parts.append(pill_list(rc.get("low_likely"), "low-likely"))
    parts.append('</div>')
    parts.append('<div class="detail-col"><div class="dl">Doctor’s own stated candidates</div>')
    if ds:
        parts.append(pill_list(ds.get("predicted"), "moderate-likely"))
        parts.append(f'<div class="stat-inline">precision <b>{fmt(ds.get("precision"))}</b> · '
                      f'recall <b>{fmt(ds.get("recall"))}</b> · '
                      f'accuracy <b>{fmt(ds.get("accuracy"))}</b> · '
                      f'jaccard <b>{fmt(ds.get("jaccard"))}</b></div>')
        parts.append(f'<div class="stat-inline">TP {fmt(ds.get("tp"),0)} · FP {fmt(ds.get("fp"),0)} · FN {fmt(ds.get("fn"),0)}</div>')
    else:
        parts.append('<span style="color:var(--text-muted);font-size:12px">no inference logged this turn</span>')
    parts.append('</div>')
    parts.append('</div></div>')  # detail-row, turn-analysis

    return "".join(parts)


def render_model_bars(agg: dict, this_model: str, higher_is_better=True) -> str:
    if not agg:
        return ""
    items = sorted(agg.items(), key=lambda kv: kv[1], reverse=higher_is_better)
    vmax = max(abs(v) for _, v in items) or 1.0
    vmin = min(v for _, v in items)
    span = (max(v for _, v in items) - vmin) or 1.0
    rows = []
    for m, v in items:
        pct = max(4, (v - vmin) / span * 100)
        cls = "this" if m == this_model else ""
        rows.append(f'<div class="modelbar-row {cls}"><span class="name">{esc(MODEL_LABELS.get(m, m))}</span>'
                     f'<span class="track"><span class="fill" style="width:{pct:.1f}%"></span></span>'
                     f'<span class="val">{v:.3f}</span></div>')
    return "".join(rows)


def render_diagnostic_reasoning(dre: dict) -> str:
    if not dre or dre.get("overall_score") is None:
        return '<div class="card"><h2>Diagnostic reasoning</h2><p style="color:var(--text-muted)">No structured checklist evaluation for this episode.</p></div>'
    parts = ['<div class="card"><h2>Diagnostic reasoning (algorithmic symptom coverage + LLM-judged scalar requirements)</h2>']
    parts.append('<div class="metric-grid" style="margin-bottom:12px">')
    parts.append(f'<div class="metric"><div class="k">Overall score</div><div class="v">{fmt(dre.get("overall_score"))}</div></div>')
    parts.append(f'<div class="metric"><div class="k">Symptom coverage</div><div class="v">{fmt(dre.get("symptom_satisfaction_score"))}</div></div>')
    parts.append(f'<div class="metric"><div class="k">Duration</div><div class="v">{fmt(dre.get("duration_score"))}</div></div>')
    parts.append(f'<div class="metric"><div class="k">Functional impairment</div><div class="v">{fmt(dre.get("functional_impairment_score"))}</div></div>')
    parts.append('</div>')
    for ce in dre.get("symptom_criterion_evaluations") or []:
        parts.append('<div class="judge-group">')
        parts.append(f'<span class="score">{fmt(ce.get("symptom_coverage_score"))}</span>')
        parts.append(f'<div class="gname">{esc(ce.get("group"))} <span style="font-weight:400;color:var(--text-muted)">'
                      f'({esc(ce.get("relation"))}, {fmt(ce.get("valid_symptom_count"),0)}/{fmt(ce.get("min_count_required"),0)} required)</span></div>')
        if ce.get("matched_symptom_descriptions"):
            parts.append('<div class="matched">✓ ' + "; ".join(esc(s) for s in ce["matched_symptom_descriptions"]) + '</div>')
        if ce.get("missing_required_symptoms"):
            parts.append('<div class="missing">✗ missing: ' + "; ".join(esc(s) for s in ce["missing_required_symptoms"]) + '</div>')
        parts.append('</div>')
    notes = dre.get("judge_notes") or {}
    if notes:
        note_bits = []
        for k, v in notes.items():
            if v is None or v == "":
                continue
            note_bits.append(f'<div class="stat-inline"><b>{esc(k)}</b>: {esc(v)}</div>')
        if note_bits:
            parts.append('<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border)">' + "".join(note_bits) + '</div>')
    parts.append('</div>')
    return "".join(parts)


def render_case(bundle: dict) -> str:
    axis = bundle["axis"]
    level = bundle["level"]
    meta = AXIS_META[axis]
    model = bundle["doctor_model"]
    correct = bundle.get("final_accuracy") == 1.0
    gt_ids = {bundle["ground_truth_id"]} if bundle.get("ground_truth_id") else set()
    pol = polarity(axis, level)
    turns = bundle.get("turns", [])
    highlighted_turn = bundle.get("highlighted_turn")

    # Turn-dots in the header — same component as templates/index.html's live
    # progress indicator, pre-colored here since this is a completed replay.
    dots = []
    for t in turns:
        role = "doctor" if (t.get("question") or t.get("question_skipped_reason")) else "patient"
        hl_cls = " highlight" if highlighted_turn is not None and t["turn"] == highlighted_turn else ""
        dots.append(f'<div class="turn-dot {role}{hl_cls}" title="Turn {t["turn"]}"></div>')

    html_parts = [f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(meta['title'])} — {esc(level.upper())} — {esc(bundle['log_file'])}</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<header>
  <div class="hd-brand">
    <span class="hd-logo">DSAIL</span>
    <span class="hd-title">Case Study</span>
  </div>
  <div class="hd-progress">
    <div class="turn-dots">{"".join(dots)}</div>
    <div class="turn-label">{fmt(bundle.get("turn_count"), 0)} turns · {'✓ correct' if correct else '✗ incorrect'} diagnosis</div>
  </div>
  <a class="hd-model" href="index.html" title="Back to all case studies">{esc(MODEL_LABELS.get(model, model))}</a>
</header>
<div class="subheader"><div class="wrap">
<div class="crumbs"><a href="index.html">← All case studies</a></div>
<div class="title-row">
<span style="font-size:26px">{meta['icon']}</span>
<h1>{esc(meta['title'])}</h1>
<span class="badge {pol}">{esc(level)}</span>
<span class="badge model">{esc(MODEL_LABELS.get(model, model))}</span>
<span class="badge {'correct' if correct else 'incorrect'}">{'✓ correct dx' if correct else '✗ incorrect dx'}</span>
</div>
<div class="subtitle">{esc(meta['blurb'])}</div>
</div></div>
<div class="wrap page-body">
<div class="rationale"><b>Why this case:</b> {esc(bundle['rationale'])}</div>
"""]

    # Episode summary metrics
    eff = bundle.get("efficiency") or {}
    html_parts.append('<div class="card"><h2>Episode summary</h2><div class="metric-grid">')
    html_parts.append(f'<div class="metric"><div class="k">Ground truth</div><div class="v" style="font-size:14px">{esc(bundle["ground_truth_name"])}</div></div>')
    html_parts.append(f'<div class="metric"><div class="k">Final diagnosis</div><div class="v {"good" if correct else "bad"}" style="font-size:14px">{esc(bundle["final_diagnosis_name"])}</div></div>')
    html_parts.append(f'<div class="metric"><div class="k">Turns</div><div class="v">{fmt(bundle.get("turn_count"),0)}</div></div>')
    html_parts.append(f'<div class="metric"><div class="k">CSSR</div><div class="v">{fmt(eff.get("cssr"))}</div></div>')
    html_parts.append(f'<div class="metric"><div class="k">Redundant turn ratio</div><div class="v">{fmt(eff.get("redundant_turn_ratio"))}</div></div>')
    html_parts.append(f'<div class="metric"><div class="k">Monotonicity violations</div><div class="v">{fmt(eff.get("monotonicity_violations"),0)}</div></div>')
    html_parts.append('</div></div>')

    # Model comparison bars
    html_parts.append(f'<div class="card"><h2>{esc(meta["title"])} — all 6 doctor models</h2>')
    html_parts.append(render_model_bars(bundle.get("model_aggregate_all_models") or {}, model, meta.get("higher_is_better", True)))
    html_parts.append('</div>')

    # Transcript — chat feed, same component as the live simulation, with the
    # final diagnosis appended as a diagnosis-card exactly like addDiagnosis()
    # does in templates/index.html.
    html_parts.append('<div class="chat-section"><div class="chat-top">'
                       '<span class="chat-top-label">Clinical interview · replay</span></div>'
                       '<div class="chat-feed">')
    for t in turns:
        html_parts.append(render_turn(t, highlighted_turn))
    verdict_cls = "good" if correct else "bad"
    verdict_txt = "✓ Correct" if correct else "✗ Incorrect"
    reason_txt = f'<div style="margin-top:8px">{esc(bundle["doctor_final_reason"])}</div>' if bundle.get("doctor_final_reason") else ""
    html_parts.append(
        '<div class="diagnosis-card"><div class="dx-label">Final diagnosis</div>'
        f'<div class="dx-content"><div class="verdict {verdict_cls}">{verdict_txt} — '
        f'{esc(bundle["final_diagnosis_name"])} ({esc(bundle.get("final_diagnosis_code"))})</div>'
        f'<div>Ground truth: {esc(bundle["ground_truth_name"])}</div>{reason_txt}</div></div>'
    )
    html_parts.append('</div></div>')  # chat-feed, chat-section

    # Detailed diagnostic checklist
    checklist = bundle.get("doctor_diagnostic_checklist") or {}
    html_parts.append('<div class="dx-box"><h2>Doctor’s diagnostic checklist</h2>')
    for grp in (checklist.get("symptom_groups") or []):
        html_parts.append('<div class="checklist-group">')
        html_parts.append(f'<div class="gname">{esc(grp.get("group"))} ({fmt(grp.get("count"),0)})</div>')
        if grp.get("confirmed_symptoms"):
            html_parts.append('<ul>' + "".join(f'<li>{esc(s)}</li>' for s in grp["confirmed_symptoms"]) + '</ul>')
        html_parts.append('</div>')
    html_parts.append('</div>')

    # Diagnostic reasoning judge
    html_parts.append(render_diagnostic_reasoning(bundle.get("diagnostic_reasoning")))

    # Safety compliance
    ssc = bundle.get("safety_screening_compliance") or {}
    html_parts.append('<div class="card"><h2>Safety-critical screening compliance</h2><div class="safety-grid">')
    for it in ssc.get("items", []):
        cls = "covered" if it["covered"] else "missing"
        html_parts.append(f'<div class="safety-item {cls}"><span class="dot"></span>{esc(it["name"])}</div>')
    html_parts.append('</div></div>')

    html_parts.append(f"""
</div>
<footer>{esc(bundle["doctor_model"])} · {esc(bundle["log_file"])} · axis: {esc(axis)} / {esc(level)}</footer>
</body></html>""")
    return "".join(html_parts)


def render_index(bundles: list[dict]) -> str:
    by_axis: dict[str, list] = {}
    for b in bundles:
        by_axis.setdefault(b["axis"], []).append(b)

    sections = []
    for axis in AXIS_ORDER:
        meta = AXIS_META[axis]
        cards = []
        for b in sorted(by_axis.get(axis, []), key=lambda x: x["level"], reverse=True):
            level = b["level"]
            fname = f'{axis}_{level}.html'
            correct = b.get("final_accuracy") == 1.0
            pol = polarity(axis, level)
            cards.append(f"""
<a class="case-card {pol}" href="{fname}">
  <div class="cc-top"><span class="badge {pol}">{esc(level)}</span>
  <span class="badge model">{esc(MODEL_LABELS.get(b["doctor_model"], b["doctor_model"]))}</span></div>
  <div class="cc-log">{esc(b["log_file"])} <span style="color:var(--text-muted);font-weight:400">· {esc(b["ground_truth_name"])}</span></div>
  <div class="cc-rationale">{esc(b["rationale"])}</div>
  <div class="cc-foot">{'✓ correct diagnosis' if correct else '✗ incorrect diagnosis'} · {fmt(b.get("turn_count"),0)} turns</div>
</a>""")
        sections.append(f"""
<section class="axis-section">
<div class="axis-head"><span style="font-size:22px">{meta['icon']}</span>
<h2>{esc(meta['title'])}</h2></div>
<div class="axis-blurb">{esc(meta['blurb'])}</div>
<div class="case-grid">{''.join(cards)}</div>
</section>""")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mental Simulation — Case Studies</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>{CSS}
.wrap{{max-width:1100px}}
.axis-section{{margin-bottom:34px}}
.axis-head{{display:flex;align-items:center;gap:10px;margin-bottom:4px}}
.axis-head h2{{font-size:18px;font-weight:800}}
.axis-blurb{{color:var(--text-muted);font-size:13.5px;max-width:820px;margin-bottom:14px}}
.case-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}}
.case-card{{display:block;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:14px 16px;text-decoration:none;color:inherit;transition:transform .1s, box-shadow .1s}}
.case-card:hover{{transform:translateY(-2px);box-shadow:0 6px 18px rgba(20,20,30,.08)}}
.case-card.good{{border-left:4px solid var(--good)}}
.case-card.bad{{border-left:4px solid var(--bad)}}
.cc-top{{display:flex;gap:6px;margin-bottom:8px}}
.cc-log{{font-weight:800;font-size:14px;margin-bottom:6px}}
.cc-rationale{{font-size:12.5px;color:var(--text-secondary);line-height:1.5;margin-bottom:8px}}
.cc-foot{{font-size:11.5px;color:var(--text-muted)}}
</style></head><body>
<header>
  <div class="hd-brand">
    <span class="hd-logo">DSAIL</span>
    <span class="hd-title">Case Studies</span>
  </div>
  <div class="hd-progress">
    <div class="turn-label">{len(AXIS_ORDER)} axes · {len(bundles)} cases</div>
  </div>
  <div class="hd-model">6 doctor models</div>
</header>
<div class="subheader"><div class="wrap">
<div class="title-row"><span style="font-size:26px">🗂️</span><h1>Mental Simulation — Case Studies</h1></div>
<div class="subtitle">High- and low-scoring examples across {len(AXIS_ORDER)} evaluation axes, drawn from the doctor model that
most characteristically exemplifies each. Judge model: Gemini-3.5-flash · Patient model: Gemini-3.5-flash ·
6 doctor models compared: {', '.join(esc(v) for v in MODEL_LABELS.values())}.</div>
</div></div>
<div class="wrap page-body">
{''.join(sections)}
</div>
<footer>Generated from results/gemini-3.5-flash/gemini-3.5-flash/*/ via case_studies/select_cases.py + render.py</footer>
</body></html>"""


def main():
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    bundles = []
    for m in manifest:
        fp = DATA / f'{m["axis"]}_{m["level"]}.json'
        bundle = json.loads(fp.read_text(encoding="utf-8"))
        bundles.append(bundle)
        out_html = OUT / f'{m["axis"]}_{m["level"]}.html'
        out_html.write_text(render_case(bundle), encoding="utf-8")
        print(f"  wrote {out_html.relative_to(BASE.parent)}")
    (OUT / "index.html").write_text(render_index(bundles), encoding="utf-8")
    print(f"  wrote {(OUT / 'index.html').relative_to(BASE.parent)}")
    (BASE / "README.md").write_text(render_markdown_summary(bundles), encoding="utf-8")
    print(f"  wrote {(BASE / 'README.md').relative_to(BASE.parent)}")


def render_markdown_summary(bundles: list[dict]) -> str:
    by_axis: dict[str, list] = {}
    for b in bundles:
        by_axis.setdefault(b["axis"], []).append(b)

    lines = [
        "# Mental Simulation — Case Study Axes",
        "",
        f"High- and low-scoring examples across {len(AXIS_ORDER)} evaluation axes, drawn from the doctor "
        "model that most characteristically exemplifies each. Judge model: Gemini-3.5-flash · Patient "
        f"model: Gemini-3.5-flash · doctor models compared: {', '.join(MODEL_LABELS.values())}.",
        "",
        "Open `html/index.html` for the clickable version (transcript + inference candidates + judge scores "
        "+ episode metrics per case). See `open.sh` / `serve.py` in this folder for how to view the HTML files.",
        "",
    ]

    for axis in AXIS_ORDER:
        meta = AXIS_META[axis]
        hib = meta.get("higher_is_better", True)
        lines.append(f"## {meta['icon']} {meta['title']}")
        lines.append("")
        lines.append(meta["blurb"] + (" *(higher is better)*" if hib else " *(lower is better)*"))
        lines.append("")
        lines.append("| Level | Doctor model | Case | Ground truth | Final diagnosis | Turns | Why this case |")
        lines.append("|---|---|---|---|---|---|---|")
        for b in sorted(by_axis.get(axis, []), key=lambda x: x["level"], reverse=True):
            level = b["level"]
            fname = f'html/{axis}_{level}.html'
            correct = "✓" if b.get("final_accuracy") == 1.0 else "✗"
            rationale = b["rationale"].replace("|", "\\|")
            lines.append(
                f"| **{level.upper()}** | {MODEL_LABELS.get(b['doctor_model'], b['doctor_model'])} "
                f"| [{b['log_file']}]({fname}) | {b['ground_truth_name']} "
                f"| {correct} {b['final_diagnosis_name']} | {b.get('turn_count', '—')} | {rationale} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Generated by `case_studies/select_cases.py` (selection) + `case_studies/render.py` (HTML + this file) "
                  "from `results/gemini-3.5-flash/gemini-3.5-flash/*/`.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
