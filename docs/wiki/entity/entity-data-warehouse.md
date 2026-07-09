---
type: entity
title: DataWarehouse (분석 통합 저장소)
tags: [dwh, data-warehouse, analytics, postgresql, medallion, kimball, dwh]
status: active
---

# DataWarehouse (분석 통합 저장소)

## 개요

**Monday.com 과제 데이터**와 **wiki_pipeline 산출물(문서·실행 이력)**을 하나로 통합하는 분석용 저장소. 사내 VM의 **PostgreSQL 15+ 단일 인스턴스**에 구축하고, 본 위키의 **세 번째 시스템 축**(정적 파이프라인 · 매뉴얼 추출 파이프라인에 이어)이다.

**두 데이터 소스**:
1. **Monday.com**(외부 SaaS) — read-only API 키로 ETL 적재 → [[entity-monday-com]]
2. **wiki_pipeline control plane**(내부 PostgreSQL) — 같은 클러스터의 다른 스키마에서 direct read

**3계층 스키마**(Medallion layering — [[concept-medallion-dwh-on-postgres]]):

| 스키마 | 역할 | 규칙 |
|---|---|---|
| `bronze` | 원본 거울(PSA) — API 응답 그대로, 변환 금지 | extracted_at·extraction_batch_id 추가, _raw 접미사, 무기한 보존 |
| `silver` | 정제·통합·SCD 이력 — conformed dim + fact | dbt 변환, 타입 정규화, SCD2는 snapshot |
| `gold` | 프레젠테이션 마트 — BI 직결용 wide table | dbt 모델 + 일부 materialized view |
| `_meta` | ETL 운영 메타 — 실행·watermark·드리프트·lineage | 감사 추적 |

**역할 분리**: `etl_writer`(bronze/silver/gold/_meta 소유, DDL+DML) / `analytics_reader`(gold SELECT only). 다부서 확장 시 `_meta.tenant` + PG RLS 도입 → [[question-dwh-multi-tenancy]].

**핵심 가치 — 브릿지 팩트**: `silver.fact_item_documentation`이 Monday item ↔ wiki_pipeline source/run/문서를 잇는다. "이 과제의 진행 상태 ↔ 그 과제에서 나온 문서의 생성 이력·품질·비용" 교차 분석을 단일 팩트로 가능하게 한다. 조인 키는 [[question-monday-item-source-key]]에서 확정.

## 이 시스템에서의 역할

- **정적·매뉴얼 두 파이프라인의 산출물을 분석 가능한 형태로 영구 보존** — control plane의 runs/run_events는 30일 보존 한계가 있으나, DWH bronze(PSA)는 무기한 보존해 감사·시계열 분석 기반 제공.
- **Monday 과제 추적과의 교차 분석** — 과제 진행 ↔ 문서화 자동화 적용률·성공률·비용을 한 화면에서.
- **BI 소비 창구** — gold 마트를 BI 도구(Metabase/Superset)와 analytics_reader 역할로 직결.

## 관련

- [[entity-monday-com]] — 데이터 소스 1
- [[concept-medallion-dwh-on-postgres]] — 3계층 layering
- [[concept-monday-column-value-modeling]] — 반정형 처리
- [[concept-readonly-saas-cdc]] — Monday CDC 패턴
- [[decision-dwh-shape-kimball-medallion]] · [[decision-dwh-storage-postgres-single]] · [[decision-dwh-scd-strategy]] · [[decision-dwh-transform-dbt]] — 핵심 결정
- [[2026-07-09-dwh-design-plan]] — 설계 논의 원본
