---
type: decision
title: 데이터 수집 아키텍처 = IngestionConnector → DWH → 파이프라인 AI 쿼리
tags: [dwh, connector, ingestion, langgraph, architecture, port-adapter, scheduler]
status: active
---

# 데이터 수집 아키텍처 = IngestionConnector → DWH → 파이프라인 AI 쿼리

## 결정

외부 데이터를 우리 시스템에 들이고 활용하는 전체 흐름을 **4층**으로 확정한다.

```
[1] 데이터 수집 커넥터 (IngestionConnector 포트)
      MondayConnector (첫 구현체, read-only 래퍼 내장)
      (향후) Jira · Slack · Notion …
            │  스케줄러(SourceScheduler cron)가 트리거 → LangGraph 에이전트가 실행
            ▼
[2] DataWarehouse (bronze/silver/gold · PostgreSQL)
            │
            ▼
[3] 저장소 파이프라인 (static/manual)
      AI(LangGraph 에이전트)가 DWH를 쿼리해 컨텍스트로 활용
            │
            ▼
[4] 산출 md → DocumentStore (RunDocOutput 흡수, run_id nullable)
```

1. **Monday = `IngestionConnector`의 첫 구현체.** 소스가 늘어도 상위(스케줄러·에이전트)가 소스별 API를 모르게 하는 포트/어댑터. SCM 커넥터와 **형제 포트**(상속 아님) → [[concept-ingestion-connector]].
2. **스케줄러 설정으로 DWH 적재.** 기존 `SourceScheduler`·`TagPoller` 패턴에 수집 잡을 얹어 cron 트리거. 실제 추출·변환은 LangGraph 에이전트 → [[decision-monday-collector-langgraph-scheduled]]. 커넥터 자체의 설정(on/off·주기·범위·토큰)은 **시스템 설정 페이지**에서 구성 → [[decision-connector-settings-system-settings]].
3. **파이프라인이 DWH를 AI로 쿼리.** 저장소 파이프라인이 DWH를 조회해 문서 생성 컨텍스트로 활용 — DWH가 분석 저장소를 넘어 파이프라인 AI의 컨텍스트 소스가 된다.
4. **산출·수집물은 DocumentStore로.** md 표준 포맷, 기존 `RunDocOutput`을 흡수, 문서 정체성을 run에서 분리 → [[decision-dwh-md-document-store]] · [[decision-document-identity-run-separation]].

## 근거

- **기존 자산 재사용(코드 확인 2026-07-10)** — 포트/어댑터(`ScmConnector`)·스케줄러(`SourceScheduler`)·md 저장(`RunDocOutput`)·run 인프라(`create_run`/`launch_runner`)가 이미 있다. 새로 만들지 않고 얹으면 중복 저장·중복 스케줄러를 피한다.
- **확장성이 명시 요구** — "Monday 말고도 다른 데이터 수집 커넥터를 만들 수 있게" → 포트로 추상화하면 어댑터 추가만으로 소스 확장.
- **양방향 vs 단방향 분리** — SCM은 코드를 읽고 문서를 되돌려 제출(양방향), 수집 커넥터는 데이터를 읽어 적재(읽기 전용). 책임이 달라 포트를 나눈다.
- **DWH를 파이프라인 컨텍스트로 승격** — 수집 데이터가 단지 BI용에 머물지 않고, 문서 자동화 품질을 높이는 입력이 된다(과제 맥락 반영). 두 시스템 축(수집·생성)을 DWH가 잇는다.

## 기각 대안

- **Monday를 ScmConnector로 욱여넣기** — 코드 레포 계약(compare/tree/MR)과 SaaS 데이터 추출은 의미가 안 맞아 포트가 오염된다. 형제 포트가 깔끔.
- **커넥터 없이 Monday 전용 스크립트** — 지금은 빠르나 두 번째 소스(Jira 등) 추가 시 전면 재작성. 확장 요구를 정면 위배.
- **DWH를 BI 전용으로만(파이프라인이 안 씀)** — 수집 데이터를 문서 자동화에 못 씀. "파이프라인이 DWH를 AI로 쿼리" 요구를 못 살림.
- **수집 전용 별도 스케줄러 신설** — `SourceScheduler`와 이원화. 운영 복잡도만 증가.

## 관련

- [[concept-ingestion-connector]] — 이 결정이 도입하는 포트
- [[concept-port-adapter]] — 상위 패턴
- [[decision-scm-connector-abstraction]] — 형제 포트(코드 축)
- [[decision-monday-collector-langgraph-scheduled]] — 수집 실행 = 스케줄러 + LangGraph
- [[decision-connector-settings-system-settings]] — 커넥터 설정 위치 = 시스템 설정 페이지
- [[decision-monday-readonly-client-wrapper]] — Monday 어댑터 read-only 강제
- [[decision-dwh-md-document-store]] — 산출 저장(DocumentStore)
- [[decision-document-identity-run-separation]] — 문서 정체성 run 분리
- [[decision-bronze-single-jsonb-table]] — [2] DWH bronze 착륙 테이블 형태
- [[entity-data-warehouse]] — [2] 층
- [[entity-monday-com]] — 첫 구현체
- [[2026-07-10-ingestion-connector-architecture]] — 논의 원본
