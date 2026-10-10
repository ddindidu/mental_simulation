"""Batch (async submit/poll/collect) LLM-as-judge calls for OpenAI and Gemini.

Why batch is safe here (unlike the doctor/patient dialogue loop): every judge
call this module is used for — turn-level symptom extraction, the
question→symptom mapper, and the diagnostic-reasoning checklist judge — reads
only fixed data already sitting in a simulation log or *_result.json (the
doctor's question, the patient's alignment/response, the doctor's own final
checklist). None of these prompts depend on a *judge* call's own prior
output, only on the (already-generated) transcript, so every judge call for
an episode/doctor can be built up front and submitted together instead of
one blocking call at a time.

Both providers' batch APIs are async: submit now, poll later (minutes to
24h), then collect. This module never blocks waiting for completion — each
eval/*_batch.py script has a `--submit` phase (build every request, submit,
save a small job-state JSON) and a separate `--collect` phase (poll; if done,
fetch results and write the normal output files). Run `--collect` again
later if the job isn't done yet.

Request shape: {"custom_id": str, "system": str, "user": str, "max_tokens": int}
Job-state shape (returned by submit_batch, persisted by the caller):
  {"provider": "openai"|"gemini", "model": str, "created_at": float,
   "chunks": [{"external_id": str, "n": int}, ...]}
"""
from __future__ import annotations

import json
import time
from typing import Any

# ── OpenAI ──────────────────────────────────────────────────────────────────

def _submit_openai_chunk(requests: list[dict], model: str) -> str:
    from .llm import _get_openai_client, _openai_reasoning_style_model

    client = _get_openai_client()
    reasoning = _openai_reasoning_style_model(model)
    lines = []
    for r in requests:
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": r["system"]},
                {"role": "user", "content": r["user"]},
            ],
        }
        tok_key = "max_completion_tokens" if reasoning else "max_tokens"
        body[tok_key] = int(r.get("max_tokens", 4096))
        if not reasoning:
            body["temperature"] = 0.0
        lines.append(json.dumps({
            "custom_id": r["custom_id"],
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": body,
        }))
    jsonl_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    file_obj = client.files.create(
        file=(f"batch_{int(time.time())}_{len(requests)}.jsonl", jsonl_bytes),
        purpose="batch",
    )
    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    return batch.id


def _poll_openai(external_id: str):
    from .llm import _get_openai_client
    client = _get_openai_client()
    b = client.batches.retrieve(external_id)
    return b.status, b


def _normalize_openai_status(status: str) -> str:
    if status == "completed":
        return "completed"
    if status in ("failed", "expired", "cancelled"):
        return "failed"
    return "in_progress"


def _retrieve_openai(batch_obj) -> tuple[dict[str, str], dict[str, str]]:
    from .llm import _get_openai_client
    client = _get_openai_client()
    results: dict[str, str] = {}
    errors: dict[str, str] = {}
    if not getattr(batch_obj, "output_file_id", None):
        if getattr(batch_obj, "error_file_id", None):
            content = client.files.content(batch_obj.error_file_id).text
            for line in content.splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                errors[row.get("custom_id", "?")] = json.dumps(row.get("error") or row)
        return results, errors
    content = client.files.content(batch_obj.output_file_id).text
    for line in content.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        cid = row["custom_id"]
        resp = row.get("response")
        if resp and resp.get("status_code") == 200:
            body = resp["body"]
            results[cid] = body["choices"][0]["message"]["content"]
        else:
            errors[cid] = json.dumps(row.get("error") or resp)
    return results, errors


# ── Gemini ──────────────────────────────────────────────────────────────────

def _submit_gemini_chunk(requests: list[dict], model: str, api_key: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    inline = []
    for r in requests:
        contents = [types.Content(role="user", parts=[types.Part(text=r["user"])])]
        cfg = types.GenerateContentConfig(
            system_instruction=r["system"],
            max_output_tokens=int(r.get("max_tokens", 4096)),
            temperature=0.0,
        )
        inline.append(types.InlinedRequest(
            model=model, contents=contents, config=cfg,
            metadata={"custom_id": r["custom_id"]},
        ))
    job = client.batches.create(model=model, src=inline)
    return job.name


def _poll_gemini(external_id: str, api_key: str):
    from google import genai
    client = genai.Client(api_key=api_key)
    job = client.batches.get(name=external_id)
    return job.state.name, job


def _normalize_gemini_status(state_name: str) -> str:
    if state_name == "JOB_STATE_SUCCEEDED":
        return "completed"
    if state_name in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"):
        return "failed"
    return "in_progress"


def _retrieve_gemini(job) -> tuple[dict[str, str], dict[str, str]]:
    results: dict[str, str] = {}
    errors: dict[str, str] = {}
    dest = job.dest
    for resp in (dest.inlined_responses if dest and dest.inlined_responses else []):
        cid = (resp.metadata or {}).get("custom_id", "?")
        if resp.error:
            errors[cid] = str(resp.error)
        elif resp.response is not None:
            try:
                results[cid] = resp.response.text or ""
            except Exception as e:  # response present but no text part
                errors[cid] = f"no text in response: {e}"
        else:
            errors[cid] = "empty response"
    return results, errors


# ── Public API ────────────────────────────────────────────────────────────

def submit_batch(
    requests: list[dict],
    *,
    provider: str,
    model: str,
    api_key: str | None = None,
    chunk_size: int = 500,
) -> dict:
    """Submit `requests` as one or more batch jobs. Returns job-state to persist."""
    if provider not in ("openai", "gemini"):
        raise ValueError(f"Batch not supported for provider={provider!r} (only openai, gemini)")
    if provider == "gemini" and not api_key:
        raise ValueError("Gemini batch requires an explicit api_key")

    chunks = [requests[i:i + chunk_size] for i in range(0, len(requests), chunk_size)]
    job: dict[str, Any] = {
        "provider": provider, "model": model, "created_at": time.time(), "chunks": [],
    }
    for chunk in chunks:
        if provider == "openai":
            ext_id = _submit_openai_chunk(chunk, model)
        else:
            ext_id = _submit_gemini_chunk(chunk, model, api_key)
        job["chunks"].append({"external_id": ext_id, "n": len(chunk)})
    return job


def poll_batch(job: dict, *, api_key: str | None = None) -> str:
    """Return 'completed' | 'in_progress' | 'failed' (any non-completed chunk failed and
    none are still running) | 'partial' (a mix of completed/failed, none still running)."""
    statuses = []
    for c in job["chunks"]:
        if job["provider"] == "openai":
            st, _ = _poll_openai(c["external_id"])
            statuses.append(_normalize_openai_status(st))
        else:
            st, _ = _poll_gemini(c["external_id"], api_key)
            statuses.append(_normalize_gemini_status(st))
    if any(s == "in_progress" for s in statuses):
        return "in_progress"
    if all(s == "completed" for s in statuses):
        return "completed"
    if all(s == "failed" for s in statuses):
        return "failed"
    return "partial"


def collect_batch(job: dict, *, api_key: str | None = None) -> tuple[dict[str, str], dict[str, str]]:
    """Fetch whatever chunks are done (completed or failed). Call after poll_batch()
    reports 'completed' or 'partial'/'failed' (to at least see the error detail)."""
    all_results: dict[str, str] = {}
    all_errors: dict[str, str] = {}
    for c in job["chunks"]:
        if job["provider"] == "openai":
            st, obj = _poll_openai(c["external_id"])
            if _normalize_openai_status(st) == "in_progress":
                continue
            r, e = _retrieve_openai(obj)
        else:
            st, obj = _poll_gemini(c["external_id"], api_key)
            if _normalize_gemini_status(st) == "in_progress":
                continue
            r, e = _retrieve_gemini(obj)
        all_results.update(r)
        all_errors.update(e)
    return all_results, all_errors
