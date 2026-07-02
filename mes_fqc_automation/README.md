# MES Daily FQC → Excel → Telegram 자동화

현재 매일 하고 계신 작업:

1. CTV / DLT / JC 세 MES에 각각 웹 로그인 (DLT, JC는 VPN 필요)
2. Daily FQC 페이지에서 **E03, E19, T11, 전체 불량률**을 눈으로 확인
3. 엑셀 파일에 수동 입력 → 그래프 확인
4. 그래프 대시보드를 스크린샷
5. 텔레그램으로 전송

이 리포지토리는 위 1~5번을 매일 자동으로 실행하는 파이프라인입니다. 실제 MES 화면 구조와 엑셀 파일 구조를 몰라도 동작 뼈대와 로직은 전부 구현되어 있고(테스트로 검증됨), **selector와 컬럼 이름 등 설정값만** `config.yaml`에 채우면 바로 쓸 수 있게 설계했습니다.

## 동작 방식

```
config.yaml (사이트별 로그인/셀렉터 정보)
        │
        ▼
src/scraper.py   ── Playwright로 로그인 → Daily FQC 페이지 이동 → E03/E19/T11/전체 텍스트 읽기
        │
        ▼
src/excel_writer.py ── 기존 엑셀 파일에서 헤더 이름으로 컬럼을 찾아 "오늘 날짜 행"만 추가 (기존 행/차트/수식은 건드리지 않음)
        │
        ▼
src/chart_export.py ── 대시보드를 PNG로 "스크린샷"
        │             (xlwings로 실제 엑셀 차트 export, 안되면 LibreOffice headless, 그래도 안되면 matplotlib로 동일 데이터 재플롯)
        ▼
src/telegram_sender.py ── 텔레그램 봇 API로 PNG 전송 (실패 시 에러 알림 메시지 전송)
```

`src/main.py`가 위 단계를 순서대로 실행하는 진입점입니다. 매일 자동 실행은 Windows 작업 스케줄러(`scripts/run_daily.ps1`) 또는 cron(`scripts/run_daily.sh`)으로 설정합니다.

## 왜 이렇게 설계했나

- **selector를 코드가 아니라 config.yaml에 둠**: 세 MES 화면 구조를 모르는 상태에서 만들었기 때문에, 실제 화면의 HTML을 보고 CSS selector 몇 줄만 채우면 바로 동작하도록 분리했습니다.
- **엑셀은 "새 행 추가"만 함**: 기존 차트가 테이블(Insert > Table)을 데이터 소스로 쓰고 있다면 차트 범위도 자동으로 늘어납니다. 기존 수식/서식은 절대 건드리지 않습니다.
- **VPN은 명령어 하나로 추상화**: 회사 VPN 클라이언트가 무엇이든(Cisco AnyConnect, FortiClient, OpenConnect 등) `.env`의 `VPN_CONNECT_COMMAND`에 CLI 명령만 넣으면 됩니다. 가장 안정적인 방법은 **이미 VPN에 상시 연결된 사내 PC/서버에서 스케줄러로 돌리는 것**입니다.
- **대시보드 캡처는 3단계 fallback**: 실제로 보시는 엑셀 차트를 그대로 캡처하고 싶다면 xlwings(엑셀 설치된 Windows/Mac 필요), 리눅스 서버라면 LibreOffice headless, 이도저도 안 되면 동일한 데이터로 matplotlib 차트를 새로 그려서 보냅니다.
- **실패 시 텔레그램으로 에러 알림**: 로그인 실패, selector 못 찾음, VPN 연결 실패 등 어떤 단계에서 문제가 생기든 조용히 넘어가지 않고 텔레그램으로 에러 메시지를 보냅니다.

## 시작하기

```bash
cd mes_fqc_automation
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
# 실제 Excel(xlwings)로 대시보드 캡처하려면 (Windows/Mac + Excel 설치 시):
pip install -r requirements-windows.txt

cp config.example.yaml config.yaml
cp .env.example .env
```

그 다음 `config.yaml`과 `.env`를 실제 값으로 채웁니다.

### 1) MES 3곳 정보 채우기 (`config.yaml`)

사이트별로 아래 정보가 필요합니다. **브라우저 개발자 도구(F12) → Elements 탭**에서 해당 입력창/버튼/숫자에 마우스 우클릭 → "Copy selector"로 쉽게 뽑을 수 있습니다.

| 항목 | 설명 |
|---|---|
| `login.url` | 로그인 페이지 URL |
| `login.username_selector` / `password_selector` / `submit_selector` | 아이디/비번 입력창, 로그인 버튼의 CSS selector |
| `login.success_selector` | 로그인 성공 후에만 보이는 요소(예: 상단 메뉴, 로그아웃 버튼) |
| `fqc_page.url` | Daily FQC 페이지 URL (없으면 `navigation_steps`에 클릭할 메뉴들을 순서대로) |
| `metrics.E03/E19/T11/OVERALL.selector` | 각 불량률 숫자가 들어있는 요소의 selector |
| `requires_vpn` | DLT, JC는 `true` |

먼저 `--headed` 옵션으로 브라우저를 눈으로 보면서 selector가 맞는지 확인하는 걸 추천합니다:

```bash
python -m src.main --headed
```

### 2) 엑셀 파일 연결 (`config.yaml`의 `excel:` 섹션)

기존에 쓰시던 엑셀 파일을 그대로 씁니다. 스크립트는 **1행(헤더) 텍스트로 컬럼을 찾아서** 그 아래에 새 행만 추가하므로:

- `excel.path`: 실제 파일 경로
- `excel.sheet_name`: 데이터가 있는 시트 이름
- `excel.column_headers`: `CTV_E03`, `CTV_E19`, `CTV_T11`, `CTV_OVERALL`, `DLT_...`, `JC_...` 각각을 실제 엑셀 1행 헤더 텍스트와 매칭
- `excel.table_name`: 데이터 영역을 Excel Table(Insert > Table)로 만들어두셨다면 그 이름 (차트가 자동으로 범위를 늘려서 따라가게 하려면 강력 추천)
- `excel.dashboard_sheet_name`: 차트/대시보드가 있는 시트 이름 (스크린샷 대상)

### 3) 텔레그램 봇 (`.env`)

1. 텔레그램에서 `@BotFather` → `/newbot` → 토큰 발급 → `.env`의 `TELEGRAM_BOT_TOKEN`
2. 봇을 원하는 그룹/채널에 추가하거나 개인 챗을 열고, `@userinfobot` 또는 `https://api.telegram.org/bot<토큰>/getUpdates`로 chat_id 확인 → `.env`의 `TELEGRAM_CHAT_ID`

### 4) VPN (DLT, JC)

가장 간단하고 안정적인 방법은 **이미 VPN에 연결된 상태로 유지되는 PC/서버**에서 이 스크립트를 스케줄 실행하는 것입니다(예: 사무실 상시 켜진 PC). 매번 자동으로 VPN 연결이 필요하다면 `.env`의 `VPN_CONNECT_COMMAND`에 회사 VPN 클라이언트의 무인 접속 CLI 명령을 넣으세요 (`src/vpn.py` 참고).

### 5) 실행 & 테스트

```bash
python -m src.main --headed     # 처음엔 headed로 눈으로 확인
python -m src.main              # 이후엔 headless로 정상 자동 실행
```

매일 자동 실행:
- **Windows**: 작업 스케줄러에서 `scripts/run_daily.ps1` 등록 (README 상단 스크립트 파일 참고)
- **Linux/Mac**: crontab에 `scripts/run_daily.sh` 등록

## 개발자용: 테스트

selector 3곳 URL/구조를 몰라도 로직 자체는 아래처럼 전부 검증되어 있습니다 (가짜 MES 서버로 실제 Playwright 로그인까지 end-to-end 테스트):

```bash
pip install -r requirements-dev.txt
playwright install chromium
pytest -v
```

- `tests/test_config.py` - config.yaml/.env 로딩
- `tests/test_excel_writer.py` - 새 행 추가, Excel Table 범위 자동 확장, 헤더 불일치 에러 처리
- `tests/test_scraper_helpers.py` - "1.23%" 같은 텍스트에서 숫자 추출
- `tests/test_scraper_integration.py` - **가짜 MES 웹서버(Flask)를 띄우고 실제 Playwright로 로그인 → 페이지 이동 → 숫자 읽기까지 end-to-end 검증**
- `tests/test_chart_export.py` - matplotlib fallback으로 PNG 생성
- `tests/test_telegram_sender.py` - 텔레그램 API 호출 payload 검증 (mock)

## 이 자동화를 완성하려면 실제로 필요한 것

지금은 실제 MES 화면과 엑셀 파일 구조를 모르는 상태라 **selector/헤더 이름은 예시 값**으로 채워뒀습니다. 다음 중 하나라도 공유해주시면 `config.yaml`을 정확한 값으로 채워서 바로 동작하게 만들 수 있습니다:

1. **엑셀 파일**: 시트 이름, 헤더 행 구성(날짜/CTV·DLT·JC × E03·E19·T11·전체 컬럼이 각각 어떻게 되어 있는지), 차트가 있는 시트 이름/차트가 참조하는 데이터 범위 (또는 캡처 화면 - 민감정보는 가려주셔도 됩니다)
2. **MES 3곳의 Daily FQC 페이지 HTML 구조**: 브라우저에서 F12 개발자도구를 열고 E03/E19/T11/전체 불량률 숫자가 있는 부분의 HTML을 "Copy → Copy outerHTML" 해서 공유해주시거나, 화면 스크린샷 + 대략적인 URL 패턴만 주셔도 selector를 유추해서 채워드릴 수 있습니다
3. **로그인 페이지 구조**: 아이디/비밀번호 입력창, 로그인 버튼의 HTML (역시 Copy outerHTML)
4. 사내에서 사용 중인 VPN 클라이언트 종류(Cisco AnyConnect, FortiClient 등)와 CLI 무인 접속 지원 여부

민감한 사내 정보이므로, 실제 값 대신 **구조만** 알려주셔도 충분합니다 (예: "표는 `<table id="fqcGrid">`이고 각 행은 `<tr data-line="E03">`, 값은 마지막 `<td>` 안에 `1.23%` 형식으로 들어있음").
