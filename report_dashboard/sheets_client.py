"""Google Sheets API v4 어댑터.

`gspread`가 아니라 `googleapiclient`를 쓴다 — 웰라쥬 소재검수 앱
(`비서실/project/active/20260602_system_wellage-creative-review/sheets/client.py`)이
이미 이 조합으로 Streamlit Cloud에서 운영 중이고, `googleapiclient`와
`google.oauth2`는 이미 설치돼 있어 새 의존성이 없다.

`SheetsStore`가 이 클래스의 4개 메서드에만 의존하므로, 테스트에서는
인메모리 fake로 갈아끼울 수 있다.
"""

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


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
        ).execute()
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    def create_tab(self, title: str) -> None:
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        ).execute()

    def append_rows(self, tab: str, rows: list[list[str]]) -> None:
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

    def read_column_a(self, tab: str) -> list[str]:
        resp = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=f"{tab}!A:A"
        ).execute()
        # 빈 행은 [] 로 오므로 인덱싱 대신 길이를 확인한다.
        return [row[0] if row else "" for row in resp.get("values", [])]
