"""캠페인·콘텐츠 등록, 캠페인 키워드 등록, 브랜드 사전, 수동 조회수 입력, 수집 상태 확인.

바이럴 성과 리포팅 대시보드의 관리자 화면. 자동 수집(cron)이 못 채우는
칸(인스타그램 전량, 그 외 채널의 수집 실패 항목)은 여기서 사람이 채운다.
"""

import uuid
from datetime import datetime

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

import streamlit as st

from report_dashboard.auth import (
    ROLE_TEAM, USERS_TABLE, clear_client_emails_cache, client_emails, require_role,
)
from report_dashboard import content_sheet_sync, share, ui
from report_dashboard.design_system import inject_design_system
from report_dashboard.header import render_header
from report_dashboard.repo import ReportRepo
from report_dashboard.reporting import latest_collection_runs_by_type

# 게이트를 이 파일에서도 호출한다 — 이유는 1_상위노출.py 상단 주석과 같다
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

inject_design_system()
render_header(role, email, repo.campaigns(), current="등록 · 관리자")


def _sheet_chip_html() -> str:
    try:
        spreadsheet_id = st.secrets["sheets"]["spreadsheet_id"]
    except Exception:
        return ""
    return f'<a class="chip" href="https://docs.google.com/spreadsheets/d/{spreadsheet_id}" target="_blank">시트 열기 ↗</a>'


_controls_html = (
    _sheet_chip_html()
    + '<a class="chip" href="https://github.com/hwlee-bot/bc1-viral-report/actions" target="_blank">GitHub Actions ↗</a>'
)
st.markdown(
    ui.title_block(
        "등록 · 관리자",
        "<b>담당자 전용</b> · 캠페인·콘텐츠·키워드 등록, 수동 조회수, 수집 상태, 광고주 계정 · 저장은 시트에 즉시 반영",
        _controls_html,
    ),
    unsafe_allow_html=True,
)

CHANNELS = ["youtube", "blog", "cafe", "community", "instagram"]

campaigns = repo.campaigns()
all_contents = repo.contents()
kw_all = repo.target_keywords()
latest_run = repo.latest_collection_run()
failed_content_ids = set((latest_run or {}).get("failed_items", []))
active_clients_raw = client_emails()
active_clients_count = len(active_clients_raw) if active_clients_raw is not None else 0

toc, body = st.columns([1.6, 8.4], gap="large")
with toc:
    st.markdown(
        '<nav class="toc">'
        f'<a href="#sec-campaign">캠페인 <small>{len(campaigns)}</small></a>'
        f'<a href="#sec-content">콘텐츠 <small>{len(all_contents)}</small></a>'
        f'<a href="#sec-keyword">키워드 <small>{len(kw_all)}</small></a>'
        '<a href="#sec-manual">수동 조회수</a>'
        '<a href="#sec-status">수집 상태 <small>3</small></a>'
        f'<a href="#sec-users">광고주 계정 <small>{active_clients_count}</small></a></nav>',
        unsafe_allow_html=True,
    )


def _blk(anchor: str, title: str, desc: str) -> None:
    st.markdown(
        f'<section class="blk" id="{anchor}"><div class="sec-h reveal"><div><h2 class="h-sec">{title}</h2><p>{desc}</p></div></div></section>',
        unsafe_allow_html=True,
    )


with body:
    # -- 캠페인 ---------------------------------------------------

    _blk("sec-campaign", "캠페인", "브랜드 하나에 캠페인 여러 개. 리포트의 캠페인 선택 목록이 여기서 나온다.")

    with st.form("campaign_form"):
        f1, f2, f3, f4 = st.columns(4)
        brand = f1.text_input("브랜드", key="campaign_brand")
        name = f2.text_input("캠페인명", key="campaign_name")
        start_date = f3.text_input("시작일 (YYYY-MM-DD)", key="campaign_start")
        end_date = f4.text_input("종료일 (YYYY-MM-DD)", key="campaign_end")
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
        st.markdown(ui.table_html(
            [("캠페인", False), ("브랜드", False), ("기간", False), ("콘텐츠", True), ("키워드", True)],
            [[
                f'<span class="who">{ui.esc(c["name"])}</span>',
                ui.esc(c["brand"]),
                f'<span class="mono label">{ui.esc(c.get("start_date") or "—")} – {ui.esc(c.get("end_date") or "—")}</span>',
                f'<span class="mono">{sum(1 for x in all_contents if x["campaign_id"] == c["campaign_id"])}</span>',
                f'<span class="mono">{sum(1 for k in kw_all if k["campaign_id"] == c["campaign_id"])}</span>',
            ] for c in campaigns],
        ), unsafe_allow_html=True)
    else:
        st.markdown(ui.empty_state("아직 등록된 캠페인이 없다", "위 폼으로 첫 캠페인을 저장한다."), unsafe_allow_html=True)

    campaign_labels = {f"{c['brand']} · {c['name']}": c["campaign_id"] for c in campaigns}

    # -- 콘텐츠 ---------------------------------------------------

    _blk("sec-content", "콘텐츠", "채널별 콘텐츠 URL 등록. 자동 수집기가 이 목록을 기준으로 지표를 채운다.")

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

        st.markdown('<div class="or">시트에서 불러오기</div>', unsafe_allow_html=True)
        sheet_campaign_label = st.selectbox(
            "캠페인", options=list(campaign_labels.keys()), key="sheet_sync_campaign",
        )
        sheet_campaign_id = campaign_labels[sheet_campaign_label]
        existing_link = repo.content_sheet_link(sheet_campaign_id)
        default_sheet_url = existing_link["spreadsheet_url"] if existing_link else ""
        # st.text_input의 value=는 key가 이미 session_state에 있으면 무시된다 — 그래서
        # 캠페인을 바꿔도 URL 입력창이 이전 캠페인 값을 계속 들고 있는 버그가 있었다
        # (최종 리뷰에서 AppTest로 확인됨: A 선택 → B로 전환해도 박스가 A의 URL을
        # 보여줌 — 그 상태로 동기화하면 A 시트가 B 캠페인에 섞여 들어간다).
        # 선택된 캠페인이 직전 렌더와 달라졌을 때만 박스 값을 그 캠페인의 저장된
        # URL로 리셋한다.
        if st.session_state.get("sheet_sync_campaign_shown") != sheet_campaign_id:
            st.session_state["sheet_sync_url"] = default_sheet_url
            st.session_state["sheet_sync_campaign_shown"] = sheet_campaign_id
        sheet_url = st.text_input("구글시트 URL", key="sheet_sync_url")
        sync_clicked = st.button("시트에서 불러오기", key="sheet_sync_submit")

        if sync_clicked:
            spreadsheet_id = content_sheet_sync.extract_spreadsheet_id(sheet_url)
            if spreadsheet_id is None:
                st.error("올바른 구글시트 링크가 아니다.")
            else:
                try:
                    grid = content_sheet_sync.fetch_sheet_rows(spreadsheet_id)
                except Exception as exc:
                    if "403" in str(exc) or "PERMISSION_DENIED" in str(exc):
                        st.error(
                            "이 시트에 서비스 계정 접근 권한이 없다 — "
                            "bc1-viral@viral-solution-505017.iam.gserviceaccount.com을 "
                            "뷰어로 공유해달라."
                        )
                    else:
                        st.error(f"시트를 읽을 수 없다: {exc}")
                else:
                    existing_urls = {c["url"] for c in repo.contents(campaign_id=sheet_campaign_id)}
                    candidates, skipped = content_sheet_sync.parse_sheet_content_rows(grid, existing_urls)
                    now = _now()
                    for c in candidates:
                        repo.save_content({
                            "content_id": _new_id("cnt"),
                            "campaign_id": sheet_campaign_id,
                            "channel": c["channel"],
                            "url": c["url"],
                            "title": c["title"],
                            "release_at": c["release_at"],
                            "created_at": now,
                        })
                    if existing_link is None or existing_link["spreadsheet_url"] != sheet_url:
                        repo.save_content_sheet_link({
                            "campaign_id": sheet_campaign_id,
                            "spreadsheet_url": sheet_url,
                            "created_at": now,
                        })
                    dup_count = sum(1 for s in skipped if "이미 등록된 URL" in s)
                    error_count = len(skipped) - dup_count
                    st.success(
                        f"{len(candidates)}건 신규 등록 · {dup_count}건 중복 건너뜀 · "
                        f"{error_count}건 형식 오류로 건너뜀"
                    )
                    if skipped:
                        st.caption(" / ".join(skipped))

    contents = repo.contents()
    if contents:
        display_contents = contents[:20]
        content_rows = []
        for c in display_contents:
            raw_url = c["url"]
            url_display = raw_url if len(raw_url) <= 60 else raw_url[:57] + "…"
            collected_ok = c["content_id"] not in failed_content_ids
            content_rows.append([
                f'<span class="who">{ui.esc(_label(c))}</span>',
                f'{ui.channel_icon(c["channel"])} {ui.esc(ui.CHANNEL_LABEL.get(c["channel"], c["channel"]))}',
                f'<span class="mono label">{ui.esc(url_display)}</span>',
                f'<span class="mono">{ui.esc(c.get("release_at") or "—")}</span>',
                ui.status("ok", "정상") if collected_ok else ui.status("fail", "실패"),
            ])
        st.markdown(ui.table_html(
            [("콘텐츠", False), ("채널", False), ("URL", False), ("릴리즈", False), ("수집", False)], content_rows,
        ), unsafe_allow_html=True)
        if len(contents) > 20:
            st.caption(f"… {len(contents) - 20}건 더")
    else:
        st.markdown(ui.empty_state("아직 등록된 콘텐츠가 없다", "위 폼으로 콘텐츠를 등록하거나 시트에서 불러온다."), unsafe_allow_html=True)

    # -- 키워드 ‖ 수동 조회수 --------------------------------------

    kw_col, manual_col = st.columns(2, gap="large")

    with kw_col:
        _blk(
            "sec-keyword", "키워드",
            "네이버 순위 자동 수집기가 매일 이 목록의 키워드를 검색해서 이 캠페인 콘텐츠 중 잡히는 게 있는지 확인한다.",
        )

        if not campaign_labels:
            st.info("먼저 캠페인을 등록해야 키워드를 등록할 수 있다.")
        else:
            with st.form("target_keyword_form"):
                keyword_campaign_label = st.selectbox(
                    "캠페인", options=list(campaign_labels.keys()), key="target_keyword_campaign"
                )
                keyword_text = st.text_input("키워드", key="target_keyword_text")
                submitted_keyword = st.form_submit_button("키워드 저장", key="target_keyword_submit")

            if submitted_keyword:
                selected_campaign_id = campaign_labels[keyword_campaign_label]
                existing_keywords = {k["keyword"] for k in repo.target_keywords(campaign_id=selected_campaign_id)}
                if not keyword_text:
                    st.warning("키워드를 입력해야 저장된다.")
                elif keyword_text in existing_keywords:
                    st.warning(f"'{keyword_text}'는 이 캠페인에 이미 등록돼 있다. 중복 등록하면 수집기가 같은 키워드를 하루에 두 번 검색한다.")
                else:
                    repo.save_target_keyword({
                        "keyword_id": _new_id("kw"),
                        "campaign_id": selected_campaign_id,
                        "keyword": keyword_text,
                        "created_at": _now(),
                    })
                    st.success(f"{keyword_text} 저장했다.")
                    # rerun 안 씀 — Task 4와 같은 이유(성공 메시지가 사라지는 버그, 이미 수정됨)

            keyword_campaign_id = campaign_labels[keyword_campaign_label]
            kw_for_campaign = repo.target_keywords(campaign_id=keyword_campaign_id)
            if kw_for_campaign:
                chips = "".join(f'<span class="chip">{ui.esc(k["keyword"])}</span>' for k in kw_for_campaign)
                st.markdown(f'<div class="kw-chips">{chips}</div>', unsafe_allow_html=True)
            else:
                st.caption("이 캠페인에 등록된 키워드가 없다.")

            st.markdown('<div class="or">브랜드 사전</div>', unsafe_allow_html=True)
            # 캠페인 셀렉트는 st.form 밖에 둔다 — form 안에 있으면 "캠페인 전환 +
            # 텍스트 입력 + 제출"이 한 rerun에 몰려서, 아래 세션시드 로직이 방금
            # 제출된 텍스트를 읽기도 전에 새 캠페인의 기본값으로 덮어써버린다
            # (제출은 성공했다고 뜨지만 실제로는 아무것도 저장되지 않는 데이터
            # 유실 버그 — 리뷰에서 재현됨, R17). form 밖에 두면 캠페인을 바꾸는
            # 순간 즉시 rerun이 돌아 시드가 먼저 반영되고, 그다음 rerun에서
            # 텍스트 입력·제출이 안전하게 처리된다.
            bt_label = st.selectbox("캠페인", options=list(campaign_labels), key="brand_terms_campaign")
            cid_for_terms = campaign_labels[bt_label]
            existing = share.terms_from_rows(repo.brand_terms(cid_for_terms))
            default_text = "\n".join(f"{t['brand']} = {', '.join(t['aliases'])}" for t in existing)
            # brand_terms_text는 key가 이미 session_state에 있으면 value=가 무시되고
            # 경고가 뜬다 — 선택된 캠페인이 바뀌었을 때만 세션 상태를 직접 채우고,
            # value= 파라미터 자체는 절대 넘기지 않는다(sheet_sync_url과 같은 패턴).
            if st.session_state.get("brand_terms_campaign_shown") != cid_for_terms:
                st.session_state["brand_terms_text"] = default_text
                st.session_state["brand_terms_campaign_shown"] = cid_for_terms
            with st.form("brand_terms_form"):
                text = st.text_area(
                    "점유율 브랜드 사전 (줄마다 `브랜드 = 별칭, 별칭` · 첫 줄이 우리 브랜드)",
                    key="brand_terms_text", height=120,
                )
                bt_submit = st.form_submit_button("브랜드 사전 저장", key="brand_terms_submit")

            if bt_submit:
                parsed = share.parse_brand_terms(text)
                cid = campaign_labels[bt_label]
                now = _now()
                seen = {t["brand"] for t in parsed}
                for t in parsed:
                    repo.save_brand_terms({
                        "campaign_id": cid, "brand": t["brand"], "aliases": ",".join(t["aliases"]),
                        "is_ours": t["is_ours"], "created_at": now,
                    })
                # 새 텍스트에서 빠진 브랜드는 aliases=""로 덮어써 무효화한다 —
                # 지우지 않는다(append-only), 다음 조회에서 terms_from_rows가 건너뛴다.
                for t in existing:
                    if t["brand"] not in seen:
                        repo.save_brand_terms({
                            "campaign_id": cid, "brand": t["brand"], "aliases": "", "is_ours": False, "created_at": now,
                        })
                st.success(f"브랜드 {len(parsed)}개 저장했다 (우리 브랜드: {parsed[0]['brand'] if parsed else '—'}).")

    with manual_col:
        _blk(
            "sec-manual", "수동 조회수",
            "인스타그램 콘텐츠는 항상 여기서 입력한다. 그 외 채널은 자동 수집이 실패했을 때만 여기 뜬다.",
        )

        # latest_run / failed_content_ids / all_contents는 스크립트 상단에서 이미
        # 계산해뒀다(콘텐츠 표의 "수집" 열과 같은 값을 쓴다) — 여기서 다시 계산하지 않는다.
        fresh_manual_candidates = {
            _label(c): c["content_id"]
            for c in all_contents
            if c["channel"] == "instagram" or c["content_id"] in failed_content_ids
        }

        # 후보 목록을 매 rerun마다 통째로 새로 계산한 값으로 덮어쓰면, 폼을 그린 뒤
        # 제출하기 전에 크론이 끼어들어 후보가 사라지는 순간 selectbox 옵션에서도
        # 사라진다 — 그러면 위젯 자체가 다시 그려지지 않아 방금 누른 제출 이벤트가
        # 조용히 유실된다(경고 메시지조차 못 띄운다). 그래서 한 번 후보로 보인
        # 콘텐츠는 세션이 끝날 때까지 옵션에 남겨 폼이 계속 그려지게 하고, 실제
        # 유효성은 아래 제출 처리에서 이번 실행의 최신 failed_content_ids로 다시
        # 확인한다(동시성 방어).
        manual_candidates = st.session_state.setdefault("manual_candidates_snapshot", {})
        manual_candidates.update(fresh_manual_candidates)

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

                # 폼을 그린 시점과 제출 시점 사이에 자동 수집 크론이 끼어들어 이 콘텐츠의
                # '실패' 상태가 사라졌을 수 있다 — 제출 직전에 다시 확인한다(동시성 방어).
                # failed_content_ids는 이번 실행에서 이미 최신 상태로 읽어둔 값이다.
                still_valid = manual_channel == "instagram" or manual_content_id in failed_content_ids

                if not still_valid:
                    manual_candidates.pop(manual_label, None)
                    st.warning(
                        f"{manual_label}의 수집 상태가 방금 바뀌었다(자동 수집이 먼저 채웠을 수 있다). "
                        "새로고침 후 다시 확인해달라."
                    )
                else:
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

        # 기존 "수집 실패 항목 → 수동 입력" 경고 — 수동 조회수 섹션 아래 그대로 유지.
        # latest_run / failed_content_ids / all_contents는 위에서 이미 계산해둔 값을 쓴다.
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

    # -- 수집 상태 ----------------------------------------------------

    _blk("sec-status", "수집 상태", "GitHub Actions 워크플로별 마지막 실행.")

    runs = latest_collection_runs_by_type(repo.collection_runs())
    status_labels = [
        ("keyword_ranks", "네이버 순위 · SERP", "매일 06:00"),
        ("comments", "댓글 수집", "매일 06:30"),
        ("content_metrics", "인스타 좋아요·조회수", "매일 06:30"),
    ]
    status_rows_html = []
    for run_type, run_title, sched in status_labels:
        r = runs.get(run_type)
        if not r:
            status_rows_html.append(
                f'<div class="hs"><div class="n"><b>{run_title}</b><small>{sched}</small></div>'
                f'<span class="mono">—</span><span class="mono label">실행 기록 없음</span>{ui.status("skip", "대기")}</div>'
            )
            continue
        success = r.get("success_count", 0)
        target = r.get("target_count", 0)
        if success == target and target > 0:
            status_kind, status_label = "ok", "정상"
        elif 0 < success < target:
            status_kind, status_label = "skip", "부분 성공"
        else:
            status_kind, status_label = "fail", "실패"
        status_rows_html.append(
            f'<div class="hs"><div class="n"><b>{run_title}</b><small>{sched}</small></div>'
            f'<span class="mono">{ui.esc(r.get("started_at", "")[:16].replace("T", " "))}</span>'
            f'<span class="mono label">{success} / {target} 성공</span>'
            f'{ui.status(status_kind, status_label)}</div>'
        )
    st.markdown("".join(status_rows_html), unsafe_allow_html=True)

    # -- 광고주 계정 --------------------------------------------------

    _blk(
        "sec-users", "광고주 계정",
        "여기 등록된 구글 계정만 리포트를 볼 수 있다. 우리 팀 계정은 여기가 아니라 배포 설정(secrets)에 있다 — "
        "시트를 고쳐 관리자 권한을 얻을 수 없게 하기 위해서다.",
    )

    # "어떤 광고주가 활성인가" 규칙은 auth.client_emails()가 소유한다 — 여기서
    # 다시 구현하면 규칙이 바뀔 때 게이트와 이 화면의 목록이 서로 갈라진다.
    active_clients = active_clients_raw
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

        latest_user_rows = {r["email"]: r for r in repo.store.latest(USERS_TABLE, ("email",))}
        st.markdown(ui.table_html(
            [("계정", False), ("역할", False), ("추가일", False)],
            [[
                f'<span class="mono">{ui.esc(e)}</span>',
                '<span class="role">광고주</span>',
                f'<span class="mono label">{ui.esc((latest_user_rows.get(e, {}).get("created_at") or "")[:10] or "—")}</span>',
            ] for e in active_clients],
        ), unsafe_allow_html=True)
    else:
        st.info("아직 등록된 광고주 계정이 없다.")
