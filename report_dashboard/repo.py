"""바이럴 성과 리포팅 대시보드의 유일한 데이터 접근점.

Streamlit 페이지는 `plan_automation.store.Store`나 JSONL 경로를 직접
알아서는 안 된다 — 전부 이 `ReportRepo`를 거친다.

campaigns/contents/targets는 "현재 값" 개념이 있어 `Store.latest`로
키별 최신 리비전만 돌려준다. 반면 content_metrics/keyword_ranks/comments는
각 행이 서로 다른 시점의 관측값이라 리비전 개념이 없다 — `latest`로
뭉개면 시계열이 사라지므로 `load`/`find`로 전부 돌려준다.
"""

import os
from pathlib import Path

from plan_automation.store import Store
from report_dashboard.sheets_client import SheetsClient, build_sheets_service
from report_dashboard.store_sheets import SheetsStore


class SheetsConfigError(RuntimeError):
    """배포 환경인데 Sheets 설정이 없거나 읽히지 않는다.

    이걸 조용히 넘기면 앱은 건강해 보이는 채로 광고주 allowlist와 성과 데이터를
    Community Cloud가 재시작마다 지우는 로컬 JSONL에 쌓는다. 그리고 다음
    재시작에서 fail-closed 로직이 광고주 전원을 잠근다. 그래서 시끄럽게 터진다.
    """


def _deployed() -> bool:
    """배포 환경인지 판정한다.

    `[auth]` 섹션이 있으면 배포로 본다 — 그 섹션은 OAuth 왕복에 필요한
    redirect_uri·client_id가 들어가는 곳이므로 실제 배포에만 존재한다.
    로컬 개발과 테스트에는 secrets 자체가 없어 이 함수는 False다.
    """
    try:
        import streamlit as st

        return bool(st.secrets["auth"])
    except Exception:
        return False


def _sheets_settings() -> dict | None:
    """secrets에서 Sheets 설정을 읽는다. 로컬·테스트에서 없으면 None.

    배포 환경(Streamlit Cloud)에는 secrets가 있으니 자동으로 Sheets가 되고,
    로컬·테스트에는 없으니 자동으로 JSONL이 된다. 단 `REPORT_DASHBOARD_STORE`가
    설정돼 있으면 `_default_store`가 이 함수를 아예 호출하지 않고 로컬 JSONL로
    직행한다 — 로컬 dev secrets.toml이 있어도 테스트가 격리되게 하는 장치다.
    secrets 파일이 아예 없으면 st.secrets 접근 자체가 예외를 내므로 감싼다.

    단, `[auth]`가 설정된 배포 환경에서 Sheets 설정만 없거나 읽히지 않으면
    None을 돌려주지 않고 `SheetsConfigError`로 터진다 — 오타 하나로 조용히
    휘발성 로컬 저장소로 내려앉지 않게 한다.
    """
    try:
        import streamlit as st
    except Exception:  # streamlit 자체가 없는 환경
        return None

    missing: list[str] = []

    try:
        spreadsheet_id = st.secrets["sheets"]["spreadsheet_id"]
    except Exception:
        spreadsheet_id = None
        missing.append('[sheets] 섹션의 "spreadsheet_id" 키')
    else:
        if not spreadsheet_id:
            missing.append('[sheets]의 "spreadsheet_id"가 빈 값')

    try:
        credentials = dict(st.secrets["gcp_service_account"])
    except Exception:
        credentials = None
        missing.append("[gcp_service_account] 섹션")
    else:
        if not credentials:
            missing.append("[gcp_service_account] 섹션이 비어 있음")

    if missing:
        if _deployed():
            raise SheetsConfigError(
                "배포 설정(secrets)에 [auth]는 있는데 Google Sheets 설정이 없다: "
                + ", ".join(missing)
                + ". 이 상태로 계속하면 광고주 allowlist와 성과 데이터가 재시작마다"
                " 지워지는 로컬 파일에 쌓이고, 재시작 후 광고주 전원이 잠긴다."
                " Streamlit Cloud의 Secrets에서 위 키를 확인해라"
                " (.streamlit/secrets.toml.example 참고)."
            )
        return None

    return {"spreadsheet_id": spreadsheet_id, "credentials": credentials}


class ReportRepo:
    def __init__(self, store: Store | None = None):
        if store is None:
            store = self._default_store()
        self.store = store

    @staticmethod
    def _default_store() -> Store:
        """`REPORT_DASHBOARD_STORE`가 설정돼 있으면 secrets.toml 내용과 무관하게
        무조건 그 경로의 로컬 JSONL을 쓴다 — 테스트가 실물 Google Sheets 쿼터를
        태우지 않게 하는 유일한 스위치다. 배포 환경에는 이 env var가 없으므로
        프로덕션 동작(Sheets 우선)은 그대로다.
        """
        root = os.environ.get("REPORT_DASHBOARD_STORE")
        if root:
            return Store(root=Path(root))
        settings = _sheets_settings()
        if settings is not None:
            service = build_sheets_service(settings["credentials"])
            client = SheetsClient(settings["spreadsheet_id"], service)
            return SheetsStore(client=client, spreadsheet_id=settings["spreadsheet_id"])
        return Store()

    # -- 캠페인 ---------------------------------------------------

    def campaigns(self) -> list[dict]:
        return self.store.latest("viral_campaigns", ("campaign_id",))

    def save_campaign(self, row: dict) -> None:
        self.store.save("viral_campaigns", row)

    # -- 콘텐츠 ---------------------------------------------------

    def contents(self, campaign_id: str | None = None) -> list[dict]:
        rows = self.store.latest("viral_contents", ("content_id",))
        if campaign_id is not None:
            rows = [r for r in rows if r.get("campaign_id") == campaign_id]
        return rows

    def save_content(self, row: dict) -> None:
        self.store.save("viral_contents", row)

    # -- 목표 ---------------------------------------------------

    def targets(self, campaign_id: str | None = None) -> list[dict]:
        rows = self.store.latest("viral_targets", ("target_id",))
        if campaign_id is not None:
            rows = [r for r in rows if r.get("campaign_id") == campaign_id]
        return rows

    def save_target(self, row: dict) -> None:
        self.store.save("viral_targets", row)

    # -- 캠페인 키워드 워치리스트 -----------------------------------------

    def target_keywords(self, campaign_id: str | None = None) -> list[dict]:
        if campaign_id is not None:
            return self.store.find("viral_target_keywords", campaign_id=campaign_id)
        return self.store.load("viral_target_keywords")

    def save_target_keyword(self, row: dict) -> None:
        self.store.save("viral_target_keywords", row)

    # -- 콘텐츠 시트 연동 링크 (append-only, latest만 의미있음) --------------

    def content_sheet_link(self, campaign_id: str) -> dict | None:
        """이 캠페인에 마지막으로 저장된 시트 URL. append-only라 최신 하나만 쓴다."""
        rows = self.store.find("viral_content_sheet_links", campaign_id=campaign_id)
        return rows[-1] if rows else None

    def save_content_sheet_link(self, row: dict) -> None:
        self.store.save("viral_content_sheet_links", row)

    # -- 조회수 시계열 (append-only, 리비전 없음) -----------------------

    def content_metrics(self, content_id: str | None = None) -> list[dict]:
        if content_id is not None:
            return self.store.find("viral_content_metrics", content_id=content_id)
        return self.store.load("viral_content_metrics")

    def save_content_metric(self, row: dict) -> None:
        self.store.save("viral_content_metrics", row)

    # -- 네이버 키워드 순위 (append-only) -------------------------------

    def keyword_ranks(self, content_id: str | None = None) -> list[dict]:
        if content_id is not None:
            return self.store.find("viral_keyword_ranks", content_id=content_id)
        return self.store.load("viral_keyword_ranks")

    def save_keyword_rank(self, row: dict) -> None:
        self.store.save("viral_keyword_ranks", row)

    # -- 키워드 SERP 스냅샷 (append-only, 2026-09-02 신규) ----------------

    def keyword_serp(self, keyword: str | None = None) -> list[dict]:
        if keyword is not None:
            return self.store.find("viral_keyword_serp", keyword=keyword)
        return self.store.load("viral_keyword_serp")

    # -- 댓글 (append-only) ---------------------------------------

    def comments(self, content_id: str | None = None) -> list[dict]:
        if content_id is not None:
            return self.store.find("viral_comments", content_id=content_id)
        return self.store.load("viral_comments")

    def save_comment(self, row: dict) -> None:
        self.store.save("viral_comments", row)

    # -- 수집 실행 기록 ---------------------------------------------

    def collection_runs(self) -> list[dict]:
        return self.store.load("viral_collection_runs")

    def save_collection_run(self, row: dict) -> None:
        self.store.save("viral_collection_runs", row)

    def latest_collection_run(self, run_type: str = "content_metrics") -> dict | None:
        """가장 최근 수집 실행을 돌려준다. run_type으로 어느 수집기인지 구분한다.

        started_at이 여러 실행에서 같으면(예: 같은 초에 두 크론이 겹쳐 돈 경우)
        더 나중에 append된 실행을 우선한다 — 먼저 나온 것을 우선하는 Python
        기본 max() 동작은 이 경우 실제로 더 최신인 실행을 놓칠 수 있다.
        reporting.py의 _latest_by_content와 같은 패턴.

        run_type 필드 자체가 없는 옛 행(Plan 3 이전에 저장된 행)은
        content_metrics로 간주한다 — 그때 유일하게 쓰던 수집 종류였기 때문이다.
        """
        runs = [r for r in self.collection_runs() if r.get("run_type", "content_metrics") == run_type]
        if not runs:
            return None
        return max(enumerate(runs), key=lambda pair: (pair[1].get("started_at", ""), pair[0]))[1]

    # -- 점유율 브랜드 사전 (2026-09-03 신규, latest by (campaign_id, brand)) --------

    def brand_terms(self, campaign_id: str) -> list[dict]:
        rows = self.store.latest("viral_brand_terms", ("campaign_id", "brand"))
        return [r for r in rows if r.get("campaign_id") == campaign_id]

    def save_brand_terms(self, row: dict) -> None:
        self.store.save("viral_brand_terms", row)
