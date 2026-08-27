"""캠페인·콘텐츠별 조회수·네이버 순위 추이를 보는 화면. 읽기 전용 — 등록은 2_등록.py에서.

조회수 추이는 실측값만 연결해서 그린다. 데이터가 없는 미래 구간에
점선으로 "추세(예시)"를 지어내 그리지 않는다.

디자인은 project/active/20260820_바이럴성과-리포팅-대시보드/redesign-v2-report.html을
이 페이지에 실제로 반영한 v2 브랜드 디자인이다. 다만 두 가지는 옮기지 않았다:
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
    build_export_markdown, channel_distribution, exposure_counts_by_channel, keyword_rank_summary,
    latest_rank_row, latest_views, participation_rate, rank_history,
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

/* ---- v2 리뉴얼: 마녀공장 마스터 브랜드 옐로우 앰비언트 헤더 ---- */
.vr-amb {
  position: relative; padding: 30px 32px 60px; margin: -1rem -1rem 0;
  background: linear-gradient(135deg, #ffe066 0%, #fbc02d 55%, #f2a30f 100%);
}
.vr-amb::after {
  content: ""; position: absolute; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E");
  mix-blend-mode: overlay; pointer-events: none;
}
.vr-amb-top { display: flex; align-items: center; justify-content: space-between; position: relative; z-index: 1; }
.vr-amb-brand { font-size: 13px; font-weight: 600; color: rgba(30,22,0,0.85); }
.vr-amb-brand span { color: #7a4a00; }
.vr-amb-user { font-size: 11px; color: rgba(30,22,0,0.55); }
.vr-amb-title { position: relative; z-index: 1; margin-top: 24px; font-size: 26px; font-weight: 700; color: #1e1600; letter-spacing: -0.02em; }

/* ---- 겹치는 히어로 카드: 도넛 + 상위노출 랭크 ----
   .vr-hero를 직접 여는 div로 쓰지 않는다 — Streamlit은 st.markdown 호출마다
   독립된 DOM 컨테이너를 만들어서, 한 번의 st.markdown에서 연 <div>가 이후
   st.subheader나 다른 st.markdown 호출(별도 컨테이너)까지 감쌀 수 없다.
   대신 기존 .vr-card-marker와 같은 패턴 — st.container(border=True) 안에
   숨김 마커를 심고 그 stVerticalBlock 전체를 :has()로 스코프한다. */
.vr-hero-marker { display:none; }
/* 예전엔 음수 top margin으로 이 카드가 앰버 헤더 위로 살짝 겹쳐 보이게
   했었는데, 헤더와 이 카드 사이에 "캠페인"·"채널 필터" 네이티브 위젯이
   끼어들면서 카드가 그 위젯들을 덮어버리는 버그가 됐다(실측 확인 — 정적
   프리뷰는 네이티브 위젯을 안 잡아서 못 보였다). 그래서 일반 여백으로 뺐다. */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-hero-marker) {
  position: relative; z-index: 2; margin: 4px 0 0 !important;
  background: #fff; border-radius: 16px; padding: 22px 26px 20px;
  box-shadow: 0 12px 32px -12px rgba(30,25,15,0.18), 0 1px 0 rgba(30,25,15,0.04);
}
.vr-donut-block { display: flex; align-items: center; gap: 22px; padding-bottom: 18px; margin-bottom: 18px; border-bottom: 1px solid #f0ede8; }
.vr-donut-wrap { position: relative; flex: none; width: 96px; height: 96px; }
.vr-donut-wrap svg { width: 100%; height: 100%; }
.vr-donut-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.vr-donut-center b { font-size: 22px; font-weight: 800; color: #1c1a16; line-height: 1; }
.vr-donut-center span { font-size: 9.5px; color: var(--vr-ink-muted); font-weight: 600; margin-top: 2px; }
.vr-donut-legend { display: flex; flex-direction: column; gap: 7px; flex: 1; }
.vr-donut-legend-row { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; color: var(--vr-ink-2); }
.vr-donut-dot { width: 8px; height: 8px; border-radius: 2px; flex: none; }
.vr-donut-legend-num { margin-left: auto; color: var(--vr-ink); font-weight: 700; font-variant-numeric: tabular-nums; }
.vr-donut-legend-pct { color: var(--vr-ink-muted); font-weight: 500; font-size: 11px; min-width: 34px; text-align: right; }

/* ---- 캠페인 키워드 순위: 탭당 전체 목록 ---- */
/* 키워드 카드 자체가 한 줄에 하나씩(st.markdown 호출마다 별도 블록) 쌓이던 걸
   3열 그리드로 — 모든 키워드 카드를 하나의 st.markdown 호출로 묶어 한
   .vr-kw-grid 래퍼 안에 넣고, 그 래퍼에 grid를 건다(카드 개수가 3의 배수가
   아니어도 마지막 줄은 그냥 비워둔다). */
.vr-kw-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px 14px; align-items: start; }
.vr-kw-card { border-radius: 12px; background: var(--vr-page); padding: 16px 18px; }
.vr-kw-name { font-size: 14px; font-weight: 700; color: var(--vr-ink); margin-bottom: 12px; }
.vr-kw-tab-group { margin-bottom: 14px; }
.vr-kw-tab-group:last-child { margin-bottom: 0; }
.vr-kw-tab-head { font-size: 11px; font-weight: 700; color: var(--vr-ink-2); text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 6px; }
.vr-kw-tab-head .vr-kw-tab-count { font-weight: 500; color: var(--vr-ink-muted); text-transform: none; letter-spacing: 0; }
.vr-kw-tab-empty { color: var(--vr-ink-muted); font-size: 12px; padding: 4px 0; }
/* 매치된 콘텐츠는 세로 목록 — 키워드 카드 자체가 이제 3열 grid(.vr-kw-grid)라
   카드 폭이 좁아서, 이 안에서 또 다열 grid를 걸면 항목이 너무 빽빽해진다. */
.vr-kw-content-row {
  display: flex; flex-direction: column; gap: 3px; padding: 8px 10px; margin-bottom: 6px;
  background: var(--vr-surface); border-radius: 8px; font-size: 12px; color: var(--vr-ink-2);
  min-width: 0;
}
.vr-kw-content-row:last-child { margin-bottom: 0; }
.vr-kw-content-row-top { display: flex; align-items: center; gap: 8px; min-width: 0; }
.vr-kw-content-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.vr-kw-content-date { color: var(--vr-ink-muted); font-size: 10.5px; }

/* ---- 참여율(.vr-card-stats 뉴모피즘 패널을 2분할한 아래쪽 절반 — 위 조회수와
   같은 폰트 크기로 통일했다) ---- */
.vr-stat-secondary { flex:1; box-sizing:border-box; display:flex; flex-direction:column; align-items:center;
  justify-content:center; width:100%; text-align: center; border-top:1px solid rgba(11,11,11,0.07); }
.vr-stat-secondary b { display: block; font-size: 26px; font-weight: 800; color: var(--vr-ink); letter-spacing: -0.01em; }
.vr-stat-secondary b.empty { color: #c7c2b6; font-size: 22px; }
.vr-stat-secondary span { display: block; font-size: 11px; color: var(--vr-ink-muted); font-weight: 600; margin-top: 2px; }

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
.vr-rank-chan-name { font-size:12.5px; color:var(--vr-ink-2); white-space:nowrap; }
.vr-rank-track { position:relative; height:10px; background:var(--vr-accent-soft); border-radius:999px; overflow:hidden; }
.vr-rank-fill { position:absolute; inset:0; border-radius:999px; background:linear-gradient(90deg, var(--vr-accent), var(--vr-accent-bright)); }
.vr-rank-item--top .vr-rank-fill { box-shadow: 0 0 0 1px var(--vr-accent-wash) inset; }
.vr-rank-figures { display:flex; align-items:baseline; gap:5px; justify-content:flex-end; min-width:74px; }
.vr-rank-value { font-size:17px; font-weight:700; color:var(--vr-ink); font-variant-numeric: tabular-nums; }
.vr-rank-unit { font-size:11px; color:var(--vr-ink-muted); }
.vr-rank-share { font-size:10.5px; color:var(--vr-ink-muted); text-align:right; margin-top:2px; grid-column:4; font-variant-numeric: tabular-nums; }

/* -- 콘텐츠 카드: marker로 이 카드의 stVerticalBlock만 스코프해서 강화 ----
   목업(redesign-v2-report.html) 그대로: 흰 배경 + 헤어라인 보더 + 채널별
   상단 3px 컬러바(밴드 헤더 아님) + 우상단 작은 로고 배지. */
.vr-card-marker { display:none; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-card-marker) {
  position: relative !important; /* 카드 전체를 덮는 링크 오버레이(.vr-card-link)의 기준 */
  border-radius: 14px !important;
  border: 1px solid #ece8e0 !important;
  border-top: 3px solid #c9a86a !important;
  padding: 18px 20px !important;
  overflow: hidden;
  transition: transform 0.2s var(--vr-ease), box-shadow 0.2s var(--vr-ease);
}
.vr-card-link { position: absolute; inset: 0; z-index: 1; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-card-marker--blog) { border-top-color: #3a5ac4 !important; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-card-marker--instagram) { border-top-color: #d6478a !important; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-card-marker--community) { border-top-color: #8a6fd6 !important; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-card-marker--youtube) { border-top-color: #e2453e !important; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-card-marker):hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 28px -16px rgba(30,25,15,0.22);
}
/* 조회수 0(아직 수집 전) 카드 — 목록 맨 아래로 정렬된 것과 짝을 맞춰
   옅게 처리해서 "데이터 없음"을 한눈에 구분한다. */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-card-marker--empty) { opacity: 0.55; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-card-marker--empty):hover { opacity: 0.85; }
.vr-card-head { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; margin-bottom:4px; }
.vr-card-title { font-family: var(--vr-font-display); font-size:15px; font-weight:700; line-height:1.35; color: var(--vr-ink); }
.vr-card-logo { flex:none; width:26px; height:26px; border-radius:7px; overflow:hidden; display:block; }
.vr-card-logo svg { width:100%; height:100%; display:block; }
.vr-card-meta { font-size:11px; color:var(--vr-ink-muted); font-weight:500; margin-bottom:14px; }

/* -- 조회수 스파크라인 + 순위 추이(왼쪽, 세로로 쌓임) + 조회수/참여율
   뉴모피즘 스탯 카드(오른쪽) ---------------------------------------------
   .vr-metrics-panel은 flex row, 기본 align-items:stretch 덕분에 오른쪽
   .vr-card-stats 높이가 왼쪽 .vr-metrics-charts(그래프 2개)의 실제 콘텐츠
   높이에 자동으로 맞춰진다. 폭도 같은 flex 컬럼을 공유하므로 위 스파크라인과
   아래 순위 추이 그래프가 항상 같은 렌더 폭을 갖는다. */
.vr-metrics-panel { display:flex; align-items:stretch; gap:20px; margin: 0 2px 0; }
.vr-metrics-charts { flex:1 1 auto; min-width:0; display:flex; flex-direction:column; justify-content:center; gap:12px; }
.vr-chart-title-row { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:6px; }
.vr-chart-title { font-size:11px; font-weight:700; color:var(--vr-ink-2); }
.vr-chart-title-meta { display:flex; align-items:center; gap:6px; font-size:11px; font-weight:600; color:var(--vr-ink-2); }
/* 그래프별 "카드 속 카드" — 조회수/상위노출 그래프를 각각 뉴모피즘 박스로
   감싸서(오른쪽 스탯 카드와 같은 이중 그림자) 두 그래프의 영역이 한눈에
   구분되게 한다. */
.vr-chart-box {
  background: var(--vr-page); border-radius: 12px; padding: 12px 16px 10px;
  box-shadow: 4px 4px 8px rgba(30,25,15,0.09), -4px -4px 8px rgba(255,255,255,0.85),
    inset 0 0 0 1px rgba(255,255,255,0.4);
}
.vr-sparkline svg, .vr-rank-trend svg { display:block; width:100%; height:auto; aspect-ratio: 640 / 72; }
.vr-gridline { stroke: var(--vr-hairline); stroke-width:1; }
/* 뉴모피즘 "카드 속 카드" — 배경이 페이지톤(--vr-page)에 가깝고 그림자가
   낮은 채도라 뉴모피즘의 이중 그림자(밝음/어두움)가 잘 먹는다. 글래스모피즘은
   블러로 비칠 화려한 배경이 이 자리엔 없어서(흰 카드 위 흰 여백) 대신 골랐다.
   내부는 flex-direction:column에 .vr-stat-num/.vr-stat-secondary가 각각
   flex:1이라 박스가 정확히 반씩 나뉘고, 두 절반 안에서 각자 가운데 정렬된다. */
.vr-card-stats {
  flex:none; width:136px; margin:2px 0 0; box-sizing:border-box; display:flex; flex-direction:column;
  padding:8px 16px; border-radius:14px; background: var(--vr-page);
  box-shadow: 5px 5px 10px rgba(30,25,15,0.10), -5px -5px 10px rgba(255,255,255,0.9),
    inset 0 0 0 1px rgba(255,255,255,0.5);
}
/* 그래프 영역과 댓글 영역 사이 구분선 — 카드속카드(.vr-card-stats)가 이
   선 바로 위까지 자리잡도록 위쪽 여백을 작게 준다. */
.vr-metrics-divider { border:none; border-top:1px solid var(--vr-hairline); margin: 4px 2px 12px; }
.vr-stat-num { flex:1; box-sizing:border-box; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; }
.vr-stat-num b { display:block; font-size:26px; font-weight:800; color:var(--vr-ink); letter-spacing:-0.01em; }
.vr-stat-num span { display:block; font-size:11px; color:var(--vr-ink-muted); font-weight:600; margin-top:2px; }
.vr-stat-num.empty b { color:#c7c2b6; font-size:22px; }

.vr-rank-badge { display:inline-flex; align-items:center; justify-content:center; min-width:22px; height:20px; padding:0 5px; background:var(--vr-accent-soft); color:var(--vr-accent); font-size:11px; font-weight:700; border-radius:6px; font-variant-numeric: tabular-nums; }
.vr-rank-trend-miss { fill:var(--vr-surface); stroke:var(--vr-ink-muted); stroke-width:1.5; }
.vr-rank-trend-sep { stroke:var(--vr-hairline); stroke-width:1; stroke-dasharray:3 3; }
.vr-rank-trend-value { font-size:10px; font-weight:700; fill:var(--vr-ink-2); text-anchor:middle; }

/* -- 댓글 -------------------------------------------------------------- */
.vr-comments { display:flex; flex-direction:column; gap:5px; margin: 4px 2px 2px; }
.vr-comment-line { font-size:12.5px; color:var(--vr-ink-2); }
.vr-comment-line .vr-nick { color:var(--vr-ink-muted); }

/* -- 내보내기 버튼 ------------------------------------------------------ */
div[data-testid="stDownloadButton"] button { border-radius: 8px !important; font-weight:600 !important; }
div[data-testid="stDownloadButton"] button:hover { border-color: var(--vr-accent) !important; color: var(--vr-accent) !important; }

/* -- 스크롤 진입 모션 ----------------------------------------------------
   목업 기획 때 정한 "스크롤하면 카드가 떠오르는" 효과. Streamlit의
   st.markdown(unsafe_allow_html=True)은 보안상 <script>를 실행하지 않아서
   IntersectionObserver 기반 JS는 못 쓴다 — 대신 순수 CSS 스크롤 기반
   애니메이션(animation-timeline: view())으로 같은 효과를 낸다. 이 CSS
   기능 자체를 못 읽는 브라우저에서는 @supports가 걸러줘서 카드가 그냥
   평소처럼(불투명 상태로) 바로 보인다 — 못 읽는다고 안 보이는 사고는 없다. */
@supports (animation-timeline: view()) {
  @keyframes vr-scroll-in {
    from { opacity: 0; transform: translateY(18px); }
    to { opacity: 1; transform: translateY(0); }
  }
  div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-card-marker),
  div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vr-hero-marker),
  .vr-kw-card {
    animation: vr-scroll-in linear both;
    animation-timeline: view();
    animation-range: entry 0% entry 35%;
  }

  /* 조회수·상위노출 그래프 선이 스크롤에 맞춰 "그려지는" 모션 — stroke-dasharray/
     stroke-dashoffset을 폴리라인 실제 길이(_polyline_length)로 맞춰두고
     dashoffset을 0으로 애니메이션한다. 시작값은 인라인 속성(stroke-dashoffset)이
     그대로 0% 키프레임 역할을 하므로 @keyframes에는 to만 적는다. */
  @keyframes vr-line-draw {
    to { stroke-dashoffset: 0; }
  }
  .vr-line-draw {
    animation: vr-line-draw linear both;
    animation-timeline: view();
    animation-range: entry 10% entry 70%;
  }
}
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
    <linearGradient id="vr-grad-line-v2" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#2b3a67"/>
      <stop offset="100%" stop-color="#b8792e"/>
    </linearGradient>
    <linearGradient id="vr-grad-rank" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#2a78d6"/>
      <stop offset="100%" stop-color="#6da7ec"/>
    </linearGradient>
    <filter id="vr-glow-v2" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
</svg>
"""


def _inject_design_system() -> None:
    st.markdown(_STYLE_AND_ICONS, unsafe_allow_html=True)


def _polyline_length(points: list[tuple[float, float]]) -> float:
    """선 그리기(stroke-dashoffset) 애니메이션의 시작값으로 쓸 실제 경로 길이.

    stroke-dasharray/stroke-dashoffset을 이 길이로 맞춰야 애니메이션이 정확히
    선 끝에서 끝나고, 짧게 잘리거나 남는 부분 없이 깔끔하게 그려진다."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        total += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return total


def _sparkline_svg(metrics: list[dict], width: int = 640, height: int = 72) -> str:
    """실측 조회수 시계열만 그린다 — 데이터 없는 구간에 추세를 지어내지 않는다.

    선 색은 남색(#2b3a67, 지난 구간)에서 앰버(#b8792e, 최근 구간)로 흐르는
    그라디언트 — 승인된 v2 목업(redesign-v2-report.html) 그대로. 은은한
    글로우 언더레이 한 번 더 그려서 흰 배경에서도 살짝 번지는 느낌만 준다.
    """
    gridlines = f'<line x1="0" y1="24" x2="{width}" y2="24" class="vr-gridline"/><line x1="0" y1="48" x2="{width}" y2="48" class="vr-gridline"/>'
    if not metrics:
        return f'<svg viewBox="0 0 {width} {height}">{gridlines}</svg>'

    views = [m["views"] for m in metrics]
    vmin, vmax = min(views), max(views)
    pad_top, pad_bottom, pad_x = 8, 14, 20
    n = len(views)

    def _x(i: int) -> float:
        return pad_x + (width - 2 * pad_x) * (i / (n - 1) if n > 1 else 0.5)

    def _y(v: int) -> float:
        if vmax == vmin:
            return height / 2
        frac = (v - vmin) / (vmax - vmin)
        return (height - pad_bottom) - frac * (height - pad_bottom - pad_top)

    points = [(_x(i), _y(v)) for i, v in enumerate(views)]
    lastx, lasty = points[-1]
    dot = f'<circle cx="{lastx:.1f}" cy="{lasty:.1f}" r="5" fill="#b8792e" stroke="#fff" stroke-width="2.5"/>'

    if n == 1:
        return f'<svg viewBox="0 0 {width} {height}">{gridlines}{dot}</svg>'

    poly = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
    draw_len = _polyline_length(points)
    draw_attrs = f'stroke-dasharray="{draw_len:.1f}" stroke-dashoffset="{draw_len:.1f}"'
    return (
        f'<svg viewBox="0 0 {width} {height}">{gridlines}'
        f'<polyline points="{poly}" class="vr-line-draw" fill="none" stroke="url(#vr-grad-line-v2)" stroke-width="6" '
        f'stroke-linecap="round" stroke-linejoin="round" opacity="0.16" filter="url(#vr-glow-v2)" {draw_attrs}/>'
        f'<polyline points="{poly}" class="vr-line-draw" fill="none" stroke="url(#vr-grad-line-v2)" stroke-width="2.5" '
        f'stroke-linecap="round" stroke-linejoin="round" {draw_attrs}/>{dot}</svg>'
    )


_DONUT_COLORS = {"blog": "#3a5ac4", "cafe": "#c9a86a", "community": "#8a6fd6", "instagram": "#d6478a", "youtube": "#e2453e"}


def _render_channel_donut(distribution: dict) -> None:
    total = sum(distribution.values())
    if not total:
        st.caption("아직 등록된 콘텐츠가 없다.")
        return

    circumference = 2 * 3.14159265 * 36
    ordered = sorted(distribution.items(), key=lambda kv: kv[1], reverse=True)
    cumulative_deg = -90.0
    arcs = []
    legend_rows = []
    for channel, count in ordered:
        pct_frac = count / total
        seg_len = round(pct_frac * circumference, 2)
        color = _DONUT_COLORS.get(channel, "#a39c8c")
        arcs.append(
            f'<circle cx="48" cy="48" r="36" fill="none" stroke="{color}" stroke-width="14" '
            f'stroke-dasharray="{seg_len} {circumference:.1f}" transform="rotate({cumulative_deg:.1f} 48 48)"/>'
        )
        pct_display = round(pct_frac * 100)
        legend_rows.append(
            f'<div class="vr-donut-legend-row"><span class="vr-donut-dot" style="background:{color};"></span>'
            f'{_esc(channel)}<span class="vr-donut-legend-num">{count}건</span>'
            f'<span class="vr-donut-legend-pct">{pct_display}%</span></div>'
        )
        cumulative_deg += pct_frac * 360

    st.markdown(
        f'<div class="vr-donut-block">'
        f'<div class="vr-donut-wrap"><svg viewBox="0 0 96 96">'
        f'<circle cx="48" cy="48" r="36" fill="none" stroke="#f0ede8" stroke-width="14"/>'
        f'{"".join(arcs)}</svg>'
        f'<div class="vr-donut-center"><b>{total}</b><span>등록 콘텐츠</span></div></div>'
        f'<div class="vr-donut-legend">{"".join(legend_rows)}</div>'
        f"</div>",
        unsafe_allow_html=True,
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


def _render_card_header(content: dict, *, is_empty: bool = False) -> None:
    """카드 전체를 그 콘텐츠 원문 URL로 가는 링크로 만든다.

    카드 안에는 버튼·입력창 같은 실제 Streamlit 위젯이 없다(전부 st.markdown/
    st.caption) — 그래서 카드 전체를 덮는 투명 <a> 오버레이(.vr-card-link,
    absolute+inset:0)를 하나 깔아도 클릭을 가로챌 다른 위젯이 없다. 위치 기준은
    위 .vr-card-marker :has() 규칙에서 카드 컨테이너 자체에 준 position:relative.

    is_empty(조회수 0 = 아직 수집 전)면 마커에 --empty 클래스를 추가로 얹어
    카드 전체를 옅게(투명도) 처리한다 — 목록 맨 아래로 정렬된 것과 짝을 맞춰
    "아직 데이터 없음"을 시각적으로도 구분한다.
    """
    channel = content["channel"]
    icon = _CHANNEL_ICON.get(channel, "community")
    title = _esc(content.get("title") or content["url"])
    release = _esc(content.get("release_at") or "미정")
    url = _esc(content["url"])
    empty_class = " vr-card-marker--empty" if is_empty else ""
    st.markdown(
        f'<span class="vr-card-marker vr-card-marker--{channel}{empty_class}"></span>'
        f'<a class="vr-card-link" href="{url}" target="_blank" rel="noopener noreferrer" '
        f'aria-label="{title} 원문 열기"></a>'
        f'<div class="vr-card-head">'
        f'<div class="vr-card-title">{title}</div>'
        f'<span class="vr-card-logo"><svg><use href="#vr-logo-{icon}"/></svg></span>'
        f"</div>"
        f'<div class="vr-card-meta">{_esc(channel)} · 릴리즈 {release}</div>',
        unsafe_allow_html=True,
    )


def _rank_trend_svg(history: list[tuple[str, int]], width: int = 640, height: int = 72) -> str:
    """실측 순위 이력만 그린다 — _sparkline_svg와 같은 원칙(없는 값을 추세로
    지어내지 않는다), y축만 반대다: 1위가 위, 숫자가 클수록 아래로 내려간다.
    축 기준선 텍스트 대신 각 점 위(또는 위 여백이 없으면 아래)에 실제 순위
    값을 직접 라벨로 붙인다.

    상위노출이 안 잡힌 날(rank=0)은 차트 맨 아래 "미노출" 줄에 점만 찍고
    실측 순위와 선으로 잇지 않는다 — "0위"가 1위보다 좋다는 착시를 막기 위해서.
    """
    pad_top, pad_bottom, pad_x = 16, 20, 20
    miss_y = height - 6
    n = len(history)

    def _x(i: int) -> float:
        return pad_x + (width - 2 * pad_x) * (i / (n - 1) if n > 1 else 0.5)

    ranked_only = [r for _, r in history if r > 0]
    rmin = min(ranked_only) if ranked_only else 1
    rmax = max(ranked_only) if ranked_only else 1

    def _y(rank: int) -> float:
        if rank == 0:
            return miss_y
        if rmax == rmin:
            return pad_top + (height - pad_bottom - pad_top) / 2
        frac = (rank - rmin) / (rmax - rmin)  # 0 = 1위 방향(최고), 1 = 최악
        return pad_top + frac * (height - pad_bottom - pad_top)

    points = [(_x(i), _y(rank)) for i, (_, rank) in enumerate(history)]
    has_miss = any(rank == 0 for _, rank in history)

    gridlines = f'<line x1="0" y1="{pad_top - 2:.1f}" x2="{width}" y2="{pad_top - 2:.1f}" class="vr-gridline"/>'
    if has_miss:
        gridlines += (
            f'<line x1="{pad_x}" y1="{miss_y - 10:.1f}" x2="{width - pad_x}" y2="{miss_y - 10:.1f}" '
            f'class="vr-rank-trend-sep"/>'
        )

    # 실측 구간끼리만 잇는다 — 미노출(rank 0)이 낀 자리는 선을 끊는다.
    segments: list[list[tuple[float, float]]] = [[]]
    for (_, rank), point in zip(history, points):
        if rank == 0:
            segments.append([])
            continue
        segments[-1].append(point)
    def _polyline(seg: list[tuple[float, float]]) -> str:
        pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in seg)
        draw_len = _polyline_length(seg)
        draw_attrs = f'stroke-dasharray="{draw_len:.1f}" stroke-dashoffset="{draw_len:.1f}"'
        glow = (
            f'<polyline points="{pts}" class="vr-line-draw" fill="none" stroke="url(#vr-grad-rank)" stroke-width="6" '
            f'stroke-linecap="round" stroke-linejoin="round" opacity="0.16" filter="url(#vr-glow-v2)" {draw_attrs}/>'
        )
        line = (
            f'<polyline points="{pts}" class="vr-line-draw" fill="none" stroke="url(#vr-grad-rank)" stroke-width="2.5" '
            f'stroke-linecap="round" stroke-linejoin="round" {draw_attrs}/>'
        )
        return glow + line

    lines_svg = "".join(_polyline(seg) for seg in segments if len(seg) >= 2)
    dots_svg = "".join(
        (
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" class="vr-rank-trend-miss"/>'
            if rank == 0
            else f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#6da7ec" stroke="#fff" stroke-width="2"/>'
        )
        for (_, rank), (px, py) in zip(history, points)
    )
    # 점 위에 라벨을 놓는다 — 위쪽 여백이 모자라면(맨 위 근처 점) 아래로 내려서
    # 뷰박스 밖으로 잘리지 않게 한다.
    values_svg = "".join(
        f'<text x="{px:.1f}" y="{(py - 10 if py - 10 > 8 else py + 16):.1f}" class="vr-rank-trend-value">'
        + ("미노출" if rank == 0 else f"{rank}위")
        + "</text>"
        for (_, rank), (px, py) in zip(history, points)
    )
    return f'<svg viewBox="0 0 {width} {height}">{gridlines}{lines_svg}{dots_svg}{values_svg}</svg>'


def _render_metrics_panel(metrics: list[dict], latest_rank: dict | None, rank_hist: list[tuple[str, int]]) -> None:
    """조회수 스파크라인 + 순위 추이 그래프(왼쪽, 세로로 쌓임)와 조회수/참여율
    뉴모피즘 스탯 카드(오른쪽)를 한 flex row로 묶는다. 하나의 st.markdown
    호출이라야 flex의 align-items:stretch로 스탯 카드 높이가 왼쪽 콘텐츠
    (그래프 2개) 전체 높이에 자동으로 맞는다.

    현재 순위는 "상위노출 추이" 타이틀 줄에 이어 붙인다 — 정확도 배지는
    빼고 순위·키워드만 보여준다."""
    if metrics:
        latest_metric = metrics[-1]
        views = latest_metric["views"]
        num_html = f'<div class="vr-stat-num"><b>{views:,}</b><span>조회수</span></div>'
        rate = participation_rate(views, latest_metric.get("comments_count"))
        rate_html = (
            f'<div class="vr-stat-secondary"><b>{rate:.1f}%</b><span>참여율</span></div>'
            if rate is not None
            else '<div class="vr-stat-secondary"><b class="empty">—</b><span>참여율</span></div>'
        )
    else:
        num_html = '<div class="vr-stat-num empty"><b>—</b><span>조회수</span></div>'
        rate_html = '<div class="vr-stat-secondary"><b class="empty">—</b><span>참여율</span></div>'

    # 카드마다 순위 데이터 유무가 달라 카드 높이가 들쭉날쭉해지지 않도록,
    # 순위 정보는 없어도 항상 같은 자리(타이틀 줄)에 자리표시 텍스트로 남긴다.
    if latest_rank:
        rank_meta_html = (
            f'<span class="vr-rank-badge">{latest_rank["rank"]}위</span>'
            f'네이버 "{_esc(latest_rank["keyword"])}" · {_esc(latest_rank["search_tab"])}'
        )
    else:
        rank_meta_html = '<span class="vr-rank-badge">—</span>아직 측정된 순위 없음'

    left_blocks = [
        '<div class="vr-chart-box">'
        '<div class="vr-chart-title">조회수 추이</div>'
        f'<div class="vr-sparkline">{_sparkline_svg(metrics)}</div>'
        "</div>",
        '<div class="vr-chart-box">'
        '<div class="vr-chart-title-row"><span class="vr-chart-title">상위노출 추이</span>'
        f'<span class="vr-chart-title-meta">{rank_meta_html}</span></div>'
        # 빈 이력에도 _rank_trend_svg가 그리드라인만 있는 빈 그래프를 안전하게 그린다.
        f'<div class="vr-rank-trend">{_rank_trend_svg(rank_hist)}</div>'
        "</div>",
    ]

    st.markdown(
        f'<div class="vr-metrics-panel">'
        f'<div class="vr-metrics-charts">{"".join(left_blocks)}</div>'
        f'<div class="vr-card-stats">{num_html}{rate_html}</div>'
        f"</div>"
        f'<hr class="vr-metrics-divider">',
        unsafe_allow_html=True,
    )
    if metrics:
        latest_metric = metrics[-1]
        st.caption(f"정확도: {latest_metric['accuracy']} · 최근 수집: {latest_metric['captured_at']}")
    else:
        st.caption("아직 수집된 조회수가 없다.")


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


def _render_keyword_watchlist(summary: dict, contents_by_id: dict) -> None:
    if not summary:
        st.caption("등록된 추적 키워드가 없다.")
        return
    # 키워드마다 st.markdown()을 따로 호출하면 Streamlit이 각 호출을 독립된
    # 블록으로 세로로 쌓아서 카드가 한 줄씩 주르륵 나열된다. 모든 키워드 카드를
    # 하나의 st.markdown 호출로 묶어 .vr-kw-grid 래퍼(3열 grid) 안에 넣어야
    # 카드끼리 가로로 나란히 배치된다.
    cards_html = []
    for keyword, by_tab in summary.items():
        rows_html = [f'<div class="vr-kw-name">"{_esc(keyword)}"</div>']
        # VIEW는 GitHub Actions IP가 네이버 WAF에 막혀 항상 미취득이라 화면에서 제외한다.
        for tab in ("블로그API", "카페API"):
            if tab not in by_tab:
                continue
            tab_rows = by_tab[tab]
            rows_html.append(f'<div class="vr-kw-tab-group"><div class="vr-kw-tab-head">{_esc(tab)}')
            matched_rows = [r for r in tab_rows if r["rank"] is not None]
            if matched_rows:
                rows_html.append(f'<span class="vr-kw-tab-count"> · 상위노출 {len(matched_rows)}건</span></div>')
                for row in matched_rows:
                    matched = contents_by_id.get(row["content_id"])
                    matched_label = _esc(matched.get("title") or matched["url"]) if matched else "(콘텐츠 정보 없음)"
                    rows_html.append(
                        f'<div class="vr-kw-content-row">'
                        f'<div class="vr-kw-content-row-top"><span class="vr-rank-badge">{row["rank"]}위</span>'
                        f'<span class="vr-kw-content-title">{matched_label}</span></div>'
                        f'<span class="vr-kw-content-date">{_esc(row["captured_at"])} 수집</span></div>'
                    )
            else:
                rows_html.append('</div><div class="vr-kw-tab-empty">아직 잡히는 콘텐츠 없음</div>')
            rows_html.append("</div>")
        if len(rows_html) == 1:
            rows_html.append('<div class="vr-kw-tab-empty">아직 수집된 적 없음.</div>')
        cards_html.append(f'<div class="vr-kw-card">{"".join(rows_html)}</div>')
    st.markdown(f'<div class="vr-kw-grid">{"".join(cards_html)}</div>', unsafe_allow_html=True)


repo = ReportRepo()

_inject_design_system()
st.markdown(
    f'<div class="vr-amb"><div class="vr-amb-top">'
    f'<div class="vr-amb-brand">바이럴 <span>리포팅</span></div>'
    f'<div class="vr-amb-user">{_esc(email)}</div>'
    f'</div><div class="vr-amb-title">리포트 대시보드</div></div>',
    unsafe_allow_html=True,
)

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

if not contents:
    st.info("이 캠페인에는 등록된 콘텐츠가 없다.")
    st.stop()

# -- 겹치는 히어로 카드: 채널 비중 도넛 + 채널별 네이버 상위노출 콘텐츠 수 ----
# (다른 종합 KPI는 일부러 안 둔다 — brainstorming 결정: 콘텐츠 단위 카드가 더 중요)
# .vr-amb 헤더 아래로 겹쳐 보이도록, 기존 콘텐츠 카드와 같은 marker+:has() 패턴으로
# 이 컨테이너의 stVerticalBlock 전체를 CSS로 스코프한다(위 .vr-hero-marker 참고).

with st.container(border=True):
    st.markdown('<span class="vr-hero-marker"></span>', unsafe_allow_html=True)

    _render_channel_donut(channel_distribution(contents))

    st.subheader("채널별 네이버 상위노출 콘텐츠 수")

    exposure_counts = exposure_counts_by_channel(contents, all_ranks)
    _render_exposure_rank_list(exposure_counts)

# -- 캠페인 키워드 순위 --------------------------------------------------

st.subheader("캠페인 키워드 순위")

# keyword_ranks()는 캠페인으로 필터링하지 않는다(스키마에 campaign_id가 없다) —
# 이 캠페인에 등록된 키워드 문자열로만 걸러낸다. 알려진 한계: 다른 캠페인이
# 우연히 똑같은 키워드 문자열을 쓰면 그 결과도 섞여 보인다(design.md §3.2 참고,
# 스키마 변경 없이 가기로 한 결정).
target_keywords = list(dict.fromkeys(k["keyword"] for k in repo.target_keywords(campaign_id=campaign_id)))
keyword_ranks_for_campaign = [r for r in repo.keyword_ranks() if r["keyword"] in target_keywords]
contents_by_id = {c["content_id"]: c for c in repo.contents(campaign_id=campaign_id)}

keyword_summary = keyword_rank_summary(keyword_ranks_for_campaign, target_keywords)
_render_keyword_watchlist(keyword_summary, contents_by_id)

# -- 콘텐츠 카드 --------------------------------------------------------

st.subheader("콘텐츠별 상세")

# 조회수 높은 순으로 노출한다. 아직 조회수가 0(=수집 전)인 콘텐츠는 맨
# 아래로 보내되, 그 안에서는 원래 등록 순서를 유지한다(sorted는 안정 정렬).
contents_sorted = sorted(
    contents, key=lambda c: (latest_views(all_metrics, c["content_id"]) == 0, -latest_views(all_metrics, c["content_id"]))
)

for content in contents_sorted:
    cid = content["content_id"]
    views = latest_views(all_metrics, cid)
    with st.container(border=True):
        _render_card_header(content, is_empty=(views == 0))

        metrics = sorted((m for m in all_metrics if m["content_id"] == cid), key=lambda m: m["captured_at"])
        content_ranks = [r for r in all_ranks if r["content_id"] == cid]
        _render_metrics_panel(metrics, latest_rank_row(all_ranks, cid), rank_history(content_ranks))

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
