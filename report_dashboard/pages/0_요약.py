"""요약 카드. 마녀공장 마스터 브랜드 옐로우 헤더 + 겹치는 히어로 메트릭 +
최근 자동 수집 로그 + 채널 분포. 목업: redesign-v2-summary.html.

이 페이지를 AppTest로 직접 실행하면 라우터를 거치지 않으므로, 게이트를
여기서도 호출한다(1_리포트.py 상단 주석과 같은 이유).
"""

import html as html_lib
import os
import sys

_here = os.path.abspath(__file__)
_repo_root = _here[: _here.index(os.sep + "report_dashboard" + os.sep)]
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import streamlit as st

from report_dashboard.auth import require_role
from report_dashboard.reporting import channel_distribution
from report_dashboard.repo import ReportRepo

role, email = require_role()

repo = ReportRepo()

_CHANNEL_LOG_COLOR = {"blog": "#3a5ac4", "cafe": "#c9a86a", "community": "#8a6fd6", "instagram": "#d6478a", "youtube": "#e2453e"}
_DONUT_COLORS = _CHANNEL_LOG_COLOR


def _esc(value) -> str:
    return html_lib.escape(str(value))


_STYLE = """
<style>
.vr-sum-amb {
  position: relative; margin: -1rem -1rem 0; padding: 36px 32px 64px; overflow: hidden;
  background: linear-gradient(135deg, #ffe066 0%, #fbc02d 55%, #f2a30f 100%);
}
.vr-sum-amb::after {
  content: ""; position: absolute; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E");
  mix-blend-mode: overlay; pointer-events: none;
}
.vr-sum-top { display: flex; align-items: center; justify-content: space-between; position: relative; z-index: 1; }
.vr-sum-brand { font-size: 13px; font-weight: 600; color: rgba(30,22,0,0.85); }
.vr-sum-brand span { color: #7a4a00; }
.vr-sum-user { font-size: 11px; color: rgba(30,22,0,0.55); }
.vr-sum-greet { position: relative; z-index: 1; margin-top: 28px; font-size: 30px; font-weight: 700; color: #1e1600; letter-spacing: -0.02em; }
.vr-sum-sub { position: relative; z-index: 1; margin-top: 6px; font-size: 13px; color: rgba(30,22,0,0.6); font-weight: 500; }

.vr-sum-metrics { position: relative; z-index: 2; margin: -40px 0 0; background: #fff; border-radius: 16px; display: grid; grid-template-columns: 1.6fr 1fr; box-shadow: 0 12px 32px -12px rgba(30,25,15,0.18), 0 1px 0 rgba(30,25,15,0.04); }
.vr-metric-hero { padding: 26px 28px; border-right: 1px solid #f0ede8; }
.vr-metric-hero-label { font-size: 11px; font-weight: 600; color: #a39c8c; text-transform: uppercase; letter-spacing: 0.05em; }
.vr-metric-hero-num { font-size: 46px; font-weight: 800; color: #1c1a16; line-height: 1; margin-top: 10px; letter-spacing: -0.02em; }
.vr-metric-side { display: flex; flex-direction: column; }
.vr-metric-mini { flex: 1; padding: 18px 24px; display: flex; flex-direction: column; justify-content: center; }
.vr-metric-mini + .vr-metric-mini { border-top: 1px solid #f0ede8; }
.vr-metric-mini-label { font-size: 10px; font-weight: 600; color: #a39c8c; text-transform: uppercase; letter-spacing: 0.05em; }
.vr-metric-mini-num { font-size: 22px; font-weight: 700; color: #1c1a16; margin-top: 4px; }

.vr-sum-section { padding: 32px 0 8px; }
.vr-sum-section-title { font-size: 15px; font-weight: 700; color: #1c1a16; margin-bottom: 16px; }
.vr-log-row { display: grid; grid-template-columns: 3px 1fr 56px; align-items: center; gap: 16px; padding: 13px 8px; border-radius: 8px; }
.vr-log-bar { width: 3px; height: 30px; border-radius: 3px; }
.vr-log-title { font-size: 13px; font-weight: 600; color: #262420; }
.vr-log-meta { font-size: 11px; color: #a39c8c; margin-top: 2px; font-weight: 500; }
.vr-log-num { font-size: 15px; font-weight: 700; color: #1c1a16; text-align: right; }

.vr-stackbar { display: flex; height: 10px; border-radius: 6px; overflow: hidden; background: #eee9df; margin-bottom: 14px; }
.vr-stackbar div { height: 100%; }
.vr-legend { display: flex; gap: 20px; flex-wrap: wrap; }
.vr-legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #57524a; font-weight: 600; }
.vr-legend-dot { width: 8px; height: 8px; border-radius: 2px; }
.vr-legend-num { color: #a39c8c; font-weight: 500; }
</style>
"""

st.markdown(_STYLE, unsafe_allow_html=True)

campaigns = repo.campaigns()
contents = repo.contents()
metrics = repo.content_metrics()
# auto_instagram 행은 views=0 관례 sentinel이라(실제 조회수 아님, 스펙 §4.2),
# 조회수 참고 숫자를 계산하는 모든 자리에서 반드시 제외해야 한다 — 안 그러면
# 매일 쌓이는 이 행이 사람이 입력한 진짜 조회수를 조용히 덮어써 버린다.
view_metrics = [m for m in metrics if m.get("source") != "auto_instagram"]

st.markdown(
    f"""
<div class="vr-sum-amb">
  <div class="vr-sum-top">
    <div class="vr-sum-brand">바이럴 <span>리포팅</span></div>
    <div class="vr-sum-user">{_esc(email)}</div>
  </div>
  <div class="vr-sum-greet">안녕, 오늘의 요약이야</div>
  <div class="vr-sum-sub">캠페인별 조회수·네이버 순위 추이를 누적해서 본다</div>
</div>
""",
    unsafe_allow_html=True,
)

total_views = sum(m["views"] for m in view_metrics)
st.markdown(
    f"""
<div class="vr-sum-metrics">
  <div class="vr-metric-hero">
    <div class="vr-metric-hero-label">누적 조회수 관측값</div>
    <div class="vr-metric-hero-num">{total_views:,}</div>
  </div>
  <div class="vr-metric-side">
    <div class="vr-metric-mini"><div class="vr-metric-mini-label">캠페인</div><div class="vr-metric-mini-num">{len(campaigns)}</div></div>
    <div class="vr-metric-mini"><div class="vr-metric-mini-label">등록 콘텐츠</div><div class="vr-metric-mini-num">{len(contents)}</div></div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="vr-sum-section"><div class="vr-sum-section-title">최근 자동 수집</div></div>', unsafe_allow_html=True)

if not metrics:
    st.caption("아직 자동 수집 기록이 없다 — 등록·관리자 페이지에서 수동으로 값을 넣을 수 있다.")
else:
    contents_by_id = {c["content_id"]: c for c in contents}
    recent = sorted(view_metrics, key=lambda m: m["captured_at"], reverse=True)[:5]
    rows = []
    for metric in recent:
        content = contents_by_id.get(metric["content_id"])
        if not content:
            continue
        color = _CHANNEL_LOG_COLOR.get(content["channel"], "#a39c8c")
        title = _esc(content.get("title") or content["url"])
        rows.append(
            f'<div class="vr-log-row">'
            f'<div class="vr-log-bar" style="background:{color};"></div>'
            f'<div><div class="vr-log-title">{title}</div>'
            f'<div class="vr-log-meta">{_esc(content["channel"])} · {_esc(metric["captured_at"][:10])} 수집</div></div>'
            f'<div class="vr-log-num">{metric["views"]:,}</div>'
            f"</div>"
        )
    if rows:
        st.markdown("".join(rows), unsafe_allow_html=True)
    else:
        st.caption("최근 수집된 항목의 콘텐츠 정보를 찾을 수 없다.")

st.markdown('<div class="vr-sum-section"><div class="vr-sum-section-title">채널 분포</div></div>', unsafe_allow_html=True)

distribution = channel_distribution(contents)
if not distribution:
    st.caption("아직 등록된 콘텐츠가 없다.")
else:
    total = sum(distribution.values())
    ordered = sorted(distribution.items(), key=lambda kv: kv[1], reverse=True)
    bars, legend = [], []
    for channel, count in ordered:
        pct = count / total * 100
        color = _DONUT_COLORS.get(channel, "#a39c8c")
        bars.append(f'<div style="width:{pct:.2f}%; background:{color};"></div>')
        legend.append(
            f'<div class="vr-legend-item"><span class="vr-legend-dot" style="background:{color};"></span>'
            f'{_esc(channel)} <span class="vr-legend-num">{count}건</span></div>'
        )
    st.markdown(
        f'<div class="vr-stackbar">{"".join(bars)}</div><div class="vr-legend">{"".join(legend)}</div>',
        unsafe_allow_html=True,
    )

latest_run = repo.latest_collection_run()
if latest_run:
    st.caption(f"마지막 자동 수집: {latest_run.get('started_at', '')}")
