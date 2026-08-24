# report_dashboard/nav.py
"""역할별 페이지 목록. Streamlit에 의존하지 않는다.

`app.py`는 Streamlit이 스크립트로 실행하는 파일이라 임포트만 해도 게이트가
돌아간다. 그래서 이 순수 로직을 별도 모듈에 두고 `app.py`가 조립만 한다.

경로는 진입점(`app.py`) 기준 상대 경로다 — `st.Page`가 그렇게 해석한다.
"""

from report_dashboard.auth import ROLE_TEAM

SUMMARY = ("요약", "pages/0_요약.py")
REPORT = ("리포트", "pages/1_리포트.py")
ADMIN = ("등록 · 관리자", "pages/2_등록.py")


def pages_for(role: str) -> list[tuple[str, str]]:
    """역할별 페이지 목록.

    `team`이 아닌 모든 값은 최소 권한으로 다룬다 — 예상 못 한 역할 문자열이
    들어왔을 때 관리자 페이지가 새는 쪽으로 기울지 않게 한다.
    """
    if role == ROLE_TEAM:
        return [SUMMARY, REPORT, ADMIN]
    return [SUMMARY, REPORT]


def page_titles_for(role: str) -> list[str]:
    return [title for title, _ in pages_for(role)]
