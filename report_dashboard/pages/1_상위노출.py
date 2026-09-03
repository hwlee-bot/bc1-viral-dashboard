"""상위노출 — 스펙 v4 §3.2. 스트림릿은 게이트·헤더·데이터 로딩만 하고,
본문(스트립·키워드 점유율·검색결과·레일)은 views.exposure가 그린 HTML을 iframe으로 띄운다."""
import os, sys
_here = os.path.abspath(__file__)
_repo_root = _here[: _here.index(os.sep + "report_dashboard" + os.sep)]
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import streamlit as st

from report_dashboard import frame, share, ui
from report_dashboard.auth import require_role
from report_dashboard.design_system import inject_design_system
from report_dashboard.header import render_header
from report_dashboard.report_common import CHANNELS, load_campaign_context
from report_dashboard.repo import ReportRepo
from report_dashboard.views import exposure

# 게이트를 이 파일에서도 호출한다 — app.py의 라우터 게이트에만 의존하면 안 된다
# (미인증 트래픽만 들어오는 동안 Streamlit이 app.py 대신 이 파일을 직접 실행한다).
role, email = require_role()
repo = ReportRepo()
inject_design_system()
campaigns = repo.campaigns()
campaign_id = render_header(role, email, campaigns, current="상위노출")
if campaign_id is None:
    st.markdown(ui.empty_state("등록된 캠페인이 없습니다", "담당자가 캠페인을 등록하면 표시됩니다."), unsafe_allow_html=True); st.stop()
campaign = next(c for c in campaigns if c["campaign_id"] == campaign_id)

# 채널 필터는 항상 전체로 읽는다 — 필터는 iframe 안 JS가 클라이언트에서 처리한다(§2).
ctx = load_campaign_context(repo, campaign_id, CHANNELS)
if ctx is None:
    st.markdown(ui.empty_state("등록된 콘텐츠가 없습니다", "콘텐츠가 등록되면 키워드 순위와 점유율이 표시됩니다."), unsafe_allow_html=True); st.stop()
terms = share.terms_from_rows(repo.brand_terms(campaign_id))
frame.render(exposure.build(ctx, campaign, terms))
