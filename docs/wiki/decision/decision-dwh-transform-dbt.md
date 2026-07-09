---
type: decision
title: DWH 변환·오케스트레이션 = dbt-postgres + cron-first
tags: [dwh, dbt, orchestration, cron, airflow, transform]
status: active
---

# DWH 변환·오케스트레이션 = dbt-postgres + cron-first

## 결정

**변환**: bronze → silver → gold 변환을 **dbt-core + dbt-postgres**로 구현. snapshots(SCD2)·incremental merge(SCD1/idempotent upsert)·generic tests·source freshness·`manifest.json` lineage를 단일 도구로 확보.

**오케스트레이션**: 초기(MVP)는 **cron + Python 스크립트(systemd timer)**. 태스크가 10+ 로 늘어나거나 cross-system 의존성이 복잡해지면 **Apache Airflow**로 이관(Dagster는 dbt 중심 시 대안). 초기부터 Airflow를 두지 않는다.

dbt 프로젝트 구조: `staging/`(bronze→정제) → `intermediate/`(조인·정규화) → `marts/core/`(silver dim/fact) → `marts/business/`(gold 마트) + `snapshots/`(SCD2) + `sources.yml`(bronze·control plane 외부 소스) + `schema.yml`(테스트 선언).

## 근거

- **dbt가 PG에서 성숙** — `dbt-postgres`는 first-party maintained adapter. `append`·`merge`·`delete+insert`·`insert_overwrite` incremental 전략 지원. PG 15+ `MERGE`로 idempotent upsert 깔끔.
- **선언적 테스트·lineage를 단일 도구로** — `unique`/`not_null`/`accepted_values`/`relationships` generic tests + `source freshness` SLA + `manifest.json`/`run_results.json` lineage. 별도 관측성 도구 도입 최소화.
- **SCD2 표준 구현** — dbt 공식 권장: SCD2는 snapshots, SCD1은 merge, 같은 모델에서 섞지 말 것. snapshots가 `dbt_valid_from`/`dbt_valid_to`/`dbt_is_current` 자동 부여.
- **cron-first가 초기에 충분** — 소스 2개·DAG 깊이 얕음·일 배치 SLA. systemd timer/cron + Python 스크립트로 추출·변환·마트 적재를 묶어 실행. Airflow의 스케줄러·웹서버·DB 운영 오버헤드가 초기에 과잉.
- **점진적 확장 경로** — cron + Python → Airflow(TaskFlow API)로 태스크 수·의존성 복잡도에 따라 이관. dbt 모델은 그대로 두고 orchestration 층만 교체.
- **이미 쓰는 언어·인프라 활용** — wiki_pipeline이 Python/FastAPI. Monday 추출기·webhook 수신기도 Python으로 일관. 별도 언어·런타임 도입 없음.

## 기각 대안

- **순수 SQL 스크립트 + psql cron** — 가장 단순하나 테스트·lineage·신선도·증분 전략 추상화가 없어 유지보수 부담. dbt의 선언적 접근이 장기적으로 더 생산적.
- **데이터프레임(Pandas/Polars/DuckDB)** — Python 친화적이나 변환 로직이 코드에 묻혀 선언적 테스트·문서화·lineage 부족. ELT의 T를 코드로 관리하면 버전·검증·협업이 어려움.
- **처음부터 Airflow** — 스케줄러·웹서버·메타DB 운영 오버헤드. 초기 DAG 수가 적어 학습·운영 비용이 가치를 초과. 태스크 10+ 시 이관이 합리적 시점.
- **Dagster/Prefect** — 자산 중심 lineage(Dagster)·Python 네이티브(Prefect) 장점. 그러나 dbt 중심 작업에는 dbt 자체 + 가벼운 orchestrator가 충분. Dagster는 dbt 통합이 잘 되지만 초기엔 추가 학습 비용.
- **Airbyte OSS Monday 커넥터 + dbt** — Monday 추출은 Airbyte로 위임 가능(검토 가치 있음). 그러나 plan tier의 activity log 보존 한계·webhook 실시간 근사 부재로 초기엔 커스텀 추출기가 더 제어 가능. Phase 5 후보.

## 관련

- [[decision-dwh-shape-kimball-medallion]] — dbt 모델이 layering을 실체화
- [[decision-dwh-scd-strategy]] — SCD2 snapshots / SCD1 merge 구현 도구
- [[decision-monday-ingest-hybrid]] — cron + Python이 야간 폴링·dbt 실행을 오케스트레이션
- [[decision-dwh-column-value-hybrid]] — type dispatch 변환이 dbt intermediate 모델로 구현
- [[entity-data-warehouse]] — _meta.dbt_invocations로 dbt 실행 이력 보존
