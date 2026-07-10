---
type: summary
title: DWH Monday 적재·저장소 설계 정정 요약
tags: [dwh, monday-com, readonly, langgraph, document-store, md, llm-wiki]
status: active
---

# DWH Monday 적재·저장소 설계 정정 요약

원본: [[2026-07-10-dwh-monday-ingestion-refinements]]

## 요지

2026-07-09 DataWarehouse 설계([[summary-dwh-design-plan]])에 대한 사용자 후속 지시로, **인증 전제를 정정**하고 **자동 수집·md 저장·DB 교체 가능성** 3가지를 확정한다.

1. **Monday 토큰 = read/write** → 실제 발급 토큰이 읽기/쓰기 모두 가능하므로, **앱 계층 래퍼(`MondayReadOnlyClient`)로 읽기 전용을 강제**한다(mutation 차단). 2026-07-09가 기록한 "personal 토큰은 read-only 강제 불가" 조사 결과는 유지되나, 우리 상황에선 OAuth 대신 **코드적 강제**가 답이다 → [[entity-monday-com]] 정정.
2. **스케줄러 자동 수집** = cron/timer가 트리거 → **LangGraph 에이전트 루프**가 수집·md 변환. 기존 엔진 결정([[decision-engine-orchestration-langgraph]])과 정합, [[decision-monday-ingest-hybrid]]의 폴링 레인을 구현.
3. **md 저장 + DB 교체 가능** = md가 표준 산출 포맷, 저장 백엔드는 **`DocumentStore` 포트 + 어댑터**로 교체(지금 PostgreSQL → 향후 LLM WIKI용 VectorStore). [[concept-port-adapter]]의 새 실체화.

## 파생 페이지

**decision**:
- [[decision-monday-readonly-client-wrapper]] — read/write 토큰 → 래퍼가 mutation 차단(읽기 전용 코드적 강제)
- [[decision-monday-collector-langgraph-scheduled]] — 스케줄러 트리거 + LangGraph 에이전트 자동 수집
- [[decision-dwh-md-document-store]] — md 표준 포맷 + DocumentStore 어댑터로 DB 교체 가능(LLM WIKI 대비)

**갱신**:
- [[entity-monday-com]] — 인증 모델 정정(read/write 토큰 + 래퍼 강제)
- [[decision-monday-ingest-hybrid]] — 폴링 레인 실행체 = LangGraph 수집 에이전트, 읽기 전용 강제 참조 (이후 [[decision-monday-ingest-polling-only]]가 supersede — webhook 삭제)
- [[concept-port-adapter]] — DocumentStore 실체화 추가
