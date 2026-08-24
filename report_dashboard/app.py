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
from report_dashboard.nav import pages_for

st.set_page_config(page_title="바이럴 성과 리포팅", layout="wide")

role, email = require_role()

with st.sidebar:
    st.caption(f"{email} ({'담당자' if role == ROLE_TEAM else '광고주'})")
    if st.button("로그아웃", key="sidebar_logout"):
        st.logout()

st.navigation(
    [st.Page(path, title=title, default=(i == 0))
     for i, (title, path) in enumerate(pages_for(role))]
).run()
