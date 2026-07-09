---
type: decision
title: DWH 저장소 = PostgreSQL 단일 클러스터, 다른 스키마
tags: [dwh, postgresql, storage, single-cluster, schema-isolation]
status: active
---

# DWH 저장소 = PostgreSQL 단일 클러스터, 다른 스키마

## 결정

DataWarehouse를 wiki_pipeline control plane과 **같은 PostgreSQL 클러스터의 다른 스키마**(초기)에 둔다. `bronze`·`silver`·`gold`·`_meta` 4개 스키마로 분리하고, 역할 기반 접근 제어(`etl_writer`·`analytics_reader`)로 운영/분석 부하를 격리한다. 트래픽이 커지면 읽기 복제본(read replica)으로 분석 트래픽을 이관한다.

## 근거

- **이미 PG를 운영 중** — wiki_pipeline control plane이 PostgreSQL을 쓰고 있어 별도 DB 제품 도입 비용이 0. 동일 스택의 운영·백업·모니터링·인증 인프라 재사용.
- **PG 15+ 기능 충분** — `MERGE` upsert, 선언적 파티셔닝, JSONB + GIN, materialized view, logical replication, RLS, FDW 등 DWH에 필요한 기능이 내장.
- **control plane과의 직접 연결 용이** — wiki_pipeline 테이블(runs·run_events·run_doc_outputs 등)을 같은 클러스터의 다른 스키마에서 `dbt source` 또는 `postgres_fdw`로 직접 읽을 수 있어, 별도 추출 레이어 없이 ELT가 가능.
- **스키마 격리로 부하 분리 충분** — 같은 DB 다른 스키마는 트랜잭션 경계를 공유하지만, 역할 기반 권한·커넥션 풀 분리·쿼리 우선순위로 운영 쓰기와 분석 읽기 경합을 통제 가능. 초기 볼륨(items 수만~십만, run 일일 수백)에서는 단일 인스턴스로 충분.
- **점진적 확장 경로** — 같은 스키마 → 다른 DB(`postgres_fdw`/logical replication) → 읽기 복제본 → 별도 클러스터로, 트래픽 신호에 따라 한 단계씩 이관. 초기부터 분리하면 불필요한 운영 비용.

## 기각 대안

- **별도 PG 클러스터 (처음부터)** — 운영/분석 완전 격리는 장점이나, 초기 볼륨에서 인프라·백업·복제 설정 비용이 과잉. 읽기 보제본으로 같은 효과를 더 낮은 비용에 달성 가능.
- **클라우드 DW (Snowflake/BigQuery/Redshift)** — 확장성·분리 컴퓨트·서버리스 장점. 그러나 사내 VM 온프렘 인프라·PG 기존 투자·데이터 이동 비용·네트워크(클라우드 아웃바운드) 한계를 고려하면 오버스펙. 특히 사내 GitLab 네트워크 정책상 클라우드 아웃바운드가 이미 blocker 후보([[question-cloud-scm-network]] 참조).
- **같은 스키마에 테이블만 추가 (스키마 분리 없음)** — 가장 단순하나, DWH 테이블과 운영 테이블이 뒤섞여 권한 관리·백업 단위·네임스페이스가 불명확. layering discipline을 잃음.
- **MongoDB·Elasticsearch·ClickHouse** — 각각 장점이 있으나 이미 쓰는 PG 한 개로 충분한 상황에서 새 저장소 기술 도입은 운영 부담만 증가.

## 관련

- [[decision-dwh-shape-kimball-medallion]] — 이 저장소에 실체화할 전체 형태
- [[concept-medallion-dwh-on-postgres]] — 스키마 4개 분리의 개념적 근거
- [[entity-data-warehouse]] — 이 결정으로 구체화되는 시스템
- [[question-dwh-data-volume]] — 볼륨이 파티셔닝·읽기 복제본 이관 시점을 결정
- [[question-dwh-multi-tenancy]] — 다부서 확장 시 RLS 도입 조건
