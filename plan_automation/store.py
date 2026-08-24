import json
import logging
from pathlib import Path

from plan_automation import config

log = logging.getLogger(__name__)


class Store:
    """SQL 테이블 구조를 유지하는 JSONL 저장소.

    한 줄 = 한 행. 수정은 덮어쓰지 않고 새 리비전을 append하고,
    읽을 때 `latest`로 키별 마지막 행을 취한다.
    """

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else config.STORE_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, table: str) -> Path:
        return self.root / f"{table}.jsonl"

    def save(self, table: str, row: dict) -> None:
        self.save_many(table, [row])

    def save_many(self, table: str, rows: list[dict]) -> None:
        if not rows:
            return
        with self._path(table).open("a", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def load(self, table: str) -> list[dict]:
        path = self._path(table)
        if not path.exists():
            return []
        rows = []
        with path.open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    log.warning("%s:%d 줄을 건너뜁니다 (JSON 아님)", path.name, lineno)
        return rows

    def latest(self, table: str, key_fields: tuple[str, ...]) -> list[dict]:
        newest: dict[tuple, dict] = {}
        for row in self.load(table):
            newest[tuple(row.get(k) for k in key_fields)] = row
        return list(newest.values())

    def find(self, table: str, **filters) -> list[dict]:
        return [
            row for row in self.load(table)
            if all(row.get(k) == v for k, v in filters.items())
        ]
