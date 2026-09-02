"""바이럴 성과 리포팅 대시보드의 데이터 모델.

기획안 자동화(schemas.py의 Campaign/Influencer 등)와는 다른 도메인이다.
저장 테이블 이름을 `viral_` 접두사로 분리해 같은 Store 루트(raw/auto/)에
섞여도 기존 기획안 파이프라인 데이터와 충돌하지 않는다. Accuracy만
schemas.py 것을 그대로 재사용한다 — 정확도 등급 개념은 도메인이 달라도
같아야 한다.
"""

from dataclasses import dataclass, field, asdict

from plan_automation.schemas import Accuracy

CHANNELS = {"youtube", "blog", "cafe", "community", "instagram"}
TARGET_SCOPES = {"content", "channel"}
METRIC_SOURCES = {
    "auto_youtube", "auto_naver_blog", "auto_community", "auto_instagram",
    "manual_instagram", "manual_fallback", "manual_backfill",
}


@dataclass(slots=True)
class ViralCampaign:
    campaign_id: str
    brand: str
    name: str
    start_date: str = ""
    end_date: str = ""
    created_at: str = ""

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class Content:
    content_id: str
    campaign_id: str
    channel: str
    url: str
    title: str = ""
    release_at: str = ""
    created_at: str = ""

    def __post_init__(self):
        if self.channel not in CHANNELS:
            raise ValueError(f"알 수 없는 channel: {self.channel}")

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class Target:
    target_id: str
    campaign_id: str
    scope_type: str
    scope_key: str
    target_views: int
    created_at: str = ""

    def __post_init__(self):
        if self.scope_type not in TARGET_SCOPES:
            raise ValueError(f"알 수 없는 scope_type: {self.scope_type}")

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ContentMetric:
    content_id: str
    captured_at: str
    views: int
    source: str
    accuracy: str
    comments_count: int | None = None
    likes_count: int | None = None

    def __post_init__(self):
        if self.source not in METRIC_SOURCES:
            raise ValueError(f"알 수 없는 source: {self.source}")

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class KeywordRank:
    # search_tab은 channel/scope_type/source와 달리 폐쇄형 집합으로 검증하지 않는다.
    # 네이버 탭은 VIEW·블로그·카페·지식iN·뉴스 등 계속 늘어나며(design.md도 "등"으로
    # 비전수 명시), 닫힌 목록을 만들면 탭이 추가될 때마다 유지보수가 필요해진다.
    content_id: str
    keyword: str
    search_tab: str
    captured_at: str
    rank: int | None = None
    accuracy: str = Accuracy.MEASURED.value

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class TargetKeyword:
    """캠페인이 지키려는 키워드 워치리스트 한 줄.

    콘텐츠가 아니라 캠페인에 매단다 — 콘텐츠 하나가 특정 키워드 하나를
    전제로 기획되는 구조가 아니라, 캠페인이 키워드를 정하면 그 키워드로
    검색했을 때 캠페인 소속 콘텐츠 중 무엇이든 잡히는 걸 순위로 본다
    (design.md 2026-08-24 naver-rank-collector 참고).
    """
    keyword_id: str
    campaign_id: str
    keyword: str
    created_at: str = ""

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ContentSheetLink:
    """캠페인이 마지막으로 연결한 콘텐츠 목록 구글시트 URL.

    append-only — 매번 새 행을 쌓고 최신 것만 의미가 있다(등록 폼의 다른
    필드들과 같은 관례).
    """
    campaign_id: str
    spreadsheet_url: str
    created_at: str = ""

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class Comment:
    comment_id: str
    content_id: str
    text: str
    author_nickname: str = ""
    posted_at: str = ""
    collected_at: str = ""
    sentiment: str | None = None
    sentiment_source: str | None = None

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class CollectionRun:
    run_id: str
    started_at: str
    run_type: str = "content_metrics"  # "content_metrics" | "keyword_ranks"
    finished_at: str = ""
    target_count: int = 0
    success_count: int = 0
    failed_items: list[str] = field(default_factory=list)

    def to_row(self) -> dict:
        return asdict(self)
