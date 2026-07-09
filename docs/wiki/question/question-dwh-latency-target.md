---
type: question
title: DWH 지연 목표 (일 배치 vs 시간 단위 vs 실시간)
tags: [dwh, latency, freshness, sla, dwh]
status: open
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

<!-- answered로 전환 시: SLA + webhook 레인 도입 시점 + 폴맴스 주기 + 관련 decision 링크 -->
