"""콘텐츠 성과 — 스펙 v4 §3.2. 스트림릿은 게이트·헤더·데이터 로딩만 하고,
본문(마스터·디테일·컨트롤)은 views.performance가 그린 HTML을 iframe으로 띄운다."""
import os, sys
_here = os.path.abspath(__file__)
_repo_root = _here[: _here.index(os.sep + "report_dashboard" + os.sep)]
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import streamlit as st

from report_dashboard import frame, ui
from report_dashboard.auth import require_role
from report_dashboard.design_system import inject_design_system
from report_dashboard.header import render_header
from report_dashboard.report_common import CHANNELS, load_campaign_context
from report_dashboard.repo import ReportRepo
from report_dashboard.views import performance

role, email = require_role()
repo = ReportRepo()
inject_design_system()
campaigns = repo.campaigns()
campaign_id = render_header(role, email, campaigns, current="콘텐츠 성과")
if campaign_id is None:
    st.markdown(ui.empty_state("등록된 캠페인이 없습니다", "담당자가 캠페인을 등록하면 표시됩니다."), unsafe_allow_html=True); st.stop()
campaign = next(c for c in campaigns if c["campaign_id"] == campaign_id)

# 채널 필터는 항상 전체로 읽는다 — 필터·정렬·숨기기는 iframe 안 JS가 클라이언트에서 처리한다(§2).
ctx = load_campaign_context(repo, campaign_id, CHANNELS)
if ctx is None:
    st.markdown(ui.empty_state("등록된 콘텐츠가 없습니다", "콘텐츠가 등록되면 성과가 표시됩니다."), unsafe_allow_html=True); st.stop()
frame.render(performance.build(ctx, campaign))
