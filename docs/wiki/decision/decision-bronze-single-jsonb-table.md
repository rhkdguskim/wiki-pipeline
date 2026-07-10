---
type: decision
title: bronze 저장 = 소스 구분 없는 단일 JSONB 테이블 (raw_records)
tags: [dwh, medallion, bronze, ingestion, connector, postgres, jsonb, schema]
status: active
---

# bronze 저장 = 소스 구분 없는 단일 JSONB 테이블 (raw_records)

## 결정

데이터 수집 커넥터가 `to_bronze`로 만든 bronze row를, **소스마다 전용 테이블을 파지 않고 단일 범용 테이블 하나**(`raw_records`)에 적재한다. 원본 payload는 **PostgreSQL JSONB 컬럼에 통째로 보존**하고, 소스 식별·증분·감사에 필요한 꼬리표만 별도 컬럼으로 둔다. Monday든 Jira든 Slack이든 같은 테이블에 쌓인다.

**재수집 정책 = append(추가), upsert 아님** — 같은 `external_id`를 매일 다시 받아도 기존 행을 덮어쓰지 않고 **새 행으로 쌓는다**. 단 직전 수집분과 `content_sha256`이 같으면(내용 무변경) **skip**한다. 그래서 bronze는 "매 수집 스냅샷의 append-only 로그"가 되고, 실제로는 **바뀐 item만** 새 행이 되어 무한정 커지지 않는다.

```
raw_records
  id              PK
  connector_kind  "monday" | "jira" | ...      -- 어떤 커넥터가 넣었나
  source_id       소스(SaaS 계정/보드 등) 식별
  external_id     소스측 원본 식별자(예: Monday item id)
  payload_jsonb   원본 JSON 통째 (변환 금지 — bronze=원본 거울)
  content_sha256  payload 해시 → 재수집 시 중복/변경 감지
  watermark       증분 커서(수정시각·id 등)
  ingested_at     우리 창고에 착륙한 시각
```

## 근거

- **소스 확장성이 이 아키텍처의 핵심** — [[concept-ingestion-connector]]의 가치는 "소스 추가 시 상위 코드 무변경". 소스별 전용 테이블(대안 A)은 소스마다 마이그레이션을 요구해 이 가치를 정면으로 깎는다. 단일 테이블은 **커넥터(어댑터)만 추가**하면 끝.
- **medallion 정석** — bronze는 원래 "스키마 없는 원본 착륙장"이고 변환은 금지다([[concept-medallion-dwh-on-postgres]]). 단일 JSONB 테이블이 이 층의 교과서적 형태다. 타입 강제·필드 추출은 silver의 일.
- **기존 코드 관례 재사용** (models.py 확인 2026-07-10):
  - `RunDocOutput.content_sha256`(String(64)) → bronze도 `content_sha256`으로 `(connector_kind, external_id, content_sha256)` 비교해 "이미 받은 레코드면 skip"하는 증분 수집.
  - `RunDocOutput.content_text`의 `deferred=True` 관례 → `payload_jsonb`도 리스트 조회 시 원본 통째를 안 읽도록 deferred 적용 검토.
- **JSONB라 쿼리 가능** — 원본을 통째 보존해도 PostgreSQL JSONB 연산자로 필요한 키를 뽑을 수 있어, silver 정제 전에도 조회가 막히지 않는다.
- **append가 SCD2와 맞물린다** — silver의 Monday items는 SCD2([[decision-dwh-scd-strategy]], dbt snapshot)로 "언제 무엇이 바뀌었나"를 추적한다. bronze가 매 수집 스냅샷을 append로 보존하면 그 변경 이력이 곧 dbt snapshot의 입력이 된다. upsert(대안)면 bronze엔 현재값만 남아 SCD2가 변경 근거를 잃고, 스케줄 실행 순간의 스냅샷 차이에만 의존하게 되어 취약하다. append는 medallion의 "bronze=append-only 원본 로그" 정의와도 일치.

## 기각한 대안

- **A. 소스별 전용 테이블**(`monday_items_bronze` …): 쿼리·타입 안정성은 좋으나 소스 추가마다 스키마 마이그레이션 필요 → 확장성 원칙 위반. 기각.
- **C. bronze 생략, 곧장 DocumentStore(md)**: 지금은 제일 단순하나 오늘 확정한 4층 아키텍처([[decision-ingestion-connector-architecture]])를 스스로 뒤엎고, 원본을 안 남겨 재수집·재정제가 불가. 기각.

## 이 결정의 위치 (기존 DWH 설계와의 정합)

- **저장 위치는 이미 정해져 있다** — [[decision-dwh-storage-postgres-single]]가 DWH를 control plane과 같은 PG 클러스터의 **`bronze`·`silver`·`gold`·`_meta` 4개 스키마**로 분리 확정. 따라서 `raw_records`는 controlplane `Base`가 아니라 **`bronze` 스키마**에 둔다(`etl_writer` 역할이 쓰고, `analytics_reader`가 읽음). 이 결정은 그 `bronze` 스키마 안의 **테이블 형태(단일 범용 vs 소스별)**만 확정한다.
- **silver/gold의 이력 정책은 별도로 이미 있다** — [[decision-dwh-scd-strategy]]가 Monday items를 **SCD2(dbt snapshot)**로 확정. 그건 정제 후 차원의 시점 이력이고, 이 결정(bronze 착륙)과 층이 다르다.

## 열린 항목 (구현 시 확정)

- **skip 판정 기준 `content_sha256`의 정규화** — 재수집분이 "내용 무변경"인지 판정하려면 Monday payload를 해시 전에 정규화(키 정렬·타임스탬프성 필드 제외 등)해야 오탐(매번 다르게 보임)이 없다. 무엇을 해시 대상에서 뺄지는 Monday column value shape([[concept-monday-column-value-modeling]]) 확인 후 구현 시 확정.
- **append 로그의 보존 기간/파티셔닝** — bronze가 커지면 `ingested_at` 기준 시간 파티셔닝·오래된 스냅샷 아카이빙을 검토([[decision-dwh-storage-postgres-single]]의 선언적 파티셔닝 활용).

## 관련

- [[decision-dwh-as-karpathy-llm-wiki]] — 이 append가 실체화하는 상위 저장 철학(① 원본 축적)
- [[concept-karpathy-llm-wiki-storage]] — raw 불변 축적 원칙의 개념
- [[decision-ingestion-connector-architecture]] — 이 bronze가 속한 4층 흐름
- [[concept-ingestion-connector]] — `to_bronze`를 선언한 포트
- [[concept-medallion-dwh-on-postgres]] — bronze/silver/gold 정의
- [[decision-dwh-storage-postgres-single]] — 이 테이블이 놓일 `bronze` 스키마(저장 위치)
- [[decision-dwh-scd-strategy]] — silver/gold의 SCD2 이력 정책(층이 다름)
- [[decision-document-identity-run-separation]] — 재수집 시 리비전 정책의 연결 고리
- [[entity-monday-com]] — 첫 구현체의 원천
