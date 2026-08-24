"""캠페인·콘텐츠 등록, 목표조회수 설정, 수동 조회수 입력, 수집 상태 확인.

바이럴 성과 리포팅 대시보드의 관리자 화면. 자동 수집(cron)이 못 채우는
칸(인스타그램 전량, 그 외 채널의 수집 실패 항목)은 여기서 사람이 채운다.
"""

import uuid
from datetime import datetime

import streamlit as st

from report_dashboard.auth import (
    ROLE_TEAM, USERS_TABLE, clear_client_emails_cache, client_emails, require_role,
)
from report_dashboard.repo import ReportRepo

# 게이트를 이 파일에서도 호출한다 — 이유는 1_리포트.py 상단 주석과 같다
# (uses_pages_directory 플래그가 True인 창에서는 app.py가 아예 실행되지 않는다).
# 이 페이지는 열람 권한을 부여·해제하므로 require_role()만으로는 부족하다 —
# 그것만 쓰면 광고주(client)도 통과한다. 팀 역할까지 요구한다.
role, email = require_role()
if role != ROLE_TEAM:
    st.title("등록 · 관리자")
    st.error("이 페이지는 담당자 전용이다. 이 계정에는 등록·관리자 권한이 없다.")
    st.stop()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _label(content: dict) -> str:
    return content.get("title") or content["url"]


repo = ReportRepo()

st.title("등록 · 관리자")

# -- 1. 캠페인 등록 ---------------------------------------------------

st.header("1. 캠페인 등록")
with st.form("campaign_form"):
    brand = st.text_input("브랜드", key="campaign_brand")
    name = st.text_input("캠페인명", key="campaign_name")
    start_date = st.text_input("시작일 (YYYY-MM-DD)", key="campaign_start")
    end_date = st.text_input("종료일 (YYYY-MM-DD)", key="campaign_end")
    submitted = st.form_submit_button("캠페인 저장", key="campaign_submit")

if submitted:
    if not brand or not name:
        st.warning("브랜드와 캠페인명을 입력해야 저장된다.")
    else:
        repo.save_campaign({
            "campaign_id": _new_id("cmp"),
            "brand": brand,
            "name": name,
            "start_date": start_date,
            "end_date": end_date,
            "created_at": _now(),
        })
        st.success(f"{brand} · {name} 저장했다.")

campaigns = repo.campaigns()
if campaigns:
    st.dataframe(campaigns, width="stretch")
else:
    st.info("아직 등록된 캠페인이 없다.")

CHANNELS = ["youtube", "blog", "cafe", "community", "instagram"]

campaign_labels = {f"{c['brand']} · {c['name']}": c["campaign_id"] for c in campaigns}

# -- 2. 콘텐츠 등록 ---------------------------------------------------

st.header("2. 콘텐츠 등록")

if not campaign_labels:
    st.info("먼저 캠페인을 등록해야 콘텐츠를 등록할 수 있다.")
else:
    with st.form("content_form"):
        campaign_label = st.selectbox("캠페인", options=list(campaign_labels.keys()), key="content_campaign")
        channel = st.selectbox("채널", options=CHANNELS, key="content_channel")
        url = st.text_input("URL", key="content_url")
        title = st.text_input("제목", key="content_title")
        release_at = st.text_input("릴리즈 일정 (YYYY-MM-DD HH:MM)", key="content_release")
        submitted_content = st.form_submit_button("콘텐츠 저장", key="content_submit")

    if submitted_content:
        if not url:
            st.warning("URL을 입력해야 저장된다.")
        else:
            repo.save_content({
                "content_id": _new_id("cnt"),
                "campaign_id": campaign_labels[campaign_label],
                "channel": channel,
                "url": url,
                "title": title,
                "release_at": release_at,
                "created_at": _now(),
            })
            st.success(f"{title or url} 저장했다.")
            # rerun 안 씀 — Task 4와 같은 이유(성공 메시지가 사라지는 버그, 이미 수정됨)

contents = repo.contents()
if contents:
    st.dataframe(contents, width="stretch")
else:
    st.info("아직 등록된 콘텐츠가 없다.")

# -- 3. 목표조회수 등록 ------------------------------------------------

st.header("3. 목표조회수 등록")

if not campaign_labels:
    st.info("먼저 캠페인을 등록해야 목표를 등록할 수 있다.")
else:
    target_campaign_label = st.selectbox(
        "캠페인", options=list(campaign_labels.keys()), key="target_campaign_picker"
    )
    target_campaign_id = campaign_labels[target_campaign_label]
    scope_type = st.selectbox("목표 단위", options=["content", "channel"], key="target_scope_type_picker")

    if scope_type == "content":
        scope_options = {
            _label(c): c["content_id"]
            for c in repo.contents(campaign_id=target_campaign_id)
        }
    else:
        scope_options = {ch: ch for ch in CHANNELS}

    with st.form(f"target_form__{target_campaign_id}__{scope_type}"):
        scope_label = st.selectbox(
            "대상",
            options=list(scope_options.keys()) or ["(등록된 대상 없음)"],
            key=f"target_scope_key__{target_campaign_id}__{scope_type}",
        )
        target_views = st.number_input(
            "목표 조회수", min_value=0, step=100,
            key=f"target_views__{target_campaign_id}__{scope_type}",
        )
        submitted_target = st.form_submit_button(
            "목표 저장", key=f"target_submit__{target_campaign_id}__{scope_type}"
        )

    if submitted_target:
        if scope_label not in scope_options:
            st.warning("대상을 먼저 등록해야 목표를 저장할 수 있다.")
        else:
            repo.save_target({
                "target_id": _new_id("tgt"),
                "campaign_id": target_campaign_id,
                "scope_type": scope_type,
                "scope_key": scope_options[scope_label],
                "target_views": int(target_views),
                "created_at": _now(),
            })
            st.success(f"{scope_label} 목표 {int(target_views)}회 저장했다.")
            # rerun 안 씀 — Task 4와 같은 이유(성공 메시지가 사라지는 버그, 이미 수정됨)

targets = repo.targets()
if targets:
    st.dataframe(targets, width="stretch")
else:
    st.info("아직 등록된 목표가 없다.")

# -- 4. 수동 조회수 입력 ------------------------------------------------

st.header("4. 수동 조회수 입력")
st.caption("인스타그램 콘텐츠는 항상 여기서 입력한다. 그 외 채널은 자동 수집이 실패했을 때만 여기 뜬다.")

latest_run = repo.latest_collection_run()
failed_content_ids = set((latest_run or {}).get("failed_items", []))
all_contents = repo.contents()

manual_candidates = {
    _label(c): c["content_id"]
    for c in all_contents
    if c["channel"] == "instagram" or c["content_id"] in failed_content_ids
}

if not manual_candidates:
    st.info("지금은 수동 입력이 필요한 콘텐츠가 없다.")
else:
    with st.form("manual_metric_form"):
        manual_label = st.selectbox("콘텐츠", options=list(manual_candidates.keys()), key="manual_metric_content")
        manual_views = st.number_input("조회수", min_value=0, step=1, key="manual_metric_views")
        submitted_manual = st.form_submit_button("조회수 저장", key="manual_metric_submit")

    if submitted_manual:
        manual_content_id = manual_candidates[manual_label]
        manual_channel = next(c["channel"] for c in all_contents if c["content_id"] == manual_content_id)
        source = "manual_instagram" if manual_channel == "instagram" else "manual_fallback"
        repo.save_content_metric({
            "content_id": manual_content_id,
            "captured_at": _now(),
            "views": int(manual_views),
            "source": source,
            "accuracy": "실측",
        })
        st.success(f"{manual_label} 조회수 {int(manual_views)} 저장했다.")
        # rerun 안 씀 — Task 4와 같은 이유(성공 메시지가 사라지는 버그, 이미 수정됨)

# -- 5. 수집 상태 ------------------------------------------------------
# latest_run / failed_content_ids / all_contents 는 섹션 4에서 이미 계산해둔 값을 그대로 쓴다.
# 섹션 4를 제거·재배치하면 여기서 NameError가 난다.

st.header("5. 수집 상태")

if latest_run is None:
    st.info("아직 자동 수집이 실행된 적 없다.")
else:
    st.write(f"마지막 실행: {latest_run.get('started_at', '')} ~ {latest_run.get('finished_at', '')}")
    st.write(f"대상 {latest_run.get('target_count', 0)}건 중 {latest_run.get('success_count', 0)}건 성공")
    if failed_content_ids:
        failed_titles = [_label(c) for c in all_contents if c["content_id"] in failed_content_ids]
        st.warning("수집 실패 항목이 있다 — 위 '수동 조회수 입력'에서 채워야 한다: " + ", ".join(failed_titles))
    else:
        st.success("직전 실행에서 실패한 항목 없음.")

# -- 6. 광고주 계정 -----------------------------------------------------

st.header("6. 광고주 계정")
st.caption(
    "여기 등록된 구글 계정만 리포트를 볼 수 있다. 우리 팀 계정은 여기가 아니라 "
    "배포 설정(secrets)에 있다 — 시트를 고쳐 관리자 권한을 얻을 수 없게 하기 위해서다."
)

# "어떤 광고주가 활성인가" 규칙은 auth.client_emails()가 소유한다 — 여기서
# 다시 구현하면 규칙이 바뀔 때 게이트와 이 화면의 목록이 서로 갈라진다.
active_clients = client_emails()
if active_clients is None:
    # None은 "광고주가 없음"이 아니라 "읽기 실패"다. 빈 목록으로 뭉개면 화면이
    # "등록된 계정이 없다"고 거짓말하고, 그 상태에서 해제 폼도 사라진다.
    st.error(
        "광고주 계정 목록을 읽지 못했다. 저장소 상태를 확인해라 — "
        "이 상태에서는 아래 목록이 비어 보이지만 실제 등록 상태는 알 수 없다."
    )
    active_clients = []

with st.form("client_add_form"):
    client_email = st.text_input("광고주 구글 계정 이메일", key="client_email")
    submitted_client = st.form_submit_button("계정 추가", key="client_add_submit")

if submitted_client:
    # 소문자로 정규화한다 — Store.latest는 email 문자열을 리터럴 키로 쓰므로
    # 대소문자가 다르면 같은 주소가 서로 다른 리비전 계열로 갈라진다. 그 경우
    # 한쪽만 revoke해도 case-variant 키가 active=True로 남아 로그인 게이트를
    # 계속 통과시킨다(로그인 쪽 매칭은 정규화돼 있어서 더 위험하다).
    candidate = (client_email or "").strip().lower()
    local_part, _, domain_part = candidate.partition("@")
    if candidate.count("@") != 1 or not local_part or not domain_part:
        st.warning("올바른 이메일을 입력해야 저장된다.")
    else:
        repo.store.save(USERS_TABLE, {
            "email": candidate,
            "active": True,
            "created_at": _now(),
        })
        # allowlist 캐시를 즉시 버린다 — 안 버리면 다음 rerun에서 TTL이 만료될
        # 때까지 방금 추가한 계정이 게이트에 안 보인다.
        clear_client_emails_cache()
        st.success(f"{candidate} 계정을 추가했다.")
        # rerun 안 씀 — 성공 메시지가 사라지는 버그(9fb77bc)와 같은 이유.
        if candidate not in active_clients:
            active_clients.append(candidate)

if active_clients:
    with st.form("client_revoke_form"):
        revoke_pick = st.selectbox("해제할 계정", options=active_clients, key="client_revoke_pick")
        submitted_revoke = st.form_submit_button("열람 권한 해제", key="client_revoke_submit")

    if submitted_revoke:
        revoked = (revoke_pick or "").strip().lower()
        repo.store.save(USERS_TABLE, {
            "email": revoked,
            "active": False,
            "created_at": _now(),
        })
        # 해제는 캐시를 반드시 즉시 버려야 한다 — 안 버리면 해제된 계정이 TTL
        # 동안 계속 게이트를 통과한다.
        clear_client_emails_cache()
        st.success(f"{revoked} 계정의 열람 권한을 해제했다.")
        # active_clients에서도 지운다 — 안 지우면 방금 해제했다는 성공 메시지
        # 바로 아래 표에 그 계정이 여전히 "열람 가능"으로 남는다(표시 버그).
        # 이 표를 폼/처리보다 뒤에 그리는 것도 같은 이유 — 폼 처리 전에 그리면
        # 이 remove가 반영되기 전 상태를 그리게 된다.
        if revoked in active_clients:
            active_clients.remove(revoked)

    st.write("현재 열람 가능한 광고주 계정")
    st.dataframe([{"email": e} for e in active_clients], width="stretch")
else:
    st.info("아직 등록된 광고주 계정이 없다.")
