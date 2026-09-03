"""HTML 조각 빌더 — 목업 mix.css 클래스명 그대로. Streamlit에 의존하지 않는다."""
from __future__ import annotations

from html import escape as _escape

CHANNEL_LABEL = {"instagram": "인스타그램", "blog": "블로그", "cafe": "카페", "community": "커뮤니티", "youtube": "유튜브"}

# Simple Icons 경로(instagram·naver·youtube) — 목업 icons.js와 동일. 커뮤니티는 범용 말풍선.
CH_ICON_PATHS = {
    "instagram": "M7.0301.084c-1.2768.0602-2.1487.264-2.911.5634-.7888.3075-1.4575.72-2.1228 1.3877-.6652.6677-1.075 1.3368-1.3802 2.127-.2954.7638-.4956 1.6365-.552 2.914-.0564 1.2775-.0689 1.6882-.0626 4.947.0062 3.2586.0206 3.6671.0825 4.9473.061 1.2765.264 2.1482.5635 2.9107.308.7889.72 1.4573 1.388 2.1228.6679.6655 1.3365 1.0743 2.1285 1.38.7632.295 1.6361.4961 2.9134.552 1.2773.056 1.6884.069 4.9462.0627 3.2578-.0062 3.668-.0207 4.9478-.0814 1.28-.0607 2.147-.2652 2.9098-.5633.7889-.3086 1.4578-.72 2.1228-1.3881.665-.6682 1.0745-1.3378 1.3795-2.1284.2957-.7632.4966-1.636.552-2.9124.056-1.2809.0692-1.6898.063-4.948-.0063-3.2583-.021-3.6668-.0817-4.9465-.0607-1.2797-.264-2.1487-.5633-2.9117-.3084-.7889-.72-1.4568-1.3876-2.1228C21.2982 1.33 20.628.9208 19.8378.6165 19.074.321 18.2017.1197 16.9244.0645 15.6471.0093 15.236-.005 11.977.0014 8.718.0076 8.31.0215 7.0301.0839m.1402 21.6932c-1.17-.0509-1.8053-.2453-2.2287-.408-.5606-.216-.96-.4771-1.3819-.895-.422-.4178-.6811-.8186-.9-1.378-.1644-.4234-.3624-1.058-.4171-2.228-.0595-1.2645-.072-1.6442-.079-4.848-.007-3.2037.0053-3.583.0607-4.848.05-1.169.2456-1.805.408-2.2282.216-.5613.4762-.96.895-1.3816.4188-.4217.8184-.6814 1.3783-.9003.423-.1651 1.0575-.3614 2.227-.4171 1.2655-.06 1.6447-.072 4.848-.079 3.2033-.007 3.5835.005 4.8495.0608 1.169.0508 1.8053.2445 2.228.408.5608.216.96.4754 1.3816.895.4217.4194.6816.8176.9005 1.3787.1653.4217.3617 1.056.4169 2.2263.0602 1.2655.0739 1.645.0796 4.848.0058 3.203-.0055 3.5834-.061 4.848-.051 1.17-.245 1.8055-.408 2.2294-.216.5604-.4763.96-.8954 1.3814-.419.4215-.8181.6811-1.3783.9-.4224.1649-1.0577.3617-2.2262.4174-1.2656.0595-1.6448.072-4.8493.079-3.2045.007-3.5825-.006-4.848-.0608M16.953 5.5864A1.44 1.44 0 1 0 18.39 4.144a1.44 1.44 0 0 0-1.437 1.4424M5.8385 12.012c.0067 3.4032 2.7706 6.1557 6.173 6.1493 3.4026-.0065 6.157-2.7701 6.1506-6.1733-.0065-3.4032-2.771-6.1565-6.174-6.1498-3.403.0067-6.156 2.771-6.1496 6.1738M8 12.0077a4 4 0 1 1 4.008 3.9921A3.9996 3.9996 0 0 1 8 12.0077",
    "naver": "M16.273 12.845 7.376 0H0v24h7.726V11.156L16.624 24H24V0h-7.727v12.845Z",
    "youtube": "M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z",
    "community": "M4 4h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 4v-4H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
}
_ICON_MAP = {
    "instagram": ("instagram", "#E1306C", "인스타그램"), "cafe": ("naver", "#03C75A", "네이버 카페"),
    "blog": ("naver", "#03C75A", "네이버 블로그"), "youtube": ("youtube", "#FF0000", "유튜브"),
    "community": ("community", "currentColor", "커뮤니티"),
}


def esc(value) -> str:
    return _escape(str(value), quote=True)


def channel_icon(channel: str, size: int = 14) -> str:
    key, color, title = _ICON_MAP.get(channel, _ICON_MAP["community"])
    paint = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"' if key == "community" else f'fill="{color}"'
    return (
        f'<svg class="ch-ico" width="{size}" height="{size}" viewBox="0 0 24 24" role="img" aria-label="{title}">'
        f"<title>{title}</title><path d=\"{CH_ICON_PATHS[key]}\" {paint}/></svg>"
    )


def title_block(title: str, meta_html: str, controls_html: str = "") -> str:
    return (
        f'<section class="title enter" style="--i:0"><div><h1>{esc(title)}</h1><p>{meta_html}</p></div>'
        f'<div class="ctrl">{controls_html}</div></section>'
    )


def stat(label_html: str, value_html: str, side_html: str, delta_html: str) -> str:
    """label_html은 이스케이프하지 않는다 — 호출부 리터럴만 넘길 것(데이터 유래 문자열은 esc()로 감싸서)."""
    return (
        f'<div class="stat"><span class="label">{label_html}</span><span class="figure num">{value_html}</span>'
        f"{side_html}{delta_html}</div>"
    )


def stat_strip(stats: list[str]) -> str:
    return f'<section class="strip enter" style="--i:1">{"".join(stats)}</section>'


def spark_box(svg: str) -> str:
    return f'<div class="spark chart">{svg}</div>' if svg else '<div class="spark chart"></div>'


def big_rank(rank: int, caption: str) -> str:
    return f'<div class="big-rank"><b>{rank}위</b><span>{esc(caption)}</span></div>'


def delta(text: str, direction: str = "flat") -> str:
    return f'<span class="delta {direction}">{esc(text)}</span>'


def section_header(title: str, sub: str = "", right_html: str = "") -> str:
    sub_html = f'<span class="label">{esc(sub)}</span>' if sub else ""
    return f'<div class="sec-h reveal"><h2 class="h-sec">{esc(title)}</h2>{sub_html}<span class="sp"></span>{right_html}</div>'


def rank_badge(rank: int | None, none_text: str = "미노출") -> str:
    if rank is None:
        return f'<span class="rank none">{esc(none_text)}</span>'
    return f'<span class="rank acc">{rank}</span>'


def inline_bar(pct: float, color: str = "var(--ink)", width: int = 96) -> str:
    """color는 CSS style= 컨텍스트에 그대로 들어가므로 신뢰된 리터럴만 허용(외부 문자열 금지)."""
    pct = max(0, min(100, pct))
    return f'<span class="inline-bar grow" style="width:{width}px"><i style="width:{pct:g}%;background:{color}"></i></span>'


def channel_rows(distribution: dict[str, int], *, numerators: dict[str, int] | None = None, denominators: dict[str, int] | None = None) -> str:
    """channel key는 CSS style= 컨텍스트(var(--ch-<channel>))에 그대로 들어가므로 esc()로 감싼다
    (M4 — 외부 채널 문자열이 그대로 들어가면 style= 컨텍스트 주입이 된다).

    numerators/denominators를 주면(예: 채널별 네이버 노출 레일) 오른쪽 값과 막대 채움을
    "n / N"(노출 n건 / 전체 N건) 기준으로 그린다 — 안 주면(기본) 기존처럼 분포 비중(%)을 그린다.
    """
    rows = []
    if numerators is not None or denominators is not None:
        for ch, n in sorted(distribution.items(), key=lambda kv: -kv[1]):
            total = (denominators or {}).get(ch, n) or 0
            num = (numerators or {}).get(ch, 0)
            pct = round(num / total * 100) if total else 0
            rows.append(
                f'<div class="ch-row"><span class="n"><i class="dot" style="background:var(--ch-{esc(ch)})"></i>{esc(CHANNEL_LABEL.get(ch, ch))}</span>'
                f'<div class="hbar grow"><i style="width:{pct}%;background:var(--ch-{esc(ch)})"></i></div>'
                f'<span class="v num">{num}<small>/ {total}</small></span></div>'
            )
        return "".join(rows)
    total = sum(distribution.values()) or 1
    for ch, n in sorted(distribution.items(), key=lambda kv: -kv[1]):
        pct = round(n / total * 100)
        rows.append(
            f'<div class="ch-row"><span class="n"><i class="dot" style="background:var(--ch-{esc(ch)})"></i>{esc(CHANNEL_LABEL.get(ch, ch))}</span>'
            f'<div class="hbar grow"><i style="width:{pct}%;background:var(--ch-{esc(ch)})"></i></div>'
            f'<span class="v num">{n}<small>{pct}%</small></span></div>'
        )
    return "".join(rows)


def empty_state(title: str, hint: str) -> str:
    return f'<div class="empty"><b>{esc(title)}</b>{esc(hint)}</div>'


_R_CLASS = ' class="r"'  # Python 3.11 호환(I6) — f-string 표현식 안에 백슬래시 이스케이프를 못 넣으므로 상수로 뺐다.


def table_html(headers, rows, *, selected_index=None) -> str:
    th = "".join(f'<th{_R_CLASS if right else ""}>{esc(h)}</th>' for h, right in headers)
    body = []
    for i, cells in enumerate(rows):
        cls = ' class="is-sel"' if selected_index == i else ""
        tds = "".join(f'<td{_R_CLASS if right else ""}>{c}</td>' for c, (_, right) in zip(cells, headers))
        body.append(f"<tr{cls}>{tds}</tr>")
    return f'<table class="reveal"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def status(kind: str, label: str) -> str:
    return f'<span class="status {kind}"><i></i>{esc(label)}</span>'
