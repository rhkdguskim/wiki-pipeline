---
type: summary
title: DataWarehouse 설계 계획 요약
tags: [dwh, monday-com, etl, medallion, kimball, dbt, postgresql]
status: active
---

# DataWarehouse 설계 계획 요약

원본: [[2026-07-09-dwh-design-plan]]

## 요지

Monday.com(read-only API Key)과 wiki_pipeline 산출물을 하나의 **DataWarehouse**로 통합하는 상세 설계 계획. 두 갈래 사전 조사(Monday.com API 데이터 모델 · DWH 설계 패턴 결정 공간)와 control plane 데이터 모델 직접 확인에 근거한다.

**핵심 아키텍처**: PostgreSQL 15+ 단일 인스턴스에 **Kimball 차원 모델링 + Medallion(bronze/silver/gold) 스키마 분리**. Monday는 **webhook(실시간 근사) + 야간 전수 폴링(진실 보정) 하이브리드** 적재, wiki_pipeline은 **direct read**(같은 클러스터 다른 스키마). 변환은 **dbt-postgres**(snapshots SCD2 / merge SCD1). 오케스트레이션은 **cron+Python(MVP) → Airflow(10+ 태스크 시)**.

**반정형 처리의 핵심**: Monday column value는 타입별로 JSON shape가 다름 → **typed long table(fact_item_column_value) + JSONB 폴백 + GIN(jsonb_path_ops) 인덱스** 하이브리드.

**DWH의 핵심 가치**: `fact_item_documentation` 브릿지 팩트 — Monday 과제(item) ↔ wiki_pipeline 소스(repo)/run/문서를 잇는 교차 팩트. "이 과제의 진행 상태 ↔ 그 과제에서 나온 문서의 생성 이력·품질·비용" 교차 분석을 가능하게 한다.

**SCD 전략**: Monday items/users/boards = SCD2(dbt snapshot), statuses = SCD1, pipeline run/step = append-only fact.

**단계적 로드맵**: Phase 0 기반 → Phase 1 Monday 단방향 MVP → Phase 2 wiki_pipeline 통합(브릿지 팩트) → Phase 3 webhook 실시간 보강 → Phase 4 품질·SCD 강화 → Phase 5 확장(Airflow·RLS·TimescaleDB).

**설계 확정 전 남은 열린 질문 10건** — plan tier/사용자 매핑/item↔repo 키/볼륨/지연/소비자/보존/PG 버전/다부서/BI 도구. 이 중 일부는 사용자만 답할 수 있어 별도 question 페이지로 분리.

## 파생 페이지

**entity**:
- [[entity-monday-com]] — 데이터 소스 1 (SaaS 과제 관리, GraphQL read-only)
- [[entity-data-warehouse]] — 통합 분석 저장소 (신규 시스템)

**concept**:
- [[concept-medallion-dwh-on-postgres]] — Bronze/Silver/Gold layering을 PG 스키마로 실체화
- [[concept-monday-column-value-modeling]] — 타입별 상이한 column value JSON의 정규화 패턴
- [[concept-readonly-saas-cdc]] — 읽기 전용 SaaS의 CDC: webhook + nightly reconcile

**decision**:
- [[decision-dwh-shape-kimball-medallion]] — 전체 형태 = Kimball + Medallion
- [[decision-dwh-storage-postgres-single]] — 저장소 = PG 단일 클러스터 다른 스키마
- [[decision-monday-ingest-hybrid]] — Monday 적재 = webhook + nightly reconcile
- [[decision-dwh-column-value-hybrid]] — 반정형 = typed long + JSONB 폴백
- [[decision-dwh-scd-strategy]] — SCD = entity별 0/1/2/append 혼합
- [[decision-dwh-transform-dbt]] — 변환·오케스트레이션 = dbt + cron-first

**question** (사용자 결정 필요, 진행 블로커 아님):
- [[question-monday-plan-tier]] · [[question-monday-user-mapping]] · [[question-monday-item-source-key]]
- [[question-dwh-data-volume]] · [[question-dwh-latency-target]] · [[question-dwh-multi-tenancy]]
