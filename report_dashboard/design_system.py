"""디자인 시스템 v3 — 토큰(라이트/다크 쌍)·컴포넌트 CSS·스트림릿 크롬 재스킨·테마 훅.

정본은 목업(project/active/.../redesign-v3/base.css, mix.css, p-exposure.html,
p-content.html, p-admin.html). 값이 바뀌면 그 목업과 이 파일을 같이 고친다.

테마 감지 원리(2026-09-03 스파이크 실측): 스트림릿은 테마 상태를 DOM에 남기지 않고
`st.context.theme`는 다음 rerun까지 이전 값이다. 그래서 components.html iframe(same-origin)에서
부모 body 배경 밝기를 400ms 폴링해 <html data-theme>를 세팅하고, 우리 CSS 토큰은 그 속성에 스코프한다.
"""

import streamlit as st
import streamlit.components.v1 as components

_FONTS = (
    "@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');"
    "@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');"
)

# base.css :root 본문 그대로(주석 포함, 값 변경 금지). --invert-*·--shadow는 v3 반전
# 타일·그림자 컴포넌트가 쓰는 토큰이라 스펙 §3.1~3.3 표에 없어도 목업 원문을 따라 유지한다.
_LIGHT = """
  color-scheme: light;
  /* surfaces: page → s1(panel) → s2(card) → s3(inset) */
  --page: #f4f4f1;
  --s1: #fafaf8;
  --s2: #ffffff;
  --s3: #efefeb;
  --ink: #131311;
  --ink-2: #55544f;
  --muted: #8b8a84;
  --hair: #e3e2db;
  --border: rgba(19,19,17,0.10);
  --border-2: rgba(19,19,17,0.16);
  /* 브랜드 액센트 (마녀공장 마스터 옐로우) — 마크·활성상태·강조선 전용 */
  --accent: #f0b90b;
  --accent-ink: #8a6400;           /* 라이트에서 텍스트로 쓸 때 (4.5:1) */
  --accent-wash: rgba(240,185,11,0.14);
  --accent-on: #1a1400;            /* 액센트 위 텍스트 */
  --invert-bg: #161614;            /* 반전 타일(잉크 표면) */
  --invert-ink: #f4f3ee;
  --invert-muted: rgba(244,243,238,0.55);
  /* 채널 팔레트 (validate_palette.js 통과, 이 순서 고정) */
  --ch-instagram: #c94b78;
  --ch-blog: #2a78d6;
  --ch-youtube: #eb6834;
  --ch-cafe: #1baf7a;
  --ch-community: #4a3aa7;
  --good: #0a7d0a;
  --bad: #c43535;
  --grid: #e3e2db;
  --shadow: 0 1px 0 rgba(19,19,17,0.04), 0 12px 32px -20px rgba(19,19,17,0.18);
  --wash: #f0b90b; --wash-op: 0.10;
  --r-card: 14px; --r-btn: 8px; --r-pill: 999px;
  --font: "Pretendard Variable", Pretendard, -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  --ease: cubic-bezier(0.16, 1, 0.3, 1);
"""
_DARK = """
  color-scheme: dark;
  --page: #0f0f0e; --s1: #161615; --s2: #1c1c1a; --s3: #232321;
  --ink: #f3f2ec; --ink-2: #b6b5ac; --muted: #7e7d77;
  --hair: #2a2a27; --border: rgba(255,255,255,0.09); --border-2: rgba(255,255,255,0.15);
  --accent: #f5c542; --accent-ink: #f5c542; --accent-wash: rgba(245,197,66,0.14); --accent-on: #1a1400;
  --invert-bg: #f3f2ec; --invert-ink: #131311; --invert-muted: rgba(19,19,17,0.55);
  --ch-instagram: #d55181; --ch-blog: #3987e5; --ch-youtube: #d95926; --ch-cafe: #199e70; --ch-community: #9085e9;
  --good: #35b535; --bad: #e66767; --grid: #2a2a27;
  --shadow: 0 1px 0 rgba(0,0,0,0.3), 0 16px 40px -24px rgba(0,0,0,0.7);
  --wash: #f3f2ec; --wash-op: 0.06;
"""

# 헤더 계열(.hdr/.hdr-brand/.hdr-logo/.hdr-tabs/.hdr-right/.sel/.icon-btn/.avatar)은
# 여기 넣지 않는다 — base.css는 정적 HTML 헤더용이고, 실제 스트림릿 헤더는 header.py
# (Task 5)가 렌더링하며 CHROME_CSS의 .hdr-marker 계열 규칙이 그 유일한 소스다. 두 곳에
# 같은 클래스명을 다른 값으로 정의해두면 로드 순서에 의존하는 죽은 코드가 된다(2026-09
# 리뷰 지적, fix round 1).
TOKENS_CSS = f"""
{_FONTS}
:root {{{_LIGHT}}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{{_DARK}}} }}
:root[data-theme="dark"] {{{_DARK}}}

* {{ box-sizing: border-box; }}
/* body 리셋은 여기서 안 한다(Task 13 fix round 3) — body는 스트림릿이 소유한다.
   전엔 body{{background:var(--page);...}}를 우리가 깔아서 테마 훅(부모 body 배경
   밝기를 읽어 다크/라이트 판정)이 스트림릿의 실제 테마 배경이 아니라 항상 우리
   라이트 토큰만 보는 순환 참조가 생겨 다크 모드 전환이 죽어 있었다. 배경·잉크는
   [data-testid="stAppViewContainer"]에만 적용한다(CHROME_CSS). */
a {{ color: inherit; text-decoration: none; }}
"""

# mix.css 전문(D4 공용 컴포넌트) + base.css의 공용 타이포·차트·모션 블록 + 페이지별
# <style> 추가분(p-exposure/p-content/p-admin). 목업 파일에서 그대로 복사한 문자열 리터럴 —
# 런타임에 파일을 읽지 않는다(배포 미러에 원본 파일이 없을 수 있어서).
# v3의 `.lrow*` 오버레이 블록(행마다 st.container + 행 클릭용 투명 st.button)은 Task 7에서
# 삭제했다 — 콘텐츠 리스트는 iframe 안 `<table>`(report_common.content_list_rows_html)이 그리고
# 행 클릭은 JS가 처리하므로, 스트림릿 컨테이너를 :has()로 잡아 꾸미던 규칙엔 대상이 없다.
COMPONENT_CSS = """
/* ===== base.css: 공용 타이포 ===== */
.num { font-variant-numeric: tabular-nums; }
.mono { font-family: var(--mono); font-variant-numeric: tabular-nums; }
.label { font-size: 12px; font-weight: 500; color: var(--muted); letter-spacing: 0.01em; }
.h-sec { font-size: 15px; font-weight: 600; letter-spacing: -0.01em; margin: 0; }
.figure { font-weight: 700; letter-spacing: -0.03em; line-height: 1; }
.delta { font-size: 12px; font-weight: 600; }
.delta.up { color: var(--good); } .delta.down { color: var(--bad); } .delta.flat { color: var(--muted); }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; vertical-align: middle; }
.pill { display: inline-flex; align-items: center; gap: 6px; height: 22px; padding: 0 9px; border-radius: var(--r-pill); font-size: 11.5px; font-weight: 600; background: var(--s3); color: var(--ink-2); }
.pill.acc { background: var(--accent-wash); color: var(--accent-ink); }
.tag-ex { font-size: 10.5px; color: var(--muted); border: 1px dashed var(--border-2); padding: 1px 6px; border-radius: 4px; }
/* ===== base.css: 차트 공용 ===== */
.chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.chart .grid-l { stroke: var(--grid); stroke-width: 1; }
.chart .axis-t { fill: var(--muted); font-size: 10.5px; font-family: var(--font); }
.chart .ln { fill: none; stroke: var(--accent); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.chart .ln.ink { stroke: var(--ink); }
.chart .wash { fill: var(--wash); opacity: var(--wash-op); }
.chart .end { fill: var(--accent); stroke: var(--s2); stroke-width: 2; }
.chart .end.ink { fill: var(--ink); }
.chart .lbl { fill: var(--ink); font-size: 11px; font-weight: 600; font-family: var(--font); }
.hbar { height: 8px; border-radius: 4px; background: var(--s3); overflow: hidden; }
.hbar > i { display: block; height: 100%; border-radius: 4px; }
/* ===== base.css: 모션 ===== */
@media (prefers-reduced-motion: no-preference) {
  .reveal { animation: reveal-up linear both; animation-timeline: view(); animation-range: entry 0% entry 38%; }
  @keyframes reveal-up { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: none; } }
  .draw { animation: draw-ln linear both; animation-timeline: view(); animation-range: entry 10% entry 70%; }
  @keyframes draw-ln { to { stroke-dashoffset: 0; } }
  .grow > i { transform-origin: left; animation: grow-x linear both; animation-timeline: view(); animation-range: entry 10% entry 60%; }
  @keyframes grow-x { from { transform: scaleX(0); } to { transform: scaleX(1); } }
  .fade-late { animation: fade-in linear both; animation-timeline: view(); animation-range: entry 40% entry 80%; }
  @keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
  /* 첫 화면(뷰포트 안에 이미 있는 것)은 로드 애니메이션으로 */
  .enter { animation: enter-up 0.7s var(--ease) both; animation-delay: calc(var(--i, 0) * 70ms); }
  @keyframes enter-up { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
}
/* ===== mix.css 전문 — D4(에디토리얼 × 프로덕트) 공용 컴포넌트, 4페이지가 같이 쓴다 ===== */
.wrap { max-width: 1200px; margin: 0 auto; padding: 40px 28px 96px; }
/* 제목 블록 + 컨트롤 */
.title { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; }
.title h1 { font-size: 32px; font-weight: 700; letter-spacing: -0.03em; margin: 0 0 6px; line-height: 1.1; }
.title p { margin: 0; color: var(--ink-2); font-size: 13.5px; }
.title p b { color: var(--ink); font-weight: 600; }
.ctrl { display: flex; gap: 8px; align-items: center; padding-bottom: 2px; flex-wrap: wrap; justify-content: flex-end; }
.chip { height: 32px; padding: 0 11px; border-radius: 8px; border: 1px solid var(--border); background: var(--s2); font-size: 12.5px; font-weight: 500; display: inline-flex; align-items: center; gap: 6px; color: var(--ink-2); cursor: pointer; }
.chip.on { border-color: var(--border-2); color: var(--ink); }
.chip.acc { background: var(--accent); border-color: transparent; color: var(--accent-on); font-weight: 600; }
.btn { height: 32px; padding: 0 13px; border-radius: 8px; background: var(--ink); color: var(--page); font-size: 12.5px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; border: 0; }
.btn.ghost { background: transparent; color: var(--ink); border: 1px solid var(--border-2); }
hr.rule { border: 0; border-top: 1px solid var(--hair); margin: 0; }
/* 스탯 스트립 */
.strip { display: grid; grid-template-columns: repeat(4, 1fr); margin: 28px 0; }
.stat { padding: 6px 26px 6px 0; display: grid; grid-template-columns: 1fr 112px; gap: 8px 12px; align-items: end; }
.stat + .stat { padding-left: 26px; border-left: 1px solid var(--hair); }
.stat .label { grid-column: 1 / -1; }
.stat .figure { font-size: 30px; }
.stat .figure small { font-size: 12.5px; color: var(--muted); font-weight: 500; margin-left: 4px; letter-spacing: 0; }
.stat .spark { grid-row: 2 / 4; align-self: end; }
.stat .delta { font-family: var(--mono); font-weight: 500; font-size: 11.5px; white-space: nowrap; }
.stat .big-rank { grid-row: 2 / 4; align-self: center; justify-self: end; display: inline-flex; flex-direction: column; align-items: center; justify-content: center; width: 72px; height: 56px; border-radius: 10px; background: var(--accent-wash); color: var(--accent-ink); }
.stat .big-rank b { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; line-height: 1; }
.stat .big-rank span { font-size: 10.5px; font-weight: 600; margin-top: 3px; }
/* 섹션 헤더 + 세그먼트 */
.sec-h { display: flex; align-items: center; gap: 12px; margin: 30px 0 14px; }
.sec-h .sp { flex: 1; }
.sec-h a { font-size: 12.5px; color: var(--ink-2); font-weight: 500; }
.seg { display: inline-flex; background: var(--s3); padding: 2px; border-radius: 8px; }
.seg span { padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500; color: var(--ink-2); cursor: pointer; }
.seg span.on { background: var(--s2); color: var(--ink); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,0.06); }
.hero-chart { margin: 0 0 8px; }
/* 표 */
table { width: 100%; border-collapse: collapse; }
th { text-align: left; font-size: 11.5px; font-weight: 500; color: var(--muted); padding: 0 8px 10px 0; white-space: nowrap; border-bottom: 1px solid var(--hair); }
th.r, td.r { text-align: right; }
td { padding: 10px 8px 10px 0; border-bottom: 1px solid var(--hair); font-size: 13px; vertical-align: middle; }
td .label { font-size: 12px; }
tr.is-sel td { background: var(--accent-wash); }
tr.is-sel td:first-child { box-shadow: inset 3px 0 0 var(--accent); padding-left: 10px; }
.rank { white-space: nowrap; display: inline-flex; align-items: center; justify-content: center; min-width: 44px; height: 24px; padding: 0 8px; border-radius: 7px; font-family: var(--mono); font-size: 12.5px; font-weight: 600; }
.rank.acc { background: var(--accent-wash); color: var(--accent-ink); }
.rank.none { color: var(--muted); font-weight: 500; }
.who { font-weight: 600; }
td .spark { width: 84px; height: 22px; }
td .spark svg { width: 84px; height: 22px; display: block; }
.inline-bar { display: inline-block; width: 96px; height: 6px; background: var(--s3); border-radius: 3px; vertical-align: middle; margin-right: 10px; overflow: hidden; }
.inline-bar i { display: block; height: 100%; background: var(--ink); border-radius: 3px; }
/* 채널 바 */
.ch-row { display: grid; grid-template-columns: 96px 1fr 64px; gap: 14px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--hair); }
.ch-row .n { font-weight: 500; display: flex; align-items: center; gap: 8px; font-size: 13px; }
.ch-row .v { text-align: right; font-weight: 600; }
.ch-row .v small { color: var(--muted); font-weight: 500; margin-left: 4px; }
.mini { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 22px; }
.mini .figure { font-size: 26px; margin: 4px 0 2px; }
.mini .figure small { font-size: 12px; color: var(--muted); font-weight: 600; letter-spacing: 0; }
.mini .sub { font-size: 12px; color: var(--ink-2); }
.recent { display: flex; gap: 28px; color: var(--ink-2); font-size: 12.5px; margin-top: 28px; }
.recent b { color: var(--ink); font-weight: 600; }
/* 2단 */
.two { display: grid; grid-template-columns: 7fr 5fr; gap: 56px; margin-top: 36px; }
/* 빈 상태 */
.empty { padding: 22px 0; color: var(--muted); font-size: 12.5px; border-bottom: 1px solid var(--hair); }
.empty b { color: var(--ink-2); font-weight: 600; display: block; margin-bottom: 3px; font-size: 13px; }
/* 폼(등록) */
.field { display: grid; gap: 6px; }
.field label { font-size: 12px; font-weight: 500; color: var(--ink-2); }
.field .in { height: 36px; border: 1px solid var(--border-2); border-radius: 8px; background: var(--s2); padding: 0 12px; font-size: 13px; display: flex; align-items: center; color: var(--ink); }
.field .in.ph { color: var(--muted); }
.field .in.sel2 { justify-content: space-between; }
.field .in.sel2::after { content: ""; width: 7px; height: 7px; border-right: 1.5px solid var(--muted); border-bottom: 1.5px solid var(--muted); transform: rotate(45deg) translateY(-2px); }
.field .help { font-size: 11.5px; color: var(--muted); }
.form-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px 16px; align-items: end; }
.form-grid .span2 { grid-column: span 2; }
.form-grid .span3 { grid-column: span 3; }
.status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; }
.status i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.status.ok { color: var(--good); } .status.ok i { background: var(--good); }
.status.fail { color: var(--bad); } .status.fail i { background: var(--bad); }
.status.skip { color: var(--muted); } .status.skip i { background: var(--muted); }

/* 채널 로고 */
.ch-ico { display: inline-block; vertical-align: middle; color: var(--ink-2); flex: none; }
.ch-cell { display: inline-flex; align-items: center; gap: 7px; }

/* ===== p-exposure.html 전용 <style> ===== */
/* 키워드 선택 칩 줄 */
.kw-chips { display: flex; gap: 6px; flex-wrap: wrap; margin: 6px 0 18px; }
.kw-chips .chip b { font-family: var(--mono); font-size: 11.5px; font-weight: 600; margin-left: 2px; }
.kw-chips .chip.on { background: var(--ink); color: var(--page); border-color: transparent; }
.kw-chips .chip.on b { color: var(--accent); }
/* SERP 2열: 블로그 | 카페 */
.serp { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }
.serp-h { display: flex; align-items: baseline; gap: 10px; padding-bottom: 10px; border-bottom: 1px solid var(--hair); }
.serp-h .h-sec { font-size: 14px; }
.serp-h .sp { flex: 1; }
.srow { display: grid; grid-template-columns: 30px 1fr auto; gap: 12px; align-items: center; padding: 9px 0; border-bottom: 1px solid var(--hair); font-size: 13px; }
.srow .r { font-family: var(--mono); font-size: 12px; color: var(--muted); font-weight: 500; }
.srow .t { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--ink-2); }
.srow .src { font-size: 11.5px; color: var(--muted); white-space: nowrap; }
.srow.ours { background: var(--accent-wash); margin: 0 -10px; padding-left: 10px; padding-right: 10px; border-radius: 6px; border-bottom-color: transparent; }
.srow.ours .r { color: var(--accent-ink); font-weight: 700; }
.srow.ours .t { color: var(--ink); font-weight: 600; }
.srow.ours .src { color: var(--accent-ink); font-weight: 600; }
.beyond { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 12px 0 4px; font-size: 12.5px; color: var(--ink-2); }
.beyond .rank { min-width: 0; } .beyond .label { white-space: nowrap; }
/* 우측 레일 */
.rail .sec-h { margin-top: 0; }
.rail section + section { margin-top: 34px; }
.wl { display: grid; grid-template-columns: 1fr 56px 90px 60px; gap: 10px; align-items: center; padding: 9px 0; border-bottom: 1px solid var(--hair); font-size: 13px; }
.wl .k small { color: var(--muted); margin-left: 6px; font-size: 11.5px; }
.wl .d { font-family: var(--mono); font-size: 11.5px; text-align: right; }
.wl .spark svg { width: 90px; height: 22px; display: block; }
.wl .rk { text-align: right; }
.lead { display: grid; grid-template-columns: 22px 1fr 1fr auto; gap: 10px; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--hair); font-size: 13px; }
.lead .n { font-family: var(--mono); color: var(--muted); font-size: 12px; }
.lead .v { font-family: var(--mono); font-size: 12.5px; text-align: right; }

/* 점유율 */
.legend { display: flex; gap: 14px; font-size: 11.5px; color: var(--ink-2); }
.legend i { margin-right: 5px; }
.share-grid { display: grid; grid-template-columns: 8fr 4fr; gap: 48px; }
.sh { display: grid; grid-template-columns: 120px 1fr 92px; gap: 14px; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--hair); font-size: 13px; }
.sh .k { font-weight: 500; } .sh .k small { color: var(--muted); margin-left: 6px; font-size: 11.5px; }
.sh .v { text-align: right; font-family: var(--mono); font-size: 12.5px; } .sh .v small { color: var(--muted); font-family: var(--font); margin-left: 4px; }
.stack { display: flex; height: 12px; border-radius: 6px; overflow: hidden; gap: 2px; background: var(--s3); }
.stack i { display: block; height: 100%; transform-origin: left; }
.stack i.ours { box-shadow: inset 0 0 0 1.5px var(--ink); background: var(--accent) !important; }
.stack-lg { display: grid; gap: 6px; margin-top: 12px; font-size: 12.5px; }
.stack-lg div { display: flex; justify-content: space-between; } .stack-lg b { font-family: var(--mono); font-weight: 600; }
.share-side .stack { height: 16px; margin-top: 8px; }

/* ===== p-content.html 전용 <style> ===== */
.md { display: grid; grid-template-columns: 7fr 5fr; gap: 44px; margin-top: 8px; align-items: start; }
/* 리스트 */
.list td { padding: 11px 0; cursor: pointer; }
.list tr:hover td { background: var(--s1); }
.list .t { display: flex; flex-direction: column; gap: 2px; }
.list .t small { color: var(--muted); font-size: 11.5px; font-weight: 400; }
.list .chev { color: var(--muted); font-size: 12px; }
.list .inline-bar { width: 64px; }
.list td.r { white-space: nowrap; }
/* 상세 패널: 박스 대신 왼쪽 헤어라인 + sticky */
.detail { position: sticky; top: 84px; padding-left: 40px; border-left: 1px solid var(--hair); }
.detail .dh { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.detail h2 { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; margin: 0 0 4px; }
.detail .meta { color: var(--ink-2); font-size: 12.5px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.detail .meta a { color: var(--accent-ink); font-weight: 600; }
.detail .kpis { display: grid; grid-template-columns: repeat(3, 1fr); margin: 20px 0 6px; }
.detail .kpi { padding: 4px 18px 4px 0; }
.detail .kpi + .kpi { padding-left: 18px; border-left: 1px solid var(--hair); }
.detail .kpi .figure { font-size: 26px; margin: 4px 0 2px; }
.detail .kpi .figure small { font-size: 12px; color: var(--muted); font-weight: 600; letter-spacing: 0; }
.detail .kpi .sub { font-size: 11.5px; color: var(--muted); }
.detail .sec-h { margin: 22px 0 8px; }
.detail .sec-h .h-sec { font-size: 13.5px !important; }
.cm { padding: 9px 0; border-bottom: 1px solid var(--hair); font-size: 13px; color: var(--ink-2); display: grid; grid-template-columns: 1fr auto; gap: 12px; }
.cm b { color: var(--ink); font-weight: 600; margin-right: 6px; }
.cm small { color: var(--muted); font-size: 11.5px; white-space: nowrap; }
.acc-note { font-size: 11.5px; color: var(--muted); margin-top: 8px; }

/* ===== p-admin.html 전용 <style> ===== */
.adm { display: grid; grid-template-columns: 180px 1fr; gap: 56px; margin-top: 28px; align-items: start; }
.toc { position: sticky; top: 84px; display: grid; gap: 2px; }
.toc a { padding: 7px 10px; border-radius: 7px; font-size: 13px; color: var(--ink-2); display: flex; justify-content: space-between; }
.toc a.on { background: var(--s3); color: var(--ink); font-weight: 600; }
.toc a small { color: var(--muted); font-family: var(--mono); font-size: 11px; }
.blk { padding: 26px 0 30px; border-bottom: 1px solid var(--hair); }
.blk:first-child { padding-top: 6px; }
.blk .sec-h { margin: 0 0 16px; }
.blk .sec-h .h-sec { font-size: 16px !important; }
.blk .sec-h p { margin: 0; font-size: 12.5px; color: var(--muted); }
.blk table { margin-top: 18px; }
.blk td, .blk th { font-size: 12.5px; }
.blk td { padding: 8px 0; }
.actions { display: flex; gap: 8px; align-items: center; }
.or { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 11.5px; margin: 16px 0; }
.or::before, .or::after { content: ""; flex: 1; border-top: 1px dashed var(--border-2); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }
.hs { display: grid; grid-template-columns: 1fr auto auto auto; gap: 16px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--hair); font-size: 13px; }
.hs .n b { font-weight: 600; display: block; }
.hs .n small { color: var(--muted); font-size: 11.5px; }
.hs .mono { font-size: 12px; color: var(--ink-2); }
.role { font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 5px; background: var(--s3); color: var(--ink-2); }
"""

# 스트림릿 자체 요소 재스킨(실서버 Task 13에서 testid 실측 후 보정 가능).
# .hdr-logo/.hdr-brand/.avatar는 이 블록이 유일한 소스다 — 목업 base.css의 정적 헤더
# 계열(.hdr/.hdr-tabs/.sel/.icon-btn 등)은 TOKENS_CSS에서 의도적으로 제외했다.
CHROME_CSS = """
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
[data-testid="stAppViewContainer"] { font-family: var(--font) !important; background: var(--page) !important; color: var(--ink) !important; font-size: 14px !important; line-height: 1.5 !important; -webkit-font-smoothing: antialiased; font-feature-settings: "ss05"; }
/* Task 13 fix round 5: body 리셋 제거(round 3)로 body { font-size: 14px; line-height: 1.5;
   -webkit-font-smoothing: antialiased; font-feature-settings: "ss05"; }도 같이 사라져서, 클래스
   없이 쓰는 텍스트(3_등록.py의 st.caption/st.write, header.py, 인증 화면 등)가 스트림릿 기본
   타이포로 돌아가고 Pretendard ss05 숫자꼴도 빠졌었다 — body가 아니라 여기(앱 컨테이너)에
   그 네 선언을 다시 건다. */
[data-testid="stHeader"] { background: transparent !important; }          /* ⋮ 메뉴(테마 토글)만 남긴다 */
[data-testid="stMainBlockContainer"] { max-width: 1256px; padding: 0 28px 96px !important; }
[data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 { font-family: var(--font) !important; }
[data-testid="stMarkdownContainer"] a { color: inherit; text-decoration: none !important; }
/* 스트림릿이 마크다운 컨테이너에 자기 폰트 스택을 걸어서 우리 마크다운 조각(헤더·등록·관리자)이
   Pretendard를 잃는다 — 컨테이너 **자체**에만 걸고 자식은 상속으로 받게 한다. `:where(*)` 같은
   자손 셀렉터로 내리면 COMPONENT_CSS의 `.mono`(주입 순서상 앞, 명시도 동급)가 뒤에 오는 이
   규칙에 밀려 JetBrains Mono가 죽는다 — 상속은 자식 요소 자신의 규칙에 항상 진다(Task 7). */
[data-testid="stMarkdownContainer"] { font-family: var(--font) !important; }
/* 위젯 재스킨 — 스펙 §4 칩/세그먼트/인풋 규격 */
[data-testid="stSelectbox"] [data-baseweb="select"] > div { background: var(--s2) !important; border: 1px solid var(--border-2) !important; border-radius: var(--r-btn) !important; min-height: 34px; font-size: 13px; }
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stTextArea"] textarea { background: var(--s2) !important; border: 1px solid var(--border-2) !important; border-radius: var(--r-btn) !important; color: var(--ink) !important; font-size: 13px; }
[data-testid="stButton"] > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stDownloadButton"] > button { height: 32px; padding: 0 13px; border-radius: var(--r-btn) !important; background: var(--ink) !important; color: var(--page) !important; border: 0 !important; font-size: 12.5px; font-weight: 600; }
[data-testid="stDownloadButton"] button { white-space: nowrap; }
/* pills·segmented_control 실측(streamlit 1.58): stPills/stSegmentedControl
   래퍼 testid는 안 잡힌다 — 실제 DOM은 stButtonGroup 안에 stBaseButton-pills*
   /stBaseButton-segmented_control* 버튼이다(Task 13 실서버 확인). */
[data-testid="stButtonGroup"] { gap: 6px; }
[data-testid="stButtonGroup"] button[data-testid^="stBaseButton-pills"],
[data-testid="stButtonGroup"] button[data-testid^="stBaseButton-segmented_control"] {
    height: 32px !important; border-radius: 8px !important; border: 1px solid var(--border) !important;
    background: var(--s2) !important; color: var(--ink-2) !important; font-size: 12.5px !important;
    font-weight: 500 !important; padding: 0 11px !important;
}
[data-testid="stButtonGroup"] button[data-testid="stBaseButton-pillsActive"] {
    border-color: var(--border-2) !important; color: var(--ink) !important; font-weight: 600 !important; background: var(--s2) !important;
}
[data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"] {
    border-color: var(--border-2) !important; color: var(--ink) !important; font-weight: 600 !important; background: var(--s2) !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}
/* page_link 실측: 실제 앵커 testid는 stPageLink-NavLink(래퍼는 stPageLink 그대로) —
   구 셀렉터도 유지한다(회귀 대비). aria-current가 안 붙으므로 활성 탭은 header.py가
   페이지 링크 대신 .hdr-tab.on 마크다운으로 그린다(§9.2). */
[data-testid="stPageLink"] a, [data-testid="stPageLink-NavLink"] {
    padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500;
    color: var(--ink-2) !important; background: transparent !important;
}
[data-testid="stPageLink-NavLink"] p { color: inherit !important; }
[data-testid="stPageLink"] a[aria-current="page"], [data-testid="stPageLink"] a[data-active="true"] { background: var(--s2); color: var(--ink) !important; font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,0.06); }
.hdr-tab { display: inline-block; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500; color: var(--ink-2); }
.hdr-tab.on { background: var(--s2); color: var(--ink); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,0.06); }
/* 커스텀 헤더 행: header.py가 심는 .hdr-marker를 :has()로 잡아 sticky 처리 */
.hdr-marker { display: none; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) { position: sticky; top: 0; z-index: 10; margin: 0 -28px; padding: 10px 28px; background: color-mix(in srgb, var(--page) 86%, transparent); backdrop-filter: blur(12px); border-bottom: 1px solid var(--hair); }
/* 실측: .hdr-logo span이 stMarkdownContainer 안에서 display:block으로 계산돼
   브랜드 텍스트가 로고 아래로 줄바꿈됐다 — 래퍼를 flex로 강제하고 로고는 grid로 고정. */
.hdr-brand { display: flex !important; align-items: center; gap: 10px; }
.hdr-logo { width: 30px; height: 30px; border-radius: 8px; background: var(--accent); display: grid !important; place-items: center; color: var(--accent-on); font-weight: 800; font-size: 13px; }
.hdr-brand b { font-size: 14px; font-weight: 700; display: block; line-height: 1.1; } .hdr-brand span { font-size: 11px; color: var(--muted); display: block; }
.avatar { width: 34px; height: 34px; border-radius: 50%; background: var(--s3); border: 1px solid var(--border); display: inline-grid; place-items: center; font-size: 11px; font-weight: 700; color: var(--ink-2); }
/* 실측: 계정 팝오버 트리거("HW" 이니셜)가 좁아서 두 줄로 줄바꿈됐다 — 최소 폭 확보.
   실제 트리거 버튼 testid는 stPopoverButton(래퍼는 stPopover) — 둘 다 잡아둔다. */
[data-testid="stPopover"] button, [data-testid="stPopoverButton"] { min-width: 38px; height: 34px; border-radius: 50% !important; padding: 0 8px !important; white-space: nowrap; }
/* v4.1 헤더 재스킨(스펙 §11.1) — 목업 base.css .hdr 규격: 60px 한 줄, 탭 묶음 s3 필, 셀렉트 34px, 아바타 34px 원 */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) { height: 60px !important; min-height: 60px; padding: 0 28px !important; display: flex; flex-direction: column; justify-content: center; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) > [data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] { align-items: center; }
/* 가운데 탭 묶음: 셀렉트/팝오버가 없는 중첩 가로 블록 = 탭 3개 */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stColumn"] [data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]:has([data-testid="stPageLink-NavLink"], .hdr-tab):not(:has([data-testid="stSelectbox"], [data-testid="stPopover"])) {
    display: inline-flex; align-items: center; min-height: 38px !important; height: 38px; box-sizing: border-box; width: fit-content; margin: 0 auto; gap: 4px !important; padding: 3px; border-radius: 10px; background: var(--s3); }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stColumn"] [data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]:not(:has([data-testid="stSelectbox"], [data-testid="stPopover"])) > div { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
/* 오른쪽: 셀렉트 · 등록 탭 · 아바타 — 우측 정렬, 간격 8 */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stColumn"] [data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) { justify-content: flex-end; gap: 8px !important; align-items: center; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stColumn"] [data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > div { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stSelectbox"] { width: 200px; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stSelectbox"] [data-baseweb="select"] > div { min-height: 34px !important; height: 34px; font-weight: 500; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stSelectbox"] [data-baseweb="select"] > div > div { padding-top: 0; padding-bottom: 0; line-height: 32px; }
[data-testid="stPageLink-NavLink"] { min-height: 0 !important; height: 32px; display: inline-flex !important; align-items: center; margin: 0 !important; }
[data-testid="stPageLink"] { width: auto !important; }
.hdr-tab { display: inline-flex !important; align-items: center; height: 32px; line-height: 20px; }
/* 활성 탭(마크다운 span)의 줄상자를 32px로 맞춰 링크 탭(앵커 32px)과 같은 높이에 앉힌다.
   실측(1.58): stElementContainer가 page_link에 margin ±6px, stMarkdownContainer에 margin-bottom -16px을 걸어
   열 박스(20px/17px)가 내용(32px)보다 작아져 가운데 정렬이 어긋났다 — 탭 묶음 안에서는 그 음수 마진을 0으로. */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stColumn"] [data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]:not(:has([data-testid="stSelectbox"])) [data-testid="stElementContainer"] { margin: 0 !important; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stColumn"] [data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]:not(:has([data-testid="stSelectbox"])) [data-testid="stMarkdownContainer"] { margin: 0 !important; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stColumn"] [data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"]:not(:has([data-testid="stSelectbox"])) [data-testid="stMarkdownContainer"] p { line-height: 32px !important; margin: 0 !important; }
/* 스트림릿 마크다운 p 여백 제거(헤더 안) */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stMarkdownContainer"] p { margin: 0; }
/* 아바타 팝오버: 34px 원, 캐럿 제거 */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stPopoverButton"] { width: 34px !important; min-width: 34px !important; height: 34px !important; min-height: 34px !important; padding: 0 !important; background: var(--s3) !important; border: 1px solid var(--border) !important; color: var(--ink-2) !important; font-size: 11px !important; font-weight: 700 !important; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stPopoverButton"] svg { display: none; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) [data-testid="stPopoverButton"] > div { display: flex; justify-content: center; }
/* 헤더와 본문 iframe 사이의 스트림릿 블록 간격(1rem) 제거 — 목업은 헤더 60px 바로 아래 .wrap 패딩 40px */
[data-testid="stElementContainer"]:has(> iframe[title="st.iframe"][scrolling="auto"]) { margin-top: -16px; }
/* 툴바(⋮ 테마 메뉴) 아래 바로 헤더가 오도록 본문 상단 여백 제거 */
section.stMain { padding-top: 0 !important; }
[data-testid="stMainBlockContainer"] { padding-top: 60px !important; }
div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .hdr-marker) { top: 60px !important; }
/* 보이지 않는 선행 요소(스타일 전용 마크다운·높이 0 테마 훅 iframe)가 1rem 간격을 두 번 먹어 헤더가 32px 내려오던 것 */
[data-testid="stElementContainer"]:has(> iframe[title="st.iframe"][scrolling="no"]), [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style:only-child) { display: none !important; }
/* 실측(1.58): 스타일 전용 마크다운은 stElementContainer > stMarkdown > div > stMarkdownContainer > style, 테마 훅 iframe은 scrolling="no"(본문 iframe은 scrolling=True → "auto"). display:none이어도 iframe 스크립트는 실행된다. */

/* 실측: .h-sec(h2)이 stMarkdownContainer h2 규칙(더 높은 명시도)에 밀려 36px로
   계산됐다 — .title h1/.detail h2도 같은 위험이 있어 전부 !important로 못박는다. */
.sec-h .h-sec, .serp-h .h-sec { font-size: 15px !important; font-weight: 600 !important; margin: 0 !important; padding: 0 !important; line-height: 1.3 !important; }
.title h1 { font-size: 32px !important; font-weight: 700 !important; margin: 0 0 6px !important; padding: 0 !important; }
.detail h2 { font-size: 22px !important; font-weight: 700 !important; margin: 0 0 4px !important; padding: 0 !important; }
.sec-h .h-sec a, .detail h2 a { display: none; }
"""

THEME_HOOK_HTML = """<script>
(function(){const P=window.parent; if(!P||!P.document) return;
 function lum(c){const m=c.match(/\\d+/g); if(!m) return 1; const [r,g,b]=m.map(Number); return (0.2126*r+0.7152*g+0.0722*b)/255;}
 function tick(){const bg=P.getComputedStyle(P.document.body).backgroundColor; const t=lum(bg)<0.5?'dark':'light';
   if(P.document.documentElement.dataset.theme!==t){P.document.documentElement.dataset.theme=t;}}
 tick(); setInterval(tick,400);})();
</script>"""


def theme_type() -> str:
    """서버에서 본 현재 테마. 한 rerun 늦을 수 있으므로 화면 색 결정에 쓰지 않는다(스펙 §9.1)."""
    try:
        return getattr(st.context.theme, "type", None) or "light"
    except Exception:
        return "light"


def inject_design_system() -> None:
    """페이지 스크립트 맨 위에서 1회 호출. CSS 3블록 + 테마 훅(높이 0 iframe).

    실서버 로그(Task 13): "Please replace `st.components.v1.html` with
    `st.iframe`. `st.components.v1.html` will be removed after 2026-06-01."
    이 streamlit 1.58에서 `st.iframe`으로 바꿔봤지만(inspect.signature상 raw
    HTML 문자열을 자동 감지해 srcdoc으로 넣어주므로 겉보기엔 대체 가능해
    보인다) 실측 결과 `st.iframe(..., height=0)`은 StreamlitInvalidHeightError
    로 즉시 죽는다 — `validate_height`가 0을 거부하고 양의 정수·"stretch"·
    "content"만 허용한다(components.html/구 st.components.v1.html은 0을
    허용했다). 이 훅은 화면에 아무것도 안 보여야 하는 폭 0 트릭이 핵심이라
    height를 1 이상으로 올리는 것도 대체가 아니다. 그래서 지금은 마이그레
    이션을 보류하고 구 API를 유지한다 — 2026-06-01 제거 전에 `st.iframe`이
    height=0(또는 동급 "완전히 숨김" 옵션)을 지원하게 되면 그때 바꾼다.
    """
    st.markdown(f"<style>{TOKENS_CSS}{COMPONENT_CSS}{CHROME_CSS}</style>", unsafe_allow_html=True)
    try:
        # R24: 테마 훅은 화면 표시에 필수가 아니라 다크/라이트 보정용 진행성 향상(progressive
        # enhancement)이다 — components.html/구 API가 향후 streamlit 버전에서 제거되거나
        # 런타임에서 예외를 던져도 페이지 전체가 죽으면 안 되므로 여기서 흡수한다.
        # 실패 시 토큰은 :root의 prefers-color-scheme 미디어쿼리 기본값으로 자연히 폴백된다.
        components.html(THEME_HOOK_HTML, height=0)
    except Exception:
        pass
