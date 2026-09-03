# report_dashboard/frame.py
"""리포트 본문 iframe 문서 조립(스펙 v4 §3.1). 목업 CSS/JS 원문 + runtime.js를 한 HTML로 묶어 components.html로 띄운다."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from report_dashboard import ui

_STATIC = Path(__file__).parent / "static"


@lru_cache(maxsize=None)
def static_text(name: str) -> str:
    return (_STATIC / name).read_text(encoding="utf-8")


PAGE_CSS = {"exposure": static_text("page-exposure.css"), "content": static_text("page-content.css")}

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
