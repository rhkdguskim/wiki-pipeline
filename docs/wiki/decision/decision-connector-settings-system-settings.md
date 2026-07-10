---
type: decision
title: 커넥터 설정 = 시스템 설정 페이지(SystemSetting connector.* 네임스페이스)
tags: [dwh, connector, ingestion, settings, system-settings, secret]
status: active
---

# 커넥터 설정 = 시스템 설정 페이지(SystemSetting connector.* 네임스페이스)

## 결정

데이터 수집 커넥터(Monday 등, [[concept-ingestion-connector]])의 설정을 **시스템 설정 페이지**에서 구성한다.

- 기존 `SystemSetting`(키-값 DB, `"namespace.field"`)의 **`connector.<kind>.*` 새 네임스페이스**로 저장. 예: `connector.monday.enabled`·`connector.monday.api_token`·`connector.monday.schedule_cron`·`connector.monday.board_ids`·`connector.monday.api_version`.
- `SettingsService`의 DB 우선 → .env 폴백·redact·`updated_by` 감사 패턴을 그대로 재사용.
- 스케줄러는 `connector.monday.schedule_cron`을 읽어 수집 잡을 건다([[decision-monday-collector-langgraph-scheduled]]).

## 근거

- **기존 자산 정합(코드 확인 2026-07-10)** — `SystemSetting`/`SettingsService`가 이미 `llm.*` 네임스페이스를 이 방식으로 운영한다(".env 의존↓, 대시보드에서 운영 중 변경"). 커넥터 설정은 새 네임스페이스만 추가하면 되어 새 저장·UI 계층이 불필요.
- **SCM 소스 등록과 성격이 다름** — SCM은 `Source`/`ScmInstance`에 "무엇을 문서화할지"를 레포×브랜치 단위로 등록. 커넥터는 "어떤 외부 소스에서 데이터를 끌어올지"의 **시스템 수준 구성**이라 시스템 설정 페이지가 맞다.
- **운영 편의** — 재배포 없이 대시보드에서 커넥터 on/off·주기·범위·토큰을 바꾼다.

## 기각 대안

- **.env / 설정 파일로만** — 변경 시 재배포 필요, 대시보드 운영 불가. `SystemSetting` 도입 취지에 역행.
- **커넥터별 전용 테이블 신설** — 커넥터가 늘 때마다 스키마 변경. 키-값 네임스페이스면 어댑터 추가만으로 확장([[decision-ingestion-connector-architecture]]의 확장성과 정합).
- **SCM처럼 `Source` 테이블에 등록** — 커넥터는 레포×브랜치 단위가 아니라 소스(SaaS) 단위라 모델이 안 맞다.

## 열린 항목 — 토큰 암호화

`SystemSetting`은 v1 평문 저장이나, Monday 토큰은 **read/write 가능**한 민감 토큰([[decision-monday-readonly-client-wrapper]]). 따라서:
- `connector.*.api_token`은 `SecretBox` 암호화로 저장하거나 기존 `ScmInstance` 암호화 저장소를 재사용(구현 시 확정).
- `SettingsService.list_recent`의 redact 대상에 `connector.*.api_token` 포함(현재 `llm.api_key`만).

## 관련

- [[decision-ingestion-connector-architecture]] — 이 설정이 구성하는 수집 커넥터 아키텍처
- [[concept-ingestion-connector]] — 설정 대상 포트
- [[decision-monday-readonly-client-wrapper]] — 토큰이 read/write라 암호화 필요
- [[decision-monday-collector-langgraph-scheduled]] — 스케줄러가 이 설정의 cron을 읽음
- [[entity-data-warehouse]] — 적재 목적지
- [[2026-07-10-connector-settings-in-system-settings]] — 논의 원본
