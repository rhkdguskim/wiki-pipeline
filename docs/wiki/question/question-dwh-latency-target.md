---
type: question
title: DWH 지연 목표 (일 배치 vs 시간 단위 vs 실시간)
tags: [dwh, latency, freshness, sla, dwh]
status: answered
---

# DWH 지연 목표 (일 배치 vs 시간 단위 vs 실시간)

## 질문

DataWarehouse 데이터의 **신선도 SLA**는 어느 정도인가 — 일 배치(다음 날 아침), 시간 단위, 실시간(분 단위)?

## 맥락

지연 목표가 [[decision-monday-ingest-hybrid]]의 두 레인(webhook + 야간 폴링) 비중과 [[decision-dwh-transform-dbt]]의 오케스트레이션 빈도를 결정한다.

- **일 배치(야간 1회)** — Monday 야간 전수 폴맨스 + dbt 전체 실행. webhook 레인은 생략 가능. 가장 단순. "오늘 진행 상황을 내일 아침 분석" UX.
- **시간 단위(예: 매 정시)** — webhook + 매시간 증분 폴맨스 + dbt incremental. 근실시간 근사. 오늘 진행 상황을 오늘 분석 가능. API 호출량·rate limit 증가.
- **실시간(분 단위)** — webhook만으로는 부족(CDC 30분 재시도 한계). Monday activity log polling을 분 단위로 돌려야 → rate limit 위험. 일반적으로 불필요한 수준.

가정(설계 계획): **일 배치**(다음 날 아침 아침 분석 가능 수준). 이 경우 webhook 레인은 Phase 3 후보(초기 MVP는 폴링만으로 충분)로 미룰 수 있어 구현 비용 절감.

지연 목표가 시간 단위로 빨라지면:
- webhook 레인을 Phase 1로 앞당김
- 폴맨스 주기를 시간 단위로
- dbt incremental 빈도 증가

## 답

**일 배치(야간 1회)로 확정** (2026-07-10). 문서 자동화 파이프라인이 야간 배치라 "오늘 진행 상황을 오늘" 볼 필요가 없다 — "오늘 데이터를 내일 문서에 반영"을 수용.

- **SLA** = 야간 전수 폴링 1회 후 정확(다음 날 아침 분석 가능).
- **폴링 주기** = 매일 02:00 KST 전수 순회 ([[decision-monday-ingest-polling-only]]).
- **webhook 레인 = 삭제(유보)** — 일 배치엔 실시간 근사가 불필요. [[decision-monday-ingest-hybrid]]를 supersede하고 폴링 단일 레인으로 단순화.
- **재검토 조건** — 지연 목표가 근실시간(시간 단위 이하)으로 바뀌면 webhook을 옵션 레인으로 되살린다(폴링은 유지). 그 하이브리드 패턴은 [[concept-readonly-saas-cdc]]에 보존.

→ [[decision-monday-ingest-polling-only]] · [[decision-monday-ingest-hybrid]](superseded)
