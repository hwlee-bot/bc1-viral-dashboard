# report_dashboard/pages/0_요약.py
"""요약 카드. 기존 app.py의 내용이 이사 왔다 — app.py는 라우터가 된다(Task 6).

이 페이지를 AppTest로 직접 실행하면 라우터를 거치지 않으므로, 게이트를 여기서도
호출한다. 다른 페이지와 달리 이 파일이 게이트의 테스트 대상이다.
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

from report_dashboard.auth import require_role
from report_dashboard.repo import ReportRepo

role, email = require_role()

repo = ReportRepo()

st.title("바이럴 성과 리포팅")
st.caption("캠페인별 조회수·네이버 순위 추이를 누적해서 본다.")

c1, c2, c3 = st.columns(3)
c1.metric("캠페인", len(repo.campaigns()))
c2.metric("등록된 콘텐츠", len(repo.contents()))
c3.metric("누적된 조회수 관측값", len(repo.content_metrics()))

latest_run = repo.latest_collection_run()
if latest_run:
    st.caption(f"마지막 자동 수집: {latest_run.get('started_at', '')}")
else:
    st.info("아직 자동 수집 기록이 없다 — 등록·관리자 페이지에서 수동으로 값을 넣을 수 있다.")
