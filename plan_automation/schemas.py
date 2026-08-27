"""정본(bc1-viral-report)의 plan_automation/schemas.py 중 이 배포 미러가
실제로 쓰는 조각만 옮겨왔다 — Accuracy 하나뿐이다.

정본의 schemas.py 전체는 이 대시보드와 무관한 별도 사내 파이프라인
("기획안 자동화": Campaign/Influencer/Assignment/Performance/Feedback)의
스키마를 담고 있어서, report_dashboard/content_sheet_sync.py가 실제로
필요로 하는 Accuracy 하나 때문에 그 전체를 public 미러에 들일 이유가
없다. plan_automation/report_schemas.py·store.py·config.py를 이 미러에
최소한만 들여온 것과 같은 원칙이다.
"""

from enum import StrEnum


class Accuracy(StrEnum):
    MEASURED = "실측"
    ESTIMATED = "추정"
    IMPOSSIBLE = "불가"
    UNAVAILABLE = "미취득"
