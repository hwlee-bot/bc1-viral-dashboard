"""상위노출 — 스펙 §5.2. 제목/스트립(점유율 2종 포함)/키워드 점유율/키워드 검색결과 2열 + 우측 레일.

읽기 전용 — 등록은 3_등록.py에서. 헤더·필터·카드 렌더링은
report_dashboard/report_common.py 공용 모듈을 쓴다(다른 리포트 페이지와
같은 디자인 시스템을 써야 해서).
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

from report_dashboard import share, ui
from report_dashboard.auth import require_role
from report_dashboard.design_system import inject_design_system
from report_dashboard.header import render_header
from report_dashboard.report_common import (
    CHANNELS, SERP_TABS, load_campaign_context, render_export_button, render_serp_columns, render_share_section,
    render_watchlist_rail,
)
from report_dashboard.repo import ReportRepo
from report_dashboard.reporting import (
    keyword_impact_leaderboard, keyword_rank_summary, keyword_weekly_exposure_counts, keyword_weekly_view_sums,
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
inject_design_system()

campaigns = repo.campaigns()
campaign_id = render_header(role, email, campaigns, current="상위노출")
if campaign_id is None:
    st.markdown(ui.empty_state("등록된 캠페인이 없습니다", "담당자가 캠페인을 등록하면 표시됩니다."), unsafe_allow_html=True)
    st.stop()
campaign = next(c for c in campaigns if c["campaign_id"] == campaign_id)

# 제목 블록은 빈 슬롯만 먼저 잡는다(화면 맨 위) — 메타 문구(마지막 수집 시각 등)는
# ctx가 갖춰진 뒤 채운다. 내보내기 버튼도 점유율 요약(tot)이 ctx 이후에나
# 계산되므로 슬롯만 먼저 잡아두고 나중에 채운다(둘 다 st.empty() 트릭).
title_slot = st.empty()
c1, c2, c3, c4 = st.columns([3, 3, 4, 1.4])
with c1:
    basis = st.segmented_control("파급력 기준", ["상위노출 콘텐츠 수", "매치 조회수 합"], default="상위노출 콘텐츠 수", key="impact_basis", label_visibility="collapsed") or "상위노출 콘텐츠 수"
with c2:
    mode = st.segmented_control("점유율", ["슬롯 수", "위치 가중"], default="슬롯 수", key="share_mode", label_visibility="collapsed") or "슬롯 수"
with c3:
    channels = st.pills("채널", options=CHANNELS, default=CHANNELS, selection_mode="multi", key="channel_filter",
                        format_func=lambda c: ui.CHANNEL_LABEL.get(c, c), label_visibility="collapsed") or CHANNELS
with c4:
    export_slot = st.empty()

ctx = load_campaign_context(repo, campaign_id, channels)
if ctx is None:
    st.markdown(ui.empty_state("등록된 콘텐츠가 없습니다", "콘텐츠가 등록되면 키워드 순위와 점유율이 표시됩니다."), unsafe_allow_html=True)
    st.stop()

terms = share.terms_from_rows(repo.brand_terms(campaign_id))
weighted = mode == "위치 가중"
kws = ctx["target_keywords"]
rows = share.keyword_share_rows(ctx["keyword_serp_for_campaign"], kws, SERP_TABS, terms, weighted=weighted) if terms else []
tot = share.total_share(rows, share.ours_brand_of(terms)) if rows else None
summary = keyword_rank_summary(ctx["keyword_ranks_for_campaign"], kws)
# 파급력·순위 스트립은 VIEW 탭을 집계하지 않는다 — 메타 문구("VIEW 탭은 수집
# 대상이 아닙니다")와 어긋나지 않도록 블로그·카페(SERP_TABS)만 본다. VIEW는
# GitHub Actions IP가 네이버 WAF에 막혀 실서비스에서 수집 자체가 안 된다.
best = min((r["rank"] for by_tab in summary.values() for tab in SERP_TABS for r in by_tab.get(tab, []) if r["rank"] is not None), default=None)
best_kw = next(((kw, tab) for kw, by_tab in summary.items() for tab in SERP_TABS for r in by_tab.get(tab, []) if r["rank"] == best), None) if best else None
in_top10 = sum(1 for by_tab in summary.values() for tab in SERP_TABS for r in by_tab.get(tab, []) if r["rank"] is not None and r["rank"] <= 10)

_last_collected = max((r["captured_at"] for r in ctx["keyword_serp_for_campaign"]), default=None)
meta = (f"<b>키워드 {len(kws)}개 · 블로그·카페 탭</b> · 매일 06:00 자동 수집 · VIEW 탭은 수집 대상이 아닙니다"
        f" · 마지막 수집 {ui.esc(_last_collected[:16].replace('T', ' ')) if _last_collected else '없음'}")
with title_slot:
    st.markdown(ui.title_block("네이버 상위노출", meta), unsafe_allow_html=True)
render_export_button(campaign, ctx, share_summary=tot, container=export_slot)
slots = len(kws) * len(SERP_TABS) * share.SLOTS_PER_TAB
stats = [
    ui.stat("추적 키워드", f"{len(kws)}<small>개 · {slots}슬롯</small>", ui.spark_box(""), ui.delta("블로그·카페 상위 10", "flat")),
    ui.stat("브랜드 점유율", f"{tot['ours_pct']:.1f}<small>%</small>" if tot else "—", ui.spark_box(""), ui.delta(f"분모 {tot['denominator']}" if tot else "브랜드 사전 필요", "flat")),
    ui.stat("캠페인 콘텐츠 점유율", f"{tot['campaign_pct']:.1f}<small>%</small>" if tot else "—", ui.spark_box(""), ui.delta(f"상위 10 진입 {in_top10}", "flat")),
    ui.stat("상위 100위 내 노출", f"{sum(1 for by_tab in summary.values() for tab in SERP_TABS for r in by_tab.get(tab, []) if r['rank'] is not None)}<small>건</small>",
            ui.big_rank(best, f"{best_kw[0]} · {best_kw[1].replace('API', '')}") if best else ui.spark_box(""), ui.delta("최고 순위" if best else "아직 노출 없음", "flat")),
]
st.markdown(ui.stat_strip(stats) + '<hr class="rule">', unsafe_allow_html=True)

render_share_section(ctx, terms, weighted)

left, rail = st.columns([8, 4], gap="large")
with left:
    st.markdown(ui.section_header("키워드 검색결과", sub="실제 SERP 상위 10 · 우리 콘텐츠는 색으로 표시"), unsafe_allow_html=True)
    if kws:
        picked = st.pills("키워드", options=kws, default=kws[0], selection_mode="single", key="serp_keyword", label_visibility="collapsed") or kws[0]
        render_serp_columns(ctx, picked)
    else:
        st.markdown(ui.empty_state("추적 키워드가 없습니다", "등록·관리자에서 키워드를 등록하면 검색결과가 수집됩니다."), unsafe_allow_html=True)
with rail:
    if basis == "상위노출 콘텐츠 수":
        weekly, unit = keyword_weekly_exposure_counts(ctx["keyword_ranks_for_campaign"], kws), "건"
    else:
        weekly, unit = keyword_weekly_view_sums(ctx["keyword_ranks_for_campaign"], ctx["view_metrics"], kws), "회"
    week, impact_rows = keyword_impact_leaderboard(weekly)
    render_watchlist_rail(ctx, week, impact_rows, unit)
