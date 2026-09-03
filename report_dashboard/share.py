"""키워드 점유율(스펙 §7 · v4.2 §12). 순수 함수, Streamlit 없음.

분모 = 키워드 × 탭 × `slots`슬롯(가중이면 × `slots(slots+1)/2`). 미수집 탭도 분모에 넣는다 —
"안 보인 것"을 점유율에서 빼면 점유율이 부풀려진다. 최신 captured_at 배치만 집계(append-only 규칙).

`slots`(= 깊이)는 10 / 30 / 50 세 값을 쓴다(`DEPTHS`). 기본값 10은 v4.1까지의 호출부·
내보내기(`share_summary`)와 그대로 호환된다. 깊이 N을 집계하려면 그 배치에 N위까지 저장돼
있어야 한다는 정직성 규칙은 `stored_depth`·`latest_stored_depth`·`trend_batches`가 담당한다.
"""
from __future__ import annotations

from collections import defaultdict

DEPTHS = (10, 30, 50)
SLOTS_PER_TAB = 10
WEIGHTED_PER_TAB = 55  # 10+9+...+1 = weighted_denominator(10)


def weighted_denominator(slots: int) -> int:
    """위치 가중 분모 — slots + (slots-1) + ... + 1."""
    return slots * (slots + 1) // 2


def WEIGHT(rank: int, slots: int = SLOTS_PER_TAB) -> int:
    """위치 가중치 — 1위가 `slots`점, `slots`위가 1점, 그 밖은 0점(집계에서 빠진다)."""
    return max(0, slots + 1 - rank)


def stored_depth(batch_rows) -> int:
    """이 배치가 실제로 몇 위까지 저장돼 있는지(= 최대 rank). 행이 없으면 0."""
    return max((r["rank"] for r in batch_rows if r.get("rank")), default=0)


def parse_brand_terms(text: str) -> list[dict]:
    out = []
    for line in (l.strip() for l in (text or "").splitlines()):
        if not line:
            continue
        brand, _, alias_str = line.partition("=")
        brand = brand.strip()
        aliases = [a.strip() for a in alias_str.split(",") if a.strip()] or [brand]
        out.append({"brand": brand, "aliases": aliases, "is_ours": len(out) == 0})
    return out


def terms_from_rows(rows: list[dict]) -> list[dict]:
    """repo.brand_terms() 행 → parse_brand_terms()와 같은 모양. 우리 브랜드를 맨 앞으로.

    aliases가 빈 문자열인 행은 건너뛴다 — 브랜드를 무효화하는 데 쓰인다(Task 10).
    """
    parsed = []
    for r in rows:
        aliases = [a.strip() for a in str(r.get("aliases", "")).split(",") if a.strip()]
        if not aliases:
            continue
        parsed.append({"brand": r["brand"], "aliases": aliases, "is_ours": bool(r.get("is_ours"))})
    return sorted(parsed, key=lambda t: not t["is_ours"])


def _norm(s: str) -> str:
    return "".join(str(s).lower().split())


def match_brands(title: str, terms: list[dict]) -> set[str]:
    t = _norm(title)
    return {term["brand"] for term in terms if any(_norm(a) and _norm(a) in t for a in term["aliases"])}


def latest_batch(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    latest = max(r["captured_at"] for r in rows)
    return [r for r in rows if r["captured_at"] == latest]


def ours_brand_of(terms: list[dict]) -> str | None:
    """terms에서 우리 브랜드(is_ours=True) 이름을 돌려준다. 없으면 None."""
    return next((t["brand"] for t in terms if t["is_ours"]), None)


def _ours(terms) -> str | None:
    return ours_brand_of(terms)


def latest_stored_depth(serp_rows, keywords, tabs) -> int:
    """최신 수집이 실제로 몇 위까지 저장했는지 — (키워드, 탭) 쌍별 최신 배치 `stored_depth`의 **최댓값**.

    최솟값이 아니라 최댓값인 이유: 수집기는 한 실행에서 모든 쌍에 같은 `top_n`
    (`SERP_STORE_DEPTH`)을 쓴다. 그래서 쌍마다 저장 깊이가 다르다면 그건 "저장을 덜
    했다"가 아니라 "그 키워드·탭의 검색결과가 원래 그만큼뿐이었다"(또는 아직 미수집)라는
    뜻이고, 결과가 적게 잡힌 쌍은 §7 규칙대로 **분모에 그대로 남아** 점유율을 낮춘다.
    최솟값을 쓰면 얇은 키워드 하나가 다른 쌍의 저장 깊이까지 가려 깊이 선택 자체를
    막아버린다(미수집 탭이 하나만 있어도 0이 된다).
    """
    return max(
        (stored_depth(latest_batch([r for r in serp_rows if r["keyword"] == kw and r["search_tab"] == tab]))
         for kw in keywords for tab in tabs),
        default=0,
    )


def keyword_share_rows(serp_rows, keywords, tabs, terms, *, weighted=False, slots=SLOTS_PER_TAB) -> list[dict]:
    """(키워드, 탭)마다 최신 배치의 `rank <= slots` 행만 집계한다.

    깊이 밖(`rank > slots`) 행은 분자·`slots` 카운트 어디에도 들어가지 않고, 분모는
    항상 `slots`(가중이면 `weighted_denominator(slots)`)로 고정이다 — 실제로 몇 건이
    잡혔는지와 무관하게 "그 깊이의 슬롯 전부"가 분모다(§7).

    **쌍 단위 수집 범위 게이트**(§12.1 "기존 배치는 30/50에 절대 섞지 않는다"):
    깊이가 10보다 깊을 때, 자기 최신 배치가 그 깊이까지 저장되지 않은 (키워드, 탭)은
    분자에 아무것도 넣지 않는다(`by_brand {}`, `campaign_score 0`, `ours_score 0`) —
    분모 `slots`는 그대로 남는다. 화면의 깊이 선택 자체는 `latest_stored_depth`(쌍
    최댓값)가 열지만, 그 안에서 얕게 저장된 쌍의 11~50위를 "아무도 없었다"로 세면
    우리 점유율이 실제보다 높게 나오기 때문이다. 어느 쪽이든 행에 `observed`(그 쌍의
    최신 배치 저장 범위)를 담아 화면이 "왜 막대가 없는지"를 말할 수 있게 한다.
    """
    ours = _ours(terms)
    out = []
    for kw in keywords:
        for tab in tabs:
            batch = latest_batch([r for r in serp_rows if r["keyword"] == kw and r["search_tab"] == tab])
            observed = stored_depth(batch)
            gated = slots > SLOTS_PER_TAB and observed < slots
            rows = [] if gated else [r for r in batch if r.get("rank") and r["rank"] <= slots]
            by_brand: dict[str, int] = defaultdict(int)
            campaign = 0
            for r in rows:
                score = WEIGHT(r["rank"], slots) if weighted else 1
                for b in match_brands(r.get("title") or "", terms):
                    by_brand[b] += score
                if r.get("content_id"):
                    campaign += score
            out.append({
                "keyword": kw, "tab": tab, "slots": len(rows), "by_brand": dict(by_brand),
                "ours_score": by_brand.get(ours, 0) if ours else 0, "campaign_score": campaign,
                "denominator": weighted_denominator(slots) if weighted else slots,
                "observed": observed, "gated": gated,
            })
    return out


def total_share(rows: list[dict], ours_brand: str | None) -> dict:
    """전체 점유율 집계. 잔여분을 두 갈래로 정직하게 나눈다(R23):

    - other_brands_pct: 우리·상위 2개 경쟁 브랜드 밖에서 실제로 제목에 매칭된
      다른 브랜드들의 합 — "기타 브랜드".
    - unmatched_pct: 그러고도 남는, 아예 브랜드가 안 매칭된(또는 미수집) 슬롯
      비율 — "미매칭 슬롯". 100에서 우리·top2·기타 브랜드를 뺀 나머지이므로
      반올림 오차로 음수가 나올 수 있어 0 이상으로 clamp한다.

    other_pct는 예전 키 이름과의 하위 호환을 위한 unmatched_pct의 별칭이다.
    """
    denom = sum(r["denominator"] for r in rows) or 1
    by_brand: dict[str, float] = defaultdict(float)
    for r in rows:
        for b, s in r["by_brand"].items():
            by_brand[b] += s
    ours_total = by_brand.get(ours_brand, 0) if ours_brand is not None else 0
    pct = {b: round(s / denom * 100, 1) for b, s in by_brand.items()}
    competitors = sorted((b for b in pct if b != ours_brand), key=lambda b: -pct[b])
    top = competitors[:2]
    other_brands = competitors[2:]
    ours_pct = round(ours_total / denom * 100, 1)
    other_brands_pct = round(sum(pct[b] for b in other_brands), 1)
    unmatched_pct = max(0.0, round(100 - ours_pct - sum(pct[b] for b in top) - other_brands_pct, 1))
    return {
        "by_brand": pct,
        "ours_pct": ours_pct,
        "campaign_pct": round(sum(r["campaign_score"] for r in rows) / denom * 100, 1),
        "denominator": denom,
        "top_brands": top,
        "other_brands_pct": other_brands_pct,
        "unmatched_pct": unmatched_pct,
        "other_pct": unmatched_pct,  # 하위 호환 별칭
        "ours_brand": ours_brand,
    }


def trend_batches(serp_rows, keywords, tabs, *, last_n=15, slots=SLOTS_PER_TAB) -> list[str]:
    """추이에 쓸 captured_at 목록(오름차순, 마지막 `last_n`개) — 창의 **단일 정본**.

    깊이가 10보다 깊으면, 요청한 (키워드 × 탭) 중 **어느 한 쌍이라도** 그 깊이에 닿은
    배치만 남긴다(§12.1). 배치 전체를 통과/탈락으로 가르지 않는 이유는 집계가 이미
    쌍 단위로 게이트되기 때문이다(`keyword_share_rows`) — 닿는 쌍은 세고 얕은 쌍은
    빠지므로, 배치를 남기는 조건도 "닿는 쌍이 하나라도 있는가"가 맞다. 반대로 닿는
    쌍이 **하나도 없는** 배치는 전부 게이트돼 0%가 되므로 곡선에 거짓 바닥을 찍는다 —
    그래서 버린다. 요청 밖 키워드·탭의 깊은 쌍은 배치를 살리지 못한다(집계에 안 들어가니).

    깊이 10은 v4.1까지의 동작 그대로 — 3건만 잡힌 배치도 빼지 않는다(미수집 슬롯은
    분모에 남는 것이 §7 규칙이다).

    `share.share_trend`와 `views.share_trend_points`가 이 함수를 함께 쓴다 — 창이 다르면
    스트립 스파크와 점유율 섹션의 추이 차트가 같은 지표를 다른 곡선으로 보여준다.
    """
    ats = sorted({r["captured_at"] for r in serp_rows})
    if slots > SLOTS_PER_TAB:
        # 요청 쌍으로 좁힌 뒤의 최대 rank = 쌍별 저장 범위의 최댓값이다(합집합의 max).
        ats = [
            at for at in ats
            if stored_depth([
                r for r in serp_rows
                if r["captured_at"] == at and r["keyword"] in keywords and r["search_tab"] in tabs
            ]) >= slots
        ]
    return ats[-last_n:]


def share_trend(serp_rows, keywords, tabs, terms, *, last_n=15, slots=SLOTS_PER_TAB) -> list[tuple[str, float]]:
    """배치별 (captured_at, 우리 브랜드 점유율 %) — `keyword_share_rows`+`total_share`에 **위임**한다.

    직접 세지 않는 이유(fix-2): 손으로 세면 쌍 단위 수집 범위 게이트를 지나지 않아,
    같은 섹션 안에서 막대·스택은 1.0%인데 추이 곡선은 11.0%를 그리는 일이 생긴다.
    추이의 한 점은 "그 배치를 지금 값으로 계산한 것"과 글자 그대로 같아야 한다.
    깊이 10 결과는 예전 식과 동일하다(분자 = 매칭 슬롯 수, 분모 = 키워드×탭×10,
    `total_share`도 소수 1자리로 반올림한다).
    """
    ours = _ours(terms)
    out = []
    for at in trend_batches(serp_rows, keywords, tabs, last_n=last_n, slots=slots):
        batch = [r for r in serp_rows if r["captured_at"] == at]
        rows = keyword_share_rows(batch, keywords, tabs, terms, weighted=False, slots=slots)
        out.append((at, total_share(rows, ours)["ours_pct"]))
    return out
