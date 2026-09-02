# report_dashboard/app.py
"""바이럴 성과 리포팅 대시보드 — 진입점 겸 라우터.

`st.navigation`을 쓰므로 이 파일이 모든 rerun에서 실행되는 라우터다. 즉 로그인
게이트를 여기 한 번만 두면 모든 페이지가 보호된다.

공식 문서: "As soon as any session of your app executes the st.navigation
command, your app will ignore the pages/ directory (across all sessions)."
그래서 pages/ 디렉토리를 그대로 두어도 자동 네비게이션이 끼어들지 않고,
기존 테스트가 페이지 파일을 직접 실행하는 경로도 유지된다.

실행: `python3 -m streamlit run report_dashboard/app.py`
"""

# Streamlit Cloud는 실행할 스크립트가 있는 폴더만 sys.path에 넣는다(공식 소스
# streamlit/web/bootstrap.py::_fix_sys_path 확인함) — 저장소 루트는 안 들어간다.
# 로컬은 `python3 -m streamlit run`(-m이 CWD를 넣어줌)이나 pytest(패키지 루트를
# 자동 추가)가 이 문제를 가려서 배포 전엔 안 드러났다. report_dashboard.* 절대
# 임포트가 되려면 저장소 루트가 필요하므로 여기서 직접 넣는다.
import os
import sys

_here = os.path.abspath(__file__)
_repo_root = _here[: _here.index(os.sep + "report_dashboard" + os.sep)]
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import streamlit as st

from report_dashboard.auth import ROLE_TEAM, require_role
from report_dashboard.design_system import inject_base_fonts
from report_dashboard.nav import PAGE_ICONS, pages_for
from report_dashboard.reporting import latest_sync_timestamp
from report_dashboard.repo import ReportRepo

st.set_page_config(page_title="바이럴 성과 리포팅", layout="wide")

role, email = require_role()

# 사이드바 브랜드 로고·동기화 상태(2026-09-02 신규 — manyo.madup.app
# 레퍼런스처럼 사이드바에 로고 락업과 "마지막 동기화" 표시를 둔다). 페이지이
# 몇 개든 여기 한 곳에서만 주입하면 전 페이지에 적용된다(app.py가 라우터라
# 모든 rerun에서 실행됨, 파일 상단 docstring 참고). CSS는 어디서 주입하든
# 문서 전체에 적용되지만, 로고·동기화 표시용 실제 마크업은 반드시
# `with st.sidebar:` 블록 "안"에서 그려야 사이드바에 나타난다.
inject_base_fonts()
st.markdown(
    """
<style>
[data-testid="stSidebarNav"] { padding-top: 0; }
.vr-sidebar-logo { padding: 4px 4px 18px; }
.vr-sidebar-logo b { font-family: var(--vr-font-display); font-size: 22px; font-weight: 400;
  letter-spacing: 0.01em; color: #1e1600; display:block; line-height: 1; }
.vr-sidebar-logo span { font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
  color: #b9860a; display:block; margin-top: 4px; }
/* 활성 페이지를 옅은 앰버 알약으로 — 스트림릿이 활성 링크에 붙이는
   aria-current="page"를 그대로 스코프한다(실측 확인, 별도 클래스 필요 없음). */
[data-testid="stSidebarNavLink"] { border-radius: 10px !important; }
[data-testid="stSidebarNavLink"][aria-current="page"] {
  background: rgba(242,163,15,0.14) !important;
}
.vr-sidebar-sync { padding: 10px 4px 2px; font-size: 11px; color: #8a8578; }
.vr-sidebar-sync b { color: #5a5648; }
</style>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        '<div class="vr-sidebar-logo"><b>바이럴 리포팅</b><span>VIRAL PERFORMANCE</span></div>',
        unsafe_allow_html=True,
    )
    st.caption(f"{email} ({'담당자' if role == ROLE_TEAM else '광고주'})")
    if st.button("로그아웃", key="sidebar_logout"):
        st.logout()

st.navigation(
    [st.Page(path, title=title, icon=PAGE_ICONS.get(title), default=(i == 0))
     for i, (title, path) in enumerate(pages_for(role))]
).run()

with st.sidebar:
    sync_at = latest_sync_timestamp(ReportRepo().content_metrics())
    st.markdown(
        f'<div class="vr-sidebar-sync">🟢 <b>DATA SYNCED</b><br>{sync_at or "아직 수집된 데이터 없음"}</div>',
        unsafe_allow_html=True,
    )
