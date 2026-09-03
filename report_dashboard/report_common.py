"""상위노출·콘텐츠 성과 두 페이지가 공유하는 화면 구성요소 (v3).

원래 하나의 pages/1_리포트.py 안에 있던 CSS·렌더 함수를(2026-09-02, 메뉴
분리로) 이 모듈로 옮겼다 — 상위노출/콘텐츠 성과가 각자 다른 사이드바
메뉴(페이지)가 되면서 둘 다 같은 디자인 시스템·카드 렌더링을 써야 했기
때문. 이 파일은 pages/*.py처럼 Streamlit이 직접 실행하는 스크립트가
아니라 그냥 임포트되는 모듈이라, require_role() 게이트나 sys.path 삽입
같은 페이지 전용 로직은 안 들어있다 — 그건 호출하는 각 페이지 파일이
스스로 해야 한다(보안 이유는 각 페이지 파일 상단 주석 참고).

v2 시절 CSS 블롭(_STYLE_AND_ICONS)과 그 CSS가 그리던 SVG 렌더러들
(_sparkline_svg, _rank_trend_svg, _render_channel_donut 등)은 디자인
시스템이 report_dashboard/design_system.py(v3, base.css/mix.css 정본)로
옮겨가면서 쓸모가 없어졌다 — Task 12에서 제거했다. 지금 이 모듈에 남은
함수는 데이터 계산(load_campaign_context, _content_rows, sorted_content_rows 등)과
v3 HTML을 그리는 render_* 함수들뿐이고, 전부 report_dashboard.ui/.charts가
제공하는 v3 컴포넌트 문자열을 조립해서 쓴다.

함수 이름에 언더스코어가 붙어있는 건(_esc, _content_rows 등) 원래 페이지
파일 안에서만 쓰던 이름을 그대로 옮겨서다 — 모듈 경계를 넘어 명시적으로
import해서 쓰는 용도라 실제로는 이 모듈의 공개 API지만, 이름을 전부
바꾸면 거대한 파일 전체에 오타 위험만 커져서 이번엔 이름은 그대로 두고
옮기기만 했다.
"""

import html as html_lib

import streamlit as st

from report_dashboard import charts, ui
from report_dashboard.reporting import (
    build_export_markdown, channel_distribution, delta_over_days, exposure_counts_by_channel,
    keyword_rank_summary, latest_keyword_serp, latest_matched_ranks, latest_rank_row, latest_views,
    likes_history, participation_rate, rank_history, week_label,
)

CHANNELS = ["youtube", "blog", "cafe", "community", "instagram"]


def _esc(value) -> str:
    return html_lib.escape(str(value))


def _safe_href(url) -> str:
    """`href=`에 그대로 넣기 전에 스킴을 검증한다(M3) — `javascript:` 등으로
    콘텐츠 URL이 오염되면 클릭 한 번으로 XSS가 되므로, http(s)가 아니면 무해한
    `#`로 대체한다. 대소문자·앞뒤 공백을 허용(브라우저 URL 파서 관용과 동일)."""
    s = str(url or "").strip()
    if s.lower().startswith(("http://", "https://")):
        return s
    return "#"


SERP_TABS = ("블로그API", "카페API")  # 상위노출 v3 페이지(1_상위노출.py)가 쓰는 SERP 탭 목록.
_SHARE_COLORS = ["var(--accent)", "var(--ch-blog)", "var(--ch-community)", "var(--s3)"]


def _primary_metric_value(content: dict, view_metrics: list[dict], all_metrics: list[dict]) -> int:
    """카드 정렬·빈 상태 판정에 쓸 대표 지표. 인스타는 조회수를 구조적으로
    못 모으므로(스펙 §1) 좋아요 최신값을 대신 쓴다 — 안 그러면 좋아요
    데이터가 있어도 카드가 항상 '데이터 없음'으로 표시되고 맨 아래로
    밀린다. 콘텐츠 성과 페이지의 카드 정렬·히어로 스탯(최다 조회 콘텐츠)
    둘 다 이 함수를 쓴다."""
    if content["channel"] == "instagram":
        cid = content["content_id"]
        series = likes_history([m for m in all_metrics if m["content_id"] == cid])
        return series[-1][1] if series else 0
    return latest_views(view_metrics, content["content_id"])


def render_export_button(campaign: dict, ctx: dict, *, share_summary: dict | None = None, container=None) -> None:
    """내보내기 다운로드 버튼 — 세 페이지(0_요약/1_상위노출/
    2_콘텐츠성과)가 각자 복붙해 쓰던 `st.columns([5, 1])` + `st.download_button`
    블록을 여기 하나로 모았다(Task 11에서 미룬 DRY, Task 12에서 처리).

    라벨은 "리포트 내보내기"에서 "내보내기"로 줄였다(Task 13 fix round 4) —
    좁은 컨트롤 칸(export_col/export_slot)에서 긴 라벨이 두 줄로 줄바꿈되던
    실측 문제. 목업 원래 라벨도 "내보내기"였다.

    share_summary는 상위노출 페이지만 넘긴다(share.total_share 결과) — 나머지
    두 페이지는 점유율 요약이 없어 기본값 None 그대로 build_export_markdown에 전달된다.

    container는 Task 13에서 추가 — 각 페이지가 제목 블록 아래 컨트롤 행에
    쓰는 슬롯(`st.columns(...)`의 한 칸 또는 `st.empty()`)을 넘기면 그 안에
    바로 그린다(중첩 `st.columns` 없이). 안 넘기면(container=None) 예전처럼
    이 함수가 직접 `st.columns([5, 1])`로 우측 칸을 만들어 쓴다 — 하위 호환.
    """
    def _button() -> None:
        st.download_button(
            "내보내기",
            data=build_export_markdown(
                f"{campaign['brand']} · {campaign['name']}", ctx["contents"], ctx["view_metrics"],
                ctx["all_ranks"], ctx["all_comments"], share_summary=share_summary,
            ),
            file_name=f"{campaign['name']}_리포트.md", mime="text/markdown", key="export_button",
        )

    if container is not None:
        with container:
            _button()
    else:
        _, export_col = st.columns([5, 1])
        with export_col:
            _button()


def load_campaign_context(repo, campaign_id: str, channel_filter: list[str]) -> dict | None:
    """캠페인 데이터 로딩만 한다(위젯 없음 — 캠페인 선택은 header.py, 채널 필터는 각 페이지 컨트롤).
    콘텐츠가 없으면 None. 반환 키: contents/content_ids/all_metrics/view_metrics/all_ranks/all_comments/
    target_keywords/keyword_ranks_for_campaign/keyword_serp_for_campaign/contents_by_id/all_contents"""
    all_contents = repo.contents(campaign_id=campaign_id)
    contents = [c for c in all_contents if c["channel"] in channel_filter]
    if not contents:
        return None
    content_ids = {c["content_id"] for c in contents}
    all_metrics = [m for m in repo.content_metrics() if m["content_id"] in content_ids]
    view_metrics = [m for m in all_metrics if m.get("source") != "auto_instagram"]
    all_ranks = [r for r in repo.keyword_ranks() if r["content_id"] in content_ids]
    all_comments = [c for c in repo.comments() if c["content_id"] in content_ids]
    target_keywords = list(dict.fromkeys(k["keyword"] for k in repo.target_keywords(campaign_id=campaign_id)))
    keyword_ranks_for_campaign = [r for r in repo.keyword_ranks() if r["keyword"] in target_keywords]
    keyword_serp_for_campaign = [r for r in repo.keyword_serp() if r["keyword"] in target_keywords]
    return {
        "campaign_id": campaign_id, "contents": contents, "all_contents": all_contents, "content_ids": content_ids,
        "all_metrics": all_metrics, "view_metrics": view_metrics, "all_ranks": all_ranks, "all_comments": all_comments,
        "target_keywords": target_keywords, "keyword_ranks_for_campaign": keyword_ranks_for_campaign,
        "keyword_serp_for_campaign": keyword_serp_for_campaign, "contents_by_id": {c["content_id"]: c for c in all_contents},
    }


def _content_rows(ctx):
    """[(content, primary_value, spark_svg, comments_n, latest_rank)] 정렬: 값 내림차순, 0은 맨 아래."""
    out = []
    for c in ctx["contents"]:
        cid = c["content_id"]
        metrics = sorted((m for m in ctx["all_metrics"] if m["content_id"] == cid), key=lambda m: m["captured_at"])
        pv = _primary_metric_value(c, ctx["view_metrics"], ctx["all_metrics"])
        series = [v for _, v in likes_history(metrics)] if c["channel"] == "instagram" else [m["views"] for m in metrics if m.get("source") != "auto_instagram"]
        spark = charts.sparkline_svg(series, width=84, height=22) if len(series) >= 2 else ""
        n_comments = sum(1 for k in ctx["all_comments"] if k["content_id"] == cid)
        rank = latest_rank_row(ctx["all_ranks"], cid)
        out.append((c, pv, spark, n_comments, rank))
    return sorted(out, key=lambda t: (t[1] == 0, -t[1]))


def _row_participation_rate(ctx, content: dict, primary_value: int) -> float | None:
    """행 정렬용 참여율. 인스타는 조회수를 구조적으로 못 모으므로(§1) 항상
    None — nonzero 그룹 안에서도 맨 뒤로 보낸다(R16). 나머지 채널은 콘텐츠의
    최신 non-auto_instagram 지표 행(댓글수)을 pv(=최신 조회수)와 나눈다."""
    if content["channel"] == "instagram":
        return None
    cid = content["content_id"]
    vm_c = sorted(
        (m for m in ctx["all_metrics"] if m["content_id"] == cid and m.get("source") != "auto_instagram"),
        key=lambda m: m["captured_at"],
    )
    if not vm_c:
        return None
    return participation_rate(primary_value, vm_c[-1].get("comments_count"))


def sorted_content_rows(ctx, sort_key: str = "value", *, hide_empty: bool = False) -> list:
    """행 리스트 표시 순서의 단일 정본 — 페이지(기본 선택)와
    render_content_rows(실제 렌더)가 항상 같은 함수를 써야 "초기 선택 =
    정렬 1위"가 어떤 정렬·필터 조합에서도 어긋나지 않는다(R15).

    모든 정렬에서 값(pv)이 0인 행은 맨 아래로 고정한다 — 안정 정렬을
    두 번(부차 키 → 주 키) 적용해서 각 정렬의 내부 순서를 보존한다.
    """
    rows = _content_rows(ctx)
    if hide_empty:
        rows = [r for r in rows if r[1] != 0]
    if sort_key == "comments":
        rows.sort(key=lambda t: -t[3])
        rows.sort(key=lambda t: t[1] == 0)
    elif sort_key == "recent":
        rows.sort(key=lambda t: (t[0].get("release_at") or ""), reverse=True)
        rows.sort(key=lambda t: t[1] == 0)
    elif sort_key == "rate":
        def _rate_key(t):
            rate = _row_participation_rate(ctx, t[0], t[1])
            return (rate is None, -(rate or 0))

        rows.sort(key=_rate_key)
        rows.sort(key=lambda t: t[1] == 0)
    # sort_key == "value"(기본): _content_rows가 이미 (값 0 여부, -값)으로 정렬해서 돌려준다.
    return rows


def render_content_rows(ctx, selected_id: str | None, *, sort_key: str = "value", hide_empty: bool = False) -> str | None:
    """행 리스트(마스터). 행 클릭 시 선택된 content_id를 돌려준다(없으면 None).

    sort_key: value|comments|rate|recent. hide_empty=True면 미수집(pv==0) 행을 아예 뺀다.
    """
    rows = sorted_content_rows(ctx, sort_key, hide_empty=hide_empty)
    vmax = max((r[1] for r in rows), default=0) or 1
    clicked = None
    st.markdown('<div class="lrow-head lrow"><span class="label">콘텐츠</span><span></span><span class="label">추이</span><span class="label r">조회 · 좋아요</span><span class="label r">댓글</span><span class="label r">순위</span><span></span></div>', unsafe_allow_html=True)
    for c, pv, spark, n_comments, rank in rows:
        cid = c["content_id"]
        unit = "좋아요" if c["channel"] == "instagram" else "조회"
        sel = " is-sel" if cid == selected_id else ""
        rank_html = ui.rank_badge(rank["rank"] if rank else None, "—") if c["channel"] != "instagram" else '<span class="label">—</span>'
        with st.container():
            st.markdown(
                f'<span class="lrow-marker{sel}"></span>'
                f'<div class="lrow{" is-empty" if pv == 0 else ""}">'
                f'<div class="t"><span class="who">{_esc(c.get("title") or c["url"])}</span><small>{ui.CHANNEL_LABEL.get(c["channel"], c["channel"])} · {_esc((c.get("release_at") or "")[:10])}</small></div>'
                f'<span>{ui.channel_icon(c["channel"], 15)}</span>'
                f'<div class="spark chart">{spark}</div>'
                f'<span class="r">{ui.inline_bar(pv / vmax * 100, width=64)}<span class="mono">{pv:,}</span> <span class="label">{unit}</span></span>'
                f'<span class="r mono">{n_comments or "—"}</span><span class="r">{rank_html}</span><span class="chev">›</span></div>',
                unsafe_allow_html=True,
            )
            if st.button(f"{c.get('title') or c['url']} 상세", key=f"lrow_{cid}"):
                clicked = cid
    return clicked


def render_content_detail(ctx, content_id: str) -> None:
    c = ctx["contents_by_id"][content_id]
    metrics = sorted((m for m in ctx["all_metrics"] if m["content_id"] == content_id), key=lambda m: m["captured_at"])
    comments = [k for k in ctx["all_comments"] if k["content_id"] == content_id]
    is_ig = c["channel"] == "instagram"
    if is_ig:
        hist = likes_history(metrics)
        series, dates = [v for _, v in hist], [d[:10] for d, _ in hist]
        primary, primary_label = (series[-1] if series else None), "좋아요"
        manual = [m for m in metrics if m.get("source") != "auto_instagram"]
        third = (f"{manual[-1]['views']:,}", "조회수(참고)", "수동 입력") if manual else ("—", "조회수(참고)", "수동 입력 없음")
        # KPI 캡션(정확도·시각)은 primary 숫자를 만든 것과 같은 행에서 뽑는다(§8) —
        # likes_history가 실제로 본 auto_instagram 행 중 가장 최근 것.
        auto_rows = [m for m in metrics if m.get("source") == "auto_instagram" and m.get("likes_count") is not None]
        source_row = auto_rows[-1] if auto_rows else None
    else:
        vm = [m for m in metrics if m.get("source") != "auto_instagram"]
        series, dates = [m["views"] for m in vm], [m["captured_at"][:10] for m in vm]
        primary, primary_label = (series[-1] if series else None), "조회수"
        rate = participation_rate(primary, vm[-1].get("comments_count")) if vm else None
        third = (f"{rate:.1f}%" if rate is not None else "—", "참여율", "댓글 ÷ 조회수")
        source_row = vm[-1] if vm else None
    latest_at = (source_row["captured_at"][:16].replace("T", " ") if source_row else "—")
    kpis = (
        f'<div class="kpi"><span class="label">{primary_label}</span><div class="figure num">{f"{primary:,}" if primary is not None else "—"}</div><div class="sub">{_esc(source_row["accuracy"]) if source_row else "미수집"} · {latest_at}</div></div>'
        f'<div class="kpi"><span class="label">댓글</span><div class="figure num">{len(comments)}</div><div class="sub">자동 수집</div></div>'
        f'<div class="kpi"><span class="label">{third[1]}</span><div class="figure num">{third[0]}</div><div class="sub">{third[2]}</div></div>'
    )
    chart = (f'<div class="chart">{charts.area_chart_svg(series, labels=[d[5:].replace("-", ".") for d in dates], width=420, height=140, pad_right=52)}</div>'
             if len(series) >= 3 else ui.empty_state("추이는 수집 3회부터 표시됩니다", f"현재 {len(series)}회"))
    if is_ig:
        rank_block = ui.section_header("네이버 순위 추이", right_html='<span class="rank none">인스타 콘텐츠는 대상 아님</span>') + '<div class="empty" style="border:0;padding:6px 0 0">네이버 순위는 블로그·카페·커뮤니티 콘텐츠에서만 추적됩니다.</div>'
    else:
        hist = rank_history([r for r in ctx["all_ranks"] if r["content_id"] == content_id])
        ranks = [r for _, r in hist if r]
        latest = latest_rank_row(ctx["all_ranks"], content_id)
        rank_block = ui.section_header("네이버 순위 추이", right_html=(f'{ui.rank_badge(latest["rank"])} <span class="label">{_esc(latest["keyword"])} · {_esc(latest.get("search_tab", "").replace("API", ""))}</span>' if latest else ui.rank_badge(None)))
        rank_block += (f'<div class="chart">{charts.rank_chart_svg(ranks, width=420, height=90)}</div>' if len(ranks) >= 2 else ui.empty_state("아직 측정된 순위가 없습니다", "키워드 수집 후 표시됩니다."))
    cm = "".join(f'<div class="cm"><span><b>{_esc(k.get("author_nickname") or "익명")}</b>{_esc(k["text"])}</span><small>{_esc((k.get("commented_at") or "")[:10])}</small></div>' for k in comments[:8]) \
        or ui.empty_state("수집된 댓글이 없습니다", "카페·인스타 댓글은 매일 06:30 수집됩니다.")
    st.markdown(
        f'<aside class="detail"><div class="dh"><div><h2>{_esc(c.get("title") or c["url"])}</h2>'
        f'<div class="meta">{ui.channel_icon(c["channel"])}{ui.CHANNEL_LABEL.get(c["channel"], c["channel"])} · {_esc((c.get("release_at") or "미정")[:10])} 게시 · <a href="{_esc(_safe_href(c["url"]))}" target="_blank" rel="noopener noreferrer">원문 열기 ↗</a></div></div></div>'
        f'<div class="kpis">{kpis}</div>'
        + ui.section_header(f"{primary_label} 추이", right_html=f'<span class="label">{len(series)}회 수집</span>') + chart
        + rank_block
        + ui.section_header(f"댓글 {len(comments)}") + cm
        + "</aside>",
        unsafe_allow_html=True,
    )


def render_content_table(ctx, *, limit=None) -> None:
    rows = _content_rows(ctx)
    if limit:
        rows = rows[:limit]
    vmax = max((r[1] for r in rows), default=0) or 1
    body = []
    for c, pv, spark, n_comments, rank in rows:
        unit = "좋아요" if c["channel"] == "instagram" else "조회"
        body.append([
            f'<span class="who">{_esc(c.get("title") or c["url"])}</span>',
            f'<span class="ch-cell">{ui.channel_icon(c["channel"])}<span class="label">{ui.CHANNEL_LABEL.get(c["channel"], c["channel"])}</span></span>',
            f'<span class="mono label">{_esc((c.get("release_at") or "")[:10])}</span>',
            f'<div class="spark chart">{spark}</div>',
            f'{ui.inline_bar(pv / vmax * 100)}<span class="mono">{pv:,}</span> <span class="label">{unit}</span>',
            f'<span class="mono">{n_comments or "—"}</span>',
            ui.rank_badge(rank["rank"] if rank else None, "—") if c["channel"] != "instagram" else '<span class="label">—</span>',
        ])
    st.markdown(ui.table_html([("콘텐츠", False), ("채널", False), ("게시일", False), ("추이", False), ("조회 · 좋아요", True), ("댓글", True), ("순위", True)], body), unsafe_allow_html=True)


def render_share_section(ctx, terms: list[dict], weighted: bool) -> None:
    """키워드 점유율(스펙 §7) — 키워드×탭 슬롯에서 제목에 브랜드가 매칭된 비율.

    브랜드 사전이 비어 있으면 집계할 대상이 없으므로 빈 상태만 보여준다.
    """
    from report_dashboard import share

    ours = share.ours_brand_of(terms)
    if not terms or not ctx["target_keywords"] or ours is None:
        if terms and ours is not None and not ctx["target_keywords"]:
            empty = ui.empty_state("추적 키워드가 없어 점유율을 계산할 수 없습니다", "등록·관리자에서 키워드를 등록하면 다음 수집부터 집계됩니다.")
        else:
            empty = ui.empty_state("점유율 브랜드 사전이 없습니다", "담당자가 등록·관리자 → 키워드 섹션에서 브랜드 사전을 입력하면 집계됩니다.")
        st.markdown(ui.section_header("키워드 점유율") + empty, unsafe_allow_html=True)
        return
    rows = share.keyword_share_rows(ctx["keyword_serp_for_campaign"], ctx["target_keywords"], SERP_TABS, terms, weighted=weighted)
    tot = share.total_share(rows, ours)
    order = [ours] + tot["top_brands"]
    color_of = {b: _SHARE_COLORS[i] for i, b in enumerate(order)}
    other_brands_color, unmatched_color = "var(--muted)", _SHARE_COLORS[3]
    has_other_brands = tot["other_brands_pct"] > 0
    unit = "점" if weighted else "슬롯"
    legend = "".join(f'<span><i class="dot" style="background:{color_of[b]}"></i>{_esc(b)}</span>' for b in order)
    if has_other_brands:
        legend += f'<span><i class="dot" style="background:{other_brands_color}"></i>기타 브랜드</span>'
    legend += f'<span><i class="dot" style="background:{unmatched_color}"></i>미매칭 슬롯</span>'
    row_html = []
    for r in rows:
        # 행별 막대: 표시 밖 매칭 브랜드 합(기타 브랜드); 미매칭 슬롯은 트랙 배경으로 남긴다 —
        # by_brand에는 애초에 매칭된 브랜드만 들어있으므로(§7), 여기서 뺀 나머지(진짜 미매칭)는
        # 세그먼트를 아예 안 그려서 stack_bar_html의 빈 트랙 배경이 자연히 그 몫을 표시한다.
        segs = [(color_of[b], r["by_brand"].get(b, 0) / r["denominator"] * 100) for b in order]
        others = sum(v for b, v in r["by_brand"].items() if b not in order)
        segs.append((other_brands_color, others / r["denominator"] * 100))
        ours_pct = r["ours_score"] / r["denominator"] * 100
        row_html.append(
            f'<div class="sh"><span class="k">{_esc(r["keyword"])}<small>{r["tab"].replace("API", "")}</small></span>'
            f'{charts.stack_bar_html(segs, ours_index=0)}'
            f'<span class="v">{ours_pct:.0f}%<small>{_esc(ours)} {r["ours_score"]}/{r["denominator"]}{unit if weighted else ""}</small></span></div>'
        )
    total_segs = [(color_of[b], tot["by_brand"].get(b, 0)) for b in order]
    if has_other_brands:
        total_segs.append((other_brands_color, tot["other_brands_pct"]))
    total_segs.append((unmatched_color, tot["unmatched_pct"]))
    lg = "".join(
        f'<div><span><i class="dot" style="background:{color_of[b]}"></i> {_esc(b)}</span><b>{tot["by_brand"].get(b, 0):.1f}%</b></div>'
        for b in order
    )
    if has_other_brands:
        lg += f'<div><span><i class="dot" style="background:{other_brands_color}"></i> 기타 브랜드</span><b>{tot["other_brands_pct"]:.1f}%</b></div>'
    lg += f'<div><span><i class="dot" style="background:{unmatched_color}"></i> 미매칭 슬롯</span><b>{tot["unmatched_pct"]:.1f}%</b></div>'
    trend = share.share_trend(ctx["keyword_serp_for_campaign"], ctx["target_keywords"], SERP_TABS, terms)
    trend_html = (
        f'<div class="chart">{charts.area_chart_svg([p for _, p in trend], labels=[a[5:10].replace("-", ".") for a, _ in trend], width=360, height=110, pad_right=50)}</div>'
        if len(trend) >= 3 else ui.empty_state("추이는 수집 3회부터 표시됩니다", f"현재 {len(trend)}회 수집")
    )
    st.markdown(
        ui.section_header(
            "키워드 점유율",
            sub=f"키워드×탭 네이버 검색 API 최신순 상위 10 슬롯 중 제목에 브랜드가 매칭된 비율 · 분모 {tot['denominator']}",
            right_html=f'<div class="legend">{legend}</div>',
        )
        + f'<div class="share-grid"><div>{"".join(row_html)}</div><div class="share-side">'
        f'<div class="label">전체 {tot["denominator"]}{unit} 브랜드 분포</div>{charts.stack_bar_html(total_segs, ours_index=0, height=16)}'
        f'<div class="stack-lg">{lg}</div><div class="label" style="margin-top:18px">{_esc(ours)} 점유율 추이</div>{trend_html}</div></div>',
        unsafe_allow_html=True,
    )


def render_serp_columns(ctx, keyword: str) -> None:
    """네이버 검색 API 최신순 상위 10 두 탭(블로그API·카페API)을 나란히 보여준다.

    우리 콘텐츠(content_id 있는 행)만 .srow.ours로 강조하고, 목록에 안 잡힌
    10위 밖 매치는 탭마다 별도 노트로 붙인다.
    """
    cols_html = []
    for tab in SERP_TABS:
        rows = latest_keyword_serp(ctx["keyword_serp_for_campaign"], keyword, tab)
        ours_n = sum(1 for r in rows if r["content_id"])
        items = "".join(
            f'<a class="srow{" ours" if r["content_id"] else ""}" href="{_esc(_safe_href(r["url"]))}" target="_blank" rel="noopener noreferrer">'
            f'<span class="r">{r["rank"]}</span><span class="t">{_esc(r.get("title") or r["url"])}</span>'
            f'<span class="src">{"우리 콘텐츠" if r["content_id"] else tab.replace("API", "")}</span></a>'
            for r in rows
        ) or ui.empty_state("아직 수집 전입니다", "다음 06:00 수집 후 표시됩니다.")
        visible = {r["content_id"] for r in rows if r["content_id"]}
        beyond = [r for r in latest_matched_ranks(ctx["keyword_ranks_for_campaign"], keyword, tab) if r["content_id"] not in visible]
        beyond_html = "".join(
            f'<div class="beyond"><span class="label">10위 밖 우리 콘텐츠</span>{ui.rank_badge(r["rank"])}'
            f'<span>「{_esc((ctx["contents_by_id"].get(r["content_id"]) or {}).get("title") or r["content_id"])}」</span></div>'
            for r in beyond
        ) or '<div class="beyond"><span class="label">10위 밖 우리 콘텐츠</span><span class="rank none">없음</span></div>'
        cols_html.append(
            f'<div><div class="serp-h"><h3 class="h-sec">{tab.replace("API", "")}</h3><span class="label">우리 콘텐츠 {ours_n}</span>'
            f'<span class="sp"></span><span class="label">"{_esc(keyword)}"</span></div>{items}{beyond_html}</div>'
        )
    st.markdown(f'<div class="serp">{"".join(cols_html)}</div>', unsafe_allow_html=True)


def render_watchlist_rail(ctx, impact_week, impact_rows, score_unit) -> None:
    """우측 레일 — 캠페인 키워드 순위 워치리스트 · 채널별 네이버 노출 · 주간 키워드 파급력."""
    summary = keyword_rank_summary(ctx["keyword_ranks_for_campaign"], ctx["target_keywords"])
    wl = []
    for kw, by_tab in summary.items():
        for tab in SERP_TABS:
            rows = by_tab.get(tab, [])
            matched = [r for r in rows if r["rank"] is not None]
            best = min((r["rank"] for r in matched), default=None)
            hist = rank_history([r for r in ctx["keyword_ranks_for_campaign"] if r["keyword"] == kw and r.get("search_tab") == tab and r.get("rank")])
            ranks = [r for _, r in hist if r]
            spark = charts.rank_chart_svg(ranks, width=90, height=22) if len(ranks) >= 2 else ""
            # rank_history는 captured_at을 원문(시간 포함) 그대로 키로 쓴다 — delta_over_days는
            # 순수 날짜 문자열(YYYY-MM-DD)을 요구하므로(date.fromisoformat) 여기서 앞 10자로 자른다.
            cal_series = [(d[:10], r) for d, r in hist if r]
            dd = delta_over_days(cal_series, 7)
            if dd is None:
                d_html = ui.delta("—", "flat")
            else:
                dv, span = dd
                if dv < 0:
                    d_html = ui.delta(f"▲{-dv} · {span}d", "up")
                elif dv > 0:
                    d_html = ui.delta(f"▼{dv} · {span}d", "down")
                else:
                    d_html = ui.delta(f"— · {span}d", "flat")
            wl.append(f'<div class="wl"><span class="k">{_esc(kw)}<small>{tab.replace("API", "")}</small></span><span class="rk">{ui.rank_badge(best, "—")}</span><div class="spark chart">{spark}</div>{d_html}</div>')
    exposure = exposure_counts_by_channel(ctx["contents"], ctx["all_ranks"])
    # M4: .ch-row 자체 렌더링(채널 키를 var(--ch-{ch}) 스타일 컨텍스트에 미이스케이프로
    # 꽂던 코드)을 걷어내고 ui.channel_rows에 위임한다 — 이스케이프·포맷을 한 곳으로
    # 모으고, 여기선 "노출 n / 채널 전체 N" 형태를 위해 numerators/denominators로 넘긴다.
    by_ch = {ch: n for ch, n in channel_distribution(ctx["contents"]).items() if ch != "instagram"}
    ch_html = ui.channel_rows(by_ch, numerators=exposure, denominators=by_ch)

    def _lead_row(r) -> str:
        # I6: 3.11 호환 — f-string 표현식 안에 델리미터와 같은 종류의 따옴표를 중첩하면
        # (구버전 f-string 파서 제약) SyntaxError이므로 델타 라벨을 먼저 변수로 뺀다.
        delta_label = "NEW" if r["delta"] is None else f"지난주 대비 {r['delta']:+d}"
        return (
            f'<div class="lead"><span class="n">{r["rank"]}</span><span>{_esc(r["keyword"])}</span>'
            f'<span class="label">{delta_label}</span><span class="v">{r["score"]:,}{score_unit}</span></div>'
        )

    lead = "".join(_lead_row(r) for r in impact_rows) if impact_rows else ui.empty_state("아직 집계할 주간 데이터가 없습니다", "다음 주 수집부터 순위 변동과 함께 채워집니다.")
    st.markdown(
        ui.section_header("캠페인 키워드 순위", right_html='<span class="label">최고 순위 · 7일 변동(달력)</span>') + "".join(wl)
        + ui.section_header("채널별 네이버 노출", right_html='<span class="label">100위 내</span>')
        + (ch_html or ui.empty_state("네이버 추적 대상 채널이 없습니다", "카페·블로그·커뮤니티 콘텐츠만 순위를 추적합니다."))
        + ui.section_header("주간 키워드 파급력", right_html=f'<span class="label">{week_label(impact_week) if impact_week else ""}</span>') + lead,
        unsafe_allow_html=True,
    )
