"""노출 지면 캡쳐 이미지를 날짜별로 묶어 ZIP으로 만든다.

등록 페이지 "게재지면 보기" 버튼(Slack 요청 2026-09-09) 전용 — 그 날 찍힌
캡쳐(키워드×탭×풀샷/상위15)를 한 번에 내려받을 수 있게 한다. 네트워크
호출(Drive 다운로드)은 얇은 download_fn 콜백으로 주입해서, 이 모듈은
순수 로직만 담고 네트워크 없이 테스트한다(이 저장소의 다른 캡쳐·업로드
모듈과 같은 패턴).
"""

from __future__ import annotations

import io
import zipfile

CAPTURE_TAB_LABEL = {"blog": "블로그", "cafe": "카페"}
CAPTURE_TYPE_LABEL = {"full": "풀샷", "top15": "상위15"}


def capture_dates(captures: list[dict]) -> list[str]:
    """캡쳐 목록에서 날짜(YYYY-MM-DD)만 중복 제거해 최신순으로 돌려준다."""
    dates = {c["captured_at"][:10] for c in captures if c.get("captured_at")}
    return sorted(dates, reverse=True)


def captures_for_date(captures: list[dict], date: str) -> list[dict]:
    return [c for c in captures if c.get("captured_at", "")[:10] == date]


def _zip_entry_base_name(capture: dict) -> str:
    keyword = capture.get("keyword") or "키워드"
    tab_key = capture.get("search_tab", "")
    type_key = capture.get("capture_type", "")
    tab = CAPTURE_TAB_LABEL.get(tab_key, tab_key or "탭")
    ctype = CAPTURE_TYPE_LABEL.get(type_key, type_key or "종류")
    return f"{keyword}_{tab}_{ctype}.png"


def build_captures_zip(captures: list[dict], *, download_fn) -> bytes:
    """캡쳐 행 목록을 받아 각 이미지를 download_fn(drive_file_id)로 내려받고 ZIP 바이트로 묶는다.

    download_fn: (drive_file_id: str) -> bytes, 실패 시 예외를 던지는 인터페이스.
    한 파일이 실패해도 나머지는 계속 담는다 — 실패한 항목은 조용히 빠뜨리지
    않고 "<이름>__실패.txt"로 사유를 zip 안에 남긴다(다른 수집기들의 "하나
    실패해도 계속 진행" 패턴과 동일).

    같은 이름이 여러 번 나오면(같은 키워드·탭·종류가 그 날 두 번 이상
    캡쳐됐다면) 뒤에 일련번호를 붙여 덮어쓰지 않는다.
    """
    buf = io.BytesIO()
    seen_counts: dict[str, int] = {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for c in captures:
            base_name = _zip_entry_base_name(c)
            count = seen_counts.get(base_name, 0)
            seen_counts[base_name] = count + 1
            name = base_name if count == 0 else f"{base_name[:-4]}_{count + 1}.png"

            try:
                data = download_fn(c["drive_file_id"])
            except Exception as exc:
                zf.writestr(f"{name[:-4]}__실패.txt", f"다운로드 실패: {exc!r}")
                continue
            zf.writestr(name, data)

    return buf.getvalue()
