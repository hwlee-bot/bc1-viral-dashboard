"""콘텐츠 리스트를 외부 구글시트에서 읽어와 등록하는 동기화 로직 (Plan 5).

설계: docs/superpowers/specs/2026-08-25-content-sheet-sync-design.md

등록·관리자 페이지(pages/2_등록.py)가 이 모듈의 함수를 호출한다. 페이지
코드는 Streamlit 위젯 조립만 하고, URL 파싱·행 검증·네트워크 호출은
여기로 분리했다 — auth.current_identity를 monkeypatch하는 기존 테스트
관례와 같은 방식으로, AppTest에서 fetch_sheet_rows만 갈아끼워서 네트워크
없이 페이지를 테스트할 수 있다.
"""

from __future__ import annotations

import re

from plan_automation.report_schemas import CHANNELS
from report_dashboard.repo import _sheets_settings
from report_dashboard.sheets_client import SheetsClient, build_sheets_service

_SHEET_ID_PATTERN = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


def extract_spreadsheet_id(url: str) -> str | None:
    """구글시트 URL에서 스프레드시트 ID를 뽑는다. URL 형식이 아니면 None."""
    match = _SHEET_ID_PATTERN.search(url.strip())
    return match.group(1) if match else None


def parse_sheet_content_rows(
    grid: list[list[str]],
    existing_urls: set[str],
) -> tuple[list[dict], list[str]]:
    """헤더를 제외한 데이터 행을 검증해서 (신규 콘텐츠 후보, 건너뜀 사유) 로 나눈다.

    existing_urls는 호출자가 이미 등록된 URL로 채워서 넘긴다 — 이 함수는
    신규로 통과시킨 URL을 그 집합에 바로 추가해서(in-place), 같은 시트
    안에 같은 URL이 여러 번 있어도 한 번만 등록되게 한다.

    URL 정규화는 하지 않는다(그대로 문자열 비교) — 사람이 직접 URL을
    붙여넣는 용도라 트래킹 파라미터 차이까지 다루는 건 스코프 밖이다
    (design.md §5.4, §8).
    """
    if len(grid) <= 1:
        return [], []

    candidates: list[dict] = []
    skipped: list[str] = []

    for i, row in enumerate(grid[1:], start=2):  # 1-base, 1행은 헤더
        channel = row[0].strip() if len(row) > 0 else ""
        url = row[1].strip() if len(row) > 1 else ""
        title = row[2].strip() if len(row) > 2 else ""
        release_at = row[3].strip() if len(row) > 3 else ""

        if not url:
            skipped.append(f"{i}행: URL이 비어있음")
            continue
        if channel not in CHANNELS:
            skipped.append(f"{i}행: 알 수 없는 채널 '{channel}'")
            continue
        if url in existing_urls:
            skipped.append(f"{i}행: 이미 등록된 URL — {url}")
            continue

        candidates.append({"channel": channel, "url": url, "title": title, "release_at": release_at})
        existing_urls.add(url)

    return candidates, skipped


def fetch_sheet_rows(spreadsheet_id: str) -> list[list[str]]:
    """스프레드시트의 첫 탭 전체를 raw grid로 읽는다.

    대시보드 자체가 이미 쓰는 서비스 계정 인증(_sheets_settings())을 그대로
    재사용한다 — 새 인증 경로를 만들지 않는다. 이 시트는 단일 탭 전용이라
    탭 선택 UI 없이 첫 탭을 그대로 쓴다(design.md §5.3, §8). 읽기 전용
    호출 1회라 Plan 2가 겪은 분당 쓰기 60회 quota와는 무관하다(그건 쓰기
    제한).
    """
    settings = _sheets_settings()
    if settings is None:
        raise RuntimeError(
            "Google Sheets 자격증명이 설정되지 않았다 — 로컬 개발 환경에서는 "
            "이 기능을 쓸 수 없다(배포 환경의 secrets에만 있음)."
        )
    service = build_sheets_service(settings["credentials"])
    client = SheetsClient(spreadsheet_id, service)
    tabs = client.list_tabs()
    if not tabs:
        raise RuntimeError("이 스프레드시트에 탭이 없다.")
    return client.read_range(tabs[0])
