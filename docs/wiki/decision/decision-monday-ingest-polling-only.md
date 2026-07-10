---
type: decision
title: Monday.com 적재 = 스케줄러 폴링 단일 레인 (webhook 삭제)
tags: [dwh, monday-com, etl, cdc, polling, scheduler]
status: active
---

# Monday.com 적재 = 스케줄러 폴링 단일 레인 (webhook 삭제)

> [[decision-monday-ingest-hybrid]](webhook + 야간 폴링 하이브리드)를 **supersede**한다. 지연 목표가 "일 배치(오늘 데이터를 내일 문서에 반영)"로 확정([[question-dwh-latency-target]])되어, webhook 레인(실시간 근사)이 순수 과잉이 되었기 때문이다.

## 결정

Monday.com 데이터를 DWH로 적재할 때 **스케줄러가 트리거하는 폴링 레인 하나**만 운영한다. webhook 레인을 두지 않는다.

1. **스케줄러 폴링 레인(유일)** — 매일 02:00 KST에 Monday GraphQL API를 `items_page` cursor(500/page)로 전수 순회. boards/groups/columns/users/teams/tags는 전수 refresh, updates/activity_logs는 `from_date` 증분. 결과를 bronze 단일 JSONB 테이블 `raw_records`에 **append**(직전 수집분과 `content_sha256` 동일 시 skip) → [[decision-bronze-single-jsonb-table]]. **이 레인의 실행체는 스케줄러가 트리거하는 LangGraph 수집 에이전트다 → [[decision-monday-collector-langgraph-scheduled]]. 모든 Monday 접근은 읽기 전용 래퍼를 통과 → [[decision-monday-readonly-client-wrapper]].**
2. **lifecycle 복원(reconcile)** — 폴링이 전수를 보므로 별도 보정 레인이 필요 없다. `state: deleted/archived`는 soft delete, PG 15+ `MERGE WHEN NOT MATCHED BY SOURCE`로 사라진 row 비활성 마킹, activity log 기반 lifecycle fact 복원 — 이 모두가 야간 폴링 안에서 이뤄진다.

webhook은 **삭제가 아니라 유보**다: 지연 목표가 근실시간으로 바뀌면 옵션 레인으로 되살릴 수 있다(→ 아래 재검토 조건).

## 근거

- **파이프라인이 이미 있다** — 사용자 지적: "적재 전략(하이브리드)은 필요 없는데, 파이프라인 있잖아." [[decision-monday-collector-langgraph-scheduled]]의 스케줄러 + LangGraph 수집 에이전트가 폴링을 돌리는 파이프라인이다. webhook 레인은 여기에 얹는 별도 수신 경로라 운영 표면(FastAPI endpoint·서명 검증·재시도·중복 처리)을 이중으로 늘린다.
- **정확성은 폴링이 전담** — webhook은 Monday가 30분(1분×30회) 재시도만 보장([[entity-monday-com]])해 유실 위험이 있어, 어차피 야간 전수 폴링이 진실 소스였다. webhook은 correctness에 기여하지 않고 오직 latency만 줄인다.
- **지연 목표가 일 배치로 확정** — [[question-dwh-latency-target]]가 "일 배치(다음 날 아침 분석)"로 answered. 문서 자동화 파이프라인이 야간 배치라 "오늘 진행 상황을 오늘" 볼 필요가 없다. webhook의 유일한 값(실시간 근사)이 요구되지 않는다.
- **단순함이 곧 신뢰성** — 레인 하나면 중복 전달·두 레인 정합(idempotency)·webhook 유실 복구 로직이 통째로 사라진다. bronze append(sha256 skip)의 멱등성만으로 충분.

## 기각 대안

- **webhook + 야간 폴링 하이브리드** ([[decision-monday-ingest-hybrid]]) — 실시간 근사를 주지만, 지연 목표가 일 배치면 그 값이 요구되지 않는다. 운영 표면만 이중. supersede.
- **webhook만으로 실시간 수집** — 30분 재시도 한계로 유실. 폴링 없이는 진실 보정 불가. (원래 hybrid 결정에서 이미 기각.)
- **Airbyte 등 외부 ETL 단독** — plan tier activity log 보존 한계 경고([[question-monday-plan-tier]]) + LangGraph 재사용 이점 상실 + md 변환·DocumentStore 적재 커스텀 로직을 못 얹음. Phase 5 후보로만 유지.

## 재검토 조건 (webhook 되살리기)

지연 목표가 **근실시간(시간 단위 이하)** 으로 바뀌면 webhook을 **옵션 레인**으로 되살린다 — 그때는 폴링(진실 보정)은 유지한 채 webhook(실시간 근사)을 더하는 하이브리드로 복귀. 그 형태의 일반 패턴은 [[concept-readonly-saas-cdc]]에 보존돼 있다.

## 관련

- [[decision-monday-ingest-hybrid]] — ⛔ 이 결정이 supersede (webhook 레인 삭제)
- [[question-dwh-latency-target]] — 이 결정의 근거(일 배치 확정)가 된 질문
- [[concept-readonly-saas-cdc]] — webhook+폴링 하이브리드의 일반 패턴(근실시간 요구 시 복귀 대상)
- [[decision-monday-collector-langgraph-scheduled]] — 폴링 레인 실행체(스케줄러 + LangGraph)
- [[decision-monday-readonly-client-wrapper]] — 폴링이 통과하는 읽기 전용 래퍼
- [[decision-bronze-single-jsonb-table]] — 폴링 결과가 착륙하는 bronze 테이블(append)
- [[decision-dwh-as-karpathy-llm-wiki]] — bronze append = 카파시 ① 원본 축적
- [[decision-dwh-transform-dbt]] — 폴링 결과의 변환을 dbt로
- [[decision-dwh-scd-strategy]] — lifecycle 이력으로 SCD2 적용
- [[question-monday-plan-tier]] — activity log 보존 한계가 증분 폴링 안전성을 결정
- [[2026-07-10-monday-ingest-polling-only]] — 논의 원본
