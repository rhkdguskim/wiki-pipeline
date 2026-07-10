---
type: concept
title: 데이터 수집 커넥터 (IngestionConnector) — SaaS·외부 소스 적재 포트
tags: [dwh, connector, port-adapter, ingestion, etl, extensibility]
status: active
---

# 데이터 수집 커넥터 (IngestionConnector) — SaaS·외부 소스 적재 포트

## 정의

외부 데이터 소스(SaaS·API·파일 등)에서 데이터를 **추출해 DataWarehouse에 적재**하는 책임을 우리 언어로 선언한 포트. Monday·Jira·Slack처럼 소스가 늘어도 상위 로직(스케줄러·수집 에이전트)이 소스별 API를 모르게 한다 — [[concept-port-adapter]]의 데이터 적재 축 실체화.

```
interface IngestionConnector:
    kind: str
    extract(watermark) -> [raw_record]     # 증분/전수 추출
    to_bronze(raw_record) -> bronze_row     # 원본 거울 정규화(변환 금지)
    verify_access() -> bool                 # 등록 dry-run

make_ingestion_connector(kind="monday" | ...) -> IngestionConnector
```

## SCM 커넥터와의 관계 — 형제 포트, 상속 아님

이 위키에는 이미 커넥터 포트가 있다: [[decision-scm-connector-abstraction]]의 `ScmConnector`. 그러나 둘은 **책임이 다르다**:

| 축 | ScmConnector | IngestionConnector |
|----|-------------|--------------------|
| 대상 | 코드 레포(GitLab·GitHub) | SaaS·외부 데이터 소스(Monday·…) |
| 책임 | compare·tree 읽기 + MR/PR 제출 + auth (3책임) | extract → DWH 적재 + auth |
| 방향 | 코드를 읽고 문서를 되돌려 제출(양방향) | 데이터를 읽어 적재(읽기 전용) |
| 산출 | md 문서(파이프라인 입력) | bronze row(DWH 입력) |

따라서 `IngestionConnector`는 `ScmConnector`를 **상속하지 않고 형제 포트**로 둔다. 코드 확인(2026-07-10): 현재 `backend/connectors/`는 SCM 전용(`ScmConnector`만 export)이라, 수집 커넥터는 별도 포트로 신설한다.

## 왜 중요한가

- **소스 확장성** — Monday는 첫 구현체일 뿐, 다른 SaaS를 같은 포트의 어댑터로 추가한다. 상위 코드 무변경.
- **읽기 전용 강제와 정합** — 각 어댑터가 자기 read-only 강제를 품는다(Monday는 [[decision-monday-readonly-client-wrapper]]).
- **스케줄러 재사용** — 수집 잡을 기존 `SourceScheduler` 패턴에 얹어 cron 트리거([[decision-monday-collector-langgraph-scheduled]]).
- **DWH 입력 계약 단일화** — 어떤 소스든 `to_bronze`로 medallion bronze 계층에 같은 방식으로 안착([[concept-medallion-dwh-on-postgres]]).

## 관련

- [[concept-port-adapter]] — 상위 패턴
- [[decision-ingestion-connector-architecture]] — 이 포트를 채택한 아키텍처 결정
- [[decision-connector-settings-system-settings]] — 이 포트의 설정 위치(시스템 설정 페이지)
- [[decision-scm-connector-abstraction]] — 형제 포트(코드 축)
- [[decision-monday-readonly-client-wrapper]] — Monday 어댑터의 read-only 강제
- [[concept-medallion-dwh-on-postgres]] — 적재 목적지(bronze)
- [[decision-bronze-single-jsonb-table]] — `to_bronze`가 넣는 bronze 테이블의 형태
- [[entity-monday-com]] — 첫 구현체의 원천
