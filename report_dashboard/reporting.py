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


def latest_rank(ranks: list[dict], content_id: str) -> int | None:
    latest = _latest_by_content(ranks, content_id, "captured_at")
    return latest["rank"] if latest else None


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

        latest_rank_row = _latest_by_content(ranks, cid, "captured_at")
        if latest_rank_row:
            lines.append(f"- 네이버 \"{latest_rank_row['keyword']}\" 순위: {latest_rank_row['rank']}위")

        content_comments = [c for c in comments if c["content_id"] == cid]
        if content_comments:
            lines.append("- 대표 댓글:")
            for comment in content_comments[:3]:
                nickname = comment.get("author_nickname") or "익명"
                lines.append(f"  - \"{comment['text']}\" — {nickname}")

        lines.append("")
    return "\n".join(lines)
