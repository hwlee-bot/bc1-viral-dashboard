"""리포트 iframe 본문 뷰(스펙 v4 §4). 페이지별 조립은 views.performance/summary/exposure에 있고,
이 모듈은 세 뷰가 공유하는 마크업 조각과 payload 시리즈 헬퍼만 갖는다.

`ui.py`의 컴포넌트와 겹치는 함수가 몇 개 있는 건 의도적이다 — iframe 런타임(JS)이
읽어야 하는 `data-*` 속성을 `ui.stat`·`ui.spark_box`·`ui.delta`가 받지 못하기 때문이고,
`ui.py`는 v3 페이지(등록·관리자)도 쓰므로 여기서 고치지 않는다. 마크업 자체는 ui의
같은 컴포넌트와 **문자 단위로 같아야 한다**(목업 CSS가 클래스에만 걸려 있으므로).
"""
from __future__ import annotations

from report_dashboard import ui
from report_dashboard.report_common import _content_rows, _row_participation_rate, plain_section_header
from report_dashboard.reporting import channel_distribution, delta_over_days

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


def strip_delta_html(dates: list[str], values: list[int], key: str = "") -> str:
    """스트립 델타 한 칸. `ui.delta`와 같은 마크업 + `data-delta`(JS 재계산 자리).

    7일 이상 떨어진 기준점이 없으면 `수집 N일차`(N = 관측 지점 수)로 정직하게 쓴다
    — runtime.js `deltaLabel`과 같은 문구여야 한다(스펙 §5).
    """
    change = delta_over_days(list(zip(dates, values)))
    if change is None:
        text, direction = f"수집 {len(dates)}일차", "flat"
    else:
        diff, span = change
        if diff > 0:
            text, direction = f"+{diff:,} · {span}d", "up"
        elif diff < 0:
            text, direction = f"{diff:,} · {span}d", "down"
        else:
            text, direction = f"변동 없음 · {span}d", "flat"
    attr = f' data-delta="{ui.esc(key)}"' if key else ""
    return f'<span class="delta {direction}"{attr}>{ui.esc(text)}</span>'


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
