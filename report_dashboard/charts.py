"""순수 SVG 생성기 — 목업 charts.js를 파이썬으로 옮긴 것. Streamlit에 의존하지 않는다.

스펙 §4.1: 선 2px, 끝점 r4.5(+표면색 2px 링은 CSS .end), 격자 헤어라인 3줄, 워시는 <g class="fade-late">로
감싸서 애니메이션이 path의 opacity 토큰을 덮지 않게 한다. 색은 전부 CSS 클래스(테마 토큰)로만 정한다.
"""
from __future__ import annotations

from html import escape


def path_length(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        total += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return total


def _points(values, width, height, pad_l, pad_r, pad_t, pad_b) -> list[tuple[float, float]]:
    vmin, vmax = min(values), max(values)
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    n = len(values)
    span = (vmax - vmin) or 1
    return [(pad_l + iw * i / (n - 1), pad_t + ih - (v - vmin) / span * ih) for i, v in enumerate(values)]


def _d(points) -> str:
    return " ".join(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}" for i, (x, y) in enumerate(points))


def _fmt(v: float) -> str:
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"


def area_chart_svg(values, *, labels=None, width=720, height=200, pad_right=60, ink=False) -> str:
    if len(values) < 2:
        return ""
    pad_l, pad_t = 8, 14
    pad_b = 26 if labels else 10
    pts = _points(values, width, height, pad_l, pad_right, pad_t, pad_b)
    base = height - pad_b
    d = _d(pts)
    wash = f"{d} L{pts[-1][0]:.1f} {base} L{pts[0][0]:.1f} {base} Z"
    length = round(path_length(pts))
    ink_cls = " ink" if ink else ""
    grid = "".join(
        f'<line class="grid-l" x1="{pad_l}" x2="{width - pad_right}" y1="{pad_t + (base - pad_t) * t:.1f}" y2="{pad_t + (base - pad_t) * t:.1f}"/>'
        for t in (0.0, 0.5, 1.0)
    )
    label_svg = ""
    if labels:
        n = len(values)
        step = max(1, round(n / 5))
        last = n - 1
        picked: list[tuple[int, str]] = []
        for i, text in enumerate(labels):
            if not text:
                continue
            if (i % step == 0 and last - i >= step) or i == last:
                # 하루에 여러 번 수집된 시리즈는 같은 날짜 라벨이 연달아 나온다
                # (배포 실측 "08.31 08.31 08.31 09.02") — 연속 중복은 뒤쪽 하나만 남긴다.
                if picked and picked[-1][1] == str(text):
                    picked[-1] = (i, str(text))
                else:
                    picked.append((i, str(text)))
        for i, text in picked:
            anchor = "end" if i == last else "middle"
            label_svg += f'<text class="axis-t" x="{pts[i][0]:.1f}" y="{height - 6}" text-anchor="{anchor}">{escape(text)}</text>'
    lx, ly = pts[-1]
    return (
        f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" style="aspect-ratio:{width}/{height}">'
        f"{grid}"
        f'<text class="axis-t" x="{width - pad_right + 8}" y="{pad_t + 4:.1f}">{_fmt(max(values))}</text>'
        f'<text class="axis-t" x="{width - pad_right + 8}" y="{base + 3:.1f}">{_fmt(min(values))}</text>'
        f'<g class="fade-late"><path class="wash" d="{wash}"/></g>'
        f'<path class="ln draw{ink_cls}" d="{d}" stroke-dasharray="{length}" stroke-dashoffset="{length}"/>'
        f'<circle class="end fade-late{ink_cls}" cx="{lx:.1f}" cy="{ly:.1f}" r="4.5"/>'
        f"{label_svg}</svg>"
    )


def sparkline_svg(values, *, width=112, height=30, ink=True) -> str:
    if len(values) < 2:
        return ""
    pts = _points(values, width, height, 2, 6, 4, 4)
    d = _d(pts)
    length = round(path_length(pts))
    ink_cls = " ink" if ink else ""
    lx, ly = pts[-1]
    return (
        f'<svg viewBox="0 0 {width} {height}" style="aspect-ratio:{width}/{height}">'
        f'<path class="ln draw{ink_cls}" d="{d}" stroke-dasharray="{length}" stroke-dashoffset="{length}"/>'
        f'<circle class="end fade-late{ink_cls}" cx="{lx:.1f}" cy="{ly:.1f}" r="4"/></svg>'
    )


def rank_chart_svg(ranks, *, width=150, height=54) -> str:
    """위가 1위. 현재 순위 높이에 가이드 헤어라인 + 끝 라벨 'N위'."""
    if len(ranks) < 2:
        return ""
    pts = _points([-r for r in ranks], width, height, 4, 34, 8, 8)
    d = _d(pts)
    length = round(path_length(pts))
    lx, ly = pts[-1]
    return (
        f'<svg viewBox="0 0 {width} {height}" style="aspect-ratio:{width}/{height}">'
        f'<line class="grid-l" x1="4" x2="{width - 34}" y1="{ly:.1f}" y2="{ly:.1f}"/>'
        f'<path class="ln draw" d="{d}" stroke-dasharray="{length}" stroke-dashoffset="{length}"/>'
        f'<circle class="end fade-late" cx="{lx:.1f}" cy="{ly:.1f}" r="4.5"/>'
        f'<text class="lbl" x="{lx + 10:.1f}" y="{ly + 4:.1f}">{escape(str(ranks[-1]))}위</text></svg>'
    )


def stack_bar_html(segments, *, ours_index=None, height=12) -> str:
    """점유율 스택바. segments=[(css_color, pct)]. 갭 2px은 CSS .stack{gap:2px}."""
    parts = []
    for i, (color, pct) in enumerate(segments):
        if pct <= 0:
            continue
        cls = ' class="ours"' if ours_index == i else ""
        parts.append(f'<i{cls} style="width:{pct:g}%;background:{escape(str(color))}"></i>')
    return f'<div class="stack grow" style="height:{height}px">{"".join(parts)}</div>'
