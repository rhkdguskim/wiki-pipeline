# 커넥터 설정 = 시스템 설정 페이지에 구성 (2026-07-10)

> 데이터 수집 커넥터([[2026-07-10-ingestion-connector-architecture]])의 설정을 어디서 관리할지 확정.
> raw 불변 — 원문 그대로 보존.

## 사용자 지시 (원문)

> 커넥터 설정은 시스템 설정 페이지로 구성했으면 좋겠습니다.

## 확정 사항

데이터 수집 커넥터(Monday 등)의 설정을 **시스템 설정 페이지**에서 구성한다.

### 기존 자산과의 정합 (코드 확인 2026-07-10)

- `controlplane/models.py`의 **`SystemSetting`** 이 이미 존재 — `"namespace.field"` 키-값을 DB에 저장(예: `llm.provider`·`llm.api_key`). ".env 의존을 줄이고 운영 중 대시보드에서 변경 가능하게 한다"가 명시 목적.
- **`SettingsService`** 는 DB 우선 → .env 폴백 병합(`get_llm_effective`), 비밀 값 redact(`llm.api_key`는 `(redacted)`), `updated_by` 감사.
- 이미 `llm.*` 네임스페이스가 이 패턴을 쓰므로, **커넥터 설정은 `connector.<kind>.*` 새 네임스페이스**로 얹힌다. 예:
  - `connector.monday.enabled`
  - `connector.monday.api_token` (비밀 — redact 대상)
  - `connector.monday.schedule_cron`
  - `connector.monday.board_ids` (수집 대상 범위)
  - `connector.monday.api_version`

### 커넥터 설정 = 시스템 설정, SCM 소스 등록과 구분

- **SCM 소스**(코드 레포)는 `Source`/`ScmInstance` 테이블에 등록 단위로 관리(레포×브랜치, 토큰은 `SecretBox` 암호화). 이건 "무엇을 문서화할지"의 등록.
- **데이터 수집 커넥터**(Monday 등)는 "어떤 외부 소스에서 데이터를 끌어올지"의 시스템 수준 설정 → **시스템 설정 페이지**가 맞다. 소스별 반복 등록이 아니라 커넥터 단위 구성.
- 스케줄러는 이 설정(`connector.monday.schedule_cron`)을 읽어 수집 잡을 건다.

### 열린 항목 — 토큰 암호화

- `SystemSetting`은 v1에서 **평문 저장**(주석: "운영에서는 Fernet 암호화 또는 SecretBox 적용이 이상"). 그러나 Monday 토큰은 **read/write 가능**한 민감 토큰이다([[decision-monday-readonly-client-wrapper]]).
- 따라서 커넥터 토큰은 (a) `SystemSetting`에 `SecretBox` 암호화 컬럼/값으로 저장하거나, (b) 기존 `ScmInstance`처럼 암호화 저장소를 재사용하는 방안을 구현 시 확정해야 한다. UI/설정 위치는 시스템 설정 페이지로 하되, 저장 계층은 암호화가 필요.
- 최소한 `list_recent`의 redact 대상에 `connector.*.api_token`을 포함해야 한다(현재는 `llm.api_key`만 redact).
