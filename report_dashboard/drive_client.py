"""Google Drive API v3 어댑터 — 노출 지면 캡쳐 이미지 업로드 전용.

`sheets_client.py`와 같은 서비스 계정 자격증명을 재사용하되, 별도 스코프로
새 서비스 객체를 만든다(Credentials는 생성 시점에 스코프가 고정돼서 재사용이 안 됨).

**공유 드라이브(Shared Drive) 전제** — 서비스 계정은 자기 소유 드라이브 용량이
0이라 일반 "내 드라이브"에는 파일을 못 만든다(`sheets_client.py` 상단 주석과
같은 제약, 웰라쥬 앱에서 이미 확인됨). 그래서 `folder_id`는 반드시 서비스
계정이 멤버로 초대된 공유 드라이브(또는 그 안의 폴더) ID여야 하고, 모든 API
호출에 `supportsAllDrives=True`를 넘긴다 — 이게 없으면 공유 드라이브 폴더에
대한 요청도 조용히 404가 난다.

**스코프는 `drive.file`이 아니라 전체 `drive`다** — 실측 확인됨(2026-09-08,
첫 실제 업로드 56건 전부 "File not found" 404). `drive.file`은 "이 앱이
직접 만들었거나 연 파일"에만 파일 단위로 접근을 허용하는 좁은 스코프라,
서비스 계정을 공유 드라이브에 멤버로 초대해도(진짜 Drive 권한은 있어도)
그 스코프 기준으로는 그 폴더가 "안 보인다" — Drive API가 403이 아니라
404로 응답해서 원인이 스코프인지 폴더 ID 오류인지 헷갈리게 만든다. 서버
쪽에서 공유 드라이브 전체를 다루는 이런 백엔드 자동화엔 전체 `drive`
스코프가 맞다(이 앱이 실제로 만들지 않은 기존 폴더에 파일을 넣어야 하므로).
"""

SCOPES = ["https://www.googleapis.com/auth/drive"]


def build_drive_service(credentials_info: dict):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_info(
        credentials_info, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


class DriveClient:
    def __init__(self, folder_id: str | None, service):
        # folder_id는 업로드(upload_png)에만 필요하다 — 대시보드 쪽 다운로드
        # 버튼(download_file)은 이미 저장된 파일 ID로만 접근하므로 폴더를
        # 몰라도 된다(GDRIVE_EXPOSURE_FOLDER_ID Secret은 GitHub Actions
        # 업로드 스크립트 전용, Streamlit 앱은 이 시크릿이 없어도 다운로드는 된다).
        self.folder_id = folder_id
        self.service = service

    def upload_png(self, filename: str, image_bytes: bytes) -> dict:
        """PNG 바이트를 업로드하고 {id, web_view_link}를 돌려준다.

        업로드 직후 파일은 서비스 계정만 볼 수 있는 상태다 — 팀·광고주가
        웹뷰 링크로 바로 열 수 있게 "링크가 있는 모든 사용자 = 뷰어" 권한을
        붙인다(대시보드에 등록된 광고주 계정 화이트리스트와는 별개 — 그
        화이트리스트는 대시보드 로그인 게이트고, 이건 그 안에서 보여줄 이미지
        링크 자체의 접근 권한이다).
        """
        from googleapiclient.http import MediaInMemoryUpload

        media = MediaInMemoryUpload(image_bytes, mimetype="image/png", resumable=False)
        file = self.service.files().create(
            body={"name": filename, "parents": [self.folder_id]},
            media_body=media,
            fields="id, webViewLink",
            supportsAllDrives=True,
        ).execute()

        self.service.permissions().create(
            fileId=file["id"],
            body={"role": "reader", "type": "anyone"},
            supportsAllDrives=True,
        ).execute()

        return {"id": file["id"], "web_view_link": file["webViewLink"]}

    def download_file(self, file_id: str) -> bytes:
        """파일 ID로 원본 바이트를 내려받는다 — "게재지면 보기" 다운로드 버튼 전용.

        upload_png가 캡쳐 직후 "링크가 있는 모든 사용자 = 뷰어" 권한을 이미
        붙여두지만, 이 메서드는 서비스 계정 자격증명으로 직접 받으므로 그
        권한과 무관하게 동작한다(권한 전파 지연이 있어도 안전).
        """
        from io import BytesIO

        from googleapiclient.http import MediaIoBaseDownload

        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
        buf = BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()
