# report_dashboard/nav.py
"""역할별 페이지 목록. Streamlit에 의존하지 않는다.

`app.py`는 Streamlit이 스크립트로 실행하는 파일이라 임포트만 해도 게이트가
돌아간다. 그래서 이 순수 로직을 별도 모듈에 두고 `app.py`가 조립만 한다.

경로는 진입점(`app.py`) 기준 상대 경로다 — `st.Page`가 그렇게 해석한다.
"""

from report_dashboard.auth import ROLE_TEAM

SUMMARY = ("요약", "pages/0_요약.py")
# "리포트" 단일 메뉴였던 것을 2026-09-02에 "상위노출"·"콘텐츠 성과" 두 개의
# 별도 사이드바 메뉴로 쪼갰다 — 처음엔 한 메뉴 안에 탭 두 개로 만들었는데,
# 팀장님이 탭이 아니라 메뉴 자체를 나누고 싶다고 확인해서 다시 나눔.
EXPOSURE = ("상위노출", "pages/1_상위노출.py")
PERFORMANCE = ("콘텐츠 성과", "pages/2_콘텐츠성과.py")
ADMIN = ("등록 · 관리자", "pages/3_등록.py")


def pages_for(role: str) -> list[tuple[str, str]]:
    """역할별 페이지 목록.

    `team`이 아닌 모든 값은 최소 권한으로 다룬다 — 예상 못 한 역할 문자열이
    들어왔을 때 관리자 페이지가 새는 쪽으로 기울지 않게 한다.
    """
    if role == ROLE_TEAM:
        return [SUMMARY, EXPOSURE, PERFORMANCE, ADMIN]
    return [SUMMARY, EXPOSURE, PERFORMANCE]


def page_titles_for(role: str) -> list[str]:
    return [title for title, _ in pages_for(role)]
