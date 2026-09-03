"""상위노출 페이지 본문(스펙 v4 §4.3) — 목업 p-exposure.html의 `<main class="wrap">` 구조.

데이터 계산은 v3 `pages/1_상위노출.py`를 그대로 옮긴 것이다(점유율 슬롯·가중,
VIEW 탭을 섞지 않는 최고 순위·노출 건수 R11, 브랜드 사전이 없으면 `.empty`).
바뀐 것은 **고르는 방식**뿐 — 세그먼트(점유율 모드·파급력 기준)와 키워드 칩으로
서버를 다시 돌리던 것을 Python이 변형을 다 그려 넣고 iframe 안 JS가
`data-variant`·`data-basis`·`data-kw`로 하나만 보여주는 방식으로 바꿨다(§2 원칙 4).
"""
from __future__ import annotations

from report_dashboard import charts, frame, share, ui, views
from report_dashboard.report_common import (
    CHANNELS, SERP_TABS, exposure_rows_html, impact_block_html, serp_columns_html,
    share_legend_html, share_section_html, watchlist_html,
)
from report_dashboard.reporting import build_export_markdown, keyword_rank_summary

# 네이버 순위를 추적하는 채널만 칩으로 낸다 — 인스타는 SERP 대상이 아니다(§4.3).
_NAVER_CHANNELS = [c for c in CHANNELS if c != "instagram"]
_BASES = (("count", "상위노출 콘텐츠 수"), ("views", "매치 조회수 합"))
# 분모는 변형마다 다르므로(40슬롯 / 220점) sub에 넣지 않고 스트립 캡션이 담당한다.
_SHARE_SUB = "키워드×탭 네이버 검색 API 최신순 상위 10 슬롯 중 제목에 브랜드가 매칭된 비율"
_SHARE_SEG = ('<div class="seg"><span class="on" data-variant="slot">슬롯 수</span>'
              '<span data-variant="weighted">위치 가중</span></div>')
_SERP_SUB = "네이버 검색 API 최신순 상위 10 · 우리 콘텐츠는 색으로 표시"
# 레일 섹션(`section.reveal`) 안에 들어가므로 평문 `.sec-h`다(R12).
_EXPOSURE_HEADER = views.sec_h("채널별 네이버 노출", right_html='<span class="label">100위 내</span>')


def build(ctx, campaign, terms) -> frame.FrameContent:
    kws = ctx["target_keywords"]
    ours = share.ours_brand_of(terms)
    rows_slot, tot_slot = _share_rows_and_total(ctx, kws, terms, ours, weighted=False)
    rows_weighted, tot_weighted = _share_rows_and_total(ctx, kws, terms, ours, weighted=True)
    summary = keyword_rank_summary(ctx["keyword_ranks_for_campaign"], kws)
    collected = _last_collected(ctx)
    sparks = _strip_sparks(ctx, kws, terms)
    export_md = build_export_markdown(
        f"{campaign['brand']} · {campaign['name']}",
        ctx["contents"], ctx["view_metrics"], ctx["all_ranks"], ctx["all_comments"],
        share_summary=tot_slot,          # 내보내기 점유율은 슬롯 기준 한 벌만 싣는다
    )
    body = (
        ui.title_block("네이버 상위노출", _meta_html(kws, collected), _controls_html(ctx["contents"], bool(export_md)))
        + ui.stat_strip(_stats(kws, summary, tot_slot, tot_weighted, sparks))
        + '<hr class="rule">'
        + _share_section(ctx, terms, (rows_slot, tot_slot), (rows_weighted, tot_weighted))
        + _two_html(ctx, kws, summary, collected)
    )
    return frame.FrameContent(
        body_html=body,
        page_css=frame.PAGE_CSS["exposure"],
        export_md=export_md,
        export_filename=f"{campaign['name']}_리포트.md",
    )


def _share_rows_and_total(ctx, kws, terms, ours, *, weighted: bool) -> tuple[list, dict | None]:
    """(점유율 행, `share.total_share` 결과) — 사전·키워드·수집이 없으면 ([], None).

    행까지 같이 돌려주는 이유는 이 값을 `share_section_html(..., rows=, tot=)`에 그대로
    넘겨 같은 집계를 두 번 돌리지 않기 위해서다(리뷰 R11) — 스트립 숫자·내보내기 요약도
    같은 결과를 쓴다.
    """
    rows = share.keyword_share_rows(
        ctx["keyword_serp_for_campaign"], kws, SERP_TABS, terms, weighted=weighted,
    ) if terms else []
    return rows, (share.total_share(rows, ours) if rows else None)


def _last_collected(ctx) -> str:
    """SERP 마지막 수집 시각 "YYYY-MM-DD HH:MM"(없으면 빈 문자열) — 원시 ISO는 노출하지 않는다."""
    at = max((r["captured_at"] for r in ctx["keyword_serp_for_campaign"]), default=None)
    return at[:16].replace("T", " ") if at else ""


def _meta_html(kws: list[str], collected: str) -> str:
    return (
        f"<b>키워드 {len(kws)}개 · 블로그·카페 탭</b> · 매일 06:00 자동 수집 · "
        f"VIEW 탭은 수집 대상이 아닙니다 · 마지막 수집 {ui.esc(collected) if collected else '없음'}"
    )


def _controls_html(contents: list[dict], has_md: bool) -> str:
    seg = "".join(
        f'<span class="on" data-basis="{key}">{label}</span>' if i == 0 else f'<span data-basis="{key}">{label}</span>'
        for i, (key, label) in enumerate(_BASES)
    )
    return (
        f'<div class="seg">{seg}</div>'
        + views.channel_chips_html(contents, channels_allowed=_NAVER_CHANNELS)
        + views.export_btn_html(has_md)
    )


def _rank_rows(summary) -> list[tuple[int, str, str]]:
    """(순위, 키워드, 탭) — 블로그·카페 탭만(R11: VIEW 탭은 수집 대상이 아님)."""
    return [
        (r["rank"], kw, tab)
        for kw, by_tab in summary.items() for tab in SERP_TABS for r in by_tab.get(tab, [])
        if r["rank"] is not None
    ]


def _variant_figure(slot_html: str, weighted_html: str) -> str:
    """점유율 figure — 슬롯·가중 두 값을 함께 심고 JS가 하나만 보여준다(§4.3)."""
    return (
        '<span class="figure num">'
        f'<span data-variant="slot">{slot_html}</span>'
        f'<span data-variant="weighted" hidden>{weighted_html}</span></span>'
    )


def _variant_delta(slot_text: str, weighted_text: str) -> str:
    return (
        '<span class="delta flat">'
        f'<span data-variant="slot">{ui.esc(slot_text)}</span>'
        f'<span data-variant="weighted" hidden>{ui.esc(weighted_text)}</span></span>'
    )


def _pct(value: float) -> str:
    return f"{value:.1f}<small>%</small>"


def _strip_sparks(ctx, kws, terms) -> dict[str, str]:
    """스트립 스파크 세 칸의 SVG(§11.3). 관측이 2점 미만이면 빈 문자열 — 예시를 그리지 않는다.

    상위노출 페이지는 payload가 없다(채널 필터가 스트립에 영향을 주지 않으므로 JS가
    다시 계산할 것이 없다) — 그래서 슬롯/가중 두 벌을 **Python이 미리 다 그려두고**
    세그먼트 토글은 `[data-spark-variant]` 표시만 바꾼다.
    """
    def spark(values):
        return charts.sparkline_svg(values, width=112, height=30, ink=True) if len(values) >= 2 else ""

    serp = ctx["keyword_serp_for_campaign"]
    keywords_svg = spark([n for _, n in views.keyword_count_series(ctx["target_keyword_rows"])])
    out = {"keywords": keywords_svg, "brand_slot": "", "brand_weighted": "", "campaign_slot": "", "campaign_weighted": ""}
    if not (kws and terms and serp):
        return out
    for name, weighted in (("slot", False), ("weighted", True)):
        points = views.share_trend_points(serp, kws, SERP_TABS, terms, weighted=weighted)
        out[f"brand_{name}"] = spark([ours for _, ours, _ in points])
        out[f"campaign_{name}"] = spark([campaign for _, _, campaign in points])
    return out


def _stats(kws, summary, tot_slot, tot_weighted, sparks) -> list[str]:
    ranks = _rank_rows(summary)
    best = min((rank for rank, _, _ in ranks), default=None)
    best_kw = next(((kw, tab) for rank, kw, tab in ranks if rank == best), None) if best else None
    in_top10 = sum(1 for rank, _, _ in ranks if rank <= 10)
    slots = len(kws) * len(SERP_TABS) * share.SLOTS_PER_TAB
    if tot_slot and tot_weighted:
        brand_figure = _variant_figure(_pct(tot_slot["ours_pct"]), _pct(tot_weighted["ours_pct"]))
        brand_delta = _variant_delta(f"분모 {tot_slot['denominator']}슬롯", f"분모 {tot_weighted['denominator']}점")
        campaign_figure = _variant_figure(_pct(tot_slot["campaign_pct"]), _pct(tot_weighted["campaign_pct"]))
    else:
        brand_figure = campaign_figure = _variant_figure("—", "—")
        brand_delta = ui.delta("브랜드 사전 필요", "flat")
    rank_side = ui.big_rank(best, f"{best_kw[0]} · {best_kw[1].replace('API', '')}") if best_kw else ui.spark_box("")
    return [
        ui.stat("추적 키워드", f"{len(kws)}<small>개 · {slots}슬롯</small>",
                views.spark_html(sparks["keywords"], "keywords"), ui.delta("블로그·카페 상위 10", "flat")),
        views._stat("브랜드 점유율", brand_figure,
                    views.spark_variants_html(sparks["brand_slot"], sparks["brand_weighted"]), brand_delta),
        views._stat("캠페인 콘텐츠 점유율", campaign_figure,
                    views.spark_variants_html(sparks["campaign_slot"], sparks["campaign_weighted"]),
                    ui.delta(f"상위 10 진입 {in_top10}", "flat")),
        ui.stat("상위 100위 내 노출", f"{len(ranks)}<small>건</small>", rank_side,
                ui.delta("최고 순위" if best else "아직 노출 없음", "flat")),
    ]


def _share_header(sub_html: str = "", right_html: str = "") -> str:
    # 목업 원문: 점유율 섹션 헤더는 .sec-h.reveal이 아니라 margin-top이 붙은 .sec-h다(R12).
    return views.sec_h("키워드 점유율", sub_html=sub_html, right_html=right_html, style="margin-top:32px")


def _share_body(ctx, terms, weighted: bool, pair) -> str:
    """이미 계산한 (행, 합계)로 본문 한 벌 — 합계가 없으면(집계 대상 0건) 아무것도 넘기지 않는다.

    `share_section_html`은 `rows`·`tot`을 **둘 다 주거나 둘 다 생략**해야 한다(한쪽만
    주면 ValueError) — 넘긴 값과 여기서 다시 돌린 값이 섞이면 행 막대와 전체 스택이
    다른 집계를 그리기 때문이다. `_share_rows_and_total`은 집계 대상이 없을 때 합계를
    None으로 돌려주므로 그 경우엔 재계산 경로로 보낸다(결과는 예전과 같다).
    """
    rows, tot = pair
    if tot is None:
        return share_section_html(ctx, terms, weighted)
    return share_section_html(ctx, terms, weighted, rows=rows, tot=tot)


def _share_section(ctx, terms, slot, weighted_pair) -> str:
    """헤더 1개 + `.share-grid[data-variant]` 두 벌. 계산이 불가능하면 `.empty` 한 벌.

    `slot`·`weighted_pair`는 `_share_rows_and_total`의 (행, 합계)다 — 본문 두 벌이
    같은 집계를 다시 돌리지 않게 그대로 넘긴다(R11). 두 벌인지 아닌지는
    `share_section_html`이 실제로 돌려준 것으로 판단한다 — 빈 상태 조건(사전 없음·
    키워드 없음·우리 브랜드 없음)을 여기서 다시 적으면 report_common과 갈라질 수 있다.
    """
    _, tot_slot = slot
    slot_body = _share_body(ctx, terms, False, slot)
    if not slot_body.startswith('<div class="share-grid">') or tot_slot is None:
        # 빈 상태는 변형이 없으므로 범례·세그먼트를 붙이지 않는다(고를 것이 없다).
        return f'<section class="share enter" style="--i:2">{_share_header()}{slot_body}</section>'
    header = _share_header(
        sub_html=f'<span class="label">{_SHARE_SUB}</span>',
        right_html=f'<div class="legend">{share_legend_html(tot_slot, tot_slot["ours_brand"])}</div>{_SHARE_SEG}',
    )
    slot_html = slot_body.replace('<div class="share-grid">', '<div class="share-grid" data-variant="slot">', 1)
    weighted = _share_body(ctx, terms, True, weighted_pair).replace(
        '<div class="share-grid">', '<div class="share-grid" data-variant="weighted" hidden>', 1,
    )
    return f'<section class="share enter" style="--i:2">{header}{slot_html}{weighted}</section>'


def _kw_chips_html(kws: list[str], summary) -> str:
    chips = []
    for i, kw in enumerate(kws):
        by_tab = summary.get(kw, {})
        ranks = [r["rank"] for tab in SERP_TABS for r in by_tab.get(tab, []) if r["rank"] is not None]
        best = min(ranks) if ranks else "—"
        cls = "chip on" if i == 0 else "chip"
        chips.append(f'<span class="{cls}" data-kw="{ui.esc(kw)}">{ui.esc(kw)} <b>{best}</b></span>')
    return f'<div class="kw-chips enter" style="--i:3">{"".join(chips)}</div>'


def _serp_blocks_html(ctx, kws: list[str]) -> str:
    """키워드마다 한 벌씩 미리 그리고 첫 것만 보인다 — 전환은 JS가 한다(§4.1)."""
    blocks = []
    for i, kw in enumerate(kws):
        hidden = "" if i == 0 else " hidden"
        open_tag = f'<div class="serp enter" style="--i:4" data-kw="{ui.esc(kw)}"{hidden}>'
        blocks.append(serp_columns_html(ctx, kw).replace('<div class="serp">', open_tag, 1))
    return "".join(blocks)


def _serp_section(ctx, kws: list[str], summary, collected: str) -> str:
    header = views.sec_h(
        "키워드 검색결과",
        sub_html=f'<span class="label">{_SERP_SUB}</span>',
        right_html=f'<span class="label">{ui.esc(collected)}</span>',
        style="--i:2", extra_class="enter",
    )
    if not kws:
        inner = ui.empty_state("추적 키워드가 없습니다", "등록·관리자에서 키워드를 등록하면 검색결과가 수집됩니다.")
    else:
        inner = _kw_chips_html(kws, summary) + _serp_blocks_html(ctx, kws)
    return f"<section>{header}{inner}</section>"


def _rail_html(ctx) -> str:
    exposure_rows = exposure_rows_html(ctx) or ui.empty_state(
        "네이버 추적 대상 채널이 없습니다", "카페·블로그·커뮤니티 콘텐츠만 순위를 추적합니다.",
    )
    impact_views = impact_block_html(ctx, "views").replace(
        '<div class="lead-block" data-basis="views">', '<div class="lead-block" data-basis="views" hidden>', 1,
    )
    return (
        '<aside class="rail">'
        f'<section class="reveal">{watchlist_html(ctx)}</section>'
        f'<section class="reveal">{_EXPOSURE_HEADER}{exposure_rows}</section>'
        f'<section class="reveal">{impact_block_html(ctx, "count")}{impact_views}</section>'
        "</aside>"
    )


def _two_html(ctx, kws, summary, collected: str) -> str:
    return (
        '<div class="two" style="grid-template-columns: 8fr 4fr; gap: 48px;">'
        f'{_serp_section(ctx, kws, summary, collected)}{_rail_html(ctx)}</div>'
    )
