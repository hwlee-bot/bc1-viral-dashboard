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
    """키워드별로 탭마다 가장 최근 관측 행을 묶어 돌려준다.

    반환: {키워드: {탭: 최신 행 dict}}. 그 탭에 이 키워드로 저장된 행이 아예
    없으면 그 탭 키 자체가 빠진다 — "검색했지만 매치 없음"인 rank=None 행과
    "이 탭이 아직 한 번도 안 돌았음"을 구분하기 위해서다.
    """
    summary = {}
    for keyword in keywords:
        keyword_ranks = [r for r in ranks if r["keyword"] == keyword]
        by_tab = {}
        for tab in KEYWORD_RANK_TABS:
            tab_ranks = [r for r in keyword_ranks if r.get("search_tab") == tab]
            if not tab_ranks:
                continue
            by_tab[tab] = max(
                enumerate(tab_ranks), key=lambda pair: (pair[1]["captured_at"], pair[0])
            )[1]
        summary[keyword] = by_tab
    return summary


def exposure_counts_by_channel(contents: list[dict], ranks: list[dict]) -> dict:
    counts = defaultdict(int)
    for content in contents:
        rank = latest_rank(ranks, content["content_id"])
        if rank is not None and rank <= TOP_EXPOSURE_RANK:
            counts[content["channel"]] += 1
    return dict(counts)


def target_progress_pct(current_views: int, target_views: int) -> int:
    if not target_views:
        return 0
    return round(current_views / target_views * 100)


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
