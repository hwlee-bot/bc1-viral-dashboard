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
# 분모는 변형·깊이마다 다르므로(40슬롯 / 220점 / …) sub에 넣지 않고 스트립 캡션이 담당한다.
# 깊이 숫자만 `[data-depth-label]`로 남겨 세그먼트가 바꾼다(§12.2).
_SHARE_SUB = ('키워드×탭 네이버 검색 API 최신순 상위 <span data-depth-label>10</span> 슬롯 중 '
              "제목에 브랜드가 매칭된 비율")
_DEPTH_SEG = '<div class="seg" data-seg="depth">' + "".join(
    f'<span class="on" data-depth="{d}">상위 {d}</span>' if i == 0 else f'<span data-depth="{d}">상위 {d}</span>'
    for i, d in enumerate(share.DEPTHS)
) + "</div>"
_SHARE_SEG = ('<div class="seg" data-seg="variant"><span class="on" data-variant="slot">슬롯 수</span>'
              '<span data-variant="weighted">위치 가중</span></div>')
_SERP_SUB = "네이버 검색 API 최신순 상위 10 · 우리 콘텐츠는 색으로 표시"
# 레일 섹션(`section.reveal`) 안에 들어가므로 평문 `.sec-h`다(R12).
_EXPOSURE_HEADER = views.sec_h("채널별 네이버 노출", right_html='<span class="label">100위 내</span>')


def build(ctx, campaign, terms) -> frame.FrameContent:
    kws = ctx["target_keywords"]
    ours = share.ours_brand_of(terms)
    stored = share.latest_stored_depth(ctx["keyword_serp_for_campaign"], kws, SERP_TABS)
    depths = [d for d in share.DEPTHS if _depth_available(d, stored)]
    pairs = {
        (depth, variant): _share_rows_and_total(ctx, kws, terms, ours, weighted=weighted, slots=depth)
        for depth in depths for variant, weighted in views.SHARE_VARIANTS
    }
    summary = keyword_rank_summary(ctx["keyword_ranks_for_campaign"], kws)
    collected = _last_collected(ctx)
    sparks = _strip_sparks(ctx, kws, terms, depths)
    export_md = build_export_markdown(
        f"{campaign['brand']} · {campaign['name']}",
        ctx["contents"], ctx["view_metrics"], ctx["all_ranks"], ctx["all_comments"],
        # 내보내기 점유율은 깊이 10 · 슬롯 기준 한 벌만 싣는다(§12.1) — 깊이는 화면에서 고르는 것이다.
        share_summary=pairs[(share.SLOTS_PER_TAB, "slot")][1],
    )
    body = (
        ui.title_block("네이버 상위노출", _meta_html(kws, collected), _controls_html(ctx["contents"], bool(export_md)))
        + ui.stat_strip(_stats(kws, summary, pairs, sparks, stored))
        + '<hr class="rule">'
        + _share_section(ctx, terms, pairs, stored)
        + _two_html(ctx, kws, summary, collected)
    )
    return frame.FrameContent(
        body_html=body,
        page_css=frame.PAGE_CSS["exposure"],
        export_md=export_md,
        export_filename=f"{campaign['name']}_리포트.md",
    )


def _depth_available(depth: int, stored: int) -> bool:
    """이 깊이를 집계해도 되는가(§12.1) — 최신 저장 범위가 그 깊이까지 닿아야 한다.

    깊이 10은 예외 없이 항상 집계한다: v4.1까지의 동작이고, 얕게 잡힌 (키워드, 탭)의
    빈 슬롯은 §7 규칙대로 이미 분모에 남아 점유율을 낮추는 쪽으로 정직하다. 30/50은
    "10위까지만 저장된 옛 배치"를 섞으면 점유율이 실제보다 높게 나오므로 막는다.
    """
    return depth <= share.SLOTS_PER_TAB or depth <= stored


def _share_rows_and_total(ctx, kws, terms, ours, *, weighted: bool, slots: int) -> tuple[list, dict | None]:
    """(점유율 행, `share.total_share` 결과) — 사전·키워드·수집이 없으면 ([], None).

    행까지 같이 돌려주는 이유는 이 값을 `share_section_html(..., rows=, tot=)`에 그대로
    넘겨 같은 집계를 두 번 돌리지 않기 위해서다(리뷰 R11) — 스트립 숫자·내보내기 요약도
    같은 결과를 쓴다.
    """
    rows = share.keyword_share_rows(
        ctx["keyword_serp_for_campaign"], kws, SERP_TABS, terms, weighted=weighted, slots=slots,
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


def _depth_figure(html_of) -> str:
    """점유율 figure — 깊이 3 × 변형 2 = 6벌을 함께 심고 JS가 하나만 보여준다(§4.3·§12.2).

    `html_of(depth, variant)`는 이미 만들어진 HTML을 돌려준다(이스케이프하지 않는다 —
    `<small>%</small>` 같은 단위 마크업이 들어간다).
    """
    return '<span class="figure num">' + views.depth_variant_cells(
        lambda depth, variant, hidden: f'<span data-depth="{depth}" data-variant="{variant}"{hidden}>{html_of(depth, variant)}</span>',
    ) + "</span>"


def _depth_delta(text_of) -> str:
    """점유율 캡션 6벌 — 분모(깊이·변형마다 다르다)나 못 쓰는 깊이의 저장 범위를 적는다."""
    return '<span class="delta flat">' + views.depth_variant_cells(
        lambda depth, variant, hidden: f'<span data-depth="{depth}" data-variant="{variant}"{hidden}>{ui.esc(text_of(depth, variant))}</span>',
    ) + "</span>"


def _pct(value: float) -> str:
    return f"{value:.1f}<small>%</small>"


_UNIT = {"slot": "슬롯", "weighted": "점"}


def _denominator_caption(tot, variant: str, depth: int, stored: int) -> str:
    """브랜드 점유율 카드의 캡션 — 쓸 수 있으면 분모, 못 쓰면 왜 없는지."""
    if tot is None:
        return "브랜드 사전 필요" if _depth_available(depth, stored) else f"수집 범위 {stored}위"
    return f"분모 {tot['denominator']}{_UNIT[variant]}"


def _strip_sparks(ctx, kws, terms, depths) -> dict:
    """스트립 스파크의 SVG(§11.3·§12.2). 관측이 2점 미만이면 빈 문자열 — 예시를 그리지 않는다.

    상위노출 페이지는 payload가 없다(채널 필터가 스트립에 영향을 주지 않으므로 JS가
    다시 계산할 것이 없다) — 그래서 깊이 3 × 슬롯/가중 = 6벌을 **Python이 미리 다 그려두고**
    세그먼트 토글은 `[data-depth]`·`[data-spark-variant]` 표시만 바꾼다.

    `depths`에 없는 깊이(저장 범위 밖)는 아예 계산하지 않으므로 빈 스파크가 남는다.
    반환: `{"keywords": svg, "brand": {(깊이, 변형): svg}, "campaign": {...}}`.
    """
    def spark(values):
        return charts.sparkline_svg(values, width=112, height=30, ink=True) if len(values) >= 2 else ""

    serp = ctx["keyword_serp_for_campaign"]
    out = {
        "keywords": spark([n for _, n in views.keyword_count_series(ctx["target_keyword_rows"])]),
        "brand": {}, "campaign": {},
    }
    if not (kws and terms and serp):
        return out
    for depth in depths:
        for variant, weighted in views.SHARE_VARIANTS:
            points = views.share_trend_points(serp, kws, SERP_TABS, terms, weighted=weighted, slots=depth)
            out["brand"][(depth, variant)] = spark([ours for _, ours, _ in points])
            out["campaign"][(depth, variant)] = spark([campaign for _, _, campaign in points])
    return out


def _stats(kws, summary, pairs, sparks, stored: int) -> list[str]:
    """스트립 네 칸. ②③(점유율)은 깊이 3 × 변형 2 = 6벌을 미리 그린다(§12.2).

    집계할 수 없는 조합(저장 범위 밖 깊이, 또는 브랜드 사전이 없어 `tot`이 None)은
    figure `—`, 캡션은 왜 없는지(`수집 범위 M위` / `브랜드 사전 필요`)를 적는다 —
    빈 값에 0%를 적어 "점유율 0%"로 읽히게 하지 않는다.
    """
    ranks = _rank_rows(summary)
    best = min((rank for rank, _, _ in ranks), default=None)
    best_kw = next(((kw, tab) for rank, kw, tab in ranks if rank == best), None) if best else None
    in_top10 = sum(1 for rank, _, _ in ranks if rank <= 10)
    slots = len(kws) * len(SERP_TABS) * share.SLOTS_PER_TAB
    no_terms = all(tot is None for _, tot in pairs.values())

    def tot_of(depth, variant):
        return pairs.get((depth, variant), (None, None))[1]

    def figure(key):
        return _depth_figure(lambda depth, variant: _pct(tot_of(depth, variant)[key]) if tot_of(depth, variant) else "—")

    def caption(available_text):
        """깊이·변형과 무관한 문구를 6벌로 심는다(카드 ③ `상위 10 진입 N`).

        같은 문자열이 여섯 번 들어가는 게 낭비로 보이지만, 정적 캡션 한 벌로 두면
        **저장 범위 밖 깊이에서 `수집 범위 M위`를 말할 자리가 없어진다** — figure는
        `—`인데 캡션은 `상위 10 진입 3`을 계속 띄워 "왜 값이 없는지"가 사라진다.
        6벌 기계장치(`_depth_delta`)를 카드 ②③이 같이 쓰는 편이 카드마다 다른
        규칙을 두는 것보다 싸다(리뷰 fix-1 항목 5).
        """
        return _depth_delta(
            lambda depth, variant: available_text if _depth_available(depth, stored) else f"수집 범위 {stored}위",
        )

    # 분모 단위는 변형마다 다르다(T8: 가중은 '슬롯'이 아니라 '점').
    brand_delta = (
        ui.delta("브랜드 사전 필요", "flat") if no_terms
        else _depth_delta(lambda depth, variant: _denominator_caption(tot_of(depth, variant), variant, depth, stored))
    )
    rank_side = ui.big_rank(best, f"{best_kw[0]} · {best_kw[1].replace('API', '')}") if best_kw else ui.spark_box("")
    return [
        ui.stat("추적 키워드", f"{len(kws)}<small>개 · {slots}슬롯</small>",
                views.spark_html(sparks["keywords"], "keywords"), ui.delta("블로그·카페 상위 10", "flat")),
        views._stat("브랜드 점유율", figure("ours_pct"),
                    views.spark_variants_html(sparks["brand"]), brand_delta),
        views._stat("캠페인 콘텐츠 점유율", figure("campaign_pct"),
                    views.spark_variants_html(sparks["campaign"]),
                    caption(f"상위 10 진입 {in_top10}")),
        ui.stat("상위 100위 내 노출", f"{len(ranks)}<small>건</small>", rank_side,
                ui.delta("최고 순위" if best else "아직 노출 없음", "flat")),
    ]


def _share_header(sub_html: str = "", right_html: str = "") -> str:
    # 목업 원문: 점유율 섹션 헤더는 .sec-h.reveal이 아니라 margin-top이 붙은 .sec-h다(R12).
    return views.sec_h("키워드 점유율", sub_html=sub_html, right_html=right_html, style="margin-top:32px")


def _share_body(ctx, terms, weighted: bool, pair, slots: int) -> str:
    """이미 계산한 (행, 합계)로 본문 한 벌 — 합계가 없으면(집계 대상 0건) 아무것도 넘기지 않는다.

    `share_section_html`은 `rows`·`tot`을 **둘 다 주거나 둘 다 생략**해야 한다(한쪽만
    주면 ValueError) — 넘긴 값과 여기서 다시 돌린 값이 섞이면 행 막대와 전체 스택이
    다른 집계를 그리기 때문이다. `_share_rows_and_total`은 집계 대상이 없을 때 합계를
    None으로 돌려주므로 그 경우엔 재계산 경로로 보낸다(결과는 예전과 같다).
    `slots`는 넘기는 (행, 합계)를 계산할 때 쓴 깊이와 같아야 한다 — 다르면 행 막대와
    섹션 안 추이 차트가 다른 깊이를 그린다.
    """
    rows, tot = pair
    if tot is None:
        return share_section_html(ctx, terms, weighted, slots=slots)
    return share_section_html(ctx, terms, weighted, rows=rows, tot=tot, slots=slots)


def _depth_empty_html(depth: int, stored: int) -> str:
    """저장 범위 밖 깊이 한 벌 — 변형 두 벌 대신 `.empty` **하나**다(고를 것이 없다, §12.1)."""
    return ui.empty_state(
        f"상위 {depth}위 점유율은 다음 수집부터 집계됩니다",
        f"현재 저장 범위 {stored}위 · 06:00 수집 후 표시",
    ).replace('<div class="empty">', f'<div class="empty" data-depth="{depth}" hidden>', 1)


def _share_section(ctx, terms, pairs, stored: int) -> str:
    """헤더 1개 + `.share-grid[data-depth][data-variant]` 최대 6벌. 계산이 불가능하면 `.empty` 한 벌.

    `pairs`는 (깊이, 변형) → `_share_rows_and_total`의 (행, 합계)다 — 본문이 같은 집계를
    다시 돌리지 않게 그대로 넘긴다(R11). 변형이 있는지 없는지는 `share_section_html`이
    실제로 돌려준 것으로 판단한다 — 빈 상태 조건(사전 없음·키워드 없음·우리 브랜드 없음)을
    여기서 다시 적으면 report_common과 갈라질 수 있다.

    저장 범위 밖 깊이는 `pairs`에 아예 없다 — 그 자리에는 `.empty` 한 벌이 들어가고
    범례도 만들지 않는다(브랜드 순서를 정할 근거가 없다).
    """
    base = share.SLOTS_PER_TAB
    slot_body = _share_body(ctx, terms, False, pairs[(base, "slot")], base)
    if not slot_body.startswith('<div class="share-grid">') or pairs[(base, "slot")][1] is None:
        # 빈 상태는 변형이 없으므로 범례·세그먼트를 붙이지 않는다(고를 것이 없다).
        return f'<section class="share enter" style="--i:2">{_share_header()}{slot_body}</section>'
    legends, bodies = [], []
    for i, depth in enumerate(share.DEPTHS):
        if not _depth_available(depth, stored):
            bodies.append(_depth_empty_html(depth, stored))
            continue
        tot = pairs[(depth, "slot")][1]
        hidden_legend = "" if i == 0 else " hidden"
        legends.append(
            f'<div class="legend" data-depth="{depth}"{hidden_legend}>'
            f'{share_legend_html(tot, tot["ours_brand"])}</div>'
        )
        for j, (variant, weighted) in enumerate(views.SHARE_VARIANTS):
            hidden = "" if i == 0 and j == 0 else " hidden"
            body = slot_body if (i, j) == (0, 0) else _share_body(ctx, terms, weighted, pairs[(depth, variant)], depth)
            bodies.append(body.replace(
                '<div class="share-grid">',
                f'<div class="share-grid" data-depth="{depth}" data-variant="{variant}"{hidden}>', 1,
            ))
    header = _share_header(
        sub_html=f'<span class="label">{_SHARE_SUB}</span>',
        right_html=f'{"".join(legends)}{_DEPTH_SEG}{_SHARE_SEG}',
    )
    return f'<section class="share enter" style="--i:2">{header}{"".join(bodies)}</section>'


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
