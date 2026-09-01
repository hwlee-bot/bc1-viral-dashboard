"""3개 페이지(0_요약·1_리포트·2_등록)가 공유하는 폰트 시스템.

폰트 문자열을 여기 한 곳에서만 관리한다 — 페이지마다 따로 박아두면
나중에 하나만 바꾸고 나머지를 깜빡하는 사고가 난다.

기본(본문) 폰트는 Noto Sans KR, 제목(h1~h3·카드 타이틀·"REPORT DASHBOARD"
히어로 타이틀)은 Bebas Neue → Noto Sans KR 순으로 폴백한다. Bebas Neue는
한글 글리프가 없어서 한글 문자는 자동으로 Noto Sans KR로 넘어간다(브라우저
기본 동작) — 영문 문구가 있는 자리(히어로 타이틀 등)에서만 Bebas Neue가
실제로 보인다. 페이지 subheader·header 문구는 한글로 유지한다
(2026-09-02, 팀장님 요청으로 영문화했다가 되돌림. 히어로 타이틀 폰트는
Josefin Sans → Bebas Neue로 같은 날 재변경, 잡지 표지풍으로 확정).
"""

import streamlit as st

FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Bebas+Neue&family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');"
)

FONT_BODY = '"Noto Sans KR", -apple-system, "Apple SD Gothic Neo", sans-serif'
FONT_DISPLAY = f'"Bebas Neue", {FONT_BODY}'

BASE_FONT_CSS = f"""
<style>
{FONT_IMPORT}
:root {{
  --vr-font-body: {FONT_BODY};
  --vr-font-display: {FONT_DISPLAY};
}}
/* !important 필수 — 스트림릿 자체 기본 테마가 h1~h3·본문에 font-family를
   이미 걸어두고 있어서, 그냥 규칙으로는 우선순위에서 진다(실측 확인:
   !important 없이 냈다가 팀장님이 "폰트가 안 바뀐다"고 확인해줌). */
[data-testid="stAppViewContainer"] {{ font-family: var(--vr-font-body) !important; }}
[data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 {{
  font-family: var(--vr-font-display) !important;
  font-weight: 800 !important;
  letter-spacing: -0.01em;
}}
</style>
"""


def inject_base_fonts() -> None:
    st.markdown(BASE_FONT_CSS, unsafe_allow_html=True)
