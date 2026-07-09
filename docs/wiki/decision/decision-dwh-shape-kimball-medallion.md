---
type: decision
title: DWH 전체 형태 = Kimball 차원 모델링 + Medallion layering
tags: [dwh, kimball, medallion, dimensional-modeling, architecture]
status: active
---

# DWH 전체 형태 = Kimball 차원 모델링 + Medallion layering

## 결정

DataWarehouse의 전체 형태를 **Kimball 차원 모델링**(star schema + conformed dimension + bus matrix)으로 하고, 저장소 layering은 **Medallion(Bronze/Silver/Gold) 스키마 분리**로 한다. 둘은 직교하는 선택이다 — Kimball은 *데이터 모델*(어떻게 모델링할까), Medallion은 *계층 규칙*(어떻게 층을 나눌까).

## 근거

- **소스가 2개뿐** — Monday.com(외부 SaaS) + wiki_pipeline control plane(내부 PG). Inmon의 enterprise 3NF DW·Data Vault 2.0의 hub/link/satellite는 다수 소스·높은 스키마 변동 전제에서 가치가 있는데, 우리 규모에서는 오버엔지니어링이다.
- **분석 소비 = BI 지향** — Kimball star는 "적은 조인·단순 비즈니스 질문"에 최적. Inmon 정규형은 분석 쿼리마다 다수 조인이 필요해 BI에 불리.
- **Medallion은 substrate 무관** — 본래 lakehouse(Delta/Iceberg + 객체 저장소) 맥락이지만, 본질은 *계층화 규칙*이지 데이터 모델이 아니다. PostgreSQL 스키마 3개로 동일한 규칙을 실체화할 수 있다. lakehouse의 time-travel/ACID-on-files 저장소 기능은 PG에 해당하지 않지만 layering discipline은 그대로 유효.
- **재생(replay) 가능** — Bronze(PSA)가 원본을 불변 보존하므로 Silver/Gold 변환 로직을 바꿔도 재호출 없이 재생 가능. SaaS API rate limit·activity log 보존 한계를 회피.
- **이미 쓰는 PG 활용** — wiki_pipeline control plane이 이미 PostgreSQL. 별도 DW 제품(Snowflake/BigQuery/Redshift) 도입 없이 동일 스택으로 통합.
- **Kimball과 Medallion의 자연스러운 결합** — Gold 계층이 곧 Kimball presentation mart. Silver가 integration/conformed dimension 계층. Bronze가 staging/PSA. 두 패턴의 용어가 거의 1:1로 대응.

## 기각 대안

- **Inmon(CIF)** — 정규형 enterprise DW + 부서별 마트. 단일 진실 원천·확장성은 장점이나, 소스 2개에 top-down 설계 부담·느린 초기 납품. 우리 규모에서 과잉.
- **Data Vault 2.0** — Hub/Link/Satellite. 높은 소스 변동·감시 요건에 강하지만, satellite마다 소스별 테이블·무거운 point-in-time 조인. 안정적 소스 2개에서는 복잡도만 증가.
- **Lakehouse(Databricks/Apache Iceberg on 객체 저장소)** — 저장소 경제성·분리 컴퓨트가 장점이나, 사내 VM·PG 기반 인프라에서 별도 lakehouse 도입은 운영 비용 증가. layering 규칙만 빌리고 저장소는 PG에 머무는 것이 합리적.
- **One Big Table(OBT, 단일 와이드 테이블)** — 조인이 필요 없으나 다중 마트에서 재구성이 안 되고 cardinality 폭발·쿼리 플래너 유연성 상실. 작은 규모에서도 star가 더 낫다.

## 관련

- [[concept-medallion-dwh-on-postgres]] — layering 개념의 PG 실체화
- [[decision-dwh-storage-postgres-single]] — 이 형태를 담을 저장소 결정
- [[decision-dwh-scd-strategy]] — 차원 모델의 SCD 전략
- [[decision-dwh-transform-dbt]] — 변환 도구로 Kimball 모델·Medallion layer를 dbt로 구현
- [[entity-data-warehouse]] — 이 결정으로 구축되는 시스템
- [[2026-07-09-dwh-design-plan]] — 설계 논의 원본
