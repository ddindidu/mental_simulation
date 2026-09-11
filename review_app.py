"""대화 기록 리뷰 전용 웹 뷰어 (read-only).

시뮬레이션 서버(app.py)와 완전히 분리된 독립 앱.
실행 전에 볼 run 폴더를 지정한다:

    python review_app.py --run saved/current_target [--port 5004]

run 폴더 구조 (app.py/batch_worker.py 산출물 그대로):
    <run>/logs/<patient>/<judge>/<doctor>/<profile_id>.json   ← transcript + doctor_memory

한국어 번역:
  - UI에서 체크 시 /api/translate 호출 → 번역 provider로 transcript 전체를
    한 번에 직역 위주로 번역.
  - 캐시하지 않는다. 요청할 때마다 그 시점의 로그를 읽어 새로 번역하므로,
    시뮬레이션을 다시 돌려 로그가 바뀌어도 항상 현재 대화가 번역된다.
"""
from __future__ import annotations

import argparse
import json
import re
import threading
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

PROJECT_ROOT = Path(__file__).resolve().parent

app = Flask(__name__)

# ── run root (CLI에서 지정) ───────────────────────────────────────────────────
RUN_ROOT: Path = PROJECT_ROOT / "saved" / "current_target"

# ── disorder 메타 (D코드 ↔ 이름 ↔ ICD-10 허용 코드) ──────────────────────────
_KG_EN = PROJECT_ROOT / "mentalbench" / "resources" / "knowledge_graph" / "EN"


def _load_disorder_meta() -> tuple[dict[str, str], dict[str, list[str]], dict[str, str]]:
    """(id→name, id→accepted_icd10_codes, icd10_code→id)"""
    with open(_KG_EN / "disorder.json", encoding="utf-8") as f:
        id2name = {k: v["name"] for k, v in json.load(f).items()}
    id2codes: dict[str, list[str]] = {}
    code2id: dict[str, str] = {}
    icd_path = _KG_EN / "disorder_icd10.json"
    if icd_path.exists():
        with open(icd_path, encoding="utf-8") as f:
            for k, v in json.load(f).items():
                codes = [c.strip().upper() for c in (v.get("icd10_accepted_codes") or [v["icd10_code"]])]
                id2codes[k] = codes
                for c in codes:
                    code2id[c] = k
    return id2name, id2codes, code2id


ID2NAME, ID2CODES, CODE2ID = _load_disorder_meta()


def _build_icd10_info() -> dict[str, dict]:
    """ICD-10 코드 → {id, name, icd10_name} (KG disorder_icd10.json 기준)."""
    out: dict[str, dict] = {}
    icd_path = _KG_EN / "disorder_icd10.json"
    if not icd_path.exists():
        return out
    with open(icd_path, encoding="utf-8") as f:
        for k, v in json.load(f).items():
            codes = [c.strip().upper() for c in (v.get("icd10_accepted_codes") or [v["icd10_code"]])]
            for c in codes:
                out[c] = {"id": k, "name": ID2NAME.get(k, ""), "icd10_name": v.get("icd10_name", "")}
    return out


ICD10_INFO = _build_icd10_info()


# ── 모델 디렉터리 / 에피소드 인덱스 ──────────────────────────────────────────
def _logs_root() -> Path:
    return RUN_ROOT / "logs"


def discover_model_dirs() -> list[dict]:
    """logs/<patient>/<judge>/<doctor>/ 중 *.json이 있는 leaf 디렉터리 목록."""
    out = []
    root = _logs_root()
    if not root.is_dir():
        return out
    for p in sorted(root.glob("*/*/*/")):
        n = sum(1 for _ in p.glob("*.json"))
        if n == 0:
            continue
        rel = p.relative_to(root)
        patient, judge, doctor = rel.parts[:3]
        out.append({
            "key": str(rel).rstrip("/"),
            "patient": patient,
            "judge": judge,
            "doctor": doctor,
            "episodes": n,
        })
    return out


_MODEL_KEY_RE = re.compile(r"^[\w.\-]+/[\w.\-]+/[\w.\-]+$")


def _model_dir(key: str) -> Path:
    """검증된 모델 키 → logs leaf 디렉터리 (경로 탈출 방지)."""
    if not _MODEL_KEY_RE.match(key):
        abort(400, "bad model key")
    p = (_logs_root() / key).resolve()
    if not str(p).startswith(str(_logs_root().resolve())) or not p.is_dir():
        abort(404, "model dir not found")
    return p


def _gt_code(profile_id: str) -> str | None:
    m = re.match(r"^(D\d{3})", profile_id)
    return m.group(1) if m else None


def _is_correct(gt: str | None, final_icd: str | None) -> bool | None:
    """최종 진단 ICD 코드가 ground truth D코드의 허용 코드 집합에 있는지."""
    if not gt or not final_icd or gt not in ID2CODES:
        return None
    return final_icd.strip().upper() in ID2CODES[gt]


def _episode_index(key: str) -> list[dict]:
    """매 요청마다 로그를 다시 읽는다 (캐시 없음).

    서버를 켜 둔 채 시뮬레이션을 다시 돌려도 목록이 옛 값으로 남지 않게 한다.
    """
    d = _model_dir(key)
    rows = []
    for fp in sorted(d.glob("*.json")):
        pid = fp.stem
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        gt = _gt_code(data.get("profile_id") or pid)
        final = (data.get("final_diagnosis") or "").strip() or None
        transcript = data.get("transcript") or []
        rows.append({
            "id": pid,
            "gt": gt,
            "gt_name": ID2NAME.get(gt, ""),
            "final": final,
            "final_disease": CODE2ID.get((final or "").upper()),
            "correct": _is_correct(gt, final),
            "closed_at": data.get("closed_at_patient_turn"),
            "n_messages": len(transcript),
        })
    return rows


def _episode_path(key: str, ep_id: str) -> Path:
    if not re.match(r"^[\w\-]+$", ep_id):
        abort(400, "bad episode id")
    fp = _model_dir(key) / f"{ep_id}.json"
    if not fp.is_file():
        abort(404, "episode not found")
    return fp


# ── 턴별 profile alignment 결과 (txt 로그에서 추출) ────────────────────────
_META_RE = re.compile(r"^-{10} turn (\d+) \| patient:(alignment|response) \|", re.M)


def _alignment_from_turns(dm: dict) -> dict[str, dict]:
    """doctor_memory/v6부터는 턴별 산출물이 로그 안에 그대로 들어 있다.

    {turn: {key, name, manifestation, reason, intent}} — 프롬프트 텍스트를 되짚을 필요가
    없는 새 실행용 경로이고, 그 이전 실행은 _extract_alignment_history가 받아준다.
    """
    out: dict[str, dict] = {}
    for slot in dm.get("turns") or []:
        pt = slot.get("patient") or {}
        item = pt.get("target_item") or {}
        entry: dict[str, str] = {}
        if item.get("matched"):
            for src, dst in (("key", "key"), ("name", "name"),
                             ("manifestation", "manifestation"), ("reason", "reason")):
                if item.get(src):
                    entry[dst] = str(item[src])
        elif pt:
            entry["key"] = "None"
            if item.get("reason"):
                entry["reason"] = str(item["reason"])
        intent = ((slot.get("doctor") or {}).get("intent") or "").strip()
        if intent:
            entry["intent"] = intent
        if entry:
            out[str(slot.get("turn"))] = entry
    return out


_DOCTOR_OUT_RE = re.compile(r"={10} OUTPUT \[doctor\] ={10}\n(.*?)\n={37}", re.DOTALL)


def _extract_question_intents(key: str, ep_id: str) -> dict[str, str]:
    """{turn: intent} — 의사가 그 턴에 무엇을 알아내려 했는지.

    doctor_memory/v6 이전 실행은 이 값을 따로 저장하지 않으므로 프롬프트 로그의
    doctor 출력 블록에서 순서대로 되읽는다. n번째 질문이 n번째 턴이고, 그때의 필드
    이름은 실행 시기에 따라 intent 또는 category(+subcategory)다.
    """
    txt_path = _model_dir(key) / f"{ep_id}.txt"
    if not txt_path.is_file():
        return {}
    try:
        text = txt_path.read_text(encoding="utf-8")
    except OSError:
        return {}

    out: dict[str, str] = {}
    turn = 0
    for block in _DOCTOR_OUT_RE.findall(text):
        try:
            parsed = json.loads(block.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(parsed, dict) or "question" not in parsed:
            continue
        turn += 1
        intent = str(parsed.get("intent") or parsed.get("category") or "").strip()
        sub = str(parsed.get("subcategory") or "").strip()
        if sub and sub.lower() != "null":
            intent = f"{intent} · {sub}" if intent else sub
        if intent:
            out[str(turn)] = intent
    return out


def _extract_alignment_history(key: str, ep_id: str) -> dict[str, dict]:
    """{turn: {key, name, description, reason, manifestation}} for each patient turn.

    Which profile item the patient answered from is the one thing a transcript cannot
    show — the reply is in the patient's words either way — so it is read back out of
    the run log: the key from the alignment stage's own output, and the wording it was
    handed from the [Targeted Info] block of the response prompt.
    """
    txt_path = _model_dir(key) / f"{ep_id}.txt"
    if not txt_path.is_file():
        return {}
    try:
        text = txt_path.read_text(encoding="utf-8")
    except OSError:
        return {}

    out: dict[str, dict] = {}
    marks = list(_META_RE.finditer(text))
    for i, m in enumerate(marks):
        turn, phase = m.group(1), m.group(2)
        block = text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        entry = out.setdefault(turn, {})

        if phase == "alignment":
            tail = block.split("========== OUTPUT", 1)
            if len(tail) < 2:
                continue
            body = tail[1].split("=====================")[0]
            found = re.search(r"\{[\s\S]*\}", body)
            if not found:
                continue
            try:
                picked = json.loads(found.group())
            except json.JSONDecodeError:
                continue
            for field in ("key", "name", "description", "reason"):
                value = picked.get(field, picked.get("matched_section") if field == "key" else None)
                if value not in (None, ""):
                    entry[field] = str(value)
            continue

        # response 프롬프트의 [Targeted Info]에는 환자가 실제로 건네받은 문장이 들어 있다.
        head = block.split("========== OUTPUT", 1)[0]
        payload = head.split("==========\n", 1)
        if len(payload) < 2:
            continue
        try:
            msgs = json.JSONDecoder().raw_decode(payload[1].strip())[0]
        except (json.JSONDecodeError, ValueError):
            continue
        content = next((m.get("content", "") for m in msgs if m.get("role") == "system"), "")
        # 프롬프트 서두 문장에도 "[Targeted Info]"가 나오므로 섹션 헤더로 잘라야 한다.
        # 오래된 실행은 같은 내용을 "[This Turn: ...]" 아래 label/"text" 형태로 담고 있다.
        if "\n[Targeted Info]\n" in content:
            targeted = content.split("\n[Targeted Info]\n", 1)[1].split("\n\n[", 1)[0].strip()
        elif "\n[This Turn: Profile Item to Talk About]\n" in content:
            targeted = content.rsplit("\n[This Turn: Profile Item to Talk About]\n", 1)[1].strip()
            if targeted.startswith("(none"):
                targeted = "None"
            else:
                label, _, said = targeted.partition("\n")
                targeted = f"name: {label.rstrip(':')}\nmanifestation: {said.strip()}"
        else:
            continue
        if targeted == "None":
            entry.setdefault("key", "None")
            continue
        for line in targeted.splitlines():
            line = line.strip()
            if line.startswith("manifestation:"):
                entry["manifestation"] = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("name:") and not entry.get("name"):
                entry["name"] = line.split(":", 1)[1].strip()
    return out


# ── 환자 증상 프로필 (txt 로그의 patient system prompt에서 추출) ────────────
def _extract_patient_profile(key: str, ep_id: str) -> dict | None:
    """<id>.txt의 첫 INPUT [patient] 블록에서 [Symptom Profile] 섹션을 파싱.

    반환: {"raw": str, "sections": [{"title": str, "items": [{"label","text"}]}]}
    """
    txt_path = _model_dir(key) / f"{ep_id}.txt"
    if not txt_path.is_file():
        return None
    try:
        text = txt_path.read_text(encoding="utf-8")
    except OSError:
        return None
    seg = None
    for m in re.finditer(r"={10} INPUT \[patient\] ={10}\n(.*?)\n={10} OUTPUT", text, re.DOTALL):
        try:
            msgs = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for msg in msgs:
            c = msg.get("content", "")
            if "\n[Symptom Profiles]\n" in c:
                seg = c.split("\n[Symptom Profiles]\n", 1)[1].split("\n\n[", 1)[0].strip()
                break
            if "[Symptom Profile]" in c:
                seg = c.split("[Symptom Profile]", 1)[1]
                for stop in ("\nRules:", "\n[Behavioral Guidelines]"):
                    i = seg.find(stop)
                    if i != -1:
                        seg = seg[:i]
                # 프롬프트 서두 문장에 "[Symptom Profile]"이 또 나올 수 있으므로
                # 실제 섹션 시작(첫 "▸" 라인)부터 취한다.
                j = seg.find("▸")
                if j != -1:
                    seg = seg[j:]
                seg = seg.strip()
                break
        if seg:
            break
    if not seg:
        return None
    # "▸ 섹션" / "- 항목: 내용" 구조로 파싱
    sections: list[dict] = []
    cur: dict | None = None
    for line in seg.split("\n"):
        if line.startswith("▸"):
            cur = {"title": line.lstrip("▸ ").strip(), "items": []}
            sections.append(cur)
            continue
        if cur is None:
            cur = {"title": "", "items": []}
            sections.append(cur)
        if line.startswith("- "):
            body = line[2:]
            label, sep, rest = body.partition(":")
            if sep and len(label) < 80:
                cur["items"].append({"label": label.strip(), "text": rest.strip()})
            else:
                cur["items"].append({"label": None, "text": body.strip()})
        elif line.strip():
            if cur["items"]:
                cur["items"][-1]["text"] += "\n" + line.strip()
            else:
                cur["items"].append({"label": None, "text": line.strip()})
    for sec in sections:
        sec["items"] = _fold_profile_records(sec["items"])
        if not sec["title"]:
            sec["title"] = "Symptom Manifestations"
    return {"raw": seg, "sections": sections}


def _fold_profile_records(items: list[dict]) -> list[dict]:
    """"- key: S030" + 들여쓴 name/description/manifestation 줄을 한 항목으로 접는다.

    현재 프롬프트의 [Symptom Profiles]는 증상 하나를 네 줄짜리 레코드로 적는다. 줄
    단위로 읽으면 label이 전부 "key"가 되어버리므로, 레코드를 다시 모아 라벨은
    "S030 (Worthlessness_Guilt)", 본문은 환자가 실제로 말하게 될 manifestation으로
    바꾼다. 이 형식이 아닌 오래된 로그는 그대로 통과시킨다.
    """
    out: list[dict] = []
    for it in items:
        if (it.get("label") or "").strip() != "key":
            out.append(it)
            continue
        fields: dict[str, str] = {}
        current = "key"
        for line in str(it.get("text") or "").split("\n"):
            head, sep, rest = line.partition(":")
            if sep and head.strip() in ("name", "description", "manifestation"):
                current = head.strip()
                fields[current] = rest.strip()
            elif current in fields:
                fields[current] += " " + line.strip()
            else:
                fields.setdefault(current, line.strip())
        code = fields.get("key", "").strip()
        name = fields.get("name", "").strip()
        out.append({
            "label": f"{code} ({name})" if code and name else (code or name or None),
            "text": fields.get("manifestation", "").strip() or fields.get("description", "").strip(),
            "desc": fields.get("description", "").strip(),
        })
    return out


# ── 번역 ─────────────────────────────────────────────────────────────────────
# config.json의 judge와 무관하게, 이 머신에서 키가 있는 provider를 골라 쓴다.
# (--translator-provider / --translator-model 로 오버라이드 가능)
# 셋 다 OpenAI 호환 API라 openai SDK 하나로 처리한다.
_PROVIDERS = {
    "openai": {"key_env": "OPENAI_API_KEY", "base_url": None,
               "default_model": "gpt-5.4-mini"},
    "openrouter": {"key_env": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1",
                   "default_model": "google/gemini-3.5-flash"},
    "gemini": {"key_env": "GEMINI_API_KEY",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
               "default_model": "gemini-3.5-flash"},
}
TRANSLATOR: dict = {"provider": None, "model": None, "client": None}
_translate_lock = threading.Lock()   # 과도한 동시 호출 방지

_TRANSLATE_SYSTEM = (
    "You are a professional Korean medical translator.\n"
    "Translate each numbered English utterance from a psychiatric interview into Korean.\n"
    "Rules:\n"
    "- Translate faithfully and literally. Do NOT paraphrase, summarize, soften, or embellish.\n"
    "- Keep sentence boundaries and content 1:1 with the source.\n"
    "- Use natural spoken Korean (doctor: 존댓말, patient: 자연스러운 구어체).\n"
    "- Keep clinical/diagnostic terms accurate; if a term is ambiguous, keep the English in parentheses.\n"
    "- Keep codes like F90.0, D001, S013 as-is.\n"
    "Output JSON only, no other text: an object mapping each input number (as a string) "
    "to its Korean translation. Every input number must appear exactly once."
)


def _resolve_translator(provider: str | None, model: str | None) -> None:
    """실행 시 provider/model 확정. provider 미지정이면 키가 있는 것을 자동 선택."""
    import os
    if provider:
        cands = [provider]
    else:
        cands = [p for p in ("openai", "gemini", "openrouter")
                 if os.environ.get(_PROVIDERS[p]["key_env"], "").strip()]
    for p in cands:
        if os.environ.get(_PROVIDERS[p]["key_env"], "").strip():
            TRANSLATOR["provider"] = p
            TRANSLATOR["model"] = model or _PROVIDERS[p]["default_model"]
            return
    TRANSLATOR["provider"] = None  # 번역 비활성 (뷰어는 정상 동작)


def _get_translator_client():
    if TRANSLATOR["client"] is None:
        import os
        from openai import OpenAI
        spec = _PROVIDERS[TRANSLATOR["provider"]]
        kw = {"api_key": os.environ[spec["key_env"]].strip(), "timeout": 300}
        if spec["base_url"]:
            kw["base_url"] = spec["base_url"]
        TRANSLATOR["client"] = OpenAI(**kw)
    return TRANSLATOR["client"]


def _chat_translate(messages: list[dict], max_tokens: int) -> str:
    client = _get_translator_client()
    kw = {"model": TRANSLATOR["model"], "messages": messages,
          "max_completion_tokens": max_tokens}
    try:
        resp = client.chat.completions.create(**kw)
    except Exception as e:  # 구형 모델/프록시는 max_tokens만 받는 경우
        if "max_completion_tokens" in str(e).lower():
            kw.pop("max_completion_tokens")
            kw["max_tokens"] = max_tokens
            resp = client.chat.completions.create(**kw)
        else:
            raise
    if not getattr(resp, "choices", None):
        return ""
    return resp.choices[0].message.content or ""


def _parse_json_obj(raw: str) -> dict:
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", s)
        if m:
            return json.loads(m.group(0))
        raise


def _translate_batch(items: list[str]) -> list[str | None]:
    """번역 대상 문자열 리스트 → 같은 길이의 한국어 리스트(실패 항목은 None)."""
    numbered = "\n\n".join(f"[{i}] {t}" for i, t in enumerate(items))
    out: list[str | None] = [None] * len(items)
    try:
        raw = _chat_translate(
            [{"role": "system", "content": _TRANSLATE_SYSTEM},
             {"role": "user", "content": numbered}],
            max_tokens=16384,
        )
        parsed = _parse_json_obj(raw)
        for i in range(len(items)):
            v = parsed.get(str(i))
            if isinstance(v, str) and v.strip():
                out[i] = v.strip()
    except Exception as e:
        print(f"[translate] batch call failed: {e}", flush=True)
    # 누락분은 개별 호출로 보충
    for i, v in enumerate(out):
        if v is not None:
            continue
        try:
            raw = _chat_translate(
                [{"role": "system", "content": _TRANSLATE_SYSTEM},
                 {"role": "user", "content": f"[0] {items[i]}"}],
                max_tokens=4096,
            )
            v2 = _parse_json_obj(raw).get("0")
            if isinstance(v2, str) and v2.strip():
                out[i] = v2.strip()
        except Exception as e:
            print(f"[translate] item {i} failed: {e}", flush=True)
    return out


# ── routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("review.html", run_name=RUN_ROOT.name, run_path=str(RUN_ROOT))


@app.route("/api/meta")
def api_meta():
    return jsonify({
        "run_name": RUN_ROOT.name,
        "run_path": str(RUN_ROOT),
        "models": discover_model_dirs(),
        "disorders": ID2NAME,
        "icd10_map": ICD10_INFO,
    })


@app.route("/api/episodes")
def api_episodes():
    key = request.args.get("model", "")
    return jsonify({"episodes": _episode_index(key)})


def _episode_alignment(dm: dict, key: str, ep_id: str) -> dict[str, dict]:
    """턴별 {환자가 고른 항목 + 의사의 질문 의도}.

    새 실행은 로그 안의 turns가 전부 들고 있고, 그 이전 실행은 프롬프트 로그에서
    두 조각을 따로 긁어 합친다.
    """
    from_turns = _alignment_from_turns(dm)
    if from_turns:
        return from_turns
    merged = _extract_alignment_history(key, ep_id)
    for turn, intent in _extract_question_intents(key, ep_id).items():
        merged.setdefault(turn, {})["intent"] = intent
    return merged


@app.route("/api/episode")
def api_episode():
    key = request.args.get("model", "")
    ep_id = request.args.get("id", "")
    fp = _episode_path(key, ep_id)
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)
    dm = data.get("doctor_memory") or {}
    gt = _gt_code(data.get("profile_id") or ep_id)
    final = (data.get("final_diagnosis") or "").strip() or None
    fd = dm.get("final_diagnosis") or {}
    return jsonify({
        "id": ep_id,
        "gt": gt,
        "gt_name": ID2NAME.get(gt, ""),
        "final": final,
        "final_disease": CODE2ID.get((final or "").upper()),
        "final_disease_name": ID2NAME.get(CODE2ID.get((final or "").upper(), ""), ""),
        "final_reason": fd.get("reason") if isinstance(fd, dict) else None,
        "final_candidates": dm.get("final_candidates_used") or [],
        "correct": _is_correct(gt, final),
        "closed_at": data.get("closed_at_patient_turn"),
        "transcript": data.get("transcript") or [],
        "inference_history": dm.get("inference_history") or [],
        "profile": _extract_patient_profile(key, ep_id),
        "alignment": _episode_alignment(dm, key, ep_id),
    })


@app.route("/api/translate", methods=["POST"])
def api_translate():
    body = request.get_json(silent=True) or {}
    key = str(body.get("model", ""))
    ep_id = str(body.get("id", ""))
    include_profile = bool(body.get("include_profile"))
    fp = _episode_path(key, ep_id)

    # 프로필 번역 대상 텍스트 (섹션→항목 순서로 평탄화; 클라이언트도 같은 순서로 매핑)
    prof_texts: list[str] = []
    if include_profile:
        profile = _extract_patient_profile(key, ep_id)
        if profile:
            prof_texts = [it["text"] for sec in profile["sections"] for it in sec["items"]]

    if not TRANSLATOR["provider"]:
        return jsonify({"error": "사용 가능한 번역 API 키가 없습니다 (.env에 OPENAI/GEMINI/OPENROUTER_API_KEY 필요)"}), 503

    with open(fp, encoding="utf-8") as f:
        data = json.load(f)
    transcript = data.get("transcript") or []
    dm = data.get("doctor_memory") or {}
    fd = dm.get("final_diagnosis") or {}
    reason = fd.get("reason") if isinstance(fd, dict) else None

    items = [m.get("content", "") for m in transcript]
    if reason:
        items.append(reason)
    n_base = len(items)
    items += prof_texts

    with _translate_lock:   # 과도한 동시 호출 방지
        try:
            ko = _translate_batch(items)
        except Exception as e:
            return jsonify({"error": f"translation failed: {e}"}), 502

    payload = {
        "id": ep_id,
        "model": f"{TRANSLATOR['provider']}/{TRANSLATOR['model']}",
        "messages": ko[: len(transcript)],
        "final_reason": ko[len(transcript)] if reason else None,
        "profile": ko[n_base:] if prof_texts else None,
    }
    n_fail = sum(1 for v in ko if v is None)
    if n_fail:
        payload["partial"] = n_fail
    return jsonify(payload)


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    global RUN_ROOT
    ap = argparse.ArgumentParser(description="Doctor-Patient 대화 기록 리뷰 뷰어")
    ap.add_argument("--run", default="saved/run_batch_20260911",
                    help="결과 run 폴더 (예: saved/current_target, 절대경로 허용)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5004)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--translator-provider", choices=list(_PROVIDERS),
                    help="번역 API provider (기본: 키가 있는 것 자동 선택)")
    ap.add_argument("--translator-model", help="번역 모델명 (기본: provider별 기본값)")
    args = ap.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass
    _resolve_translator(args.translator_provider, args.translator_model)

    run = Path(args.run)
    RUN_ROOT = run if run.is_absolute() else (PROJECT_ROOT / run)
    if not (RUN_ROOT / "logs").is_dir():
        raise SystemExit(f"[review] logs 폴더가 없습니다: {RUN_ROOT / 'logs'}")

    models = discover_model_dirs()
    print(f"[review] run    : {RUN_ROOT}")
    print(f"[review] models : {len(models)}")
    for m in models:
        print(f"  - {m['key']} ({m['episodes']} episodes)")
    if TRANSLATOR["provider"]:
        print(f"[review] translator: {TRANSLATOR['provider']}/{TRANSLATOR['model']}")
    else:
        print("[review] translator: 비활성 (API 키 없음)")
    print(f"[review] http://localhost:{args.port}/")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
