"""키워드 점유율(스펙 §7). 순수 함수, Streamlit 없음.

분모 = 키워드 × 탭 × 10슬롯(가중이면 × 55). 미수집 탭도 분모에 넣는다 — "안 보인 것"을 점유율에서 빼면
점유율이 부풀려진다. 최신 captured_at 배치만 집계(append-only 규칙).
"""
from __future__ import annotations

from collections import defaultdict

SLOTS_PER_TAB = 10
WEIGHTED_PER_TAB = 55  # 10+9+...+1


def WEIGHT(rank: int) -> int:
    return max(0, 11 - rank)


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


def keyword_share_rows(serp_rows, keywords, tabs, terms, *, weighted=False) -> list[dict]:
    ours = _ours(terms)
    out = []
    for kw in keywords:
        for tab in tabs:
            rows = latest_batch([r for r in serp_rows if r["keyword"] == kw and r["search_tab"] == tab])
            by_brand: dict[str, int] = defaultdict(int)
            campaign = 0
            for r in rows:
                score = WEIGHT(r["rank"]) if weighted else 1
                for b in match_brands(r.get("title") or "", terms):
                    by_brand[b] += score
                if r.get("content_id"):
                    campaign += score
            out.append({
                "keyword": kw, "tab": tab, "slots": len(rows), "by_brand": dict(by_brand),
                "ours_score": by_brand.get(ours, 0) if ours else 0, "campaign_score": campaign,
                "denominator": WEIGHTED_PER_TAB if weighted else SLOTS_PER_TAB,
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


def share_trend(serp_rows, keywords, tabs, terms, *, last_n=15) -> list[tuple[str, float]]:
    ours = _ours(terms)
    batches = sorted({r["captured_at"] for r in serp_rows})[-last_n:]
    denom = len(keywords) * len(tabs) * SLOTS_PER_TAB or 1
    out = []
    for at in batches:
        rows = [r for r in serp_rows if r["captured_at"] == at and r["keyword"] in keywords and r["search_tab"] in tabs]
        score = sum(1 for r in rows if ours in match_brands(r.get("title") or "", terms))
        out.append((at, round(score / denom * 100, 1)))
    return out
