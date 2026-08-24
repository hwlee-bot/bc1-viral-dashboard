# 배포 순서 (사람이 직접 해야 하는 부분)

## 0. 서비스 계정 만들기 (앱이 시트에 쓰기 위한 로봇 계정)

앱은 사람 계정이 아니라 **서비스 계정**으로 스프레드시트에 쓴다. 이게 없으면
1단계의 "편집자로 공유"할 대상이 없다. 이미 쓰고 있는 서비스 계정이 있으면
0단계를 건너뛰고 그 이메일을 1단계에 쓰면 된다.

1. [Google Cloud Console](https://console.cloud.google.com) → 프로젝트를 만들거나 고른다.
   **좌측 상단 프로젝트 선택기를 확인한다** — 2번과 3번을 서로 다른 프로젝트에서 하면
   키는 받아지는데 호출이 막힌다(흔한 실수).
2. **Google Sheets API 사용 설정** → https://console.cloud.google.com/apis/library/sheets.googleapis.com
   이걸 빼먹으면 공유가 맞아도 호출이 403으로 막힌다.
3. **서비스 계정 만들기** → https://console.cloud.google.com/iam-admin/serviceaccounts
   `+ 서비스 계정 만들기` → 이름은 아무거나(예: `viral-report-writer`).
   역할(role)은 **주지 않아도 된다** — 시트 접근 권한은 IAM 역할이 아니라
   1단계의 "스프레드시트 공유"로 부여된다.
4. 목록에서 만든 계정 클릭 → **키 탭 → 키 추가 → 새 키 만들기 → JSON.** 파일이 다운로드된다.
   - 키 만들기 버튼이 비활성이거나 정책 오류가 나면 회사 Workspace가 서비스 계정 키
     생성을 막아둔 것이다(`iam.disableServiceAccountKeyCreation`). 조직 관리자에게
     해당 프로젝트 예외를 요청해야 한다.
   - 이 파일이 곧 자격증명이다. **git에 커밋하지 말고 슬랙·노션에 붙이지 마라.**
     최종 목적지는 Streamlit Cloud의 Secrets 화면뿐이다.
5. 그 JSON 안의 **`client_email` 값**이 1단계에서 공유할 주소다
   (`...iam.gserviceaccount.com` 형태). 이 주소는 자격증명이 아니라 식별자이므로
   공유 대상으로 쓰는 건 정상이다 — 비밀로 지켜야 하는 건 같은 파일의 `private_key`다.

## 1. 스프레드시트 준비
1. Google Drive에서 새 스프레드시트를 만든다(이름 예: `viral-report-store-마녀공장`).
2. URL의 `/d/` 다음 문자열이 `spreadsheet_id`다.
3. 서비스 계정 이메일(0단계에서 만든 JSON 키의 `client_email`)을 **편집자**로 공유한다.
   뷰어로 공유하면 읽기는 되고 쓰기가 403으로 막힌다 — 4번 검증이 그걸 잡아준다.
   - 탭은 앱이 처음 쓸 때 자동으로 만든다. 미리 만들 필요 없다.
   - 서비스 계정의 Drive 용량이 0이라 파일 생성은 403이 된다. 그래서 스프레드시트는
     사람이 만들어 공유하는 방식이다(웰라쥬 앱에서 확인된 제약).
4. **여기서 바로 검증한다** — 공유를 빠뜨렸거나 ID를 잘못 복사했으면 배포를 다 끝내고
   앱을 열어볼 때까지 알 수 없다. 이 명령이 그 앞단에서 잡아준다:

   ```bash
   cd ~/Desktop/콘텐츠마케팅팀/tools && python3 -m report_dashboard.verify_sheets_setup \
       --key <서비스계정 JSON 키 경로> --spreadsheet-id <시트 ID>
   ```

   임시 탭에서 쓰기·읽기 왕복까지 확인한 뒤 그 탭을 지운다. 데이터 탭(`viral_*`)은
   건드리지 않는다. 실패하면 원인(공유 누락 403 / 뷰어 권한 403 / ID 오타 404)을
   이름으로 알려준다.

## 2. Google OAuth 클라이언트 만들기
1. Google Cloud Console → API 및 서비스 → OAuth 동의 화면을 구성한다.
2. 사용자 인증 정보 → OAuth 클라이언트 ID(웹 애플리케이션)를 만든다.
3. 승인된 리디렉션 URI에 `https://<앱이름>.streamlit.app/oauth2callback` 를 넣는다.
4. 요청 스코프는 기본(name·email·profile)만 쓴다 — 그래야 Testing 상태의
   7일 리프레시 토큰 만료 규칙에서 면제된다.
5. 동의 화면이 Testing 상태면 테스트 사용자에 광고주 이메일을 등록해야 한다
   (100명 제한). 게시(Publishing) 심사가 필요한지는 미확인이므로 이 단계에서 확인한다.

## 3. Streamlit Community Cloud 배포
1. private 저장소에서 앱을 만든다. 진입점은 `report_dashboard/app.py`.
2. Advanced settings의 Secrets에 `.streamlit/secrets.toml.example`을 채운 내용을 붙인다.
3. 앱 sharing은 **공개**로 둔다. 접근 통제는 전부 `st.login`이 한다.
   Cloud의 viewer allowlist는 쓰지 않는다 — 초대된 사람이 다른 사람을 또 초대할 수 있고,
   초대 이메일이 워크스페이스 전체 앱 분석에 노출된다.
4. **확인할 것**: "비공개 앱 동시 1개" 제한이 private 저장소 + 앱 공개 조합에서
   실제로 걸리는지. 문서가 애매하다. 걸리면 두 번째 브랜드부터 저장소 분리가 필요하다.

## 4. 수동 스모크
- [ ] 실제 구글 로그인 왕복이 동작한다
- [ ] 우리 팀 계정으로 등록·관리자 페이지가 보인다
- [ ] 광고주 계정을 추가한 뒤, 그 계정으로 로그인하면 **등록 페이지가 사이드바에 없다**
- [ ] 광고주 계정에서 캠페인·콘텐츠를 등록하면 스프레드시트에 탭과 행이 생긴다
- [ ] 앱을 재시작(Reboot)한 뒤에도 데이터가 남아있다
- [ ] 브라우저를 완전히 닫고 다시 열어도 로그인이 유지된다
- [ ] 권한 없는 제3의 구글 계정으로 로그인하면 "접근 권한이 없다"가 뜬다

## 5. 트러블슈팅

- 로그인 버튼을 눌렀을 때 `StreamlitAuthError`가 뜨고 `client_id`/`client_secret`/
  `server_metadata_url`이 없다고 나오면: 이 세 값이 잘못된 위치에 있다는 뜻이다.
  앱이 `st.login()`을 provider 이름 없이 호출하므로, 이 세 값은 `[auth.google]` 같은
  하위 섹션이 아니라 `[auth]` 테이블에 바로 있어야 한다. `secrets.toml`에서 위치를
  확인한다.
- 서비스 계정의 `private_key`는 **한 줄**로 넣고 줄바꿈을 `\n`으로 이스케이프해야 한다.
  JSON 키 파일에서 복사한 여러 줄 PEM 블록(`-----BEGIN PRIVATE KEY-----` 다음에 실제
  줄바꿈이 이어지는 형태)을 그대로 붙이면 secrets TOML 파싱 자체가 실패한다. JSON
  파일 안의 값(이미 `\n`으로 이스케이프돼 있다)을 따옴표째로 그대로 옮기면 된다.
- `[sheets]`나 `[gcp_service_account]`의 키를 잘못 적으면 앱이 시작 시
  `SheetsConfigError`로 **어느 키가 없는지 이름을 붙여** 터진다. 조용히 로컬 파일
  저장소로 내려앉지 않게 일부러 그렇게 만들었다(그 상태로 돌면 광고주 allowlist가
  재시작마다 지워지고, 재시작 후 광고주 전원이 잠긴다).
