"""리포트 대시보드의 순수 계산 로직.

Streamlit에 의존하지 않는다 — `pages/1_리포트.py`는 이 함수들을 가져다
화면에 조립만 한다. 빠른 단위 테스트를 위해 분리했다.
"""

from collections import defaultdict

TOP_EXPOSURE_RANK = 10  # 네이버 검색 1페이지 진입 기준


def _latest_by_content(rows: list[dict], content_id: str, order_field: str) -> dict | None:
    """content_id에 해당하는 행 중 order_field가 가장 큰 것을 돌려준다.

    order_field 값이 여러 행에서 같으면(예: 같은 날짜 문자열) 리스트에서
    더 나중에 나온 행(= Store에 더 나중에 append된 행)을 우선한다 —
    먼저 나온 행을 우선하는 Python 기본 max() 동작은 날짜만 있는
    captured_at 값이 흔한 이 도메인에서 "더 최신"의 의미와 반대로 갈 수 있다.
    """
    matching = [r for r in rows if r["content_id"] == content_id]
    if not matching:
        return None
    return max(enumerate(matching), key=lambda pair: (pair[1][order_field], pair[0]))[1]


def latest_views(metrics: list[dict], content_id: str) -> int:
    latest = _latest_by_content(metrics, content_id, "captured_at")
    return latest["views"] if latest else 0


def latest_rank_row(ranks: list[dict], content_id: str) -> dict | None:
    """content_id의 가장 최근 captured_at 시점 행 중 VIEW 탭을 우선해서 돌려준다.

    Plan 3부터 콜렉터가 한 번의 실행에서 같은 content_id에 VIEW/블로그API/
    카페API 3탭 행을 동시에(같은 captured_at으로) 남길 수 있다. 그중 사람이
    실제로 보는 통합검색에 가장 가까운 VIEW를 우선한다 — 없으면 나중에
    append된 행(리스트 뒤쪽)을 쓴다. search_tab이 아예 없는 옛 행(Plan 3
    이전 테스트 데이터 등)도 안전하게 처리하도록 .get()을 쓴다.
    """
    matching = [r for r in ranks if r["content_id"] == content_id]
    if not matching:
        return None
    latest_captured_at = max(r["captured_at"] for r in matching)
    same_time = [r for r in matching if r["captured_at"] == latest_captured_at]
    for row in same_time:
        if row.get("search_tab") == "VIEW":
            return row
    return same_time[-1]


def latest_rank(ranks: list[dict], content_id: str) -> int | None:
    row = latest_rank_row(ranks, content_id)
    return row["rank"] if row else None


KEYWORD_RANK_TABS = ("VIEW", "블로그API", "카페API")


def keyword_rank_summary(ranks: list[dict], keywords: list[str]) -> dict:
    """키워드별로 탭마다 가장 최근 수집 배치에서 잡힌 콘텐츠 전부를 순위
    오름차순으로 묶어 돌려준다.

    "가장 최근 수집 배치"는 그 키워드·탭 조합에서 captured_at 문자열이 가장
    큰 값과 정확히 일치하는 행 전부다 — collect_naver_ranks.py::main()이 한
    번의 실행 안에서는 모든 행에 똑같은 now 타임스탬프를 쓰기 때문에
    (루프 시작 전에 한 번만 계산), 이 문자열 일치가 "같은 실행에서 나온 행"과
    정확히 대응한다. 별도 run_id 연결이 필요 없다.

    반환: {키워드: {탭: [행, ...]}}. 그 탭에 이 키워드로 저장된 행이 아예
    없으면 그 탭 키 자체가 빠진다 — "검색했지만 매치 없음"인 rank=None 행과
    "이 탭이 아직 한 번도 안 돌았음"을 구분하기 위해서다(매치 없음도 행은
    있다 — content_id=""인 행 하나로, 리스트에 그 행 하나만 담긴다).
    """
    summary = {}
    for keyword in keywords:
        keyword_ranks = [r for r in ranks if r["keyword"] == keyword]
        by_tab = {}
        for tab in KEYWORD_RANK_TABS:
            tab_ranks = [r for r in keyword_ranks if r.get("search_tab") == tab]
            if not tab_ranks:
                continue
            latest_captured_at = max(r["captured_at"] for r in tab_ranks)
            latest_batch = [r for r in tab_ranks if r["captured_at"] == latest_captured_at]
            by_tab[tab] = sorted(
                latest_batch, key=lambda r: (r["rank"] is None, r["rank"] if r["rank"] is not None else 0)
            )
        summary[keyword] = by_tab
    return summary


def exposure_counts_by_channel(contents: list[dict], ranks: list[dict]) -> dict:
    counts = defaultdict(int)
    for content in contents:
        rank = latest_rank(ranks, content["content_id"])
        if rank is not None and rank <= TOP_EXPOSURE_RANK:
            counts[content["channel"]] += 1
    return dict(counts)


def channel_distribution(contents: list[dict]) -> dict[str, int]:
    """캠페인에 등록된 전체 콘텐츠가 채널별로 몇 건인지 센다.

    exposure_counts_by_channel()과 이름이 비슷하지만 다른 지표다 — 저건
    "네이버 상위노출까지 된 것만" 세고, 이건 "등록된 전체"를 센다. 요약·리포트
    페이지의 채널 비중 도넛/스택바가 이 함수를 쓴다.
    """
    counts: dict[str, int] = defaultdict(int)
    for content in contents:
        counts[content["channel"]] += 1
    return dict(counts)


def rank_history(ranks_for_content: list[dict]) -> list[tuple[str, int]]:
    """콘텐츠 하나의 순위 이력을 관측일 오름차순으로 전부 돌려준다.

    (수집일, 순위) 쌍의 리스트. 상위노출이 안 돼 순위를 못 잡은 날은
    0으로 취급한다 — "측정 불가"를 나타내는 sentinel이며, 화면 쪽
    (1_리포트.py)에서 0을 "미노출"로 따로 표시한다.

    같은 날 여러 키워드가 동시에 잡히면 그 날의 대표값은 더 잘 잡힌(작은,
    0 제외) 순위를 쓴다 — "그날 이 콘텐츠가 얼마나 눈에 띄었는가"를 가장
    잘 나타내는 값이 그거다.
    """
    by_date: dict[str, int] = {}
    for row in ranks_for_content:
        date = row["captured_at"]
        rank = row["rank"] if row["rank"] is not None else 0
        if date not in by_date:
            by_date[date] = rank
        elif rank != 0 and (by_date[date] == 0 or rank < by_date[date]):
            by_date[date] = rank
    return [(date, by_date[date]) for date in sorted(by_date.keys())]


def target_progress_pct(current_views: int, target_views: int) -> int:
    if not target_views:
        return 0
    return round(current_views / target_views * 100)


def participation_rate(views: int, comments_count: int | None) -> float | None:
    """댓글수/조회수를 퍼센트로. 계산할 수 없으면 None — 0%나 지어낸 값 대신
    호출부가 '—'로 정직하게 표시하게 한다."""
    if comments_count is None or not views:
        return None
    return round(comments_count / views * 100, 3)


def build_export_markdown(
    campaign_label: str, contents: list[dict], metrics: list[dict], ranks: list[dict], comments: list[dict]
) -> str:
    lines = [f"# {campaign_label} 성과 리포트", ""]
    for content in contents:
        cid = content["content_id"]
        lines.append(f"## {content.get('title') or content['url']} ({content['channel']})")

        latest_metric = _latest_by_content(metrics, cid, "captured_at")
        if latest_metric:
            lines.append(f"- 최근 조회수: {latest_metric['views']} ({latest_metric['captured_at']})")

        rank_row = latest_rank_row(ranks, cid)
        if rank_row:
            lines.append(f"- 네이버 \"{rank_row['keyword']}\" 순위: {rank_row['rank']}위")

        content_comments = [c for c in comments if c["content_id"] == cid]
        if content_comments:
            lines.append("- 대표 댓글:")
            for comment in content_comments[:3]:
                nickname = comment.get("author_nickname") or "익명"
                lines.append(f"  - \"{comment['text']}\" — {nickname}")

        lines.append("")
    return "\n".join(lines)
