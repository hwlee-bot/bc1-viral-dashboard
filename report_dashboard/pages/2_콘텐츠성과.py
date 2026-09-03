"""콘텐츠 성과 — 스펙 §5.3 마스터·디테일. 좌 행 리스트(클릭 선택) / 우 sticky 상세."""
import os, sys
_here = os.path.abspath(__file__)
_repo_root = _here[: _here.index(os.sep + "report_dashboard" + os.sep)]
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import streamlit as st

from report_dashboard import charts, ui
from report_dashboard.auth import require_role
from report_dashboard.design_system import inject_design_system
from report_dashboard.header import render_header
from report_dashboard.report_common import (
    CHANNELS, _sorted_rows, load_campaign_context, render_content_detail, render_content_rows, render_export_button,
)
from report_dashboard.repo import ReportRepo
from report_dashboard.reporting import average_participation_rate, latest_views, likes_total

role, email = require_role()
repo = ReportRepo()
inject_design_system()
campaigns = repo.campaigns()
campaign_id = render_header(role, email, campaigns, current="콘텐츠 성과")
if campaign_id is None:
    st.markdown(ui.empty_state("등록된 캠페인이 없습니다", "담당자가 캠페인을 등록하면 표시됩니다."), unsafe_allow_html=True); st.stop()
campaign = next(c for c in campaigns if c["campaign_id"] == campaign_id)

# 제목 블록은 빈 슬롯만 먼저 잡는다(화면 맨 위) — 메타 문구(채널별 건수)는
# ctx가 갖춰진 뒤 채운다.
title_slot = st.empty()
c1, c2, c3, c4 = st.columns([3, 4, 2, 1.4])
with c1:
    sort_label = st.segmented_control("정렬", ["조회·좋아요", "댓글", "참여율", "최신"], default="조회·좋아요", key="perf_sort", label_visibility="collapsed") or "조회·좋아요"
with c2:
    channels = st.pills("채널", options=CHANNELS, default=CHANNELS, selection_mode="multi", key="channel_filter",
                        format_func=lambda c: ui.CHANNEL_LABEL.get(c, c), label_visibility="collapsed") or CHANNELS
with c3:
    hide_empty_sel = st.pills("표시", ["미수집 숨기기"], selection_mode="single", key="hide_empty", label_visibility="collapsed")
with c4:
    export_slot = st.empty()
hide_empty = bool(hide_empty_sel)
sort_key = {"조회·좋아요": "value", "댓글": "comments", "참여율": "rate", "최신": "recent"}[sort_label]

ctx = load_campaign_context(repo, campaign_id, channels)
if ctx is None:
    st.markdown(ui.empty_state("등록된 콘텐츠가 없습니다", "콘텐츠가 등록되면 성과가 표시됩니다."), unsafe_allow_html=True); st.stop()
contents, view_metrics, all_metrics = ctx["contents"], ctx["view_metrics"], ctx["all_metrics"]

meta = (f"<b>{len(contents)}건</b> · " + " · ".join(f"{ui.CHANNEL_LABEL.get(ch, ch)} {n}" for ch, n in sorted(((ch, sum(1 for c in contents if c['channel'] == ch)) for ch in {c['channel'] for c in contents}), key=lambda t: -t[1]))
        + " · 좋아요·조회수·댓글 매일 06:30 자동 수집 · 인스타 조회수는 수집 불가(좋아요로 대체)")
with title_slot:
    st.markdown(ui.title_block("콘텐츠 성과", meta), unsafe_allow_html=True)
render_export_button(campaign, ctx, container=export_slot)
total_views = sum(latest_views(view_metrics, c["content_id"]) for c in contents if c["channel"] != "instagram")
avg = average_participation_rate(contents, view_metrics)
stats = [
    ui.stat('총 조회수 <span class="pill">카페·커뮤니티</span>', f"{total_views:,}", ui.spark_box(""), ui.delta("네이버 채널 합", "flat")),
    ui.stat('총 좋아요 <span class="pill">인스타</span>', f"{likes_total(all_metrics, contents):,}", ui.spark_box(""), ui.delta("릴스 좋아요 합", "flat")),
    ui.stat("평균 참여율", f"{avg:.1f}<small>%</small>" if avg is not None else "—", ui.spark_box(""), ui.delta("댓글 ÷ 조회수", "flat")),
    ui.stat("수집 댓글", f"{len(ctx['all_comments'])}<small>건</small>", ui.spark_box(""), ui.delta("카페·인스타", "flat")),
]
st.markdown(ui.stat_strip(stats) + '<hr class="rule">', unsafe_allow_html=True)

ordered = _sorted_rows(ctx, sort_key, hide_empty=hide_empty)
ids = [r[0]["content_id"] for r in ordered]
selected = st.session_state.get("selected_content_id")
if selected not in ids:
    selected = ids[0] if ids else None
    st.session_state["selected_content_id"] = selected

left, right = st.columns([7, 5], gap="large")
with left:
    hint = "빈 데이터 숨김" if hide_empty else "데이터 없는 콘텐츠는 맨 아래"
    st.markdown(ui.section_header("전체 콘텐츠", sub=hint), unsafe_allow_html=True)
    clicked = render_content_rows(ctx, selected, sort_key=sort_key, hide_empty=hide_empty)
    if clicked and clicked != selected:
        st.session_state["selected_content_id"] = clicked
        st.rerun()
with right:
    if selected:
        render_content_detail(ctx, selected)
    else:
        st.markdown(ui.empty_state("표시할 콘텐츠가 없습니다", "미수집 숨기기를 해제하면 다시 표시됩니다."), unsafe_allow_html=True)
