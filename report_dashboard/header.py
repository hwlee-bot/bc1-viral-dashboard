# report_dashboard/header.py
"""상단 헤더(스펙 §5 공통·§9.2). 스트림릿 헤더 영역엔 위젯을 못 넣으므로 본문 첫 줄을 sticky 헤더로 쓴다.

한 줄 = [로고+브랜드] [페이지 탭 3개(+담당자면 등록)] [캠페인 셀렉트 · 계정]. 테마 토글은 스트림릿 ⋮ 메뉴가 담당.
계정 슬롯은 팝오버(R7 컨트롤러 판정) — 사이드바 폐기로 로그아웃 동선이 사라졌던 것을 여기서 되살린다.
"""
from __future__ import annotations

import streamlit as st
from streamlit.errors import StreamlitAPIException

from report_dashboard.auth import ROLE_TEAM
from report_dashboard.nav import ADMIN, pages_for
from report_dashboard.ui import esc

BRAND_NAME = "마녀공장"   # 브랜드별 배포 시 이 상수와 design_system 액센트 4토큰만 바꾼다(스펙 §3.2)


def header_links_for(role: str) -> list[tuple[str, str]]:
    return pages_for(role)


def _tab(title: str, path: str, current: str) -> None:
    """현재 탭이면 링크가 아니라 마크다운 스팬으로 그린다(§9.2 실측 보정).

    실서버(streamlit 1.58) 실측: st.page_link 앵커에 aria-current가 안 붙어서
    CSS만으로는 활성 탭을 판별할 수 없다. 그래서 활성 탭 자체를 링크로 만들지
    않고 `.hdr-tab.on` 클래스가 붙은 순수 텍스트로 렌더링해 판별 문제를 없앤다.
    """
    if title == current:
        st.markdown(f'<span class="hdr-tab on">{esc(title)}</span>', unsafe_allow_html=True)
    else:
        _page_link(title, path, current)


def _page_link(title: str, path: str, current: str) -> None:
    try:
        st.page_link(path, label=title)
    except (StreamlitAPIException, KeyError):
        # AppTest가 페이지 파일을 단독 실행하면 st.navigation 미등록 → 마크다운 탭으로 폴백.
        # 실측(streamlit 1.58): st.navigation이 안 돈 컨텍스트에서는 page_link 내부가
        # StreamlitPageNotFoundError로 정리되기 전에 all_app_pages 딕셔너리 조회에서
        # KeyError('url_pathname')로 먼저 죽는다 — StreamlitAPIException(그 에러의 부모
        # 클래스)만 잡으면 여길 안 타서 브리프대로 폴백이 안 됐다. 그래서 KeyError도 같이 잡는다.
        cls = "on" if title == current else ""
        st.markdown(f'<span class="hdr-tab {cls}">{esc(title)}</span>', unsafe_allow_html=True)


def render_header(role: str, email: str, campaigns: list[dict], *, current: str) -> str | None:
    labels = {f"{c['brand']} · {c['name']}": c["campaign_id"] for c in campaigns}
    with st.container():
        st.markdown('<span class="hdr-marker"></span>', unsafe_allow_html=True)
        left, mid, right = st.columns([2.4, 4, 3.6], vertical_alignment="center")
        with left:
            st.markdown(
                f'<div class="hdr-brand"><span class="hdr-logo">{esc(BRAND_NAME[0])}</span>'
                f'<span style="display:inline-block;vertical-align:middle"><b>{esc(BRAND_NAME)}</b><span>바이럴 리포팅</span></span></div>',
                unsafe_allow_html=True,
            )
        links = header_links_for(role)
        report_links = [l for l in links if l[0] != ADMIN[0]]
        with mid:
            cols = st.columns(len(report_links))
            for col, (title, path) in zip(cols, report_links):
                with col:
                    _tab(title, path, current)
        with right:
            c1, c2, c3 = st.columns([3, 1.6, 1.1], vertical_alignment="center")
            with c1:
                picked = None
                if labels:
                    choice = st.selectbox("캠페인", options=list(labels), key="campaign_picker", label_visibility="collapsed")
                    picked = labels[choice]
            with c2:
                if role == ROLE_TEAM:
                    _tab(ADMIN[0], dict(links).get(ADMIN[0], ADMIN[1]), current)
            with c3:
                # st.popover 라벨은 마크다운 텍스트지 HTML이 아니다(unsafe_allow_html 경로가
                # 없음) — esc()로 감싸면 "&"류 문자가 있을 때 오히려 "&amp;"가 그대로 보인다.
                # 이니셜은 이메일 로컬파트 앞 2글자라 애초에 위험 문자가 안 들어오지만, 라벨은
                # 원문 그대로 넘긴다.
                initials = (email.split("@")[0][:2] or "?").upper()
                with st.popover(initials, use_container_width=False):
                    st.caption(email)
                    if st.button("로그아웃", key="hdr_logout"):
                        st.logout()
    return picked
