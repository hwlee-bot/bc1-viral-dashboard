"""리포트 대시보드의 순수 계산 로직.

Streamlit에 의존하지 않는다 — `pages/1_상위노출.py`·`pages/2_콘텐츠성과.py`
(와 그 둘이 같이 쓰는 `report_common.py`)가 이 함수들을 가져다 화면에
조립만 한다. 빠른 단위 테스트를 위해 분리했다.
"""

from collections import defaultdict
from datetime import date

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


def latest_keyword_serp(serp_rows: list[dict], keyword: str, search_tab: str) -> list[dict]:
    """이 키워드·탭의 가장 최근 SERP 스냅샷(경쟁 게시글 포함 상위 N건)을
    순위 오름차순으로 돌려준다. keyword_rank_summary와 같은 원칙 — "가장 최근
    수집 배치"는 captured_at 문자열이 가장 큰 값과 일치하는 행 전부다(같은
    실행 안에서는 collect_keyword_serp가 모든 행에 같은 now를 쓴다).
    아직 한 번도 수집 안 됐으면(이 키워드·탭 행이 아예 없으면) 빈 리스트."""
    rows = [r for r in serp_rows if r["keyword"] == keyword and r["search_tab"] == search_tab]
    if not rows:
        return []
    latest_captured_at = max(r["captured_at"] for r in rows)
    latest_batch = [r for r in rows if r["captured_at"] == latest_captured_at]
    return sorted(latest_batch, key=lambda r: r["rank"])


def latest_matched_ranks(ranks: list[dict], keyword: str, search_tab: str) -> list[dict]:
    """이 키워드·탭에서 우리 콘텐츠와 매치된(content_id 있는) 가장 최근 수집
    배치만 돌려준다. viral_keyword_ranks는 append-only라 크론이 돌 때마다
    행이 계속 쌓이는데, 그걸 그대로 다 보여주면 콘텐츠 하나가 날짜마다 다른
    순위로 여러 번 나열되는 버그가 난다(2026-09-03 실측 확인: "파우더룸"이
    9개 날짜의 순위로 중복 표시됨). latest_keyword_serp와 같은 원칙 — 같은
    실행에서 나온 행은 captured_at 문자열이 정확히 같다."""
    matched = [r for r in ranks if r["keyword"] == keyword and r["search_tab"] == search_tab and r.get("content_id")]
    if not matched:
        return []
    latest_captured_at = max(r["captured_at"] for r in matched)
    return [r for r in matched if r["captured_at"] == latest_captured_at]


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
    (2_콘텐츠성과.py)에서 0을 "미노출"로 따로 표시한다.

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


def likes_history(metrics_for_content: list[dict]) -> list[tuple[str, int]]:
    """콘텐츠 하나의 좋아요 수 이력을 관측일 오름차순으로 돌려준다.

    auto_instagram 소스 행만 본다 — rank_history와 같은 방어적 설계로,
    인스타가 아닌 채널이나 조회수만 있는 행이 섞여 들어와도 안전하다.
    같은 날 행이 여러 개면 리스트에서 더 나중 값을 쓴다(재실행 등 대비).
    """
    by_date: dict[str, int] = {}
    for row in metrics_for_content:
        if row.get("source") != "auto_instagram":
            continue
        likes = row.get("likes_count")
        if likes is None:
            continue
        by_date[row["captured_at"]] = likes
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


def average_participation_rate(contents: list[dict], view_metrics: list[dict]) -> float | None:
    """콘텐츠 전체의 참여율(댓글수/조회수) 평균 — 스탯 카드 줄 전용
    (2026-09-02 신규, 레이아웃 리뉴얼). 콘텐츠별로 최신 조회수 시점의 값을
    쓰고, 참여율을 계산할 수 없는 콘텐츠(조회수 0이거나 댓글수 미수집)는
    평균에서 제외한다 — participation_rate()와 같은 원칙, 0%로 지어내지
    않는다. 대상이 하나도 없으면 None(호출부가 '—'로 표시)."""
    rates = []
    for content in contents:
        latest = _latest_by_content(view_metrics, content["content_id"], "captured_at")
        if latest is None:
            continue
        rate = participation_rate(latest["views"], latest.get("comments_count"))
        if rate is not None:
            rates.append(rate)
    return round(sum(rates) / len(rates), 1) if rates else None


def latest_sync_timestamp(metrics: list[dict]) -> str | None:
    """전체 콘텐츠 메트릭 중 가장 최근 captured_at — 사이드바 "DATA SYNCED"
    표시 전용(2026-09-02, 레이아웃 리뉴얼). 데이터가 하나도 없으면 None."""
    if not metrics:
        return None
    return max(m["captured_at"] for m in metrics)


def iso_week_key(captured_at: str) -> str:
    """captured_at(날짜 또는 ISO 타임스탬프)을 ISO 주차 키로 묶는다.

    "2026-08-24T09:00:00" 같은 전체 타임스탬프도 안전하게 받는다 — 앞 10자만
    본다(ISO 날짜는 항상 앞 10자, collect_naver_ranks.py는 datetime.isoformat()을
    쓰지만 테스트 픽스처는 날짜만 쓰기도 해서 둘 다 지원해야 한다)."""
    d = date.fromisoformat(captured_at[:10])
    year, week, _weekday = d.isocalendar()
    return f"{year}-W{week:02d}"


def _week_end_date(week_key: str) -> date:
    year, week = week_key.split("-W")
    return date.fromisocalendar(int(year), int(week), 7)


def week_label(week_key: str) -> str:
    """ISO 주차 키를 "8/24~8/30" 같은 사람이 읽는 날짜 범위로."""
    end = _week_end_date(week_key)
    start = date.fromisocalendar(end.isocalendar()[0], end.isocalendar()[1], 1)
    return f"{start.month}/{start.day}~{end.month}/{end.day}"


def keyword_weekly_exposure_counts(ranks: list[dict], keywords: list[str]) -> dict[str, dict[str, int]]:
    """{키워드: {주차: 그 주 상위노출(<=10위) 콘텐츠 개수}}.

    같은 주 안에 같은 (키워드, 콘텐츠) 조합이 여러 날 잡히면 그 주 최고(최소)
    순위를 그 콘텐츠의 그 주 대표 순위로 쓴다 — rank_history()가 콘텐츠
    카드에서 쓰는 것과 같은 원칙을 주 단위로 확장한 것. 같은 콘텐츠가 여러
    탭(블로그API·카페API 등)에서 잡혀도 1건으로만 센다 — "이 키워드로 우리
    콘텐츠 몇 개가 눈에 띄었나"를 보려는 것이지 탭 개수를 보려는 게 아니다."""
    best_rank: dict[tuple[str, str, str], int] = {}
    for row in ranks:
        keyword = row["keyword"]
        if keyword not in keywords:
            continue
        rank = row.get("rank")
        if rank is None:
            continue
        week = iso_week_key(row["captured_at"])
        key = (keyword, week, row["content_id"])
        if key not in best_rank or rank < best_rank[key]:
            best_rank[key] = rank

    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for (keyword, week, _content_id), rank in best_rank.items():
        if rank <= TOP_EXPOSURE_RANK:
            counts[keyword][week] += 1
    return {keyword: dict(by_week) for keyword, by_week in counts.items()}


def _views_as_of(metrics_for_content: list[dict], cutoff: str) -> int:
    """그 콘텐츠의, cutoff 날짜(포함) 이전 가장 최근 조회수. auto_instagram
    sentinel 행(스펙 §4.2, 실제 조회수 아님)은 제외한다."""
    candidates = [
        m for m in metrics_for_content
        if m.get("source") != "auto_instagram" and m["captured_at"][:10] <= cutoff
    ]
    if not candidates:
        return 0
    return max(candidates, key=lambda m: m["captured_at"])["views"]


def keyword_weekly_view_sums(ranks: list[dict], view_metrics: list[dict], keywords: list[str]) -> dict[str, dict[str, int]]:
    """{키워드: {주차: 그 주 매치된 콘텐츠들의 (그 주 시점) 조회수 합}}.

    "매치" = rank가 None이 아닌 행 — keyword_weekly_exposure_counts와 달리
    10위 문턱을 안 따진다("얼마나 화제인가"는 상위노출 여부와 별개 지표).
    조회수는 그 주가 끝난 날짜 기준으로 그 콘텐츠에 대해 관측된 가장 최근
    값을 쓴다 — 나중 주에 조회수가 더 올라도 그건 다음 주 몫으로 남긴다."""
    matched_content_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in ranks:
        keyword = row["keyword"]
        if keyword not in keywords or row.get("rank") is None:
            continue
        week = iso_week_key(row["captured_at"])
        matched_content_ids[(keyword, week)].add(row["content_id"])

    metrics_by_content: dict[str, list[dict]] = defaultdict(list)
    for metric in view_metrics:
        metrics_by_content[metric["content_id"]].append(metric)

    sums: dict[str, dict[str, int]] = defaultdict(dict)
    for (keyword, week), content_ids in matched_content_ids.items():
        cutoff = _week_end_date(week).isoformat()
        sums[keyword][week] = sum(_views_as_of(metrics_by_content.get(cid, []), cutoff) for cid in content_ids)
    return {keyword: dict(by_week) for keyword, by_week in sums.items()}


def keyword_impact_leaderboard(weekly_scores: dict[str, dict[str, int]]) -> tuple[str | None, list[dict]]:
    """캠페인 키워드끼리 서로 비교한, 가장 최근 주의 파급력 랭킹.

    weekly_scores는 keyword_weekly_exposure_counts()나 keyword_weekly_view_sums()의
    반환값(기준은 호출부가 고른다) — {키워드: {주차: 점수}}.

    점수가 0(또는 그 주 기록이 아예 없음)인 키워드는 그 주 랭킹에서 뺀다 —
    "파급력이 없다"와 "1등이 하나도 없어서 꼴찌가 1등"을 구분해야 순위가
    의미를 갖는다. 지난주에도 점수가 있었으면 순위 변동(delta, 양수=개선)을
    같이 준다 — 지난주에 없던 신규 키워드는 prev_rank/delta가 None.

    반환: (가장 최근 주차 키 또는 None, [{keyword, score, rank, prev_rank, delta}, ...]).
    아무 주차도 없으면 (None, [])."""
    all_weeks = sorted({week for by_week in weekly_scores.values() for week in by_week})
    if not all_weeks:
        return None, []
    current_week = all_weeks[-1]
    prev_week = all_weeks[-2] if len(all_weeks) >= 2 else None

    def _ranked(week: str) -> dict[str, int]:
        scored = sorted(
            (
                (keyword, by_week[week])
                for keyword, by_week in weekly_scores.items()
                if by_week.get(week, 0) > 0
            ),
            key=lambda kv: (-kv[1], kv[0]),
        )
        return {keyword: i + 1 for i, (keyword, _score) in enumerate(scored)}

    current_rank = _ranked(current_week)
    prev_rank = _ranked(prev_week) if prev_week else {}

    rows = []
    for keyword, rank in sorted(current_rank.items(), key=lambda kv: kv[1]):
        pr = prev_rank.get(keyword)
        rows.append({
            "keyword": keyword,
            "score": weekly_scores[keyword][current_week],
            "rank": rank,
            "prev_rank": pr,
            "delta": (pr - rank) if pr is not None else None,
        })
    return current_week, rows


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
