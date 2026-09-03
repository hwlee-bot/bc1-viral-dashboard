"""요약 페이지 본문(스펙 v4 §4.2) — 목업 d4-mix.html의 `<main class="wrap">` 구조.

데이터 계산은 v3 `pages/0_요약.py`를 그대로 옮긴 것이다(누적 조회수의 인스타 제외 R22,
SERP 탭 기준 최고 순위·노출 키워드 수 I1/R11, 7일 미만 이력의 `수집 N일차` R10).
바뀐 것은 그리는 자리뿐 — Python이 초기 숫자·차트를 다 그리고, iframe 안 JS는
`data-*`와 payload 시리즈만 읽어 채널 필터 뒤 값을 다시 계산한다(§2 원칙 4).
"""
from __future__ import annotations

from report_dashboard import charts, frame, ui, views
from report_dashboard.report_common import SERP_TABS, content_table_html
from report_dashboard.reporting import (
    build_export_markdown, channel_distribution, daily_view_series, keyword_rank_summary,
    latest_matched_ranks, latest_sync_timestamp, likes_total,
)

_KW_TABS = ("카페API", "블로그API")   # 요약 키워드 표의 탭 순서(v3 그대로)
# sub 라벨은 세 모드 모두 그대로 둔다(리뷰 3) — `일별`에서 sub와 범례에 같은 문장을 두 번
# 쓰던 것을 없앴다. 모드에 따라 바뀌는 것은 **범례 한 곳**이고, 그 문구 정본이 아래 둘이다
# (`tests/test_runtime_js.py`가 runtime.js 상수와 글자 단위로 같은지 고정한다).
HERO_SUB = "카페·커뮤니티 조회수"
HERO_LEGEND_CUM = "전체 누적"
HERO_DAILY = "일별 증가분(수집 시점 차)"
_HERO_LEGEND = f'<span class="label" data-hero-legend><i class="dot" style="background:var(--ink)"></i> {HERO_LEGEND_CUM}</span>'
# 목업 d4-mix.html:48 — 세그먼트는 `.sec-h`의 맨 끝(범례 다음)에 온다.
_HERO_SEG = ('<div class="seg"><span class="on" data-hero="cum">누적</span>'
             '<span data-hero="daily">일별</span><span data-hero="channel">채널별</span></div>')
_RECENT = (
    '<section class="reveal recent"><span>순위 수집 <b>매일 06:00</b></span>'
    '<span>댓글 수집 <b>매일 06:30</b></span><span>인스타 지표 <b>매일 06:30</b></span></section>'
)


def build(ctx, campaign) -> frame.FrameContent:
    export_md = build_export_markdown(
        f"{campaign['brand']} · {campaign['name']}",
        ctx["contents"], ctx["view_metrics"], ctx["all_ranks"], ctx["all_comments"],
    )
    series = _view_series(ctx)
    payload = {"series": _payload_series(ctx)}
    body = (
        ui.title_block(campaign["name"], _meta_html(ctx, campaign), _controls_html(ctx["contents"], bool(export_md)))
        + ui.stat_strip(_stats(ctx, series, payload))
        + '<hr class="rule">'
        + _hero_html(series)
        + f'<div class="two">{_keyword_section(ctx)}{_channel_section(ctx)}</div>'
        + _top_contents_section(ctx)
        + _RECENT
    )
    return frame.FrameContent(
        body_html=body,
        payload=payload,
        export_md=export_md,
        export_filename=f"{campaign['name']}_리포트.md",
    )


def _view_series(ctx) -> list[tuple[str, int]]:
    """누적 조회수 곡선 — 인스타는 채널 기준으로 아예 뺀다(R22).

    view_metrics는 auto_instagram sentinel을 이미 뺀 상태지만, 수동 입력
    (manual_instagram 등) 인스타 조회수 행이 섞여 있어도 새어 들어가지 않게
    콘텐츠 채널로 한 번 더 걸러야 콘텐츠 성과 페이지와 정의가 같아진다.
    """
    by_id = ctx["contents_by_id"]
    return daily_view_series([m for m in ctx["view_metrics"] if by_id.get(m["content_id"], {}).get("channel") != "instagram"])


def _best_rank(ctx):
    """(순위, 키워드, 탭, content_id) — 블로그·카페 탭만 본다(R11: VIEW 탭은 수집 대상이 아님)."""
    summary = keyword_rank_summary(ctx["keyword_ranks_for_campaign"], ctx["target_keywords"])
    best = None
    for keyword, by_tab in summary.items():
        for tab in SERP_TABS:
            for row in by_tab.get(tab, []):
                if row["rank"] is not None and (best is None or row["rank"] < best[0]):
                    best = (row["rank"], keyword, tab, row["content_id"])
    # I1: 노출 카운트는 최고 순위 1건 유무(1/0)가 아니라 실제로 순위가 잡힌 키워드 개수다.
    exposed = sum(
        1 for by_tab in summary.values()
        if any(row["rank"] is not None for tab in SERP_TABS for row in by_tab.get(tab, []))
    )
    return best, exposed


def _meta_html(ctx, campaign) -> str:
    period = f"{campaign.get('start_date') or '—'} – {campaign.get('end_date') or '진행 중'}"
    synced = latest_sync_timestamp(ctx["all_metrics"])   # 상위노출 페이지와 같은 "YYYY-MM-DD HH:MM" 표기
    return (
        f"<b>{ui.esc(period)}</b> · 콘텐츠 <span data-meta=\"contents\">{len(ctx['contents'])}</span>건 · "
        f"채널 <span data-meta=\"channels\">{len(channel_distribution(ctx['contents']))}</span>개 · "
        f"추적 키워드 {len(ctx['target_keywords'])}개 · "
        f"마지막 수집 {ui.esc(synced[:16].replace('T', ' ')) if synced else '없음'}"
    )


def _controls_html(contents: list[dict], has_md: bool) -> str:
    # 요약 칩은 인스타도 포함한다 — 등록 콘텐츠·채널 분포·상위 8 표가 인스타를 세기 때문.
    return views.channel_chips_html(contents) + views.export_btn_html(has_md)


def _stats(ctx, series: list[tuple[str, int]], payload: dict) -> list[str]:
    values = [value for _, value in series]
    best, exposed = _best_rank(ctx)
    rank_side = ui.big_rank(best[0], f"{best[1]} · {best[2].replace('API', '')}") if best else ui.spark_box("")
    best_title = (ctx["contents_by_id"].get(best[3]) or {}).get("title", "") if best else "아직 노출 없음"
    likes = likes_total(ctx["all_metrics"], ctx["contents"])
    comments_n = len(ctx["all_comments"])
    return [
        views.strip_card(
            '누적 조회수 <span class="pill">카페·커뮤니티</span>',
            "views",
            views.stat_figure("views", f"{values[-1]:,}" if values else "0"),
            series,
            "카페·커뮤니티 자동 수집",
        ),
        # 좋아요 합은 라벨의 `.pill`이다(리뷰 4) — 목업 카드 레이아웃(label / figure / spark /
        # delta)을 그대로 두면서 `누적 조회수`의 `카페·커뮤니티` pill과 같은 패턴을 쓴다.
        # figure 안에 두면 `put("contents")`가 캐시한 `<small>`에 좋아요 span이 딸려 들어가
        # 두 호출의 순서에 결과가 걸린다(그 의존을 없앴다).
        views.strip_card(
            f'등록 콘텐츠 <span class="pill">인스타 좋아요 합 <span data-stat="likes">{likes:,}</span></span>',
            "contents",
            views.stat_figure("contents", f"{len(ctx['contents'])}<small>건</small>"),
            views.series_points(payload["series"]["contents"]),
            "등록일 기준 누적",
        ),
        views.strip_card(
            "수집 댓글",
            "comments",
            views.stat_figure("comments", f"{comments_n}<small>건</small>"),
            views.series_points(payload["series"]["comments"]),
            "카페·인스타 자동 수집",
        ),
        # 4번째 칸은 키워드 기반이라 채널 필터와 무관하다 — data-stat 없이 정적으로 둔다(§4.2).
        ui.stat(
            "네이버 상위노출",
            f"{exposed}<small>/ {len(ctx['target_keywords'])} 키워드</small>",
            rank_side,
            ui.delta(best_title),
        ),
    ]


def _hero_html(series: list[tuple[str, int]]) -> str:
    """`data-chart="hero"` div는 데이터가 부족해도 항상 남긴다 — JS가 채널 필터 뒤
    점이 3개 이상이 되면 이 안에 곡선을 그려 넣기 때문이다."""
    if len(series) >= 3:
        inner = charts.area_chart_svg(
            [value for _, value in series],
            labels=[day[5:].replace("-", ".") for day, _ in series],
            width=1140, height=230, pad_right=64, ink=True,
        )
    else:
        inner = ui.empty_state("추이를 그릴 데이터가 아직 부족합니다", "수집일이 3일 이상 쌓이면 곡선이 나타납니다.")
    return (
        views.sec_h(
            "조회수 추이", sub_html=f'<span class="label">{HERO_SUB}</span>',
            right_html=_HERO_LEGEND + _HERO_SEG, style="--i:2", extra_class="enter",
        )
        + f'<div class="chart hero-chart enter" style="--i:3" data-chart="hero">{inner}</div>'
    )


def _keyword_section(ctx) -> str:
    rows = []
    for keyword in ctx["target_keywords"]:
        for tab in _KW_TABS:
            matched = latest_matched_ranks(ctx["keyword_ranks_for_campaign"], keyword, tab)
            tab_html = f'<span class="label">{tab.replace("API", "")}</span>'
            if matched:
                best = min(matched, key=lambda r: r["rank"])
                title = (ctx["contents_by_id"].get(best["content_id"]) or {}).get("title") or best["content_id"]
                rows.append([ui.esc(keyword), tab_html, ui.esc(title), ui.rank_badge(best["rank"])])
            else:
                rows.append([ui.esc(keyword), tab_html, '<span class="label">—</span>', ui.rank_badge(None)])
    headers = [("키워드", False), ("탭", False), ("노출 콘텐츠", False), ("순위", True)]
    return (
        '<section class="reveal">'
        + views.sec_h("네이버 키워드 순위", right_html='<a href="#" data-nav="상위노출">상위노출 →</a>', style="margin-top:0")
        + ui.table_html(headers, rows)
        + "</section>"
    )


def _channel_section(ctx) -> str:
    rate = views.avg_row_rate(ctx)
    rate_html = f"{rate:.1f}<small>%</small>" if rate is not None else "—"
    return (
        '<section class="reveal">'
        + views.sec_h("채널 분포", right_html='<a href="#" data-nav="콘텐츠 성과">콘텐츠 성과 →</a>', style="margin-top:0")
        + views.channel_rows_with_data(channel_distribution(ctx["contents"]))
        + '<div class="mini"><div><span class="label">평균 참여율</span>'
        f'<div class="figure num" data-stat="rate">{rate_html}</div></div>'
        '<div><span class="label">수집 댓글</span>'
        f'<div class="figure num" data-stat="comments">{len(ctx["all_comments"])}<small>건</small></div></div></div>'
        "</section>"
    )


def _top_contents_section(ctx) -> str:
    # 목업(d4-mix.html:82)의 상위 8 헤더는 평문 `.sec-h`다 — 등장 모션은 표(`.reveal`)가 가진다.
    # sub에 `data-meta` span이 들어가야 해서 sub_html(신뢰 HTML)로 넘긴다.
    return (
        views.sec_h(
            "콘텐츠 성과",
            sub_html=f'<span class="label"><span data-meta="contents">{len(ctx["contents"])}</span>건 중 상위 8</span>',
            right_html='<a href="#" data-nav="콘텐츠 성과">전체 →</a>',
        )
        + content_table_html(ctx, limit=8)
    )


def _payload_series(ctx) -> dict:
    """`{"views": {dates, by_channel}, "contents": {...}, "comments": {...}}` (스펙 §4.2·§11.3).

    조회수는 선택 채널 합이 `daily_view_series(filtered)`와 정확히 같아야 JS가 다시 그린
    히어로 곡선·스트립 숫자가 Python이 그린 초기값과 어긋나지 않는다. 등록 콘텐츠·수집
    댓글도 같은 `{dates, by_channel}` 모양이라 JS가 `combineSeries` 한 함수로 다 합친다.
    """
    by_id = ctx["contents_by_id"]
    channels = sorted({c["channel"] for c in ctx["contents"] if c["channel"] != "instagram"})
    per_channel = {
        channel: daily_view_series([m for m in ctx["view_metrics"] if by_id[m["content_id"]]["channel"] == channel])
        for channel in channels
    }
    return {
        "views": views.payload_series(per_channel),
        "contents": views.payload_series(views.contents_count_series(ctx["contents"])),
        "comments": views.payload_series(views.comments_count_series(ctx["all_comments"], by_id)),
    }
