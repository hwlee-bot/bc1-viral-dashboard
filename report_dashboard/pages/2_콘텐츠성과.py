"""캠페인 콘텐츠별 조회수·참여율 성과 — 콘텐츠 하나하나가 얼마나 봤는지.

읽기 전용 — 등록은 3_등록.py에서. 원래 리포트 페이지의 "콘텐츠 성과" 탭이었던
것을(2026-09-02) 별도 사이드바 메뉴로 분리했다(배경은 1_상위노출.py
docstring 참고 — 같은 결정). 조회수 추이는 실측값만 연결해서 그린다 —
데이터 없는 구간에 "추세(예시)"를 지어내 그리지 않는다.
"""

import os
import sys

_here = os.path.abspath(__file__)
_repo_root = _here[: _here.index(os.sep + "report_dashboard" + os.sep)]
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import streamlit as st

from report_dashboard.auth import require_role
from report_dashboard.report_common import (
    _primary_metric_value, _render_channel_donut, _render_content_summary_card,
    _render_stat_row, load_campaign_context, render_campaign_header,
)
from report_dashboard.repo import ReportRepo
from report_dashboard.reporting import (
    average_participation_rate, channel_distribution, latest_rank_row, latest_views, rank_history,
)

# 게이트를 이 파일에서도 호출한다 — 이유는 1_상위노출.py 상단 주석과 같다.
role, email = require_role()

repo = ReportRepo()

render_campaign_header(email)
ctx = load_campaign_context(repo)
contents = ctx["contents"]
all_metrics = ctx["all_metrics"]
view_metrics = ctx["view_metrics"]
all_ranks = ctx["all_ranks"]
all_comments = ctx["all_comments"]

# 조회수(또는 인스타는 좋아요) 높은 순으로 노출한다. 아직 값이 0(=수집 전)인
# 콘텐츠는 맨 아래로 보내되, 그 안에서는 원래 등록 순서를 유지한다(sorted는 안정 정렬).
contents_sorted = sorted(
    contents, key=lambda c: (_primary_metric_value(c, view_metrics, all_metrics) == 0, -_primary_metric_value(c, view_metrics, all_metrics))
)

_top_content = contents_sorted[0] if contents_sorted else None
_top_value = _primary_metric_value(_top_content, view_metrics, all_metrics) if _top_content else 0
_avg_participation = average_participation_rate(contents, view_metrics)
_render_stat_row(
    [
        ("등록 콘텐츠", str(len(contents)), "건"),
        ("평균 참여율", f"{_avg_participation:.1f}%" if _avg_participation is not None else "—", ""),
        ("총 조회수", f"{sum(latest_views(view_metrics, c['content_id']) for c in contents):,}", "회"),
    ],
    hero_label="최다 조회 콘텐츠",
    hero_value=(_top_content.get("title") or _top_content["url"]) if _top_content and _top_value > 0 else None,
    hero_sub=(
        f"{_top_value:,}{'좋아요' if _top_content['channel'] == 'instagram' else '회'}"
    ) if _top_content and _top_value > 0 else "아직 수집된 데이터가 없다",
    hero_pct=100 if _top_value > 0 else 0,
)

CARDS_PER_ROW = 3

perf_left, perf_right = st.columns([2, 1], gap="large")
with perf_left:
    st.subheader("콘텐츠별 성과")
    # 카드형 요약 그리드 + 클릭 시 팝업(2026-09-02, manyo.madup.app 레퍼런스,
    # 팀장님 요청) — 24건이 인라인 전체 상세로 펼쳐지면 한 화면에 1~2개만
    # 보여 훑어보기 어렵다는 피드백. 다이얼로그가 필요로 하는 데이터를
    # 카드마다 미리 한 번씩 필터링해서 넘긴다(_render_content_summary_card
    # 참고 — 클릭 시점엔 재조회하지 않는다).
    for row_start in range(0, len(contents_sorted), CARDS_PER_ROW):
        row = contents_sorted[row_start : row_start + CARDS_PER_ROW]
        cols = st.columns(CARDS_PER_ROW, gap="medium")
        for col, content in zip(cols, row):
            cid = content["content_id"]
            primary_value = _primary_metric_value(content, view_metrics, all_metrics)
            metrics = sorted((m for m in all_metrics if m["content_id"] == cid), key=lambda m: m["captured_at"])
            content_ranks = [r for r in all_ranks if r["content_id"] == cid]
            content_comments = [c for c in all_comments if c["content_id"] == cid]
            with col:
                with st.container(border=True):
                    _render_content_summary_card(
                        content,
                        primary_value=primary_value,
                        is_empty=(primary_value == 0),
                        metrics=metrics,
                        latest_rank=latest_rank_row(all_ranks, cid),
                        rank_hist=rank_history(content_ranks),
                        comments=content_comments,
                    )
with perf_right:
    st.subheader("채널 현황")
    with st.container(border=True):
        st.markdown('<span class="vr-hero-marker"></span>', unsafe_allow_html=True)
        _render_channel_donut(channel_distribution(contents))
