"""배포 1단계(스프레드시트 준비)가 제대로 됐는지 미리 확인하는 스크립트.

런북 1단계는 사람이 스프레드시트를 만들고 서비스 계정에 공유하는 작업인데,
빠뜨리거나 잘못해도 앱을 배포해서 열어볼 때까지 알 수 없다. 이 스크립트는
그걸 배포 전에 한 번에 확인한다.

확인하는 것 (순서대로, 실패하면 원인을 이름으로 알려준다):
  1. 서비스 계정 키 파일을 읽고 자격증명을 만들 수 있는지
  2. 그 스프레드시트에 접근되는지        (403=공유 누락, 404=ID 오타)
  3. 탭 목록을 읽을 수 있는지            (읽기 권한)
  4. 탭을 만들 수 있는지                  (403=뷰어로만 공유됨, 편집자여야 함)
  5. 앱과 똑같은 경로로 한 행 쓰고 읽기   (SheetsStore를 그대로 써서 왕복 확인)
  6. 확인용으로 만든 임시 탭 삭제

실제 데이터 탭(viral_*)은 건드리지 않는다 — 임시 탭에서만 검사하고 지운다.
데이터 탭은 앱이 첫 쓰기 때 스스로 만든다(런북 1단계 참고).

사용법:
    python3 -m report_dashboard.verify_sheets_setup \
        --key ~/Downloads/service-account.json \
        --spreadsheet-id 1AbC...

  또는 .streamlit/secrets.toml이 이미 채워져 있으면 인자 없이:
    python3 -m report_dashboard.verify_sheets_setup
"""

import argparse
import json
import sys
from pathlib import Path

PROBE_TAB = "_setup_probe"


def _fail(step: str, why: str, fix: str = "") -> "None":
    print(f"  FAIL  {step}")
    print(f"        원인: {why}")
    if fix:
        print(f"        조치: {fix}")
    sys.exit(1)


def _ok(step: str, detail: str = "") -> None:
    print(f"  OK    {step}" + (f" — {detail}" if detail else ""))


def _load_from_secrets() -> tuple[dict, str] | None:
    """.streamlit/secrets.toml에서 자격증명과 시트 ID를 읽는다. 없으면 None."""
    path = Path(".streamlit/secrets.toml")
    if not path.exists():
        return None
    try:
        import tomllib
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        creds = dict(data["gcp_service_account"])
        sid = data["sheets"]["spreadsheet_id"]
    except Exception as exc:
        print(f"  (.streamlit/secrets.toml을 읽었으나 사용할 수 없다: {exc})")
        return None
    if not sid or "<" in str(sid):
        return None
    return creds, sid


def main() -> int:
    ap = argparse.ArgumentParser(
        description="배포 1단계(스프레드시트 공유)가 제대로 됐는지 확인한다.",
    )
    ap.add_argument("--key", help="서비스 계정 JSON 키 파일 경로")
    ap.add_argument("--spreadsheet-id", help="스프레드시트 URL의 /d/ 다음 문자열")
    args = ap.parse_args()

    print("배포 1단계 검증 — 스프레드시트 접근 권한")
    print()

    # -- 1. 자격증명 ---------------------------------------------------
    if args.key and args.spreadsheet_id:
        key_path = Path(args.key).expanduser()
        if not key_path.exists():
            _fail("서비스 계정 키 읽기", f"파일이 없다: {key_path}",
                  "Google Cloud Console에서 받은 JSON 키 경로를 --key로 넘겨라.")
        try:
            creds_info = json.loads(key_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            _fail("서비스 계정 키 읽기", f"JSON 형식이 아니다: {exc}", "받은 키 파일을 그대로 넘겨라.")
        spreadsheet_id = args.spreadsheet_id
    else:
        loaded = _load_from_secrets()
        if loaded is None:
            _fail("입력 확인",
                  "--key와 --spreadsheet-id가 없고 .streamlit/secrets.toml도 쓸 수 없다",
                  "python3 -m report_dashboard.verify_sheets_setup "
                  "--key <키파일> --spreadsheet-id <시트ID>")
        creds_info, spreadsheet_id = loaded

    sa_email = creds_info.get("client_email", "(client_email 없음)")
    if "client_email" not in creds_info or "private_key" not in creds_info:
        _fail("서비스 계정 키 확인", "client_email 또는 private_key가 없다",
              "서비스 계정 키(JSON)가 맞는지 확인해라. OAuth 클라이언트 키와 다른 파일이다.")
    _ok("서비스 계정 키 확인", sa_email)

    from report_dashboard.sheets_client import SheetsClient, build_sheets_service
    from report_dashboard.store_sheets import SheetsStore

    try:
        service = build_sheets_service(creds_info)
    except Exception as exc:
        _fail("Sheets 서비스 생성", str(exc),
              "private_key가 잘렸거나 개행이 깨졌을 수 있다.")
    _ok("Sheets 서비스 생성")

    client = SheetsClient(spreadsheet_id, service)

    def _http_status(exc) -> int | None:
        return getattr(getattr(exc, "resp", None), "status", None)

    # -- 2·3. 접근 + 읽기 ----------------------------------------------
    try:
        tabs = client.list_tabs()
    except Exception as exc:
        status = _http_status(exc)
        if status == 403:
            _fail("스프레드시트 읽기", "권한 없음(403)",
                  f"그 스프레드시트를 {sa_email} 에게 '편집자'로 공유해라.")
        elif status == 404:
            _fail("스프레드시트 읽기", f"그런 스프레드시트가 없다(404): {spreadsheet_id}",
                  "URL의 /d/ 다음 문자열만 넣었는지 확인해라(전체 URL 아님).")
        _fail("스프레드시트 읽기", str(exc))
    _ok("스프레드시트 읽기", f"기존 탭 {len(tabs)}개" + (f": {', '.join(tabs)}" if tabs else " (빈 시트)"))

    # -- 4. 쓰기(탭 생성) ----------------------------------------------
    if PROBE_TAB in tabs:
        _ok("임시 탭 확인", f"{PROBE_TAB} 가 이미 있다(이전 검증 잔여) — 재사용")
    else:
        try:
            client.create_tab(PROBE_TAB)
        except Exception as exc:
            if _http_status(exc) == 403:
                _fail("탭 생성(쓰기 권한)", "권한 없음(403) — 읽기는 되는데 쓰기가 안 된다",
                      f"{sa_email} 의 공유 권한을 '뷰어'에서 '편집자'로 올려라.")
            _fail("탭 생성(쓰기 권한)", str(exc))
        _ok("탭 생성(쓰기 권한)", f"{PROBE_TAB} 생성")

    # -- 5. 앱과 같은 경로로 왕복 -----------------------------------------
    probe_row = {"probe": True, "note": "삭제해도 됨", "count": 1, "empty": None}
    try:
        store = SheetsStore(client=client, spreadsheet_id=spreadsheet_id)
        store.save(PROBE_TAB, probe_row)
        rows = store.load(PROBE_TAB)
    except Exception as exc:
        _fail("행 쓰기·읽기 왕복", str(exc))

    if probe_row not in rows:
        _fail("행 쓰기·읽기 왕복",
              f"쓴 값이 그대로 돌아오지 않았다. 읽은 것: {rows!r}",
              "이 시트에 앱 외의 다른 것이 쓰고 있는지 확인해라.")
    _ok("행 쓰기·읽기 왕복", "타입(불리언·정수·None) 그대로 보존됨")

    # -- 6. 정리 -------------------------------------------------------
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheet_id = next(
            s["properties"]["sheetId"] for s in meta.get("sheets", [])
            if s["properties"]["title"] == PROBE_TAB
        )
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"deleteSheet": {"sheetId": sheet_id}}]},
        ).execute()
        _ok("임시 탭 삭제", PROBE_TAB)
    except Exception as exc:
        print(f"  경고  임시 탭 삭제 실패 — 손으로 '{PROBE_TAB}' 탭을 지워라 ({exc})")

    print()
    print("통과 — 배포 1단계(스프레드시트 준비) 완료.")
    print(f"secrets의 [sheets] spreadsheet_id 에 넣을 값: {spreadsheet_id}")
    print("데이터 탭(viral_*)은 앱이 첫 쓰기 때 스스로 만든다. 미리 만들지 마라.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
