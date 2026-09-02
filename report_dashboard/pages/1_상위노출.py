"""캠페인 콘텐츠의 네이버 상위노출 현황 — 어떤 키워드로 몇 위에 떴는지 한눈에.

읽기 전용 — 등록은 3_등록.py에서. 원래 리포트 페이지의 "상위노출" 탭이었던
것을(2026-09-02) 별도 사이드바 메뉴로 분리했다 — 탭이 아니라 메뉴 자체를
나누고 싶다는 요청 확인. 헤더·필터·카드 렌더링은
report_dashboard/report_common.py 공유 모듈을 쓴다(콘텐츠 성과 페이지와
같은 모듈 — 둘 다 같은 디자인 시스템을 써야 해서).
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
from report_dashboard.report_common import (
    _render_channel_donut, _render_exposure_content_list, _render_exposure_rank_list,
    _render_keyword_impact_leaderboard, _render_keyword_watchlist, _render_stat_row, load_campaign_context,
    render_campaign_header,
)
from report_dashboard.repo import ReportRepo
from report_dashboard.reporting import (
    channel_distribution, exposure_counts_by_channel, keyword_impact_leaderboard, keyword_rank_summary,
    keyword_weekly_exposure_counts, keyword_weekly_view_sums,
)

# 게이트를 이 파일에서도 호출한다 — app.py의 라우터 게이트에만 의존하면 안 된다.
# Streamlit의 PagesManager.uses_pages_directory는 프로세스 전역 클래스 속성이고,
# pages/ 디렉토리가 존재하므로 True로 시작한다. 그 플래그는 사용자 코드가 실제로
# st.navigation을 실행하는 순간에만 False로 바뀌는데, app.py는 그 앞에서
# require_role()을 호출하고 미인증 방문자는 전부 st.stop()으로 끝난다. 따라서
# 미인증 트래픽만 들어오는 동안(배포·재부팅·슬립 해제 직후)에는 플래그가 True로
# 남아 Streamlit이 app.py 대신 이 페이지 파일을 직접 실행한다 — 라우터 게이트가
# 아예 돌지 않는다. 실제 서버에서 익명 세션으로 재현 확인함.
# 그래서 각 페이지가 스스로 안전해야 한다.
role, email = require_role()

repo = ReportRepo()

render_campaign_header(email)
ctx = load_campaign_context(repo)
contents = ctx["contents"]
view_metrics = ctx["view_metrics"]
all_ranks = ctx["all_ranks"]
target_keywords = ctx["target_keywords"]
keyword_ranks_for_campaign = ctx["keyword_ranks_for_campaign"]
contents_by_id = ctx["contents_by_id"]

_IMPACT_BASIS_OPTIONS = {"상위노출 콘텐츠 수": "exposure_count", "매치 콘텐츠 조회수 합": "view_sum"}
basis_choice = st.radio(
    "파급력 기준", options=list(_IMPACT_BASIS_OPTIONS.keys()), horizontal=True, key="keyword_impact_basis",
)
impact_basis = _IMPACT_BASIS_OPTIONS[basis_choice]

if impact_basis == "exposure_count":
    weekly_scores = keyword_weekly_exposure_counts(keyword_ranks_for_campaign, target_keywords)
    score_unit = "건"
else:
    weekly_scores = keyword_weekly_view_sums(keyword_ranks_for_campaign, view_metrics, target_keywords)
    score_unit = "회"

impact_week, impact_rows = keyword_impact_leaderboard(weekly_scores)
exposure_counts = exposure_counts_by_channel(contents, all_ranks)
_hero_row = impact_rows[0] if impact_rows else None
_hero_total = sum(r["score"] for r in impact_rows) or 1
_render_stat_row(
    [
        ("등록 콘텐츠", str(len(contents)), "건"),
        ("네이버 상위노출", str(sum(exposure_counts.values())), "건"),
        ("추적 키워드", str(len(target_keywords)), "개"),
    ],
    hero_label="이번 주 파급력 1위",
    hero_value=_hero_row["keyword"] if _hero_row else None,
    hero_sub=(
        f"{_hero_row['score']:,}{score_unit} · 이번 주 비중 "
        f"{round(_hero_row['score'] / _hero_total * 100)}%"
    ) if _hero_row else "아직 집계된 주가 없다",
    hero_pct=round(_hero_row["score"] / _hero_total * 100) if _hero_row else 0,
)

exp_left, exp_right = st.columns([2, 1], gap="large")
with exp_left:
    st.subheader("상위노출 콘텐츠")
    _render_exposure_content_list(contents_by_id, all_ranks)
with exp_right:
    st.subheader("채널 현황")
    with st.container(border=True):
        st.markdown('<span class="vr-hero-marker"></span>', unsafe_allow_html=True)
        _render_channel_donut(channel_distribution(contents))
        st.markdown('<div class="vr-chart-title" style="margin-top:14px">채널별 네이버 상위노출</div>', unsafe_allow_html=True)
        _render_exposure_rank_list(exposure_counts)

    st.subheader("주간 키워드 파급력")
    _render_keyword_impact_leaderboard(impact_week, impact_rows, score_unit)

    st.subheader("캠페인 키워드 순위")
    keyword_summary = keyword_rank_summary(keyword_ranks_for_campaign, target_keywords)
    _render_keyword_watchlist(keyword_summary, contents_by_id)
