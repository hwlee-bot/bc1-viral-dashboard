# bc1-viral-dashboard

바이럴 성과 리포팅 대시보드 — **배포용 미러 저장소.**

## 이 저장소가 왜 존재하나

정본 코드는 `bc1-viral-report`(private)에 있다. 그 저장소는 과거 커밋에
인플루언서 실명 계정과 캠페인 상세가 남아 있어서 public으로 바꿀 수 없다.

반면 이 저장소는 그중 `report_dashboard/`(브랜드 무관 코드, 개인정보·광고주
데이터 없음)만 뽑아 히스토리 없이 새로 만들었다. Streamlit Community Cloud의
무료 티어는 private 저장소에서 배포한 앱을 워크스페이스당 1개까지만 허용하는데,
이 저장소를 public으로 두면 그 제한이 적용되지 않아 **브랜드가 늘어나도 앱을
몇 개든 배포할 수 있다** — 브랜드별로 다른 건 코드가 아니라 Streamlit Cloud의
Secrets(`[sheets] spreadsheet_id`, `[auth]` 리다이렉트 URI 등)뿐이다.

## 데이터는 여기 없다

- 캠페인·콘텐츠·댓글 데이터는 브랜드별 Google 스프레드시트에 있다(코드에 없음).
- 로그인은 `st.login`(구글 OAuth)이 막고, 광고주 allowlist는 그 스프레드시트에
  있다(코드에 없음).
- 이 저장소가 public이어도 위 두 가지는 그대로 보호된다 — public이 되는 건
  소스코드뿐이다.

## 여기서 고치지 마라

이 저장소는 정본이 아니라 배포 산물이다. 코드를 고치려면:

1. `bc1-viral-report`(private)의 `report_dashboard/`에서 고치고 테스트한다.
2. 검토가 끝나면 이 저장소로 다시 내보낸다(`report_dashboard/` +
   `plan_automation/{__init__.py,config.py,store.py}` + `requirements.txt`).
3. 이 저장소에 커밋·push한다.
4. Streamlit Cloud에서 재배포(자동으로 되거나, 수동으로 Reboot).

## 브랜드별 배포

같은 이 저장소에서, 브랜드마다 별도 Streamlit Cloud 앱을 만든다.
Main file path는 항상 `report_dashboard/app.py`. 앱마다 Secrets만 다르게
넣는다(다른 `spreadsheet_id`, 다른 OAuth 리다이렉트 URI). 자세한 순서는
`DEPLOY.md` 참고.
