"""Side panel용 system prompt를 읽기 쉬운 HTML로 변환한다."""
from __future__ import annotations

import html
import re

_SUB_MARK = "▸"


def _line_to_html(raw: str) -> str | None:
    """한 줄을 HTML 조각으로 변환. 빈 줄은 gap div."""
    raw_stripped = raw.rstrip()
    stripped = raw_stripped.strip()

    if not stripped:
        return '<div class="prompt-gap" aria-hidden="true"></div>'

    if stripped.startswith("/"):
        parts = stripped.split(None, 1)
        cmd = parts[0]
        if cmd.lower() == "/no_think":
            return None
        rest = parts[1] if len(parts) > 1 else ""
        return (
            '<div class="prompt-cmd">'
            f'<span class="prompt-cmd-name">{html.escape(cmd)}</span>'
            f'<span class="prompt-cmd-rest">{html.escape(rest)}</span>'
            "</div>"
        )

    if stripped.startswith(_SUB_MARK):
        inner = stripped[len(_SUB_MARK) :].strip()
        return (
            '<div class="prompt-subsection">'
            f'<span class="prompt-subsection-mark" aria-hidden="true">'
            f"{html.escape(_SUB_MARK)}</span>"
            f'<span class="prompt-subsection-text">{html.escape(inner)}</span>'
            "</div>"
        )

    if (
        stripped.startswith("[")
        and stripped.endswith("]")
        and len(stripped) >= 2
    ):
        inner = stripped[1:-1]
        return f'<div class="prompt-section">{html.escape(inner)}</div>'

    m = re.match(r"^(\s*)-\s+(.+)$", raw)
    if m:
        ws, body = m.group(1), m.group(2)
        level = min(len(ws) // 2, 4)
        cls = "prompt-item" + (f" prompt-item--l{level}" if level else "")
        return (
            f'<div class="{cls}">'
            '<span class="prompt-item-dot" aria-hidden="true"></span>'
            f'<span class="prompt-item-text">{html.escape(body)}</span>'
            "</div>"
        )

    return f'<p class="prompt-line">{html.escape(raw_stripped)}</p>'


def _lines_to_html(lines: list[str]) -> str:
    frags: list[str] = []
    for line in lines:
        h = _line_to_html(line)
        if h is not None:
            frags.append(h)
    return "".join(frags)


def system_prompt_to_html(text: str) -> str:
    """플레인 텍스트 프롬프트를 패널 테마에 맞는 HTML로 변환 (이스케이프 포함)."""
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == "[Symptom Profile]":
            h = _line_to_html(lines[i])
            if h is not None:
                out.append(h)
            i += 1
            inner: list[str] = []
            while i < len(lines) and lines[i].strip() != "[행동 지침]":
                inner.append(lines[i])
                i += 1
            out.append('<div class="prompt-sp-shell">')
            out.append(_lines_to_html(inner))
            out.append("</div>")
            continue
        h = _line_to_html(lines[i])
        if h is not None:
            out.append(h)
        i += 1
    return "".join(out)
