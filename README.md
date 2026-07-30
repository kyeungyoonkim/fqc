# FQC Daily Automation (CTV / DLT / JC)

MES Daily FQC를 7일 rolling(어제 포함 최근 7일)으로 수집하고,
라인별(E03/E19/T11/Total) 대시보드 2장을 만들어 텔레그램 그룹으로 전송하는 자동화 템플릿입니다.

## 포함 기능

- 날짜 자동 계산: `어제 ~ 어제-6일` (7일)
- 라인별 처리:
  - CTV: `R1, R2, R3`
  - DLT: `E1 ~ E7`
  - JC: `J03`
- 결과물:
  - `output/daily_fqc_*.xlsx`
  - `output/dashboard_1_*.png`
  - `output/dashboard_2_*.png`
- 텔레그램 전송(선택, `--test-telegram`로 연결 테스트 가능)
- CTV/DLT 브라우저 자동 수집(`--auto-export`, Playwright, `mes_collector.py`)
- DLT/JC용 VPN 연결 훅(`vpn.py`, 회사 VPN 클라이언트 CLI 명령을 그대로 실행)
- 매일 자동 실행 스크립트(`scripts/run_daily.sh` / `scripts/run_daily.ps1`)

## 현재 상태

- `mes_automation.py`는 **즉시 테스트 가능한 dry-run 모드**를 기본값으로 제공합니다.
- 실제 MES/JC 환경 연결은 회사망/VPN/DUO 및 UI 선택자에 따라 조정이 필요합니다.

## 빠른 시작

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install
cp config.example.yaml config.yaml
python mes_automation.py --config config.yaml --no-telegram
```

성공하면 `output/`에 엑셀 + PNG 2장이 생성됩니다.

## 설정 파일

`config.yaml`에서 아래 항목을 수정하세요.

- `mes.dry_run: false` (기본값)로 두고 `export_file` 경로를 넣어 실제 데이터 사용
- MES 계정/URL/라인/선택자
- 텔레그램 `bot_token`, `chat_id`
- 대시보드 분할 라인(`first_image_lines`, `second_image_lines`)

### Excel export 기반 정확 매칭(권장 1차)

CTV/DLT에서 `Search` 후 `Excel` 버튼으로 저장한 파일을 바로 읽어 집계할 수 있습니다.

`config.yaml` 예시:

```yaml
mes:
  dry_run: false
  ctv:
    enabled: true
    export_file: "C:/Users/<you>/Downloads/CTV_{line}.xlsx"
    require_grade_total: true
    lines: ["R1", "R2", "R3"]
```

`require_grade_total: true` 이면 **Grade = TOTAL 행만** 사용합니다 (CTV 요청사항 반영).
`export_file`에 `{line}`을 쓰면 라인별 파일을 각각 읽습니다.
매트릭스 형태 export(날짜가 열인 형식)는 **한 파일이 한 라인**이어야 정확합니다.

## 텔레그램 그룹 설정

중요: 그룹 초대 링크(`https://t.me/+...`)는 Bot API의 `chat_id`가 아닙니다.

1. `@BotFather`에서 봇 생성 후 토큰 발급
2. 해당 봇을 그룹에 초대
3. 그룹에서 아무 메시지 1개 전송
4. 아래 호출로 `chat_id` 확인

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"
```

응답 JSON의 `chat.id` (보통 `-100...`)를 `config.yaml`의 `telegram.chat_id`에 입력하세요.

### 텔레그램 연결 테스트

`config.yaml`에 `telegram.bot_token`, `telegram.chat_id`를 넣은 뒤:

```bash
python mes_automation.py --config config.yaml --test-telegram
```

성공하면 해당 채팅으로 `[FQC bot test] Connection OK ...` 메시지가 갑니다.
개인 DM으로 먼저 테스트하려면 `chat_id`에 본인 개인 id(예: `7649433757`)를 넣으세요.
전체 실행에서 실제 전송을 켜려면 `telegram.enabled: true`로 두고 `--no-telegram` 없이 실행합니다.

## CTV / DLT 자동 수집 (브라우저 자동화)

MES에서 라인별 숫자를 사람이 직접 조회/Excel 저장하지 않고 자동으로 내려받습니다.
`mes_collector.py`의 `collect_all_web_exports()`가 `mes.ctv`, `mes.dlt`처럼
**enabled + export_file이 설정된 웹 기반 사이트를 전부 순회**하며 로그인 → 조회 → Excel
다운로드를 수행합니다. (JC는 데스크톱 앱이라 아래 "JC" 절 참고)

1. Playwright 설치:

```bash
pip install playwright
python -m playwright install chromium
```

회사망 SSL 때문에 `playwright install`이 인증서 오류(`UNABLE_TO_VERIFY_LEAF_SIGNATURE`)로 실패하면,
Chromium 다운로드 없이 **이미 설치된 Edge/Chrome**를 사용하세요:

```yaml
browser:
  channel: "msedge"   # 또는 "chrome"
```

`channel`이 설정되면 브라우저 바이너리 다운로드가 필요 없습니다.

2. `config.yaml`의 `mes.ctv` / `mes.dlt`에서 각각:
   - `export_file: "C:/Users/<you>/Downloads/CTV_{line}.xlsx"` (`{line}` 필수) - 이 값이 있어야 그 사이트가 자동 수집 대상이 됩니다
   - `daily_fqc_url`: Daily FQC 페이지 URL(가능하면)
   - `login.manual: true` (DUO/2차인증이 있으면 권장: 브라우저에서 직접 로그인 후 Enter)
   - `selectors`: 실제 화면 DOM에 맞게 조정
   - DLT처럼 VPN이 필요하면 `vpn.connect_command`(또는 `DLT_VPN_CONNECT_COMMAND` 환경변수)에
     회사 VPN 클라이언트의 무인 접속 CLI 명령을 입력 (`vpn.py` 참고). 비워두면 "이미 VPN에
     연결된 상태"라고 가정하고 그냥 진행합니다.

3. 실행:

```bash
python mes_automation.py --config config.yaml --auto-export --no-telegram
```

동작: (VPN 필요 시 연결) → 브라우저를 열어 로그인 → 라인별로 Work Date(7일) 입력 → Search →
Excel 다운로드 → `CTV_R1/R2/R3.xlsx`, `DLT_E1~E7.xlsx` 등 저장 → 이후 기존 파서가 그 파일을
읽어 대시보드를 생성합니다. `browser.headless: false`면 창이 보여 진행 상황/실패 지점을
확인할 수 있고(DUO 승인 필요 시 특히 유용), 실패 시 `*.error.png` 스크린샷이 저장됩니다.

### JC (데스크톱 앱)

JC MES는 웹이 아니라 데스크톱 앱이라 `mes_collector.py`로 자동 수집하지 않습니다. 현재는:
- 수동으로 내려받은 CSV/엑셀 파일을 `mes.jc.export_file`(또는 `data_source_csv`)에 지정해서
  기존 파서가 읽게 하거나,
- 필요하면 `pywinauto` 등으로 데스크톱 앱 자동화를 추가해야 합니다(이 리포지토리에는 아직 없음).

## 매일 자동 실행 (스케줄링, 매일 10:00 예시)

`scripts/run_daily.sh`(Linux/cron) / `scripts/run_daily.ps1`(Windows 작업 스케줄러)가
`python mes_automation.py --config config.yaml --auto-export`를 실행합니다.

**중요**: MES가 사내 IP(예: `10.204.41.132`)라서 이 스크립트는 **항상 사내망/VPN에 연결된
PC나 서버**에서 돌려야 합니다(클라우드 서버는 사내망에 못 들어가므로 접속 자체가 실패합니다).
DUO 2차인증이 걸린 계정이면 `login.manual: true` + 사람이 눌러줘야 하는 단계가 있으므로
완전 무인은 회사 DUO 예외 정책 또는 세션(쿠키) 재사용이 필요합니다.

### Linux/Mac: cron

```bash
chmod +x scripts/run_daily.sh
crontab -e
# 매일 아침 10:00에 실행 (Asia/Seoul 기준으로 크론탭 TZ 설정 필요할 수 있음)
0 10 * * * /path/to/repo/scripts/run_daily.sh >> /path/to/repo/output/logs/cron.log 2>&1
```

### Windows: 작업 스케줄러

```powershell
schtasks /Create /SC DAILY /ST 10:00 /TN "MES Daily FQC" ^
  /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\path\to\repo\scripts\run_daily.ps1"
```

또는 GUI에서:
- Program/script: `powershell.exe`
- Arguments: `-NoProfile -ExecutionPolicy Bypass -File "C:\path\to\repo\scripts\run_daily.ps1"`
- Start in: `C:\path\to\repo`
- Trigger: Daily 10:00

## 실환경 적용시 체크포인트

1. DLT(FortiClient) + JC(AnyConnect) VPN 연결 자동화 방식
2. DUO 푸시 승인(완전 무인은 정책 협의 필요)
3. CTV/DLT Daily FQC 화면의 실제 DOM 선택자 매핑
4. JC 소프트웨어(웹 아님) 데이터 추출 경로(파일 export 또는 pywinauto)

## 보안 주의

- 비밀번호를 저장소에 커밋하지 마세요.
- `config.yaml`은 로컬 전용으로 사용하고, 필요시 `.gitignore`에 추가하세요.
