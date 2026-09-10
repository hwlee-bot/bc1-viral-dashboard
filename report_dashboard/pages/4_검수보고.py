# report_dashboard/pages/4_검수보고.py
"""노출 지면 캡쳐 검수 + 게재지면 일괄 다운로드. 담당자 전용 — 광고주는 접근 불가.

팀장님 요청(2026-09-10)으로 신설: 등록 페이지에 있던 "노출 지면 캡쳐 링크"·
"게재지면 일괄 다운로드" 섹션을 여기로 이관했다. 앞으로 검수·리포팅이
필요한 항목은 모두 이 페이지에 추가될 예정이다(등록·관리자는 데이터
입력·관리용, 이 페이지는 결과 확인·검수용으로 성격을 나눈다).

키워드도 이분화했다 — 이 페이지가 관리하는 키워드(`repo.exposure_keywords`)는
상위노출·요약·순위수집이 보는 `repo.target_keywords`와 별개 테이블이다.
캡쳐만 더 돌리고 싶은 키워드(아직 순위 추적은 안 하는 신규 제품명 등)를
추가해도 리포트 쪽 키워드 목록엔 영향이 없다.
"""

# Streamlit Cloud는 실행할 스크립트가 있는 폴더만 sys.path에 넣는다(공식 소스
# streamlit/web/bootstrap.py::_fix_sys_path 확인함) — 저장소 루트는 안 들어간다.
# 로컬은 `python3 -m streamlit run`(-m이 CWD를 넣어줌)이나 pytest(패키지 루트를
# 자동 추가)가 이 문제를 가려서 배포 전엔 안 드러났다. report_dashboard.* 절대
# 임포트가 되려면 저장소 루트가 필요하므로 여기서 직접 넣는다.
import os
import sys

_here = os.path.abspath(__file__)
_repo_root = _here[: _here.index(os.sep + "report_dashboard" + os.sep)]
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import uuid
from datetime import datetime

import streamlit as st

from report_dashboard import drive_client as drive_client_module
from report_dashboard import exposure_zip, repo as repo_module, ui
from report_dashboard.auth import ROLE_TEAM, require_role
from report_dashboard.design_system import inject_design_system
from report_dashboard.header import render_header
from report_dashboard.repo import ReportRepo

# 게이트를 이 파일에서도 호출한다 — 이유는 1_상위노출.py 상단 주석과 같다
# (uses_pages_directory 플래그가 True인 창에서는 app.py가 아예 실행되지 않는다).
# 등록·관리자와 같은 이유로 require_role()만으로는 부족하다 — 그것만 쓰면
# 광고주(client)도 통과한다. 팀 역할까지 요구한다.
role, email = require_role()
if role != ROLE_TEAM:
    st.title("검수 · 보고")
    st.error("이 페이지는 담당자 전용이다. 이 계정에는 검수·보고 권한이 없다.")
    st.stop()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


repo = ReportRepo()
inject_design_system()
campaigns = repo.campaigns()
campaign_id = render_header(role, email, campaigns, current="검수 · 보고")

st.markdown(
    ui.title_block(
        "검수 · 보고",
        "<b>담당자 전용</b> · 노출 지면 캡쳐 검수와 게재지면 다운로드 — "
        "앞으로 검수·리포팅이 필요한 항목은 모두 이 페이지에 추가된다",
    ),
    unsafe_allow_html=True,
)

if campaign_id is None:
    st.markdown(ui.empty_state("등록된 캠페인이 없습니다", "담당자가 캠페인을 등록하면 표시됩니다."), unsafe_allow_html=True)
    st.stop()

campaign = next(c for c in campaigns if c["campaign_id"] == campaign_id)

_CAPTURE_TAB_LABEL = {"home": "홈", "blog": "블로그", "cafe": "카페"}
_CAPTURE_TYPE_LABEL = {"full": "풀샷", "top15": "상위15"}  # top15는 과거 캡쳐 라벨용(2026-09-10 제거됨)

st.markdown(
    ui.section_header("노출 지면 캡쳐 검수", "이 키워드 목록은 캡쳐 전용이다 — 상위노출 리포트가 보는 키워드와는 별개로 여기서 관리한다."),
    unsafe_allow_html=True,
)

with st.form("exposure_keyword_form"):
    keyword_text = st.text_input("캡쳐 키워드 추가", key="exposure_keyword_text")
    submitted_keyword = st.form_submit_button("추가", key="exposure_keyword_submit")

if submitted_keyword:
    existing_keywords = {k["keyword"] for k in repo.exposure_keywords(campaign_id=campaign_id)}
    if not keyword_text:
        st.warning("키워드를 입력해야 저장된다.")
    elif keyword_text in existing_keywords:
        st.warning(f"'{keyword_text}'는 이 캠페인에 이미 등록돼 있다. 중복 등록하면 수집기가 같은 키워드를 하루에 두 번 검색한다.")
    else:
        repo.save_exposure_keyword({
            "keyword_id": _new_id("ek"),
            "campaign_id": campaign_id,
            "keyword": keyword_text,
            "created_at": _now(),
        })
        st.success(f"{keyword_text} 저장했다.")
        # rerun 안 씀 — 3_등록.py의 키워드 저장과 같은 이유(성공 메시지가 사라지는 버그 방지)

exposure_kw = repo.exposure_keywords(campaign_id=campaign_id)
if exposure_kw:
    chips = "".join(f'<span class="chip">{ui.esc(k["keyword"])}</span>' for k in exposure_kw)
    st.markdown(f'<div class="kw-chips">{chips}</div>', unsafe_allow_html=True)
else:
    st.caption("이 캠페인에 등록된 캡쳐 키워드가 없다.")

# 노출 지면 캡쳐 링크 — 키워드×탭(홈·블로그·카페)×종류마다 최신 캡쳐 1건만.
# collection_run 성공 여부와 별개로 실제로 뭐가 찍혔는지 바로 열어볼 수 있게.
captures_for_campaign = repo.exposure_captures(campaign_id=campaign_id)
if captures_for_campaign:
    latest_capture_by_key: dict[tuple[str, str, str], dict] = {}
    for c in captures_for_campaign:
        key = (c["keyword"], c.get("search_tab", ""), c.get("capture_type", ""))
        prev = latest_capture_by_key.get(key)
        if prev is None or c["captured_at"] > prev["captured_at"]:
            latest_capture_by_key[key] = c
    capture_links = "".join(
        f'<a class="chip" href="{ui.esc(c["drive_url"])}" target="_blank">'
        f'{ui.esc(kw)} {ui.esc(_CAPTURE_TAB_LABEL.get(tab, tab))} '
        f'{ui.esc(_CAPTURE_TYPE_LABEL.get(ctype, ctype))} 지면 보기 ({ui.esc(c["captured_at"][:10])})</a>'
        for (kw, tab, ctype), c in sorted(latest_capture_by_key.items())
    )
    st.markdown('<div class="kw-chips">' + capture_links + '</div>', unsafe_allow_html=True)

    # 게재지면 일괄 다운로드 — 개별 링크 말고, 그 날 찍힌 캡쳐 전부를 한 번에
    # 받을 수 있어야 한다. Drive 다운로드는 몇 초 걸릴 수 있어서 버튼을 두
    # 단계로 나눈다 — "게재지면 보기"가 먼저 zip을 만들어 세션에 담고, 같은
    # 렌더에서 바로 st.download_button이 뜬다(Streamlit은 다운로드 시점에
    # 미리 준비된 데이터가 필요해서 지연 생성이 안 된다).
    capture_dl_dates = exposure_zip.capture_dates(captures_for_campaign)
    st.markdown('<div class="or">게재지면 일괄 다운로드</div>', unsafe_allow_html=True)
    dl_col1, dl_col2 = st.columns([3, 1])
    dl_date = dl_col1.selectbox("다운로드할 날짜", options=capture_dl_dates, key="exposure_zip_date")
    build_clicked = dl_col2.button("게재지면 보기", key="exposure_zip_build")

    if build_clicked:
        with st.spinner(f"{dl_date} 캡쳐 {len(exposure_zip.captures_for_date(captures_for_campaign, dl_date))}건 내려받는 중..."):
            settings = repo_module._sheets_settings()
            if settings is None:
                st.error("Google 서비스 계정 설정을 못 읽었다 — .streamlit/secrets.toml 확인 필요.")
            else:
                drive_service = drive_client_module.build_drive_service(settings["credentials"])
                drive = drive_client_module.DriveClient(folder_id=None, service=drive_service)
                day_captures = exposure_zip.captures_for_date(captures_for_campaign, dl_date)
                zip_bytes = exposure_zip.build_captures_zip(day_captures, download_fn=drive.download_file)
                st.session_state["exposure_zip_ready_key"] = (campaign_id, dl_date)
                st.session_state["exposure_zip_bytes"] = zip_bytes

    # 캠페인·날짜를 바꾸면 이전에 준비해둔 zip은 무효 — 다시 눌러야 한다
    # (다른 캠페인 이미지를 잘못된 파일명으로 내려받는 걸 막는다).
    if st.session_state.get("exposure_zip_ready_key") == (campaign_id, dl_date):
        st.download_button(
            f"{dl_date} 게재지면 ZIP 다운로드",
            data=st.session_state["exposure_zip_bytes"],
            file_name=f"{campaign['name']}_{dl_date}_게재지면.zip",
            mime="application/zip",
            key="exposure_zip_download",
        )
else:
    st.caption("아직 캡쳐된 노출 지면이 없다.")

st.markdown(
    ui.empty_state("다음에 추가될 항목", "검수·보고가 필요한 항목이 이 페이지 아래로 계속 늘어난다."),
    unsafe_allow_html=True,
)
