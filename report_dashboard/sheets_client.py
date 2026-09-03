"""Google Sheets API v4 어댑터.

`gspread`가 아니라 `googleapiclient`를 쓴다 — 웰라쥬 소재검수 앱
(`비서실/project/active/20260602_system_wellage-creative-review/sheets/client.py`)이
이미 이 조합으로 Streamlit Cloud에서 운영 중이고, `googleapiclient`와
`google.oauth2`는 이미 설치돼 있어 새 의존성이 없다.

`SheetsStore`가 이 클래스의 4개 메서드에만 의존하므로, 테스트에서는
인메모리 fake로 갈아끼울 수 있다.
"""

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Sheets API가 간헐적으로 429/5xx를 돌려준다(2026-09-02 댓글 수집 503, 09-03 배포본
# 첫 화면 HttpError). googleapiclient의 num_retries는 429·5xx·소켓 오류에만
# 지수 백오프로 재시도하고 4xx는 즉시 올린다 — 권한·범위 오류는 그대로 드러난다.
_RETRIES = 3


def build_sheets_service(credentials_info: dict):
    """서비스 계정 자격증명으로 Sheets 서비스 객체를 만든다.

    Drive 스코프는 요청하지 않는다 — 스프레드시트는 사람이 미리 만들어
    서비스 계정에 편집 권한을 주는 방식이고, 서비스 계정의 Drive 용량이 0이라
    파일 생성은 애초에 403이 된다(웰라쥬 앱에서 확인된 제약).
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_info(
        credentials_info, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


class SheetsClient:
    def __init__(self, spreadsheet_id: str, service):
        self.spreadsheet_id = spreadsheet_id
        self.service = service

    def list_tabs(self) -> list[str]:
        meta = self.service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id
        ).execute(num_retries=_RETRIES)
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    def create_tab(self, title: str) -> None:
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        ).execute(num_retries=_RETRIES)

    def append_rows(self, tab: str, rows: list[list[str]]) -> None:
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute(num_retries=_RETRIES)

    def read_column_a(self, tab: str) -> list[str]:
        resp = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=f"{tab}!A:A"
        ).execute(num_retries=_RETRIES)
        # 빈 행은 [] 로 오므로 인덱싱 대신 길이를 확인한다.
        return [row[0] if row else "" for row in resp.get("values", [])]

    def read_range(self, tab: str, cell_range: str = "") -> list[list[str]]:
        """탭 전체 또는 지정한 범위를 raw grid로 읽는다.

        `read_column_a`와 달리 빈 칸을 패딩하지 않는다 — 호출자(백필 파서)가
        각 행의 길이가 다를 수 있다는 것을 알고 안전하게 인덱싱해야 한다.
        """
        rng = f"{tab}!{cell_range}" if cell_range else tab
        resp = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=rng
        ).execute(num_retries=_RETRIES)
        return resp.get("values", [])
