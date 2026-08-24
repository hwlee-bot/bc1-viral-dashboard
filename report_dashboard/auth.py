"""로그인 게이트와 역할 판정.

Streamlit은 인증만 하고 인가는 하지 않는다(`st.user`는 신원만 준다). 역할은
우리가 판정한다.

allowlist를 두 군데로 나눈 것이 설계 의도다:
- team(우리) 이메일은 secrets에 둔다 → 권한 상승에 배포 설정 접근이 필요해진다
- client(광고주) 이메일은 시트에 둔다 → 등록·관리자 페이지에서 재배포 없이 관리한다

따라서 시트가 잘못 편집돼도 관리자 권한은 얻을 수 없다.
"""

import streamlit as st

from report_dashboard.repo import ReportRepo

ROLE_TEAM = "team"
ROLE_CLIENT = "client"


def _normalize(value: str) -> str:
    return (value or "").strip().lower()


def _normalized_set(values) -> set[str]:
    return {_normalize(v) for v in (values or []) if _normalize(v)}


def resolve_role(
    is_logged_in: bool, email: str, team_emails, client_emails
) -> str | None:
    """역할을 판정한다. 권한이 없으면 None.

    team을 먼저 본다 — 양쪽 목록에 같은 이메일이 있으면 team이 이긴다.
    `client_emails`에 빈 목록이 들어오면 client는 아무도 통과하지 못한다.
    호출자는 시트 읽기 실패 시 빈 목록을 넘겨 이 성질을 fail closed로 쓴다.
    """
    if not is_logged_in:
        return None
    who = _normalize(email)
    if not who:
        return None
    if who in _normalized_set(team_emails):
        return ROLE_TEAM
    if who in _normalized_set(client_emails):
        return ROLE_CLIENT
    return None


USERS_TABLE = "viral_users"


def current_identity() -> tuple[bool, str]:
    """(로그인 여부, 이메일). 테스트는 이 함수를 monkeypatch한다.

    `st.user.is_logged_in`을 속성으로 읽으면 `[auth]` 설정이 없는 환경에서
    AttributeError로 터진다(실측 확인). 로컬과 모든 AppTest가 그 상태이므로
    반드시 `.get()`으로 읽는다.
    """
    logged_in = bool(st.user.get("is_logged_in", False))
    return logged_in, (st.user.get("email") or "")


def team_emails() -> list[str]:
    """우리 팀 이메일 목록. secrets에만 존재한다."""
    try:
        return list(st.secrets["auth_roles"]["team_emails"])
    except Exception:
        return []


def _users_store():
    return ReportRepo().store


CLIENT_EMAILS_TTL_SECONDS = 20
"""allowlist 캐시 TTL.

왜 캐시가 필요한가: 캐시가 없으면 rerun마다 allowlist를 다시 읽는다. 게이트는
라우터(app.py)와 페이지 양쪽에서 호출되고, Streamlit은 위젯을 건드릴 때마다
스크립트 전체를 다시 돈다. Sheets API v4는 사용자당 분당 약 60읽기이고 서비스
계정은 앱 전체가 공유하는 단일 신원이다. 429가 나면 client_emails()가 None을
돌려주고 fail-closed가 광고주 전원을 잠근다 — 읽기 증폭이 곧 장애다.

왜 20초인가: 한 번의 페이지 로드(라우터 + 페이지 + 위젯 조작 몇 번)를 한 번의
읽기로 접기에 충분하고, 권한 해제가 최대 20초만 늦는다. 그보다 길게 잡으면
해제된 광고주가 그만큼 더 들어올 수 있고, 짧게 잡으면 위젯 조작 한 번에 다시
읽어 애초에 문제였던 증폭이 돌아온다. 등록·관리자 화면은 부여·해제 직후
`clear_client_emails_cache()`를 불러 TTL을 기다리지 않게 한다.
"""


@st.cache_data(ttl=CLIENT_EMAILS_TTL_SECONDS, show_spinner=False)
def client_emails() -> list[str] | None:
    """광고주 이메일 목록. **읽기 실패 시 None**을 돌려준다.

    호출자는 None을 "거부"로 다뤄야 한다. 빈 목록(정상적으로 광고주가 없음)과
    반드시 구분한다 — 저장소 장애를 접근 허용으로 번역하지 않기 위해서다.

    TTL 캐시가 붙어 있다(위 CLIENT_EMAILS_TTL_SECONDS 참고). 실패(None)도 캐시
    되지만 TTL이 짧아 저장소가 살아나면 곧 반영된다.
    """
    try:
        rows = _users_store().latest(USERS_TABLE, ("email",))
        return [
            r["email"]
            for r in rows
            if isinstance(r, dict) and r.get("active") and r.get("email")
        ]
    except Exception:
        return None


_CLIENT_EMAILS_CACHE = client_emails
"""캐시 핸들을 이름과 따로 붙잡아 둔다.

테스트는 `auth.client_emails`를 lambda로 monkeypatch한다. 그때 이름으로
`.clear()`를 찾으면 lambda에는 없어서 터진다 — 그래서 정의 직후의 핸들을
따로 보관한다.
"""


def clear_client_emails_cache() -> None:
    """allowlist 캐시를 즉시 무효화한다.

    권한을 부여·해제한 직후(등록·관리자 화면)와 테스트 격리 fixture에서 쓴다.
    """
    _CLIENT_EMAILS_CACHE.clear()


def require_role() -> tuple[str, str]:
    """게이트. 통과하면 (역할, 이메일)을 돌려주고, 아니면 화면을 세운다."""
    logged_in, email = current_identity()

    if not logged_in:
        st.title("바이럴 성과 리포팅")
        st.warning("이 페이지를 보려면 로그인이 필요하다.")
        # 공식 docstring의 예제가 모두 이 형태다 — on_click 콜백으로 st.login을
        # 트리거하는 것은 문서화된 경로가 아니다.
        if st.button("구글로 로그인", type="primary", key="login_button"):
            st.login()
        st.stop()

    clients = client_emails()
    role = resolve_role(logged_in, email, team_emails(), clients or [])

    if role is None:
        st.title("바이럴 성과 리포팅")
        st.error(f"{email} 계정에는 접근 권한이 없다. 담당자에게 계정 등록을 요청해라.")
        if clients is None:
            st.caption("광고주 계정 목록을 읽지 못했다. 저장소 상태를 확인해야 한다.")
        if st.button("로그아웃", key="logout_button"):
            st.logout()
        st.stop()

    return role, email
