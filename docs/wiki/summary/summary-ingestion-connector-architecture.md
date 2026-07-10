---
type: summary
title: 데이터 수집 커넥터 아키텍처 요약
tags: [dwh, connector, ingestion, langgraph, architecture, document-store]
status: active
---

# 데이터 수집 커넥터 아키텍처 요약

원본: [[2026-07-10-ingestion-connector-architecture]]

## 요지

grill(설계 검증) 세션에서 실제 backend 코드를 확인한 뒤, 어제까지의 개별 Monday/DWH 결정을 **하나의 상위 데이터 흐름 아키텍처**로 확정했다.

**4층 흐름**: `IngestionConnector`(수집 커넥터 포트) → DWH(bronze/silver/gold) → 저장소 파이프라인이 DWH를 AI로 쿼리 → 산출 md는 DocumentStore.

**핵심 결정 3가지**:
1. **Monday = 데이터 수집 커넥터의 첫 구현체** — SCM 커넥터([[decision-scm-connector-abstraction]])와 **형제 포트**(상속 아님, 책임 다름). Monday 말고도 Jira·Slack 등을 같은 포트 어댑터로 확장 → [[concept-ingestion-connector]] · [[decision-ingestion-connector-architecture]].
2. **스케줄러가 커넥터를 돌려 DWH 적재** — 기존 `SourceScheduler`·`TagPoller` 패턴 재사용, 실행은 LangGraph 에이전트 → [[decision-monday-collector-langgraph-scheduled]].
3. **파이프라인이 DWH를 AI로 쿼리** — DWH가 분석 저장소를 넘어 문서 자동화의 컨텍스트 소스가 됨.

**저장 모델 확정 2건(grill)**: DocumentStore가 기존 `RunDocOutput`을 흡수·일반화([[decision-dwh-md-document-store]]) + 문서 정체성을 run에서 분리(run_id nullable) → [[decision-document-identity-run-separation]].

**코드 근거**: `connectors/`는 현재 SCM 전용, DWH 테이블은 아직 코드에 없음 → 이 아키텍처는 앞으로 만들 청사진.

## 파생 페이지

**concept**:
- [[concept-ingestion-connector]] — 수집 커넥터 포트(SaaS·외부 소스 적재)

**decision**:
- [[decision-ingestion-connector-architecture]] — 4층 데이터 흐름 아키텍처
- [[decision-document-identity-run-separation]] — 문서 정체성 run 분리

**갱신**: [[entity-monday-com]](수집 커넥터 첫 구현체 역할) · [[concept-port-adapter]](수집 커넥터 실체화)
