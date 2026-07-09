---
type: decision
title: Monday column value 처리 = typed long table + JSONB 폴백 하이브리드
tags: [dwh, monday-com, semi-structured, jsonb, etl, hybrid-modeling]
status: active
---

# Monday column value 처리 = typed long table + JSONB 폴백 하이브리드

## 결정

Monday.com의 이질적인 column value(JSON string, 타입별 shape 상이)를 DWH에서 **하이브리드 3층 구조**로 모델링한다:

1. **Bronze** — `column_values_jsonb`에 원본 JSONB 그대로 보존(스키마 드리프트 생존·재생).
2. **Silver** — `fact_item_column_value`(long table)에 `(item_sk, column_id, version)` 단위로 explode. type dispatch로 typed 값 추출: `value_status_label_sk`(status)·`value_date`/`value_time`(date)·`value_user_sks[]`(people)·`value_numeric`(numbers)·`value_text`(text/formula display_value)·`value_linked_item_ids[]`(board_relation/dependency)·`value_tag_sks[]`(tags). mirror/미지원 타입은 폴백.
3. **모든 row는 `value_jsonb` 폴백 컬럼 보유** — typed 추출과 무관하게 원본 보존. `CREATE INDEX ... USING GIN (value_jsonb jsonb_path_ops)`로 포함 질의(`@>`) 최적화.

보조로 **`dim_status_label`((board, column, label_index, label) 사전)** 차원을 둬 status 값을 의미있게 조인(status label set이 보드별로 상이).

## 근거

- **스키마 드리프트 대응** — Monday 보드에 새 컬럼 추가·타입 변경이 잦음. pure exploded는 매번 DDL 변경을 요구해 운영 부담. JSONB 폴백이 새 타입을 잃지 않음.
- **쿼리 인체공학** — BI 도구가 "status='Done'인 item 수"를 물을 때 JSONB path 쿼리보다 typed 칼럼 조인이 훨씬 자연스럽고 성능 예측 가능.
- **PG 특화 이점 활용** — JSONB + GIN 인덱스가 포함 질의에 최적. Snowflake VARIANT·BigQuery JSON과 다른 PG 고유 최적화.
- **재생 안전** — typed 추출 로직이 틀려도 bronze의 JSONB에서 언제든 다시 추출 가능.
- **미래 대비** — 새 column type이 나와도 폴백이 잃지 않고, 자주 쓰이면 typed 필드를 추가하는 점진적 개선 경로.

## 기각 대안

- **JSONB 통째만** — 스키마 드리프트 생존은 장점이나, 효율적 쿼리가 어려움. 모든 분석 쿼리가 path 전개를 강요. 인덱스 없으면 느리고, 있어도 typed 조인보다 복잡.
- **pure exploded typed 칼럼** — 빠른 분석 쿼리. 그러나 보드 추가·컬럼 타입 변경 시마다 DDL 변경 필요. 운영 부담 크고 스키마 드리프트에 취약.
- **EAV(entity-attribute-value)** — `(item_id, column_id, value_variant)` 제네릭. 그러나 쿼리 성능 최악, 타입 안전성 상실, 집계 어려움. 관계형 안티패턴으로 통함.
- **타입별 side 테이블 (mirror·status·date·… 각각)** — 타입 안전 + JSONB 폴백 양립. 그러나 테이블 수 폭발로 운영·조인 복잡도 증가. long table이 단일 테이블로 같은 효과를 더 단순하게 달성.

## 관련

- [[concept-monday-column-value-modeling]] — 이 패턴의 일반화·type dispatch 표
- [[entity-monday-com]] — column value의 원천·주의점(date 타임존·status index vs id·mirror 서버 필터 불가·BatteryValue 등)
- [[decision-dwh-shape-kimball-medallion]] — long table이 silver 계층의 fact로 들어감
- [[decision-dwh-scd-strategy]] — (item_sk, column_id)별 SCD2 버전 이력
- [[concept-medallion-dwh-on-postgres]] — Bronze JSONB 보존 → Silver typed 정규화의 계층 적용
