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
옮겨가면서 쓸모가 없어졌다 — Task 12에서 제거했다.

v4(2026-09-03, 리포트 본문 iframe화)부터 화면을 그리는 함수는 전부 HTML
문자열을 돌려주는 `*_html` 빌더다 — 리포트 본문은 스트림릿 문서가 아니라
frame.py가 조립하는 독립 HTML 문서 안에 들어가고, 클라이언트 JS가
`data-*`만 읽어 필터·정렬·재계산을 한다(스펙 v4 §4·§7). 페이지 3개가
`frame.render(views.*.build(...))`로 다 넘어간 Task 7에서, 전환 기간용으로
남겨뒀던 `st.markdown` 래퍼(`render_content_detail`·`render_content_table`·
`render_share_section`·`render_serp_columns`·`render_watchlist_rail`)와
스트림릿 버튼으로 행을 그리던 `render_content_rows`·`render_export_button`을
삭제했다 — 그래서 이 모듈은 이제 `streamlit`을 import하지 않는다(순수 문자열
빌더 + 데이터 계산만 남았다).

함수 이름에 언더스코어가 붙어있는 건(_esc, _content_rows 등) 원래 페이지
파일 안에서만 쓰던 이름을 그대로 옮겨서다 — 모듈 경계를 넘어 명시적으로
import해서 쓰는 용도라 실제로는 이 모듈의 공개 API지만, 이름을 전부
바꾸면 거대한 파일 전체에 오타 위험만 커져서 이번엔 이름은 그대로 두고
옮기기만 했다.
"""

import html as html_lib

from report_dashboard import charts, ui
from report_dashboard.reporting import (
    channel_distribution, delta_over_days, exposure_counts_by_channel,
    keyword_impact_leaderboard, keyword_rank_summary, keyword_weekly_exposure_counts, keyword_weekly_view_sums,
    latest_keyword_serp, latest_matched_ranks, latest_rank_row, latest_views, likes_history,
    participation_rate, rank_history, week_label,
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


def plain_section_header(title: str, sub_html: str = "", right_html: str = "", style: str = "", extra_class: str = "") -> str:
    """`.sec-h` 섹션 헤더 — `ui.section_header`와 달리 `reveal`을 붙이지 않는다(R12).

    목업의 `.sec-h`는 `section.reveal` **안에** 들어가는 평문 헤더다. 헤더 자체에도
    `reveal`을 걸면 스크롤 등장 애니메이션이 섹션과 이중으로 걸려 헤더만 따로 늦게 뜬다.
    `ui.section_header`는 v3 페이지(등록·관리자)가 그대로 쓰므로 손대지 않고, iframe
    본문·레일이 쓸 평문 버전을 여기 둔다 — `views.sec_h`가 이 함수를 재수출한다
    (views가 report_common을 import하므로 반대 방향은 순환 import가 된다).

    `title`만 이스케이프한다 — `sub_html`·`right_html`은 호출부 리터럴(신뢰된 HTML)이다.
    `style`·`extra_class`는 목업이 특정 자리에만 붙여둔 `margin-top:0`·`enter --i:N`용.
    """
    cls = f"sec-h {extra_class}" if extra_class else "sec-h"
    style_attr = f' style="{style}"' if style else ""
    return (
        f'<div class="{cls}"{style_attr}><h2 class="h-sec">{_esc(title)}</h2>'
        f'{sub_html}<span class="sp"></span>{right_html}</div>'
    )


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
    """행 리스트 표시 순서의 단일 정본 — 표를 그리는 쪽(`content_list_rows_html`·
    `content_table_html`)과 초기 선택을 고르는 쪽(`views.performance`), 그리고 JS의
    `orderRows`가 전부 이 순서를 따라야 "초기 선택 = 정렬 1위"가 어떤 정렬·필터
    조합에서도 어긋나지 않는다(R15).

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


def row_data_attrs(c: dict, pv: int, n_comments: int, rate: float | None) -> str:
    """두 콘텐츠 표(요약 상위 8·콘텐츠 성과 리스트)가 공유하는 `data-*` 계약(스펙 §4.2·§4.4).

    iframe 런타임(runtime.js)이 필터·정렬·합계를 이 속성만 읽어 다시 계산하므로
    속성 이름과 **순서**를 여기 한 곳에서 고정한다. `data-rate`는 계산할 수 없으면
    빈 문자열이다 — 0%로 지어내지 않는다(정직성 규칙).
    """
    rate_attr = "" if rate is None else f"{rate:g}"
    return (
        f'data-cid="{ui.esc(c["content_id"])}" data-ch="{ui.esc(c["channel"])}" data-pv="{pv}"'
        f' data-comments="{n_comments}" data-rate="{rate_attr}"'
        f' data-release="{ui.esc((c.get("release_at") or "")[:10])}" data-empty="{1 if pv == 0 else 0}"'
    )


def content_detail_html(ctx, content_id: str) -> str:
    """콘텐츠 상세 패널 `<aside class="detail">…</aside>` HTML.

    `id="detail"`은 붙이지 않는다 — iframe 본문(views/performance.py)이 현재 선택
    행의 상세만 `aside#detail`로 심고 나머지는 `<template data-detail=…>`에 담기
    때문에, id는 호출부가 붙이는 게 맞다(스펙 §4.4).
    """
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
    return (
        f'<aside class="detail"><div class="dh"><div><h2>{_esc(c.get("title") or c["url"])}</h2>'
        f'<div class="meta">{ui.channel_icon(c["channel"])}{_esc(ui.CHANNEL_LABEL.get(c["channel"], c["channel"]))} · {_esc((c.get("release_at") or "미정")[:10])} 게시 · <a href="{_esc(_safe_href(c["url"]))}" target="_blank" rel="noopener noreferrer">원문 열기 ↗</a></div></div></div>'
        f'<div class="kpis">{kpis}</div>'
        + ui.section_header(f"{primary_label} 추이", right_html=f'<span class="label">{len(series)}회 수집</span>') + chart
        + rank_block
        + ui.section_header(f"댓글 {len(comments)}") + cm
        + "</aside>"
    )


# 요약 페이지 콘텐츠 표(스펙 §4.2) — 목업 d4-mix.html의 thead 그대로.
_PERF_THEAD = (
    '<thead><tr><th>콘텐츠</th><th>채널</th><th>게시일</th><th>추이</th>'
    '<th class="r">조회 · 좋아요</th><th class="r">댓글</th><th class="r">순위</th></tr></thead>'
)


def content_table_html(ctx, *, limit=None) -> str:
    """콘텐츠 성과 표 HTML — **전 콘텐츠 행**을 값 내림차순(0은 맨 아래)으로 그린다.

    limit을 주면 그 이후 행에 `hidden`만 붙인다(행을 빼지 않는다) — JS가 채널
    필터 후 "보이는 순서로 앞 N개"를 다시 고르므로 서버는 전부 그려둬야 한다.
    inline-bar 폭도 전체 최대값 기준이고, 필터 후 폭은 JS가 재계산한다.
    """
    rows = sorted_content_rows(ctx, "value")
    vmax = max((r[1] for r in rows), default=0) or 1
    body = []
    for i, (c, pv, spark, n_comments, rank) in enumerate(rows):
        unit = "좋아요" if c["channel"] == "instagram" else "조회"
        hidden = " hidden" if limit is not None and i >= limit else ""
        attrs = row_data_attrs(c, pv, n_comments, _row_participation_rate(ctx, c, pv))
        rank_html = ui.rank_badge(rank["rank"] if rank else None, "—") if c["channel"] != "instagram" else '<span class="label">—</span>'
        body.append(
            f"<tr {attrs}{hidden}>"
            f'<td><span class="who">{_esc(c.get("title") or c["url"])}</span></td>'
            f'<td><span class="ch-cell">{ui.channel_icon(c["channel"])}<span class="label">{_esc(ui.CHANNEL_LABEL.get(c["channel"], c["channel"]))}</span></span></td>'
            f'<td><span class="mono label">{_esc((c.get("release_at") or "")[:10])}</span></td>'
            f'<td><div class="spark chart">{spark}</div></td>'
            f'<td class="r">{ui.inline_bar(pv / vmax * 100)}<span class="mono">{pv:,}</span> <span class="label">{unit}</span></td>'
            f'<td class="r"><span class="mono">{n_comments or "—"}</span></td>'
            f'<td class="r">{rank_html}</td></tr>'
        )
    return f'<table class="reveal tbl-perf">{_PERF_THEAD}<tbody>{"".join(body)}</tbody></table>'


# 콘텐츠 성과 리스트 표(스펙 §4.4) — 목업 p-content.html의 colgroup·thead 원문.
_LIST_COLGROUP = (
    '<colgroup><col style="width:34%"><col style="width:32px"><col style="width:96px">'
    '<col><col style="width:48px"><col style="width:72px"><col style="width:20px"></colgroup>'
)
_LIST_THEAD = (
    '<thead><tr><th>콘텐츠</th><th></th><th>추이</th><th class="r">조회 · 좋아요</th>'
    '<th class="r">댓글</th><th class="r">순위</th><th></th></tr></thead>'
)


def content_list_rows_html(ctx, selected_id: str | None) -> str:
    """콘텐츠 성과 마스터 리스트 표 HTML — 전 콘텐츠 행, 정렬은 value 기준.

    선택 행에 `class="is-sel"`을 붙인다. 정렬·필터·선택 이동은 JS가 이 표의
    `data-*`만 읽어 처리하므로(스펙 §4.4) 서버는 한 벌만 그린다.

    `selected_id`가 None이거나 이 캠페인에 없는 id면 **첫 행**을 선택한다(R4) —
    상세 패널(`aside#detail`)은 항상 어떤 행의 내용을 보여주므로, 표에 선택 행이
    하나도 없으면 강조와 상세가 어긋난다. 첫 행은 `views.performance`가 초기 상세로
    고르는 행(`sorted_content_rows(ctx, "value")[0]`)과 같다.
    """
    rows = sorted_content_rows(ctx, "value")
    ids = [r[0]["content_id"] for r in rows]
    sel_id = selected_id if selected_id in ids else (ids[0] if ids else None)
    vmax = max((r[1] for r in rows), default=0) or 1
    body = []
    for c, pv, spark, n_comments, rank in rows:
        unit = "좋아요" if c["channel"] == "instagram" else "조회"
        cls = ' class="is-sel"' if c["content_id"] == sel_id else ""
        attrs = row_data_attrs(c, pv, n_comments, _row_participation_rate(ctx, c, pv))
        rank_html = ui.rank_badge(rank["rank"] if rank else None, "—") if c["channel"] != "instagram" else '<span class="label">—</span>'
        body.append(
            f"<tr{cls} {attrs}>"
            f'<td><div class="t"><span class="who">{_esc(c.get("title") or c["url"])}</span>'
            f'<small>{_esc(ui.CHANNEL_LABEL.get(c["channel"], c["channel"]))} · {_esc((c.get("release_at") or "")[:10])}</small></div></td>'
            f'<td>{ui.channel_icon(c["channel"], 15)}</td>'
            f'<td><div class="spark chart">{spark}</div></td>'
            f'<td class="r">{ui.inline_bar(pv / vmax * 100, width=64)}<span class="mono">{pv:,}</span> <span class="label">{unit}</span></td>'
            f'<td class="r mono">{n_comments or "—"}</td>'
            f'<td class="r">{rank_html}</td><td class="chev">›</td></tr>'
        )
    return f'<table>{_LIST_COLGROUP}{_LIST_THEAD}<tbody>{"".join(body)}</tbody></table>'


def _share_color_map(tot: dict, ours: str) -> tuple[list[str], dict[str, str]]:
    """점유율 브랜드 순서와 색의 **단일 정본**(R11) — (순서, 브랜드→색).

    순서는 `[ours] + tot["top_brands"]`이고 색은 그 순서대로 `_SHARE_COLORS`다.
    `share_legend_html`(범례)과 `share_section_html`(행별·전체 스택 세그먼트)이 이
    함수를 함께 쓴다 — 두 곳에 같은 식을 적어두면 한쪽만 고쳤을 때 범례 점 색과
    막대 색이 조용히 갈린다. 표시 밖 매칭 브랜드는 `기타 브랜드`(`var(--muted)`),
    미매칭 슬롯은 `_SHARE_COLORS[3]`으로 두 곳이 같이 쓴다.
    """
    order = [ours] + tot["top_brands"]
    return order, {brand: _SHARE_COLORS[i] for i, brand in enumerate(order)}


def share_legend_html(tot: dict, ours: str) -> str:
    """점유율 범례(`.legend` 안에 들어가는 `<span>`들) — 색·순서는 `_share_color_map`이 정본.

    표시 밖 매칭 브랜드가 있으면 `기타 브랜드`(`var(--muted)`)를, 마지막에 항상
    `미매칭 슬롯`(`_SHARE_COLORS[3]`)을 붙인다.
    """
    order, color_of = _share_color_map(tot, ours)
    parts = [
        f'<span><i class="dot" style="background:{color_of[brand]}"></i>{_esc(brand)}</span>'
        for brand in order
    ]
    if tot["other_brands_pct"] > 0:
        parts.append('<span><i class="dot" style="background:var(--muted)"></i>기타 브랜드</span>')
    parts.append(f'<span><i class="dot" style="background:{_SHARE_COLORS[3]}"></i>미매칭 슬롯</span>')
    return "".join(parts)


def share_section_html(ctx, terms: list[dict], weighted: bool, *, rows=None, tot=None) -> str:
    """키워드 점유율(스펙 §7) 본문 — `.share-grid` 또는 `.empty` 하나만 돌려준다.

    `.sec-h`는 포함하지 않는다: iframe 본문은 헤더 1개 아래에 슬롯/가중 두 변형을
    `[data-variant]`로 나란히 심고 JS가 하나만 보여주기 때문(스펙 §4.3). 범례도
    호출부가 `share_legend_html`로 따로 그린다(헤더가 하나뿐이므로).

    `rows`·`tot`을 **둘 다** 주면 `share.keyword_share_rows`·`total_share`를 다시
    돌리지 않고 그 값을 쓴다 — 상위노출 뷰는 스트립 숫자·내보내기용으로 이미 변형마다
    계산해 두므로(views/exposure.py) 같은 집계를 두 번 돌릴 이유가 없다. 빈 상태 판정은
    넘긴 값과 무관하게 여기서 다시 한다(조건을 호출부에 복제하지 않는다).
    """
    from report_dashboard import share

    # 한쪽만 넘기면 "넘긴 값"과 "여기서 다시 돌린 값"이 섞여 행 막대와 전체 스택이 다른
    # 집계를 그린다 — 조용히 섞지 않고 호출부를 고치게 한다.
    if (rows is None) != (tot is None):
        raise ValueError("rows와 tot은 둘 다 주거나 둘 다 생략해야 한다")
    ours = share.ours_brand_of(terms)
    if not terms or not ctx["target_keywords"] or ours is None:
        if terms and ours is not None and not ctx["target_keywords"]:
            return ui.empty_state("추적 키워드가 없어 점유율을 계산할 수 없습니다", "등록·관리자에서 키워드를 등록하면 다음 수집부터 집계됩니다.")
        return ui.empty_state("점유율 브랜드 사전이 없습니다", "담당자가 등록·관리자 → 키워드 섹션에서 브랜드 사전을 입력하면 집계됩니다.")
    if rows is None or tot is None:
        rows = share.keyword_share_rows(ctx["keyword_serp_for_campaign"], ctx["target_keywords"], SERP_TABS, terms, weighted=weighted)
        tot = share.total_share(rows, ours)
    order, color_of = _share_color_map(tot, ours)
    other_brands_color, unmatched_color = "var(--muted)", _SHARE_COLORS[3]
    has_other_brands = tot["other_brands_pct"] > 0
    unit = "점" if weighted else "슬롯"
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
    return (
        f'<div class="share-grid"><div>{"".join(row_html)}</div><div class="share-side">'
        f'<div class="label">전체 {tot["denominator"]}{unit} 브랜드 분포</div>{charts.stack_bar_html(total_segs, ours_index=0, height=16)}'
        f'<div class="stack-lg">{lg}</div><div class="label" style="margin-top:18px">{_esc(ours)} 점유율 추이</div>{trend_html}</div></div>'
    )


def _serp_row_html(ctx, r: dict, tab: str) -> str:
    """SERP 한 줄. 우리 콘텐츠면 그 채널을 `data-ch`로 달아 JS가 채널 필터에 맞춰
    `.ours` 강조를 끌 수 있게 한다(스펙 §4.3).

    `content_id`가 있어도 `contents_by_id`(= 같은 광고주의 전 콘텐츠)에 없으면 채널을
    알 수 없어 `data-ch` 없이 `.srow.ours`만 남는다 — 다른 캠페인 콘텐츠가 같은 키워드
    SERP에 잡힌 경우다. 이때는 어떤 채널 칩을 꺼도 강조가 유지되는데, 이 페이지의 채널
    필터는 "이 캠페인 콘텐츠"를 대상으로 하므로 그게 맞다(끌 근거가 없다).
    """
    channel = (ctx["contents_by_id"].get(r["content_id"]) or {}).get("channel") if r["content_id"] else None
    ours_cls = " ours" if r["content_id"] else ""
    ch_attr = f' data-ch="{ui.esc(channel)}"' if channel else ""
    return (
        f'<a class="srow{ours_cls}"{ch_attr} href="{_esc(_safe_href(r["url"]))}" target="_blank" rel="noopener noreferrer">'
        f'<span class="r">{r["rank"]}</span><span class="t">{_esc(r.get("title") or r["url"])}</span>'
        f'<span class="src">{"우리 콘텐츠" if r["content_id"] else tab.replace("API", "")}</span></a>'
    )


def _serp_beyond_html(ctx, r: dict) -> str:
    c = ctx["contents_by_id"].get(r["content_id"]) or {}
    channel = c.get("channel")
    ch_attr = f' data-ch="{ui.esc(channel)}"' if channel else ""
    return (
        f'<div class="beyond"{ch_attr}><span class="label">10위 밖 우리 콘텐츠</span>{ui.rank_badge(r["rank"])}'
        f'<span>「{_esc(c.get("title") or r["content_id"])}」</span></div>'
    )


def serp_columns_html(ctx, keyword: str) -> str:
    """네이버 검색 API 최신순 상위 10 두 탭(블로그API·카페API)을 나란히 그린다.

    우리 콘텐츠(content_id 있는 행)만 .srow.ours로 강조하고, 목록에 안 잡힌
    10위 밖 매치는 탭마다 별도 노트로 붙인다.
    """
    cols_html = []
    for tab in SERP_TABS:
        rows = latest_keyword_serp(ctx["keyword_serp_for_campaign"], keyword, tab)
        ours_n = sum(1 for r in rows if r["content_id"])
        items = "".join(_serp_row_html(ctx, r, tab) for r in rows) or ui.empty_state("아직 수집 전입니다", "다음 06:00 수집 후 표시됩니다.")
        visible = {r["content_id"] for r in rows if r["content_id"]}
        beyond = [r for r in latest_matched_ranks(ctx["keyword_ranks_for_campaign"], keyword, tab) if r["content_id"] not in visible]
        beyond_html = "".join(_serp_beyond_html(ctx, r) for r in beyond) \
            or '<div class="beyond"><span class="label">10위 밖 우리 콘텐츠</span><span class="rank none">없음</span></div>'
        cols_html.append(
            f'<div><div class="serp-h"><h3 class="h-sec">{tab.replace("API", "")}</h3><span class="label">우리 콘텐츠 {ours_n}</span>'
            f'<span class="sp"></span><span class="label">"{_esc(keyword)}"</span></div>{items}{beyond_html}</div>'
        )
    return f'<div class="serp">{"".join(cols_html)}</div>'


def watchlist_html(ctx) -> str:
    """캠페인 키워드 순위 워치리스트 — 평문 `.sec-h` 헤더 + `.wl` 행들.

    헤더에 `reveal`을 붙이지 않는다(R12) — 이 블록은 상위노출 레일의
    `section.reveal` 안에 들어가고, 등장 모션은 그 섹션이 담당한다.

    채널 필터와 무관한 블록이라(키워드×탭 단위) `data-*`가 없다.
    """
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
    return plain_section_header("캠페인 키워드 순위", right_html='<span class="label">최고 순위 · 7일 변동(달력)</span>') + "".join(wl)


def exposure_rows_html(ctx) -> str:
    """채널별 네이버 노출 `.ch-row[data-ch]` 행들(헤더 없음, 없으면 빈 문자열).

    마크업은 `ui.channel_rows(numerators=…, denominators=…)`와 같지만 JS가 꺼진
    채널 행을 숨기려면 `data-ch`가 필요하다(스펙 §4.3) — `ui.channel_rows`는
    공용 컴포넌트라 손대지 않고 여기서 같은 구조를 직접 그린다.
    """
    exposure = exposure_counts_by_channel(ctx["contents"], ctx["all_ranks"])
    by_ch = {ch: n for ch, n in channel_distribution(ctx["contents"]).items() if ch != "instagram"}
    rows = []
    # 동률(건수가 같은 채널)에서 순서가 흔들리지 않게 `views.channel_counts`·채널 칩과 같은
    # 키로 정렬한다 — 칩 순서와 레일 행 순서가 달라 보이면 안 된다(R10).
    for ch, total in sorted(by_ch.items(), key=lambda kv: (-kv[1], kv[0])):
        num = exposure.get(ch, 0)
        pct = round(num / total * 100) if total else 0
        ch_esc = ui.esc(ch)
        rows.append(
            f'<div class="ch-row" data-ch="{ch_esc}"><span class="n"><i class="dot" style="background:var(--ch-{ch_esc})"></i>{ui.esc(ui.CHANNEL_LABEL.get(ch, ch))}</span>'
            f'<div class="hbar grow"><i style="width:{pct}%;background:var(--ch-{ch_esc})"></i></div>'
            f'<span class="v num">{num}<small>/ {total}</small></span></div>'
        )
    return "".join(rows)


def _impact_lead_html(impact_week, impact_rows, score_unit: str) -> str:
    def _lead_row(r) -> str:
        # I6: 3.11 호환 — f-string 표현식 안에 델리미터와 같은 종류의 따옴표를 중첩하면
        # (구버전 f-string 파서 제약) SyntaxError이므로 델타 라벨을 먼저 변수로 뺀다.
        delta_label = "NEW" if r["delta"] is None else f"지난주 대비 {r['delta']:+d}"
        return (
            f'<div class="lead"><span class="n">{r["rank"]}</span><span>{_esc(r["keyword"])}</span>'
            f'<span class="label">{delta_label}</span><span class="v">{r["score"]:,}{score_unit}</span></div>'
        )

    lead = "".join(_lead_row(r) for r in impact_rows) if impact_rows else ui.empty_state("아직 집계할 주간 데이터가 없습니다", "다음 주 수집부터 순위 변동과 함께 채워집니다.")
    week = week_label(impact_week) if impact_week else ""
    return plain_section_header("주간 키워드 파급력", right_html=f'<span class="label">{week}</span>') + lead


def impact_block_html(ctx, basis: str) -> str:
    """주간 키워드 파급력 블록 — 평문 `.sec-h` 헤더 포함, `<div class="lead-block" data-basis="…">`로 감싼다.

    basis: "count"(상위노출 콘텐츠 수) | "views"(매치 조회수 합). 상위노출 페이지는
    두 기준을 모두 미리 그려 넣고 JS가 세그먼트에 따라 하나만 보여준다(스펙 §4.3).
    """
    kws = ctx["target_keywords"]
    if basis == "count":
        weekly, unit = keyword_weekly_exposure_counts(ctx["keyword_ranks_for_campaign"], kws), "건"
    elif basis == "views":
        weekly, unit = keyword_weekly_view_sums(ctx["keyword_ranks_for_campaign"], ctx["view_metrics"], kws), "회"
    else:
        raise ValueError(f"basis must be 'count' or 'views': {basis!r}")
    week, impact_rows = keyword_impact_leaderboard(weekly)
    return f'<div class="lead-block" data-basis="{ui.esc(basis)}">{_impact_lead_html(week, impact_rows, unit)}</div>'
