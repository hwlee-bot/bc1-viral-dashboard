"""콘텐츠 성과 페이지 본문(스펙 v4 §4.4) — 목업 p-content.html의 `<main class="wrap">` 구조.

Python이 전 콘텐츠 행·전 상세 패널·초기 숫자를 한 번에 그려 넣고, iframe 안 JS는
`data-*`와 payload 시리즈만 읽어 숨기기·재정렬·재계산만 한다(§2 원칙 4).
"""
from __future__ import annotations

from report_dashboard import frame, ui, views
from report_dashboard.report_common import content_detail_html, content_list_rows_html, sorted_content_rows
from report_dashboard.reporting import (
    build_export_markdown, daily_view_series, latest_views, likes_history, likes_total,
)

_SORTS = (("value", "조회·좋아요"), ("comments", "댓글"), ("rate", "참여율"), ("recent", "최신"))
_META_TAIL = " · 좋아요·조회수·댓글 매일 06:30 자동 수집 · 인스타 조회수는 수집 불가(좋아요로 대체)"
# 목업 원문: 리스트 섹션 헤더는 ui.section_header(.sec-h.reveal)가 아니라 margin-top이 붙은 .sec-h다(R12).
_LIST_SEC_H = views.sec_h(
    "전체 콘텐츠",
    sub_html='<span class="label" data-hint>데이터 없는 콘텐츠는 맨 아래</span>',
    style="margin-top:22px",
)


def build(ctx, campaign) -> frame.FrameContent:
    export_md = build_export_markdown(
        f"{campaign['brand']} · {campaign['name']}",
        ctx["contents"], ctx["view_metrics"], ctx["all_ranks"], ctx["all_comments"],
    )
    payload = _payload(ctx)
    body = (
        ui.title_block("콘텐츠 성과", _meta_html(ctx["contents"]), _controls_html(ctx["contents"], bool(export_md)))
        + ui.stat_strip(_stats(ctx, payload))
        + '<hr class="rule">'
        + _list_and_detail(ctx)
    )
    return frame.FrameContent(
        body_html=body,
        page_css=frame.PAGE_CSS["content"],
        payload=payload,
        export_md=export_md,
        export_filename=f"{campaign['name']}_리포트.md",
    )


def _meta_html(contents: list[dict]) -> str:
    by_channel = " · ".join(
        f"{ui.esc(ui.CHANNEL_LABEL.get(channel, channel))} {n}" for channel, n in views.channel_counts(contents)
    )
    return (
        f'<b><span data-meta="contents">{len(contents)}</span>건</b> · '
        f'<span data-meta="by-channel">{by_channel}</span>{_META_TAIL}'
    )


def _controls_html(contents: list[dict], has_md: bool) -> str:
    seg = "".join(
        f'<span class="on" data-sort="{key}">{label}</span>' if i == 0 else f'<span data-sort="{key}">{label}</span>'
        for i, (key, label) in enumerate(_SORTS)
    )
    return (
        f'<div class="seg">{seg}</div>'
        + views.channel_chips_html(contents)
        + '<span class="chip" data-toggle="hide-empty">미수집 숨기기</span>'
        + views.export_btn_html(has_md)
    )


def _stats(ctx, payload) -> list[str]:
    total_views = sum(
        latest_views(ctx["view_metrics"], c["content_id"]) for c in ctx["contents"] if c["channel"] != "instagram"
    )
    series = payload["series"]
    view_points = views.series_points(series["views"])
    likes_points = views.series_points(series["likes"])
    rate = views.avg_row_rate(ctx)
    rate_html = f"{rate:.1f}<small>%</small>" if rate is not None else "—"
    # 참여율 스파크는 채널별 (합, 개수)를 전 채널 켜진 상태로 다시 평균한 값이다 —
    # JS `RT.combineRate`가 채널 토글 뒤 하는 계산과 같은 함수(`views.rate_points`)를 쓴다.
    rate_pts = views.rate_points(series["rate"]["dates"], series["rate"]["by_channel"], set(series["rate"]["by_channel"]))
    return [
        views.strip_card(
            '총 조회수 <span class="pill">카페·커뮤니티</span>',
            "views",
            views.stat_figure("views", f"{total_views:,}"),
            view_points,
            "카페·커뮤니티 자동 수집",
        ),
        views.strip_card(
            '총 좋아요 <span class="pill">인스타</span>',
            "likes",
            views.stat_figure("likes", f"{likes_total(ctx['all_metrics'], ctx['contents']):,}"),
            likes_points,
            "인스타 자동 수집",
        ),
        views.strip_card(
            "평균 참여율", "rate", views.stat_figure("rate", rate_html), rate_pts, "댓글 ÷ 조회수", unit="pt",
        ),
        views.strip_card(
            "수집 댓글",
            "comments",
            views.stat_figure("comments", f"{len(ctx['all_comments'])}<small>건</small>"),
            views.series_points(series["comments"]),
            "카페·인스타",
        ),
    ]


def _list_and_detail(ctx) -> str:
    rows = sorted_content_rows(ctx, "value")
    if not rows:
        # 보이는 행이 없으면 상세 자리에 빈 상태를 둔다(§4.4) — 템플릿도 없다.
        selected, detail, templates = None, ui.empty_state("표시할 콘텐츠가 없습니다", "미수집 숨기기를 해제하면 다시 표시됩니다."), ""
    else:
        selected = rows[0][0]["content_id"]
        # 목업 p-content.html의 `<aside class="detail reveal">`를 그대로 유지한다(등장 모션).
        detail = content_detail_html(ctx, selected).replace(
            '<aside class="detail">', '<aside class="detail reveal" id="detail">', 1
        )
        templates = "".join(
            f'<template data-detail="{ui.esc(content["content_id"])}">{content_detail_html(ctx, content["content_id"])}</template>'
            for content, *_ in rows
        )
    return (
        f'<div class="md"><section class="list enter" style="--i:2">{_LIST_SEC_H}'
        f'{content_list_rows_html(ctx, selected)}</section>{detail}{templates}</div>'
    )


def _payload(ctx) -> dict:
    """`{"series": {"views", "likes", "comments", "rate"}}` (스펙 §4.4·§11.3).

    조회수는 인스타를 뺀 채널별로(§1·R22), 좋아요는 인스타 콘텐츠별 이력을 날짜별
    최신값 합으로 하나의 `instagram` 시리즈로 만든다. 댓글은 요약과 같은 누적 댓글,
    참여율만 모양이 다르다 — `{ch: {sum, n}}`을 보내 JS가 `Σsum/Σn`으로 다시 평균한다
    (채널별 평균을 다시 평균하면 콘텐츠 수가 다른 채널이 같은 무게를 갖게 되어 틀린다).
    """
    by_id = ctx["contents_by_id"]
    view_channels = sorted({c["channel"] for c in ctx["contents"] if c["channel"] != "instagram"})
    per_channel = {
        channel: daily_view_series([m for m in ctx["view_metrics"] if by_id[m["content_id"]]["channel"] == channel])
        for channel in view_channels
    }
    ig_series = [
        likes_history([m for m in ctx["all_metrics"] if m["content_id"] == c["content_id"]])
        for c in ctx["contents"] if c["channel"] == "instagram"
    ]
    likes_per_channel = {"instagram": views.daily_sum_of_latest(ig_series)} if ig_series else {}
    return {
        "series": {
            "views": views.payload_series(per_channel),
            "likes": views.payload_series(likes_per_channel),
            "comments": views.payload_series(views.comments_count_series(ctx["all_comments"], by_id)),
            "rate": views.rate_series(ctx),
        }
    }
