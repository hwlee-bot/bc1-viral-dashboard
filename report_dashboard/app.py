# report_dashboard/app.py
"""진입점 겸 라우터. 인증 게이트 → 숨김 내비(커스텀 헤더가 st.page_link로 이동시킨다).
사이드바는 v3에서 폐기(스펙 §2 결정 3). 페이지마다 inject_design_system()·render_header()를 직접 호출한다 —
AppTest가 페이지 파일을 단독 실행하는 경로(1_상위노출.py 상단 주석)와 동작을 맞추기 위해서다."""

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

from report_dashboard.auth import require_role
from report_dashboard.nav import pages_for

st.set_page_config(page_title="바이럴 성과 리포팅", layout="wide", initial_sidebar_state="collapsed")

role, email = require_role()

st.navigation(
    [st.Page(path, title=title, default=(i == 0)) for i, (title, path) in enumerate(pages_for(role))],
    position="hidden",
).run()
