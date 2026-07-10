---
type: concept
title: Medallion DWH on PostgreSQL (Bronze/Silver/Gold layering)
tags: [dwh, medallion, postgresql, etl, layered-architecture]
status: active
---

# Medallion DWH on PostgreSQL (Bronze/Silver/Gold layering)

## 정의

**Medallion 아키텍처**는 데이터가 흐르면서 점진적으로 구조·품질을 개선하도록 **논리적 계층**으로 조직하는 데이터 설계 패턴이다. Databricks가 lakehouse 맥락에서 정규화했으나, 본질은 **계층화 규칙(layering discipline)이지 데이터 모델이 아니다** — substrate(对象 저장소·Delta/Iceberg vs 관계형 DB)와 무관하다.

3개 표준 계층:

| 계층 | 목적 | 본질 |
|---|---|---|
| **Bronze**(raw) | 원본 소스 추출 그대로 보존 | 변환 없음, append/upsert, PSA(Persistent Staging Area) 역할 |
| **Silver**(cleansed/integrated) | 정제·타입 정규화·conformed dimension 통합·SCD 이력 | 비즈니스 규칙·조인·중복 제거 |
| **Gold**(curated/marts) | 차원 모델·집계 — BI 직결 대상 | 넓고 얕은 wide table, materialized view |

**PostgreSQL에서의 실체화**: 별도 lakehouse 저장소가 필요 없다. 동일 PG 인스턴스에 **3개 스키마**(또는 3개 DB)로 이름만 빌려 적용한다. lakehouse의 time-travel·ACID-on-files 같은 저장소 기능은 PG에 해당하지 않지만, layering discipline은 그대로 유효하다.

## 왜 중요한가

- **재생(replay) 가능성** — Bronze가 원본을 불변 보존하므로, Silver/Gold 변환 로직을 바꿔도 Bronze에서 다시 재생할 수 있다. SaaS API를 재호출할 필요가 없다(rate limit·보존 한계 회피).
- **계층별 독립적 품질 게이트** — Bronze는 원본 충실도, Silver는 스키마 정규화·SCD 무결성, Gold는 비즈니스 마트 정확성. 각 계층에서 별도의 dbt 테스트·freshness SLA 적용.
- **운영/분리 부하 격리** — 같은 클러스터 안에서도 Bronze 적재 작업과 Gold 분석 쿼리가 스키마/역할로 분리돼 경합을 줄인다.
- **소스 추가 시 일관된 패턴** — 새 외부 소스가 들어와도 Bronze에 거울 테이블 추가 → Silver 통합 → Gold 마트 확장의 동일 패턴 적용.

## PostgreSQL 특화 고려사항

- ** bronze는 JSONB 컬럼 적극 활용** — 반정형 원본을 있는 그대로 보존(→ [[concept-monday-column-value-modeling]]).
- **Silver의 SCD는 dbt snapshot** — `dbt_valid_from`/`dbt_valid_to`/`dbt_is_current` 자동 부여(→ [[decision-dwh-scd-strategy]]).
- **Gold의 materialized view** — `CONCURRENTLY` refresh로 집계 마트 성능 확보. PG 전용 기능.
- **스키마 vs DB 선택**: 같은 DB 다른 스키마 = 가장 단순(트랜잭션 경계 공유). 다른 DB = 스키마 격리 + `postgres_fdw` 또는 logical replication 필요. 트래픽이 크면 읽기 복제본으로 아예 분리.
- **`_meta` 스키마** — Medallion 3계층 외에 ETL 운영 메타(etl_runs·watermarks·table_stats·schema_drift_log·dbt_invocations)를 별도 스키마로 둬 지식 계층과 분리.

## 관련

- [[decision-dwh-shape-kimball-medallion]] — 우리가 Kimball+Medallion을 택한 결정
- [[concept-karpathy-llm-wiki-storage]] — 같은 layering discipline의 LLM Wiki 언어 버전
- [[decision-dwh-as-karpathy-llm-wiki]] — 이 물리 계층을 Karpathy 3동작으로 재조직한 결정
- [[decision-dwh-storage-postgres-single]] — PG 단일 클러스터 다른 스키마 결정
- [[entity-data-warehouse]] — 이 패턴으로 구축되는 저장소
- [[concept-monday-column-value-modeling]] — Bronze→Silver의 반정형 처리
