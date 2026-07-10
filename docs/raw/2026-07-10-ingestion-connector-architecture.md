# 데이터 수집 커넥터 아키텍처 — Monday를 첫 구현체로 (2026-07-10)

> grill(설계 검증) 세션에서 실제 backend 코드를 확인한 뒤 사용자가 확정한 아키텍처 방향.
> 어제 개별 결정들([[2026-07-09-dwh-design-plan]] · [[2026-07-10-dwh-monday-ingestion-refinements]])을
> 하나의 상위 축으로 묶는다. raw 불변 — 원문 그대로 보존.

## 사용자 확정 (원문)

> 굳굳 이렇게 정리하자 이제 먼데이 엔티티를 데이터 수집 커넥터로 만들고 먼데이말고도 추후 나중에 다른 데이터 수집 커넥터도 만들 수 있게 구성하자. 데이터 수집 커넥터는 스케줄러 설정을 통해서 데이터 웨어하우스에 데이터를 적재하는거야 그리고 우리가 구성한 저장소 파이프라인이 데이터 웨어 하우스를 AI가 쿼리하여 정보를 활용하는 구조야

## 확정 아키텍처 (4층 데이터 흐름)

```
[1] 데이터 수집 커넥터 (IngestionConnector 포트)
      MondayConnector (첫 구현체)  ← read-only 래퍼 내장
      (향후) JiraConnector · SlackConnector · ...
            │  스케줄러(SourceScheduler)가 cron으로 트리거
            ▼
[2] 데이터 웨어하우스 (DWH — bronze/silver/gold, PostgreSQL)
            │
            ▼
[3] 저장소 파이프라인 (우리가 만든 static/manual 파이프라인)
      AI(LangGraph 에이전트)가 DWH를 쿼리해 정보를 활용
            │
            ▼
[4] 산출물 (md 문서) → DocumentStore (RunDocOutput 흡수)
```

### 1. Monday = 데이터 수집 커넥터의 첫 구현체

- Monday 엔티티를 **"데이터 수집 커넥터(IngestionConnector)"** 의 첫 구현체로 만든다.
- 이는 기존 SCM 커넥터([[decision-scm-connector-abstraction]])와 **같은 포트/어댑터 패턴이지만 다른 축**이다:
  - `ScmConnector` = 코드 레포를 **읽고**(compare/tree) 문서를 **제출**(MR/PR)하는 3책임.
  - `IngestionConnector` = SaaS/외부 소스에서 **데이터를 추출**해 DWH에 **적재**하는 책임.
  - 성격이 달라 `ScmConnector`를 상속하지 않고 **형제 포트**로 둔다. 코드 확인: 현재 `connectors/`는 SCM 전용(`ScmConnector`만 export).
- **확장성**: Monday 말고도 나중에 다른 데이터 수집 커넥터(Jira·Slack·Notion 등)를 `IngestionConnector` 구현체로 추가할 수 있어야 한다. `make_connector(kind=...)`처럼 `make_ingestion_connector(kind="monday"|...)` 팩토리.
- Monday 커넥터는 [[decision-monday-readonly-client-wrapper]]의 read-only 래퍼를 내부에 품는다.

### 2. 스케줄러 설정으로 DWH에 적재

- 데이터 수집 커넥터는 **스케줄러 설정**(cron)을 통해 주기적으로 실행돼 DWH에 데이터를 적재한다.
- 기존 `SourceScheduler`(APScheduler cron)·`TagPoller`의 "bookmark → create_run → launch" 패턴을 재사용한다. 새 잡 유형(ingestion job)을 추가하는 형태 — 별도 스케줄러를 새로 만들지 않는다.
- 실제 수집·변환은 LangGraph 에이전트가 수행([[decision-monday-collector-langgraph-scheduled]]) — 커넥터는 추출 I/O, 에이전트는 오케스트레이션.

### 3. 저장소 파이프라인이 DWH를 AI로 쿼리

- 우리가 구성한 **저장소 파이프라인**(static/manual)이 **DWH를 AI(LangGraph 에이전트)가 쿼리**해서 정보를 활용하는 구조.
- 즉 DWH는 단순 분석 저장소를 넘어, 파이프라인 AI의 **컨텍스트 소스**가 된다 — 예: 문서 생성 시 "이 과제의 Monday 진행 상태·담당자·이력"을 DWH에서 조회해 문서에 반영.
- 이 쿼리 경로가 [[question-monday-item-source-key]](item↔repo 키)의 가치를 실현하는 지점.

### 4. 산출은 DocumentStore로 (앞서 확정)

- 파이프라인 산출·수집물 모두 md 표준 포맷 + `DocumentStore` 포트로 저장([[decision-dwh-md-document-store]]).
- grill에서 추가 확정: `DocumentStore`는 기존 `RunDocOutput`을 흡수·일반화하고, 문서 정체성을 run에서 분리(run_id nullable)한다 — 아래 별도 정리.

## grill에서 함께 확정한 2건 (저장 모델)

1. **DocumentStore가 RunDocOutput을 흡수** — `RunDocOutput`(content_text·content_sha256·quality_status·metadata_json)이 이미 md를 PG에 저장 중이므로, 새 저장 계층을 만들지 않고 이를 `DocumentStore` 포트의 첫 PostgresAdapter로 재정의. 파이프라인 산출·Monday 수집물이 같은 `save(md, meta)` 계약 공유.
2. **문서 정체성을 run에서 분리** — 문서(Document)는 오래 사는 엔티티, run은 "그 문서를 갱신한 사건". `run_id`를 nullable FK로. Monday 수집물·향후 LLM WIKI 문서가 특정 run에 강제로 묶이지 않게. `run_doc_outputs`는 Document의 run별 생성 스냅샷(리비전)으로 재해석.

## 미해결 (다음 논의 후보)

- 같은 Monday item을 매일 재수집할 때 새 리비전으로 쌓을지 / 덮어쓸지(문서 식별·갱신 정책) — SCD2([[decision-dwh-scd-strategy]])와 정합 여부.
- `IngestionConnector` 포트의 정확한 메서드 시그니처(extract/watermark/to_bronze 등)는 구현 착수 시 확정.
- 저장소 파이프라인이 DWH를 쿼리하는 인터페이스(직접 SQL vs 전용 조회 도구/MCP).
