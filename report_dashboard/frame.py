# report_dashboard/frame.py
"""리포트 본문 iframe 문서 조립(스펙 v4 §3.1). 목업 CSS/JS 원문 + runtime.js를 한 HTML로 묶어 components.html로 띄운다."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from report_dashboard import ui

_STATIC = Path(__file__).parent / "static"


_CACHE: dict[str, tuple[float, str]] = {}


def static_text(name: str) -> str:
    """static/ 파일을 수정시각(mtime) 기준으로 캐시해서 읽는다.

    lru_cache(영구)였을 때의 배포 사고(2026-09-03): runtime.js만 바뀐 푸시는 .py 변경이 없어
    스트림릿이 모듈을 다시 읽지 않고, 프로세스가 살아 있는 동안 옛 JS를 계속 내보냈다.
    mtime이 바뀌면 다시 읽으므로 JS/CSS만 바뀌어도 다음 렌더부터 새 파일이 나간다.
    """
    path = _STATIC / name
    mtime = path.stat().st_mtime
    hit = _CACHE.get(name)
    if hit is None or hit[0] != mtime:
        hit = (mtime, path.read_text(encoding="utf-8"))
        _CACHE[name] = hit
    return hit[1]


class _PageCss:
    """`frame.PAGE_CSS["exposure"]` 형태를 유지하되 호출 시점에 읽는다(import 시점 고정 금지 — 위 캐시 사고와 같은 이유)."""

    _FILES = {"exposure": "page-exposure.css", "content": "page-content.css"}

    def __getitem__(self, key: str) -> str:
        return static_text(self._FILES[key])

    def keys(self):
        return self._FILES.keys()


PAGE_CSS = _PageCss()

PARENT_CSS = """
section.stMain { overflow: hidden !important; }
[data-testid="stMainBlockContainer"] { padding-bottom: 0 !important; }
iframe[title="st.iframe"] { display: block; border: 0; width: 100%; }
"""


@dataclass
class FrameContent:
    body_html: str
    page_css: str = ""
    payload: dict | None = None
    export_md: str = ""
    export_filename: str = "리포트.md"


def _script_safe(text: str) -> str:
    """<script> 안에 넣는 본문에서 조기 종료 토큰을 무력화한다(JSON·마크다운 공통)."""
    return text.replace("</", "<\\/")


def document(content: FrameContent) -> str:
    head = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<style>{static_text('base.css')}\n{static_text('mix.css')}\n{content.page_css}</style></head>"
    )
    parts = [f'<body><main class="wrap">{content.body_html}</main>']
    if content.payload is not None:
        parts.append(f'<script type="application/json" id="payload">{_script_safe(json.dumps(content.payload, ensure_ascii=False))}</script>')
    if content.export_md:
        parts.append(f'<script type="text/plain" id="export-md" data-filename="{ui.esc(content.export_filename)}">{_script_safe(content.export_md)}</script>')
    parts.append(f"<script>{static_text('charts.js')}\n{static_text('icons.js')}\n{static_text('runtime.js')}</script></body></html>")
    return head + "".join(parts)


def render(content: FrameContent) -> None:
    st.markdown(f"<style>{PARENT_CSS}</style>", unsafe_allow_html=True)
    try:
        components.html(document(content), height=800, scrolling=True)
    except Exception:
        st.markdown(ui.empty_state("리포트를 그릴 수 없습니다", "새로고침해도 반복되면 담당자에게 알려주세요."), unsafe_allow_html=True)
