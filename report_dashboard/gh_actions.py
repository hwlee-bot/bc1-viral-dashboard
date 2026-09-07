"""수동 재수집 트리거(스펙 §14) — 대시보드 상단 버튼이 부르는 얇은 GitHub Actions 클라이언트.

네이버 순위·댓글 수집은 이미 GitHub Actions(`naver-rank-collect.yml`·`comment-collect.yml`)의
`workflow_dispatch`로 수동 실행할 수 있다(지금까지는 `gh workflow run`으로 터미널에서만
가능했다) — 여기서는 그 디스패치를 REST API로 그대로 호출할 뿐, 수집 로직 자체는
다시 만들지 않는다. 팀장님이 새벽 자동 수집이 빠진 걸 발견했을 때 터미널 없이 바로
재요청할 수 있게 하는 게 목적이다(2026-09-07).

필요한 시크릿: `st.secrets["github"]["token"]` — 이 저장소(`bc1-viral-report`)의
Actions 실행 권한만 있는 fine-grained PAT. Streamlit Cloud 앱 설정의 Secrets 칸에
담당자가 직접 넣어야 한다 — 이 코드는 그 값을 읽어 요청 헤더에만 쓰고 화면·로그
어디에도 노출하지 않는다.
"""
from __future__ import annotations

import requests
import streamlit as st

REPO = "hwlee-bot/bc1-viral-report"
# {버튼에 보여줄 이름: 워크플로 파일명} — .github/workflows/의 실제 파일과 같아야 한다.
WORKFLOWS = {
    "네이버 순위": "naver-rank-collect.yml",
    "댓글": "comment-collect.yml",
}


class MissingGithubTokenError(RuntimeError):
    pass


def _token() -> str:
    try:
        token = st.secrets["github"]["token"]
    except Exception:
        token = None
    if not token:
        raise MissingGithubTokenError(
            "st.secrets['github']['token']이 없습니다 — Streamlit Cloud 앱 설정 → Secrets에 "
            "[github] token = \"<bc1-viral-report 전용 fine-grained PAT>\" 을 추가해야 합니다."
        )
    return token


def trigger_collection(*, ref: str = "main") -> dict[str, bool]:
    """네이버 순위·댓글 두 워크플로에 `workflow_dispatch`를 요청한다.

    반환값은 `{워크플로 이름: 요청 접수 성공 여부}` — GitHub이 204를 주면 "실행 큐에
    들어갔다"는 뜻이지 "수집이 끝났다"는 뜻이 아니다(Actions 특성상 몇 분 걸린다).
    토큰이 없으면 어느 요청도 보내지 않고 `MissingGithubTokenError`를 낸다.
    """
    token = _token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    results: dict[str, bool] = {}
    for label, workflow_file in WORKFLOWS.items():
        url = f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow_file}/dispatches"
        try:
            resp = requests.post(url, headers=headers, json={"ref": ref}, timeout=10)
            results[label] = resp.status_code == 204
        except requests.RequestException:
            results[label] = False
    return results
