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
- 텔레그램 전송(선택)

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

## 스케줄링 (매일 08:00)

### Windows 작업 스케줄러

- Program/script: `python`
- Arguments: `C:\path\to\repo\mes_automation.py --config C:\path\to\repo\config.yaml`
- Start in: `C:\path\to\repo`
- Trigger: Daily 08:00

## 실환경 적용시 체크포인트

1. DLT(FortiClient) + JC(AnyConnect) VPN 연결 자동화 방식
2. DUO 푸시 승인(완전 무인은 정책 협의 필요)
3. CTV/DLT Daily FQC 화면의 실제 DOM 선택자 매핑
4. JC 소프트웨어(웹 아님) 데이터 추출 경로(파일 export 또는 pywinauto)

## 보안 주의

- 비밀번호를 저장소에 커밋하지 마세요.
- `config.yaml`은 로컬 전용으로 사용하고, 필요시 `.gitignore`에 추가하세요.
