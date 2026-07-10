---
type: decision
title: Monday 자동 수집 = 스케줄러 트리거 + LangGraph 에이전트 루프
tags: [dwh, monday-com, langgraph, scheduler, etl, automation]
status: active
---

# Monday 자동 수집 = 스케줄러 트리거 + LangGraph 에이전트 루프

## 결정

Monday 데이터 수집을 사람이 돌리지 않고 **자동화**한다. **2층 구조**로 나눈다.

1. **스케줄러 층(시간 트리거)** — cron / systemd timer가 정해진 시각(야간 전수 폴링 02:00 KST — [[decision-monday-ingest-polling-only]])에 수집 작업을 발동한다. 태스크가 10+로 늘면 Airflow로 이관([[decision-dwh-transform-dbt]]와 동일 기준).
2. **수집 실행 층(LangGraph 에이전트 루프)** — 실제 Monday GraphQL 순회·페이지네이션·에러 처리·md 변환·`DocumentStore` 적재를 **LangGraph 에이전트가 수행**한다. 모든 Monday 접근은 [[decision-monday-readonly-client-wrapper]]의 래퍼를 통과한다.

스케줄러는 "언제"만, 에이전트는 "무엇을·어떻게"를 담당한다.

## 근거

- **엔진 재사용** — 생성 엔진을 이미 LangGraph로 확정([[decision-engine-orchestration-langgraph]] · [[decision-model-provider-neutral-minimax]])했으므로, 수집 에이전트도 같은 런타임·관측(get_stream_writer)·durable 체크포인팅을 재사용한다. 별도 실행 스택을 추가하지 않는다.
- **적재 전략과 정합** — [[decision-monday-ingest-polling-only]]는 스케줄러 폴링 단일 레인을 규정한다(webhook 삭제). 이 에이전트가 **그 폴링 레인의 실행체**다 — cursor 순회·증분 판단·lifecycle 복원 로직을 에이전트 그래프의 노드로 구현.
- **AI 에이전트의 이점** — 스키마 드리프트(새 컬럼·타입)·rate limit 백오프·부분 실패 재개 같은 비정형 상황을 규칙 스크립트보다 유연하게 처리. column value → md 변환도 에이전트가 담당.
- **관측·감사** — LangGraph 스텝 관측([[decision-agent-step-observability]])으로 수집 진행·토큰 비용·실패를 대시보드/이력 DB에 남긴다.

## 기각 대안

- **순수 스크립트 배치(에이전트 없음)** — cron이 고정 Python ETL 스크립트만 실행. 단순·예측 가능하나 스키마 드리프트·비정형 오류에 매번 코드 수정 필요. md 변환·품질 판단 같은 AI 강점을 못 씀. (단순 전량 폴링만이면 이걸로 충분할 수 있어, MVP에서 일부 노드는 결정적 코드로 둘 수 있음 — 하이브리드 허용.)
- **webhook만으로 실시간 수집** — 스케줄러 불필요하나 30분 재시도 한계로 유실. 폴링 레인이 반드시 필요하고, 그 폴링을 이 에이전트가 돌린다. (webhook 레인 자체가 지연 목표=일 배치 확정으로 삭제됨 → [[decision-monday-ingest-polling-only]].)
- **Airbyte 등 외부 ETL 툴 단독** — 스케줄+수집을 통째 위임. plan tier 보존 한계 경고([[question-monday-plan-tier]]) + LangGraph 재사용 이점 상실 + md 변환·DocumentStore 적재 커스텀 로직을 못 얹음. Phase 5 후보로만 유지.

## 관련

- [[decision-engine-orchestration-langgraph]] — 재사용하는 실행 런타임
- [[decision-monday-ingest-polling-only]] — 이 에이전트가 구현하는 폴링 단일 레인(webhook 삭제)
- [[decision-monday-readonly-client-wrapper]] — 에이전트의 Monday 접근 경로(읽기 전용 강제)
- [[decision-dwh-md-document-store]] — 에이전트가 md를 적재하는 대상
- [[decision-dwh-transform-dbt]] — Airflow 이관 기준(10+ 태스크) 공유
- [[question-dwh-latency-target]] — 폴링 주기·스케줄 시각을 지연 목표가 결정
- [[2026-07-10-dwh-monday-ingestion-refinements]] — 논의 원본
