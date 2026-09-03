"""요약 — 스펙 §5.1. 제목 블록 / 스탯 스트립 / 잉크 선 누적 조회수 차트 / 키워드 순위 표 + 채널 분포 / 콘텐츠 상위 8."""
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
    CHANNELS, SERP_TABS, load_campaign_context, render_content_table, render_export_button,
)
from report_dashboard.repo import ReportRepo
from report_dashboard.reporting import (
    average_participation_rate, channel_distribution, daily_view_series, delta_over_days,
    keyword_rank_summary, latest_matched_ranks, latest_sync_timestamp, likes_total,
)

role, email = require_role()
repo = ReportRepo()
inject_design_system()

campaigns = repo.campaigns()
campaign_id = render_header(role, email, campaigns, current="요약")
if campaign_id is None:
    st.markdown(ui.empty_state("등록된 캠페인이 없습니다", "담당자가 등록·관리자 페이지에서 캠페인을 추가하면 여기에 표시됩니다."), unsafe_allow_html=True)
    st.stop()
campaign = next(c for c in campaigns if c["campaign_id"] == campaign_id)

# 제목 블록은 여기서 빈 슬롯만 잡아둔다(화면상 맨 위) — 실제 내용(메타 문구)은
# ctx가 갖춰진 뒤에 채운다. 컨트롤 행(채널 필터·내보내기)이 슬롯 다음 자리를
# 차지해야 제목 밑·스탯 스트립 위에 오므로, 위젯 자체는 슬롯보다 나중에
# "생성"하되 st.pills 값은 load_campaign_context보다 먼저 있어야 한다.
title_slot = st.empty()
ctrl_cols = st.columns([5, 1.4])
with ctrl_cols[0]:
    channels = st.pills("채널", options=CHANNELS, default=CHANNELS, selection_mode="multi", key="channel_filter",
                        format_func=lambda c: ui.CHANNEL_LABEL.get(c, c), label_visibility="collapsed") or CHANNELS
with ctrl_cols[1]:
    export_slot = st.empty()

ctx = load_campaign_context(repo, campaign_id, channels)
if ctx is None:
    st.markdown(ui.empty_state("등록된 콘텐츠가 없습니다", "콘텐츠가 등록되고 첫 수집이 끝나면 숫자가 채워집니다."), unsafe_allow_html=True)
    st.stop()

contents, view_metrics, all_metrics = ctx["contents"], ctx["view_metrics"], ctx["all_metrics"]
contents_by_id = ctx["contents_by_id"]
# R22: 누적 조회수는 콘텐츠 성과 페이지와 같은 정의를 써야 한다 — 인스타는
# 조회수를 구조적으로 못 모으므로(§1) 채널 기준으로 아예 뺀다. view_metrics는
# 이미 auto_instagram sentinel을 뺀 상태지만, 수동 입력(manual_instagram 등)
# 인스타 조회수 행이 섞여 있어도 여기서 또 한 번 채널로 걸러야 새어 들어가지 않는다.
series = daily_view_series([m for m in view_metrics if contents_by_id.get(m["content_id"], {}).get("channel") != "instagram"])
total_views = series[-1][1] if series else 0
d7 = delta_over_days(series, 7)
comments_n = len(ctx["all_comments"])
kw_summary = keyword_rank_summary(ctx["keyword_ranks_for_campaign"], ctx["target_keywords"])
# R11: VIEW 탭은 수집 대상이 아니다 — 최고 순위도 1_상위노출.py와 같은 기준으로
# 블로그·카페(SERP_TABS)만 봐야 exposed 카운트·최고 순위 표시가 서로 어긋나지 않는다.
best = None
for kw, by_tab in kw_summary.items():
    for tab in SERP_TABS:
        for r in by_tab.get(tab, []):
            if r["rank"] is not None and (best is None or r["rank"] < best[0]):
                best = (r["rank"], kw, tab, r["content_id"])
# I1: "네이버 상위노출" 카운트는 최고 순위 1건 유무(1/0)가 아니라, SERP 탭(블로그·카페 —
# VIEW 제외, 1_상위노출.py와 동일 기준)에서 실제로 노출된 키워드 개수를 세야 한다.
exposed = sum(1 for by_tab in kw_summary.values() if any(r["rank"] is not None for tab in SERP_TABS for r in by_tab.get(tab, [])))

period = f"{campaign.get('start_date') or '—'} – {campaign.get('end_date') or '진행 중'}"
meta = (f"<b>{ui.esc(period)}</b> · 콘텐츠 {len(contents)}건 · 채널 {len(channel_distribution(contents))}개 · "
        f"추적 키워드 {len(ctx['target_keywords'])}개 · 마지막 수집 {ui.esc(latest_sync_timestamp(all_metrics) or '없음')}")
with title_slot:
    st.markdown(ui.title_block(campaign["name"], meta), unsafe_allow_html=True)
render_export_button(campaign, ctx, container=export_slot)

spark_views = charts.sparkline_svg([v for _, v in series]) if len(series) >= 2 else ""
rank_side = ui.big_rank(best[0], f"{best[1]} · {best[2].replace('API', '')}") if best else ui.spark_box("")
stats = [
    ui.stat('누적 조회수 <span class="pill">카페·커뮤니티</span>', f"{total_views:,}", ui.spark_box(spark_views),
            (ui.delta(f"+{d7[0]:,} · {d7[1]}d", "up") if d7[0] > 0 else
             ui.delta(f"{d7[0]:,} · {d7[1]}d", "down") if d7[0] < 0 else
             ui.delta(f"변동 없음 · {d7[1]}d", "flat")) if d7 else ui.delta(f"수집 {len(series)}일차", "flat")),
    ui.stat("등록 콘텐츠", f"{len(contents)}<small>건</small>", ui.spark_box(""), ui.delta(f"인스타 좋아요 합 {likes_total(all_metrics, contents):,}", "flat")),
    ui.stat("수집 댓글", f"{comments_n}<small>건</small>", ui.spark_box(""), ui.delta("카페·인스타 자동 수집", "flat")),
    ui.stat("네이버 상위노출", f"{exposed}<small>/ {len(ctx['target_keywords'])} 키워드</small>", rank_side,
            ui.delta((ctx["contents_by_id"].get(best[3]) or {}).get("title", "") if best else "아직 노출 없음", "flat")),
]
st.markdown(ui.stat_strip(stats) + '<hr class="rule">', unsafe_allow_html=True)

right = '<span class="label"><i class="dot" style="background:var(--ink)"></i> 전체 누적</span>'
st.markdown(ui.section_header("조회수 추이", sub="카페·커뮤니티 조회수", right_html=right), unsafe_allow_html=True)
if len(series) >= 3:
    st.markdown(f'<div class="chart hero-chart">{charts.area_chart_svg([v for _, v in series], labels=[d[5:].replace("-", ".") for d, _ in series], width=1140, height=230, pad_right=64, ink=True)}</div>', unsafe_allow_html=True)
else:
    st.markdown(ui.empty_state("추이를 그릴 데이터가 아직 부족합니다", "수집일이 3일 이상 쌓이면 곡선이 나타납니다."), unsafe_allow_html=True)

left, rightcol = st.columns([7, 5], gap="large")
with left:
    rows = []
    for kw in ctx["target_keywords"]:
        for tab in ("카페API", "블로그API"):
            matched = latest_matched_ranks(ctx["keyword_ranks_for_campaign"], kw, tab)
            if matched:
                m = min(matched, key=lambda r: r["rank"])
                rows.append([ui.esc(kw), f'<span class="label">{tab.replace("API", "")}</span>', ui.esc((ctx["contents_by_id"].get(m["content_id"]) or {}).get("title") or m["content_id"]), ui.rank_badge(m["rank"])])
            else:
                rows.append([ui.esc(kw), f'<span class="label">{tab.replace("API", "")}</span>', '<span class="label">—</span>', ui.rank_badge(None)])
    st.markdown(ui.section_header("네이버 키워드 순위", right_html='<a href="상위노출">상위노출 →</a>') + ui.table_html([("키워드", False), ("탭", False), ("노출 콘텐츠", False), ("순위", True)], rows), unsafe_allow_html=True)
with rightcol:
    avg = average_participation_rate(contents, view_metrics)
    st.markdown(ui.section_header("채널 분포") + ui.channel_rows(channel_distribution(contents)) +
                f'<div class="mini"><div><span class="label">평균 참여율</span><div class="figure num">{f"{avg:.1f}" if avg is not None else "—"}<small>%</small></div></div>'
                f'<div><span class="label">수집 댓글</span><div class="figure num">{comments_n}<small>건</small></div></div></div>', unsafe_allow_html=True)

st.markdown(ui.section_header("콘텐츠 성과", sub=f"{len(contents)}건 중 상위 8", right_html='<a href="콘텐츠성과">전체 →</a>'), unsafe_allow_html=True)
render_content_table(ctx, limit=8)
