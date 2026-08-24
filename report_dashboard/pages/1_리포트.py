"""캠페인·콘텐츠별 조회수·네이버 순위 추이를 보는 화면. 읽기 전용 — 등록은 2_등록.py에서.

조회수 추이는 실측값만 연결해서 그린다. 데이터가 없는 미래 구간에
점선으로 "추세(예시)"를 지어내 그리지 않는다 — 목표 대비 진행률은
별도 진행률바로 보여주므로, 예측 없이도 요구사항은 채워진다.

디자인은 project/active/20260820_바이럴성과-리포팅-대시보드/report-design-mockup.html
(v4.1)을 이 페이지에 실제로 반영한 것이다. 다만 두 가지는 옮기지 않았다:
- 종합 KPI 3개 타일(등록콘텐츠/평균목표진행률/네이버상위노출) — 브레인스토밍 때
  이미 "종합 지표는 채널별 상위노출 수 하나만 두고 나머지는 콘텐츠 카드로 본다"고
  정한 결정(context.md)과 충돌해서 뺐다. 필요하면 별도로 다시 요청.
- 스크롤 진입 모션·숫자 카운트업(IntersectionObserver 기반 JS) — Streamlit의
  st.markdown(unsafe_allow_html=True)은 보안상 <script> 태그를 실행하지 않는다
  (st.components.v1.html로 iframe에 넣으면 되지만, 그러면 그 iframe은 바깥 페이지의
  스크롤을 못 보므로 "스크롤하면 뜨는" 효과 자체가 안 된다). 대신 카드 호버는
  순수 CSS :hover라 그대로 살렸다.
- 다크모드도 이번엔 안 옮겼다 — Streamlit 1.58은 라이트/다크를 CSS 커스텀 프로퍼티로
  안 노출해서(직접 확인함) prefers-color-scheme로 우리 CSS만 어둡게 하면 Streamlit
  자체 크롬과 어긋날 수 있다. 필요하면 .streamlit/config.toml의 [theme] base="dark"로
  앱 전체를 다크로 고정하고 우리 토큰도 다크값으로 맞추는 별도 작업으로.
"""

import html as html_lib

# Streamlit Cloud는 실행할 스크립트가 있는 폴더만 sys.path에 넣는다(공식 소스
# streamlit/web/bootstrap.py::_fix_sys_path 확인함) — 저장소 루트는 안 들어간다.
# 로컬은 `python3 -m streamlit run`(-m이 CWD를 넣어줌)이나 pytest(패키지 루트를
# 자동 추가)가 이 문제를 가려서 배포 전엔 안 드러났다. report_dashboard.* 절대
# 임포트가 되려면 저장소 루트가 필요하므로 여기서 직접 넣는다.
import os
import sys

_here = os.path.abspath(__file__)
_repo_root = _here[: _here.index(os.sep + "report_dashboard" + os.sep)]
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import streamlit as st

from report_dashboard.auth import require_role
from report_dashboard.repo import ReportRepo
from report_dashboard.reporting import (
    build_export_markdown, exposure_counts_by_channel, latest_views, target_progress_pct,
)

# 게이트를 이 파일에서도 호출한다 — app.py의 라우터 게이트에만 의존하면 안 된다.
# Streamlit의 PagesManager.uses_pages_directory는 프로세스 전역 클래스 속성이고,
# pages/ 디렉토리가 존재하므로 True로 시작한다. 그 플래그는 사용자 코드가 실제로
# st.navigation을 실행하는 순간에만 False로 바뀌는데, app.py는 그 앞에서
# require_role()을 호출하고 미인증 방문자는 전부 st.stop()으로 끝난다. 따라서
# 미인증 트래픽만 들어오는 동안(배포·재부팅·슬립 해제 직후)에는 플래그가 True로
# 남아 Streamlit이 app.py 대신 이 페이지 파일을 직접 실행한다 — 라우터 게이트가
# 아예 돌지 않는다. 실제 서버에서 익명 세션으로 재현 확인함.
# 그래서 각 페이지가 스스로 안전해야 한다.
role, email = require_role()

CHANNELS = ["youtube", "blog", "cafe", "community", "instagram"]

_CHANNEL_ICON = {
    "blog": "naver", "cafe": "naver", "youtube": "youtube",
    "instagram": "instagram", "community": "community",
}
_ACCURACY_CHIP_CLASS = {"실측": "measured", "추정": "estimated", "미취득": "pending", "불가": "impossible"}


def _esc(value) -> str:
    return html_lib.escape(str(value))


_STYLE_AND_ICONS = """
<style>
:root {
  --vr-page: #f9f9f7;
  --vr-surface: #ffffff;
  --vr-ink: #0b0b0b;
  --vr-ink-2: #52514e;
  --vr-ink-muted: #898781;
  --vr-hairline: #e1e0d9;
  --vr-border: rgba(11,11,11,0.10);
  --vr-border-strong: rgba(11,11,11,0.14);
  --vr-accent: #2a78d6;
  --vr-accent-bright: #6da7ec;
  --vr-accent-soft: #eaf1fb;
  --vr-accent-wash: rgba(42,120,214,0.08);
  --vr-good: #0ca30c;
  --vr-good-soft: #e6f6e6;
  --vr-warning: #b9790a;
  --vr-warning-soft: #fdf0d9;
  --vr-critical: #d03b3b;
  --vr-critical-soft: #fbe8e8;
  --vr-radius: 12px;
  --vr-ease: cubic-bezier(0.16, 1, 0.3, 1);
  --vr-font-display: "Gothic A1", -apple-system, "Apple SD Gothic Neo", sans-serif;
}
@import url('https://fonts.googleapis.com/css2?family=Gothic+A1:wght@700;800;900&display=swap');

[data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 {
  font-family: var(--vr-font-display) !important;
  font-weight: 800 !important;
  letter-spacing: -0.01em;
}
[data-testid="stCaptionContainer"] p { color: var(--vr-ink-muted) !important; }

/* -- 채널별 상위노출 랭크 리스트 --------------------------------------- */
.vr-rank-list { display:flex; flex-direction:column; gap:14px; margin: 4px 0 8px; }
.vr-rank-item { display:grid; grid-template-columns: 32px 92px 1fr auto; align-items:center; gap:12px; }
.vr-rank-ordinal { font-family: var(--vr-font-display); font-size:13px; font-weight:800; color:var(--vr-ink-muted); text-align:center; font-variant-numeric: tabular-nums; }
.vr-rank-item--top .vr-rank-ordinal { color: var(--vr-accent); }
.vr-rank-chan { display:flex; align-items:center; gap:7px; }
.vr-channel-badge { display:flex; align-items:center; justify-content:center; width:26px; height:26px; border-radius:7px; background:var(--vr-surface); border:1px solid var(--vr-border); flex:none; }
.vr-channel-badge svg { width:15px; height:15px; display:block; }
.vr-channel-badge--lg { width:38px; height:38px; border-radius:10px; }
.vr-channel-badge--lg svg { width:21px; height:21px; }
.vr-rank-chan-name { font-size:12.5px; color:var(--vr-ink-2); white-space:nowrap; }
.vr-rank-track { position:relative; height:10px; background:var(--vr-accent-soft); border-radius:999px; overflow:hidden; }
.vr-rank-fill { position:absolute; inset:0; border-radius:999px; background:linear-gradient(90deg, var(--vr-accent), var(--vr-accent-bright)); }
.vr-rank-item--top .vr-rank-fill { box-shadow: 0 0 0 1px var(--vr-accent-wash) inset; }
.vr-rank-figures { display:flex; align-items:baseline; gap:5px; justify-content:flex-end; min-width:74px; }
.vr-rank-value { font-size:17px; font-weight:700; color:var(--vr-ink); font-variant-numeric: tabular-nums; }
.vr-rank-unit { font-size:11px; color:var(--vr-ink-muted); }
.vr-rank-share { font-size:10.5px; color:var(--vr-ink-muted); text-align:right; margin-top:2px; grid-column:4; font-variant-numeric: tabular-nums; }

/* -- 콘텐츠 카드: marker로 이 카드의 stVerticalBlock만 스코프해서 강화 ---- */
.vr-card-marker { display:none; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-card-marker) {
  border-radius: var(--vr-radius) !important;
  border-color: var(--vr-border-strong) !important;
  overflow: hidden;
  transition: transform 0.2s var(--vr-ease), border-color 0.2s var(--vr-ease), box-shadow 0.2s var(--vr-ease);
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-card-marker):hover {
  transform: translateY(-2px);
  border-color: var(--vr-accent) !important;
  box-shadow: 0 14px 28px -14px var(--vr-accent-wash);
}
.vr-card-band {
  display:flex; align-items:center; gap:12px;
  margin: -15px -15px 8px -15px; padding: 14px 15px;
  background: var(--vr-page); border-bottom: 1px solid var(--vr-hairline);
  border-radius: var(--vr-radius) var(--vr-radius) 0 0;
}
.vr-card-title { font-family: var(--vr-font-display); font-size:16px; font-weight:700; line-height:1.35; color: var(--vr-ink); }
.vr-card-date { font-size:11.5px; color:var(--vr-ink-muted); margin-top:2px; }

/* -- 스파크라인 + 스탯캡슐 --------------------------------------------- */
.vr-chart-row { display:flex; gap:14px; align-items:stretch; margin: 0 2px 4px; }
.vr-sparkline { flex:1 1 auto; min-width: 0; }
.vr-sparkline svg { display:block; width:100%; height:76px; }
.vr-gridline { stroke: var(--vr-hairline); stroke-width:1; }
.vr-spark-area { fill: url(#vr-grad-area); }
.vr-spark-line { fill:none; stroke: url(#vr-grad-line); stroke-width:3; stroke-linecap:round; stroke-linejoin:round; }
.vr-spark-dot { fill: var(--vr-accent-bright); stroke: var(--vr-surface); stroke-width:2.5; }
.vr-stat-capsule { flex:none; min-width:92px; display:flex; flex-direction:column; align-items:center; justify-content:center; background:var(--vr-accent-soft); border-radius:10px; padding:10px 14px; }
.vr-metric-value { font-size:26px; font-weight:700; letter-spacing:-0.01em; color:var(--vr-accent); font-variant-numeric: tabular-nums; }
.vr-metric-caption { font-size:11px; color:var(--vr-ink-2); margin-top:2px; }

/* -- 순위 · 정확도 배지 --------------------------------------------- */
.vr-rank-meta { display:flex; flex-direction:column; gap:6px; margin: 2px 2px 4px; }
.vr-rank-row { display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--vr-ink-2); }
.vr-rank-row-bottom { display:flex; align-items:center; justify-content:space-between; gap:8px; font-size:12px; color:var(--vr-ink-muted); }
.vr-rank-badge { display:inline-flex; align-items:center; justify-content:center; min-width:22px; height:20px; padding:0 5px; background:var(--vr-accent-soft); color:var(--vr-accent); font-size:11px; font-weight:700; border-radius:6px; font-variant-numeric: tabular-nums; }
.vr-accuracy-chip { display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:600; padding:3px 9px 3px 7px; border-radius:999px; }
.vr-accuracy-chip::before { content:""; width:6px; height:6px; border-radius:999px; background:currentColor; }
.vr-accuracy-chip.measured { background:var(--vr-good-soft); color:var(--vr-good); }
.vr-accuracy-chip.estimated { background:var(--vr-warning-soft); color:var(--vr-warning); }
.vr-accuracy-chip.pending { background:var(--vr-hairline); color:var(--vr-ink-muted); }
.vr-accuracy-chip.impossible { background:var(--vr-critical-soft); color:var(--vr-critical); }

/* -- 댓글 -------------------------------------------------------------- */
.vr-comments { display:flex; flex-direction:column; gap:5px; margin: 4px 2px 2px; }
.vr-comment-line { font-size:12.5px; color:var(--vr-ink-2); }
.vr-comment-line .vr-nick { color:var(--vr-ink-muted); }

/* -- st.progress 재스킨 (위젯은 그대로, 색·형태만 교체) -------------------- */
div[data-testid="stProgress"] [data-testid="stMarkdownContainer"] p {
  font-size:12px; color:var(--vr-ink-2); font-variant-numeric: tabular-nums; margin-bottom:2px;
}
div[data-testid="stProgressBarTrack"] {
  background: var(--vr-accent-soft) !important; border-radius:999px !important; height:8px !important;
}
div[data-testid="stProgressBarTrack"] > div {
  background: linear-gradient(90deg, var(--vr-accent), var(--vr-accent-bright)) !important; border-radius:999px !important;
}

/* -- 내보내기 버튼 ------------------------------------------------------ */
div[data-testid="stDownloadButton"] button { border-radius: 8px !important; font-weight:600 !important; }
div[data-testid="stDownloadButton"] button:hover { border-color: var(--vr-accent) !important; color: var(--vr-accent) !important; }
</style>
<svg width="0" height="0" style="position:absolute;">
  <defs>
    <symbol id="vr-logo-naver" viewBox="0 0 24 24">
      <rect width="24" height="24" rx="6" fill="#03C75A"/>
      <path d="M14.4 6.5v6.2L9.7 6.5H6.5v11h3.1v-6.2l4.7 6.2h3.2v-11h-3.1z" fill="#fff"/>
    </symbol>
    <symbol id="vr-logo-instagram" viewBox="0 0 24 24">
      <rect x="1" y="1" width="22" height="22" rx="6" fill="#fff" stroke="#DD2A7B" stroke-width="1.6"/>
      <circle cx="12" cy="12" r="4.6" fill="none" stroke="#DD2A7B" stroke-width="1.6"/>
      <circle cx="17.6" cy="6.4" r="1.15" fill="#DD2A7B"/>
    </symbol>
    <symbol id="vr-logo-youtube" viewBox="0 0 24 24">
      <rect width="24" height="24" rx="6" fill="#FF0000"/>
      <path d="M9.8 8.3l6 3.7-6 3.7z" fill="#fff"/>
    </symbol>
    <symbol id="vr-logo-community" viewBox="0 0 24 24">
      <rect width="24" height="24" rx="6" fill="#E1E0D9"/>
      <path d="M6 8.5h12v6.2H11l-2.6 2.3v-2.3H6z" fill="none" stroke="#52514E" stroke-width="1.4" stroke-linejoin="round"/>
    </symbol>
    <linearGradient id="vr-grad-line" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#2a78d6"/>
      <stop offset="100%" stop-color="#6da7ec"/>
    </linearGradient>
    <linearGradient id="vr-grad-area" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#2a78d6" stop-opacity="0.32"/>
      <stop offset="100%" stop-color="#2a78d6" stop-opacity="0"/>
    </linearGradient>
  </defs>
</svg>
"""


def _inject_design_system() -> None:
    st.markdown(_STYLE_AND_ICONS, unsafe_allow_html=True)


def _sparkline_svg(metrics: list[dict], width: int = 300, height: int = 76) -> str:
    """실측 조회수 시계열만 그린다 — 데이터 없는 구간에 추세를 지어내지 않는다."""
    gridlines = f'<line x1="0" y1="26" x2="{width}" y2="26" class="vr-gridline"/><line x1="0" y1="62" x2="{width}" y2="62" class="vr-gridline"/>'
    if not metrics:
        return f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none">{gridlines}</svg>'

    views = [m["views"] for m in metrics]
    vmin, vmax = min(views), max(views)
    pad_top, pad_bottom, pad_x = 8, 14, 10
    n = len(views)

    def _x(i: int) -> float:
        return pad_x + (width - 2 * pad_x) * (i / (n - 1) if n > 1 else 0)

    def _y(v: int) -> float:
        if vmax == vmin:
            return height / 2
        frac = (v - vmin) / (vmax - vmin)
        return (height - pad_bottom) - frac * (height - pad_bottom - pad_top)

    points = [(_x(i), _y(v)) for i, v in enumerate(views)]
    lastx, lasty = points[-1]
    dot = f'<circle cx="{lastx:.1f}" cy="{lasty:.1f}" r="5" class="vr-spark-dot"/>'

    if n == 1:
        return f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none">{gridlines}{dot}</svg>'

    poly = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
    area = poly + f" {points[-1][0]:.1f},{height} {points[0][0]:.1f},{height}"
    return (
        f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none">{gridlines}'
        f'<polygon points="{area}" class="vr-spark-area"/>'
        f'<polyline points="{poly}" class="vr-spark-line"/>{dot}</svg>'
    )


def _render_exposure_rank_list(exposure_counts: dict) -> None:
    if not exposure_counts:
        st.caption("아직 네이버 순위가 1페이지에 든 콘텐츠가 없다.")
        return

    total = sum(exposure_counts.values())
    ordered = sorted(exposure_counts.items(), key=lambda kv: kv[1], reverse=True)
    rows = []
    for i, (channel, count) in enumerate(ordered):
        pct = round(count / total * 100) if total else 0
        icon = _CHANNEL_ICON.get(channel, "community")
        top_cls = " vr-rank-item--top" if i == 0 else ""
        rows.append(
            f'<div class="vr-rank-item{top_cls}">'
            f'<div class="vr-rank-ordinal">{i + 1}위</div>'
            f'<div class="vr-rank-chan">'
            f'<span class="vr-channel-badge"><svg><use href="#vr-logo-{icon}"/></svg></span>'
            f'<span class="vr-rank-chan-name">{_esc(channel)}</span></div>'
            f'<div class="vr-rank-track"><div class="vr-rank-fill" style="width:{pct}%"></div></div>'
            f'<div class="vr-rank-figures"><span class="vr-rank-value">{count}</span>'
            f'<span class="vr-rank-unit">건</span></div>'
            f'<div class="vr-rank-share">전체의 {pct}%</div>'
            f"</div>"
        )
    st.markdown(f'<div class="vr-rank-list">{"".join(rows)}</div>', unsafe_allow_html=True)


def _render_card_header(content: dict) -> None:
    icon = _CHANNEL_ICON.get(content["channel"], "community")
    title = _esc(content.get("title") or content["url"])
    release = _esc(content.get("release_at") or "미정")
    st.markdown(
        f'<span class="vr-card-marker"></span>'
        f'<div class="vr-card-band">'
        f'<span class="vr-channel-badge vr-channel-badge--lg"><svg><use href="#vr-logo-{icon}"/></svg></span>'
        f"<div><div class=\"vr-card-title\">{title}</div>"
        f'<div class="vr-card-date">{_esc(content["channel"])} · 릴리즈 {release}</div></div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_chart_row(metrics: list[dict]) -> None:
    if metrics:
        latest_metric = metrics[-1]
        value_html = f'<div class="vr-metric-value">{latest_metric["views"]:,}</div>'
    else:
        value_html = '<div class="vr-metric-value" style="color:var(--vr-ink-muted);">—</div>'
    st.markdown(
        f'<div class="vr-chart-row">'
        f'<div class="vr-sparkline">{_sparkline_svg(metrics)}</div>'
        f'<div class="vr-stat-capsule">{value_html}<div class="vr-metric-caption">조회수</div></div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    if metrics:
        latest_metric = metrics[-1]
        st.caption(f"정확도: {latest_metric['accuracy']} · 최근 수집: {latest_metric['captured_at']}")
    else:
        st.caption("아직 수집된 조회수가 없다.")


def _render_rank_and_accuracy(content_ranks: list[dict]) -> None:
    if not content_ranks:
        return
    latest = content_ranks[-1]
    chip_class = _ACCURACY_CHIP_CLASS.get(latest["accuracy"], "pending")
    st.markdown(
        f'<div class="vr-rank-meta">'
        f'<div class="vr-rank-row"><span class="vr-rank-badge">{latest["rank"]}위</span>'
        f'네이버 "{_esc(latest["keyword"])}" · {_esc(latest["search_tab"])}</div>'
        f'<div class="vr-rank-row-bottom"><span>{_esc(latest["captured_at"])} 수집</span>'
        f'<span class="vr-accuracy-chip {chip_class}">{_esc(latest["accuracy"])}</span></div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_comments(content_comments: list[dict]) -> None:
    if not content_comments:
        return
    st.caption(f"댓글 {len(content_comments)}건")
    lines = []
    for comment in content_comments[:5]:
        nickname = comment.get("author_nickname") or "익명"
        lines.append(
            f'<div class="vr-comment-line">"{_esc(comment["text"])}" '
            f'<span class="vr-nick">— {_esc(nickname)}</span></div>'
        )
    st.markdown(f'<div class="vr-comments">{"".join(lines)}</div>', unsafe_allow_html=True)


repo = ReportRepo()

st.title("리포트 대시보드")
_inject_design_system()

campaigns = repo.campaigns()
campaign_labels = {f"{c['brand']} · {c['name']}": c["campaign_id"] for c in campaigns}

if not campaign_labels:
    st.info("아직 등록된 캠페인이 없다. '등록·관리자' 페이지에서 먼저 등록해야 한다.")
    st.stop()

campaign_label = st.selectbox("캠페인", options=list(campaign_labels.keys()), key="report_campaign_picker")
campaign_id = campaign_labels[campaign_label]

channel_filter = st.multiselect("채널 필터", options=CHANNELS, default=CHANNELS, key="report_channel_filter")

contents = [c for c in repo.contents(campaign_id=campaign_id) if c["channel"] in channel_filter]
content_ids = {c["content_id"] for c in contents}

all_metrics = [m for m in repo.content_metrics() if m["content_id"] in content_ids]
all_ranks = [r for r in repo.keyword_ranks() if r["content_id"] in content_ids]
all_comments = [c for c in repo.comments() if c["content_id"] in content_ids]
targets = repo.targets(campaign_id=campaign_id)

if not contents:
    st.info("이 캠페인에는 등록된 콘텐츠가 없다.")
    st.stop()

# -- 종합지표: 채널별 네이버 상위노출 콘텐츠 수 --------------------------
# (다른 종합 KPI는 일부러 안 둔다 — brainstorming 결정: 콘텐츠 단위 카드가 더 중요)

st.subheader("채널별 네이버 상위노출 콘텐츠 수")

exposure_counts = exposure_counts_by_channel(contents, all_ranks)
_render_exposure_rank_list(exposure_counts)

# -- 채널 목표 대비 (채널 스코프 목표가 있는 채널만) -----------------------

channel_targets = {
    t["scope_key"]: t["target_views"]
    for t in targets
    if t["scope_type"] == "channel" and t["scope_key"] in channel_filter
}
if channel_targets:
    st.subheader("채널 목표 대비")
    for channel, target_views in channel_targets.items():
        channel_views = sum(latest_views(all_metrics, c["content_id"]) for c in contents if c["channel"] == channel)
        pct = target_progress_pct(channel_views, target_views)
        st.progress(min(pct, 100) / 100, text=f"{channel}: {channel_views} / {target_views} ({pct}%)")

# -- 콘텐츠 카드 --------------------------------------------------------

st.subheader("콘텐츠별 상세")

content_targets = {t["scope_key"]: t["target_views"] for t in targets if t["scope_type"] == "content"}

for content in contents:
    cid = content["content_id"]
    with st.container(border=True):
        _render_card_header(content)

        metrics = sorted((m for m in all_metrics if m["content_id"] == cid), key=lambda m: m["captured_at"])
        _render_chart_row(metrics)

        if cid in content_targets:
            views = latest_views(all_metrics, cid)
            target_views = content_targets[cid]
            pct = target_progress_pct(views, target_views)
            st.progress(min(pct, 100) / 100, text=f"목표 대비: {views} / {target_views} ({pct}%)")
        else:
            st.caption("목표 대비: 미설정")

        content_ranks = sorted((r for r in all_ranks if r["content_id"] == cid), key=lambda r: r["captured_at"])
        _render_rank_and_accuracy(content_ranks)

        content_comments = [c for c in all_comments if c["content_id"] == cid]
        _render_comments(content_comments)

# -- 광고주 공유용 내보내기 ------------------------------------------------

st.subheader("광고주 공유용 내보내기")

export_markdown = build_export_markdown(campaign_label, contents, all_metrics, all_ranks, all_comments)
st.download_button(
    "리포트 내보내기 (Markdown)",
    data=export_markdown,
    file_name=f"{campaign_label}_리포트.md",
    mime="text/markdown",
    key="export_button",
)
