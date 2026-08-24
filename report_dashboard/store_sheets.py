"""Google Sheets 백엔드 Store.

Streamlit Community Cloud에는 지속 저장소가 없다 — 공식 문서 문구는
"Community Cloud apps do not guarantee the persistence of local file storage,
so the platform may delete data stored using this technique at any time."
그래서 배포 환경에서는 JSONL 대신 이 구현을 쓴다.

`Store`를 상속해 `save_many`와 `load`만 교체한다. `Store.latest`와 `Store.find`가
이미 `self.load()`를 호출하도록 작성돼 있어서, 그 둘과 `save`는 그대로 재사용되고
두 백엔드의 조회 의미가 어긋날 수 없다. `plan_automation/store.py`는 고치지 않는다.

한 행은 한 칸에 담긴 JSON 문자열이다. 컬럼으로 펼치지 않는 이유: Sheets는 읽을 때
타입이 뭉개져서 정수가 문자열로 돌아오고 None과 빈 칸이 구분되지 않으며,
`failed_items`(리스트)는 칸에 담을 타입이 아예 없다. 한 칸에 json.dumps를 넣으면
직렬화가 기존 Store와 같아져서 값이 그대로 왕복한다.
"""

import json
import logging

from plan_automation.store import Store

log = logging.getLogger(__name__)


class SheetsStore(Store):
    def __init__(self, client, spreadsheet_id: str = ""):
        # Store.__init__을 부르지 않는다 — 그쪽은 로컬 디렉토리를 만들려 한다.
        self.client = client
        self.spreadsheet_id = spreadsheet_id
        self._tabs: set[str] | None = None

    # -- 내부 -----------------------------------------------------

    def _known_tabs(self) -> set[str]:
        if self._tabs is None:
            self._tabs = set(self.client.list_tabs())
        return self._tabs

    def _ensure_tab(self, table: str) -> None:
        if table in self._known_tabs():
            return
        self.client.create_tab(table)
        self._known_tabs().add(table)

    # -- Store 재정의 ----------------------------------------------

    def save_many(self, table: str, rows: list[dict]) -> None:
        if not rows:
            return
        self._ensure_tab(table)
        self.client.append_rows(
            table, [[json.dumps(row, ensure_ascii=False)] for row in rows]
        )

    def load(self, table: str) -> list[dict]:
        if table not in self._known_tabs():
            return []
        out = []
        for lineno, cell in enumerate(self.client.read_column_a(table), 1):
            if not cell or not cell.strip():
                continue
            try:
                out.append(json.loads(cell))
            except json.JSONDecodeError:
                log.warning("%s 탭 %d번째 칸을 건너뜁니다 (JSON 아님)", table, lineno)
        return out
