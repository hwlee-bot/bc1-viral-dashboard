"""리포트 iframe 본문 뷰(스펙 v4 §4). 페이지별 조립은 views.performance/summary/exposure에 있고,
이 모듈은 세 뷰가 공유하는 마크업 조각과 payload 시리즈 헬퍼만 갖는다.

`ui.py`의 컴포넌트와 겹치는 함수가 몇 개 있는 건 의도적이다 — iframe 런타임(JS)이
읽어야 하는 `data-*` 속성을 `ui.stat`·`ui.spark_box`·`ui.delta`가 받지 못하기 때문이고,
`ui.py`는 v3 페이지(등록·관리자)도 쓰므로 여기서 고치지 않는다. 마크업 자체는 ui의
같은 컴포넌트와 **문자 단위로 같아야 한다**(목업 CSS가 클래스에만 걸려 있으므로).
"""
from __future__ import annotations

from report_dashboard import charts, share, ui
from report_dashboard.report_common import _content_rows, _row_participation_rate, plain_section_header
from report_dashboard.reporting import channel_distribution, delta_over_days, participation_rate

# 평문 `.sec-h` 헤더(R12) — 세 뷰가 `views.sec_h(...)`로 쓴다. 정의가 report_common에
# 있는 건 순환 import 때문이다(`report_common.watchlist_html`·`impact_block_html`도 같은
# 헤더를 쓰는데, views가 report_common을 import하므로 반대 방향은 순환이 된다).
sec_h = plain_section_header


def _stat(label_html: str, figure_html: str, side_html: str = "", delta_html: str = "") -> str:
    """`ui.stat`과 같은 마크업이지만 figure span을 호출부가 통째로 넘긴다 —
    스트립 figure에는 `data-stat`이 붙어야 하고 ui.stat은 값 문자열만 받는다."""
    return f'<div class="stat"><span class="label">{label_html}</span>{figure_html}{side_html}{delta_html}</div>'


def stat_figure(key: str, value_html: str) -> str:
    return f'<span class="figure num" data-stat="{ui.esc(key)}">{value_html}</span>'


def spark_html(svg: str = "", key: str = "") -> str:
    """`ui.spark_box`와 같은 마크업 + `data-spark`(JS가 시리즈 합으로 다시 그릴 자리)."""
    attr = f' data-spark="{ui.esc(key)}"' if key else ""
    return f'<div class="spark chart"{attr}>{svg}</div>'


SHARE_VARIANTS = (("slot", False), ("weighted", True))   # (`data-variant` 값, weighted 플래그)


def depth_variant_cells(render, *, depths=share.DEPTHS) -> str:
    """깊이 × 변형 조합마다 `render(depth, variant, hidden_attr)`을 부르고 이어 붙인다(§12.2).

    첫 조합(가장 얕은 깊이 · 슬롯)만 보이고 나머지는 `hidden`이다 — 초기 화면이
    `runtime.js`의 기본 상태(`depth="10"`, `variant="slot"`)와 어긋나지 않게 하는 정본이다.
    """
    out = []
    for i, depth in enumerate(depths):
        for j, (variant, _) in enumerate(SHARE_VARIANTS):
            out.append(render(depth, variant, "" if i == 0 and j == 0 else " hidden"))
    return "".join(out)


def spark_variants_html(svg_of, *, depths=share.DEPTHS) -> str:
    """점유율 카드의 스파크 6벌(깊이 3 × 슬롯·가중) — JS가 `[data-depth]`·`[data-spark-variant]`로 하나만 보여준다(§11.3·§12.2).

    `svg_of`는 `(depth, variant) -> svg` 매핑(dict)이다. 집계할 수 없는 조합은 빈 문자열을
    주면 빈 스파크 칸이 남는다 — 1점짜리 시리즈나 없는 깊이를 직선으로 그려 "추세"처럼
    보이게 하지 않는다(v3 §8 정직성 규칙).

    figure·delta의 `[data-variant]`와 같은 규칙이지만 셀렉터를 나눈 이유는, 점유율 세그먼트
    토글이 `.spark`를 `[data-variant]`로 잡으면 `.share-grid[data-variant]`·figure span과
    한 덩어리로 묶여 "스파크만 다른 규칙(빈 칸이면 아예 안 그림)"을 표현할 수 없기 때문이다.
    """
    return depth_variant_cells(
        lambda depth, variant, hidden: (
            f'<div class="spark chart" data-depth="{depth}" data-spark-variant="{variant}"{hidden}>'
            f'{svg_of.get((depth, variant), "")}</div>'
        ),
        depths=depths,
    )


def channel_counts(contents: list[dict], allowed: list[str] | None = None) -> list[tuple[str, int]]:
    """채널별 콘텐츠 건수를 건수 내림차순·채널명 오름차순으로. 채널 칩·메타 문구의 단일 정본.

    같은 순서를 칩(§4.1)과 제목 메타(§4.4)가 함께 써야 "칩 순서와 메타 순서가 다르다"가 생기지 않는다.
    """
    pool = contents if allowed is None else [c for c in contents if c["channel"] in allowed]
    return sorted(channel_distribution(pool).items(), key=lambda kv: (-kv[1], kv[0]))


def channel_rows_with_data(distribution: dict[str, int]) -> str:
    """채널 분포 `.ch-row[data-ch][data-n]` 행들 — 마크업은 `ui.channel_rows`와 같고 속성만 더한다.

    JS가 꺼진 채널 행을 숨기고 남은 행 기준으로 pct·hbar 폭을 다시 계산하려면
    채널과 건수가 속성으로 있어야 한다(스펙 §4.2). `ui.channel_rows`는 v3 페이지도
    쓰는 공용 컴포넌트라 손대지 않고 여기서 같은 구조를 그린다.
    """
    total = sum(distribution.values()) or 1
    rows = []
    # 동률(건수가 같은 채널)에서 순서가 흔들리지 않게 `channel_counts`·`channel_chips_html`과
    # 같은 키로 정렬한다 — 칩 순서와 분포 행 순서가 달라 보이면 안 된다(R10).
    for channel, n in sorted(distribution.items(), key=lambda kv: (-kv[1], kv[0])):
        pct = round(n / total * 100)
        ch = ui.esc(channel)
        rows.append(
            f'<div class="ch-row" data-ch="{ch}" data-n="{n}"><span class="n">'
            f'<i class="dot" style="background:var(--ch-{ch})"></i>{ui.esc(ui.CHANNEL_LABEL.get(channel, channel))}</span>'
            f'<div class="hbar grow"><i style="width:{pct}%;background:var(--ch-{ch})"></i></div>'
            f'<span class="v num">{n}<small>{pct}%</small></span></div>'
        )
    return "".join(rows)


def channel_chips_html(contents: list[dict], channels_allowed: list[str] | None = None) -> str:
    """콘텐츠가 있는 채널만, 건수 내림차순, 전부 `.on`으로 시작(스펙 §4.1).

    JS가 마지막 하나는 끌 수 없게 막으므로 서버는 "전부 켜짐" 한 가지 상태만 그린다.
    """
    chips = []
    for channel, n in channel_counts(contents, channels_allowed):
        label = ui.CHANNEL_LABEL.get(channel, channel)
        chips.append(
            f'<span class="chip on" data-ch="{ui.esc(channel)}">'
            f'<i class="dot" style="background:var(--ch-{ui.esc(channel)})"></i>{ui.esc(label)} {n}</span>'
        )
    return "".join(chips)


def export_btn_html(has_md: bool) -> str:
    if has_md:
        return '<span class="btn" data-export>내보내기</span>'
    return '<span class="btn ghost" data-export aria-disabled="true">내보내기</span>'


def strip_delta_html(dates: list[str], values: list, key: str = "", unit: str = "", extra_attrs: str = "") -> str:
    """스트립 델타 한 칸. `ui.delta`와 같은 마크업 + `data-delta`(JS 재계산 자리).

    7일 이상 떨어진 기준점이 없으면 `수집 N일차`(N = 관측 지점 수)로 정직하게 쓴다
    — runtime.js `deltaLabel`과 같은 문구여야 한다(스펙 §5).

    `unit="pt"`는 퍼센트 시리즈(평균 참여율)용이다(§11.3) — 퍼센트의 증감은 퍼센트가
    아니라 **퍼센트포인트**이므로 `+2.9pt · 7d`로 쓰고 소수 1자리로 반올림한다.
    반올림 뒤 0이면 `변동 없음`으로 간다(0.04pt를 `+0.0pt`로 쓰지 않는다).
    """
    change = delta_over_days(list(zip(dates, values)))
    if change is None:
        text, direction = f"수집 {len(dates)}일차", "flat"
    else:
        diff, span = change
        if unit == "pt":
            diff = round(diff, 1)
            body = f"{diff:+.1f}pt"
        else:
            body = f"{diff:+,}"
        if diff > 0:
            text, direction = f"{body} · {span}d", "up"
        elif diff < 0:
            text, direction = f"{body} · {span}d", "down"
        else:
            text, direction = f"변동 없음 · {span}d", "flat"
    attr = f' data-delta="{ui.esc(key)}"' if key else ""
    return f'<span class="delta {direction}"{attr}{extra_attrs}>{ui.esc(text)}</span>'


def series_points(series: dict) -> list[tuple[str, int]]:
    """payload 시리즈(`{dates, by_channel}`)의 전 채널 합 — 초기 상태(칩 전부 켜짐)의 근거.

    JS `RT.combineSeries(dates, by_channel, 전체 채널)`과 같은 값이어야 한다 — 다르면
    로드 직후 첫 `applyState()`가 서버가 그린 스파크·델타를 다른 숫자로 갈아버린다.
    """
    dates, by_channel = series["dates"], series["by_channel"]
    return [(day, sum(values[i] for values in by_channel.values())) for i, day in enumerate(dates)]


def strip_card(label_html: str, key: str, figure_html: str, points, static_caption: str, *, unit: str = "") -> str:
    """스파크 + 델타를 실측 시리즈로 채운 스트립 카드(§11.3).

    `points`는 (날짜, 값) 리스트다. 2점 이상이면 스파크(112×30 ink)와 `delta_over_days`
    델타를, 아니면 **빈 스파크 칸 + 정적 캡션**을 쓴다(v3 §8 정직성 규칙) — 1점짜리
    시리즈를 직선으로 그려 "추세"처럼 보이게 하지 않는다. `data-spark`·`data-delta`
    자리는 어느 쪽이든 남겨서 JS가 채널 필터 뒤 다시 그릴 수 있게 한다.

    스파크가 있는 카드 **여섯 칸 전부**가 이 함수를 지난다(리뷰 5) — 손으로 조립한
    `spark_html(sparkline_svg(...)) + strip_delta_html(...)` 쌍을 남겨두면 그 카드만
    `data-static`이 없어 JS가 되돌릴 문구를 못 찾는다.
    """
    dates = [day for day, _ in points]
    values = [value for _, value in points]
    # `data-static`은 JS가 되돌릴 캡션이다 — 채널을 꺼서 시리즈가 2점 미만으로 줄면
    # runtime.js가 이 문구로 되돌린다(같은 한국어 문구를 JS에 또 적지 않기 위한 장치).
    static_attr = f' data-static="{ui.esc(static_caption)}"'
    if len(values) >= 2:
        spark = spark_html(charts.sparkline_svg(values, width=112, height=30, ink=True), key)
        delta = strip_delta_html(dates, values, key, unit=unit, extra_attrs=static_attr)
    else:
        spark = spark_html("", key)
        delta = f'<span class="delta flat" data-delta="{ui.esc(key)}"{static_attr}>{ui.esc(static_caption)}</span>'
    return _stat(label_html, figure_html, spark, delta)


def series_by_channel(dates_union: list[str], per_channel: dict[str, list[tuple[str, int]]]) -> dict[str, list[int]]:
    """채널별 (날짜, 값) 관측을 날짜 합집합 길이에 맞춰 정렬한다(스펙 §4.2).

    관측이 없는 날은 직전 값을 유지하고, 첫 관측 전은 0이다 — 이렇게 해야
    선택 채널 합(JS `combineSeries`)이 `daily_view_series(filtered)`와 정확히 같다.
    """
    out: dict[str, list[int]] = {}
    for channel, points in per_channel.items():
        by_date = dict(points)
        values, last = [], 0
        for day in dates_union:
            if day in by_date:
                last = by_date[day]
            values.append(last)
        out[channel] = values
    return out


def payload_series(per_channel: dict[str, list[tuple[str, int]]]) -> dict:
    dates = sorted({day for points in per_channel.values() for day, _ in points})
    return {"dates": dates, "by_channel": series_by_channel(dates, per_channel)}


def daily_sum_of_latest(per_content_series: list[list[tuple[str, int]]]) -> list[tuple[str, int]]:
    """콘텐츠별 (관측시각, 값) 시리즈들을 날짜별 "그날까지 최신값의 합"으로 합친다.

    `daily_view_series`가 조회수에 쓰는 규칙과 같다 — 좋아요(인스타)는 콘텐츠마다
    관측일이 달라서 단순 날짜별 합계로는 아직 관측 안 된 콘텐츠가 0으로 빠져
    곡선이 내려간다. 입력 시리즈는 시간 오름차순이어야 한다(likes_history 출력).
    """
    days = sorted({moment[:10] for series in per_content_series for moment, _ in series})
    out = []
    for day in days:
        total = 0
        for series in per_content_series:
            upto = [value for moment, value in series if moment[:10] <= day]
            if upto:
                total += upto[-1]
        out.append((day, total))
    return out


def avg_row_rate(ctx) -> float | None:
    """스트립 '평균 참여율' — 행의 `data-rate`를 만드는 것과 **같은** 계산의 평균(R5).

    `reporting.average_participation_rate`는 콘텐츠의 최신 조회수 행만 보므로
    인스타 콘텐츠에 수동 조회수 행이 있으면 행 표(`_row_participation_rate`)와
    값이 갈린다 — 그러면 JS가 `data-rate`로 다시 계산한 초기값이 Python이 그린
    숫자와 달라진다. 여기서는 행과 같은 함수를 쓴다.
    """
    rates = [
        rate for rate in (_row_participation_rate(ctx, content, pv) for content, pv, *_ in _content_rows(ctx))
        if rate is not None
    ]
    return round(sum(rates) / len(rates), 1) if rates else None


# ---------------------------------------------------------------------------
# §11.3 상단 카드 스파크용 실측 시리즈. 전부 "그날까지의 누적"이라 `series_by_channel`의
# 직전값 유지 규칙과 맞물려 선택 채널 합(JS `combineSeries`)이 그대로 정답이 된다.
# 예시 데이터는 만들지 않는다 — 관측이 없으면 빈 시리즈를 돌려주고 호출부가 빈 칸을 그린다.
# ---------------------------------------------------------------------------

def _cumulative(per_channel_days: dict[str, dict[str, int]]) -> dict[str, list[tuple[str, int]]]:
    """{채널: {날짜: 그날 발생 건수}} → {채널: [(날짜, 누적 건수)]}(날짜 오름차순)."""
    out: dict[str, list[tuple[str, int]]] = {}
    for channel, counts in per_channel_days.items():
        total, points = 0, []
        for day in sorted(counts):
            total += counts[day]
            points.append((day, total))
        out[channel] = points
    return out


def _day_of(row: dict, *fields: str) -> str:
    """첫 번째로 값이 있는 날짜 필드의 `YYYY-MM-DD`. 전부 비면 빈 문자열."""
    for field in fields:
        value = row.get(field)
        if value:
            return str(value)[:10]
    return ""


def contents_count_series(contents: list[dict]) -> dict[str, list[tuple[str, int]]]:
    """채널별 (날짜, 누적 콘텐츠 수) — `release_at` 기준, 없으면 `created_at`(§11.3).

    두 필드가 다 비어 있는 콘텐츠는 **어느 날짜에도 넣지 않는다** — 등록일을 모르는
    콘텐츠를 첫날로 밀어 넣으면 곡선이 실제보다 일찍 시작한 것처럼 보인다.
    """
    per: dict[str, dict[str, int]] = {}
    for content in contents:
        day = _day_of(content, "release_at", "created_at")
        if not day:
            continue
        bucket = per.setdefault(content["channel"], {})
        bucket[day] = bucket.get(day, 0) + 1
    return _cumulative(per)


def comments_count_series(comments: list[dict], contents_by_id: dict[str, dict]) -> dict[str, list[tuple[str, int]]]:
    """채널별 (날짜, 누적 댓글 수) — `commented_at` 기준, 채널은 그 댓글이 달린 콘텐츠의 채널(§11.3)."""
    per: dict[str, dict[str, int]] = {}
    for comment in comments:
        day = _day_of(comment, "commented_at")
        channel = (contents_by_id.get(comment.get("content_id")) or {}).get("channel")
        if not day or not channel:
            continue
        bucket = per.setdefault(channel, {})
        bucket[day] = bucket.get(day, 0) + 1
    return _cumulative(per)


def keyword_count_series(target_keyword_rows: list[dict]) -> list[tuple[str, int]]:
    """(날짜, 누적 추적 키워드 수) — `created_at` 기준. 채널 필터와 무관해 채널 구분이 없다(§11.3).

    보통 키워드를 하루에 다 등록하므로 1점이 나오고, 그러면 호출부가 스파크를 안 그린다.
    """
    counts: dict[str, int] = {}
    for row in target_keyword_rows:
        day = _day_of(row, "created_at")
        if not day:
            continue
        counts[day] = counts.get(day, 0) + 1
    return _cumulative({"_": counts})["_"] if counts else []


def rate_series(ctx) -> dict:
    """`{"dates": [...], "by_channel": {채널: {"sum": [...], "n": [...]}}}` (§11.3).

    날짜마다 비인스타 콘텐츠별로 "그날까지 최신 non-auto_instagram 지표 행"을 찾아
    `participation_rate(views, comments_count)`를 구하고, 계산되는 것만 채널별 합·개수에
    넣는다. 평균을 미리 내지 않고 (합, 개수)를 보내는 이유는 채널을 껐다 켤 때 JS가
    `Σsum/Σn`으로 다시 평균할 수 있어야 하기 때문이다 — 채널별 평균의 평균은 틀린다.

    날짜 축은 `view_metrics`의 관측일 합집합이다(참여율은 조회수 관측 시점에만 갱신된다).
    """
    dates = sorted({m["captured_at"][:10] for m in ctx["view_metrics"]})
    tracked = [c for c in ctx["contents"] if c["channel"] != "instagram"]
    per_content = []
    for content in tracked:
        cid = content["content_id"]
        rows = sorted(
            (m for m in ctx["all_metrics"] if m["content_id"] == cid and m.get("source") != "auto_instagram"),
            key=lambda m: m["captured_at"],
        )
        per_content.append((content["channel"], rows))
    by_channel = {channel: {"sum": [], "n": []} for channel in sorted({c["channel"] for c in tracked})}
    for day in dates:
        acc = {channel: [0.0, 0] for channel in by_channel}
        for channel, rows in per_content:
            upto = [r for r in rows if r["captured_at"][:10] <= day]
            if not upto:
                continue
            rate = participation_rate(upto[-1].get("views") or 0, upto[-1].get("comments_count"))
            if rate is None:
                continue
            acc[channel][0] += rate
            acc[channel][1] += 1
        for channel in by_channel:
            by_channel[channel]["sum"].append(round(acc[channel][0], 3))
            by_channel[channel]["n"].append(acc[channel][1])
    return {"dates": dates, "by_channel": by_channel}


def rate_points(dates: list[str], by_channel: dict[str, dict], on) -> list[tuple[str, float]]:
    """선택 채널의 `Σsum/Σn`(소수 1자리). 그날 대상이 0건이면 그 날짜는 **빼버린다**.

    runtime.js `RT.combineRate`와 글자 그대로 같은 규칙이어야 한다(스펙 §5의 패리티 규칙) —
    0건인 날을 0%로 채우면 아직 참여율을 계산할 수 없던 날이 "참여율 0%"로 보인다.
    """
    selected = [channel for channel in by_channel if channel in on]
    out = []
    for i, day in enumerate(dates):
        n = sum(by_channel[channel]["n"][i] for channel in selected)
        if not n:
            continue
        total = sum(by_channel[channel]["sum"][i] for channel in selected)
        out.append((day, round(total / n, 1)))
    return out


def share_trend_points(
    serp_rows, keywords, tabs, terms, *, weighted: bool = False, last_n: int = 15,
    slots: int = share.SLOTS_PER_TAB,
) -> list[tuple[str, float, float]]:
    """수집 배치별 (captured_at, 브랜드 점유율, 캠페인 콘텐츠 점유율) — 슬롯/가중 두 벌용(§11.3).

    `share.share_trend`에는 가중 플래그도 캠페인 점유율도 없어서(슬롯 기준 브랜드
    점유율만 돌려준다) 배치를 직접 갈라 `keyword_share_rows`+`total_share`를 배치마다
    돌린다 — 스트립의 "지금 값"과 정확히 같은 집계를 시간축으로 늘린 것이다.

    `last_n`(마지막 15배치)도 `share.share_trend`와 같아야 한다 — 창이 다르면 스트립
    스파크와 점유율 섹션의 추이 차트가 **같은 지표를 다른 곡선으로** 보여준다.
    슬롯 기준 브랜드 점유율은 `share.share_trend`와 같은 값이어야 한다(테스트로 고정).

    `slots`(깊이)도 마찬가지다 — 창은 `share.trend_batches`가 정본이라 깊이가 10보다
    깊으면 `stored_depth < slots`인 옛 배치가 두 경로에서 똑같이 빠진다(§12.1).
    """
    ours = share.ours_brand_of(terms)
    out = []
    for at in share.trend_batches(serp_rows, keywords, tabs, last_n=last_n, slots=slots):
        batch = [r for r in serp_rows if r["captured_at"] == at]
        rows = share.keyword_share_rows(batch, keywords, tabs, terms, weighted=weighted, slots=slots)
        total = share.total_share(rows, ours)
        out.append((at, total["ours_pct"], total["campaign_pct"]))
    return out
