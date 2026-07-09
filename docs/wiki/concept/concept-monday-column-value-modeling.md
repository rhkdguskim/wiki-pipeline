---
type: concept
title: Monday column value 정규화 패턴 (반정형 → 정형 하이브리드)
tags: [dwh, monday-com, semi-structured, jsonb, etl, schema-drift]
status: active
---

# Monday column value 정규화 패턴 (반정형 → 정형 하이브리드)

## 정의

Monday.com의 Item은 **ColumnValues**라는 가변 속성 집합을 갖는다. 각 column value는 `id`·`type`·`text`(사람 읽기용 denormalized)·`value`(**JSON string**, 타입별 shape 상이) 필드로 구성된다. 핵심 어려움: **`value`가 column type마다 완전히 다른 JSON 구조**를 갖는다는 점.

타입별 JSON shape 예시:
- **status** — `{"index": 1}` (label id; index≠id 혼동 주의)
- **date** — `{"date": "2026-06-15", "time": "09:00:00", "changed_at": "..."}` (time은 UTC, text는 호출자 타임존)
- **people** — `{"personsAndTeams": [{"id": 48202303, "kind": "person"}], "changed_at": "..."}`
- **connect boards / subitems / mirror** — `text`·`value`가 **항상 null**, `linked_item_ids`/`linked_items`/`mirrored_items` 필드로만 접근
- **mirror/formula** — 서버 필터 불가, 전부 가져와 클라이언트 필터. formula는 `display_value`만 유효
- **multi-level board의 status** — `StatusValue`가 아니라 `BatteryValue` (`battery_value: [{key, count}]`)

이 이질성을 관계형 저장소로 정규화하는 4가지 패턴이 있고, 각각 명확한 단점이 있다:

| 패턴 | 장점 | 단점 |
|---|---|---|
| **JSONB 통째 보존** | 스키마 드리프트 생존 | 효율적 쿼리 어려움(인덱스 없으면) |
| **타입별 exploded 칼럼** | 빠른 분석 쿼리 | 보드 추가 시 DDL 필요, 드리프트에 취약 |
| **EAV(entity-attribute-value)** | 제네릭 | 쿼리 성능 최악, 타입 안전성 상실 |
| **타입별 side 테이블** | 타입 안전+JSONB 폴백 양립 | 테이블 폭발 |

## 왜 중요한가

- **스키마 드리프트 대응**: Monday 보드에 새 컬럼이 추가되거나 타입이 바뀌어도 ETL이 멈추지 않아야 한다. Pure exploded는 매번 DDL 변경을 요구해 운영 부담이 크다.
- **쿼리 인체공학**: BI 도구가 "status='Done'인 item 수"를 물을 때 JSONB path 쿼리보다 typed 칼럼 조인이 훨씬 자연스럽다.
- **원본 보존**: 어떤 패턴을 써도 원본 JSONB는 항상 폴백으로 남겨, 미지원 컬럼 타입·미래 필드를 잃지 않는다.
- **PG 특화 이점**: JSONB + GIN 인덱스(`jsonb_path_ops`)가 포함 질의(`@>`)에 최적. Snowflake VARIANT·BigQuery JSON과 다른 최적화 기 동작.

## 관계형 정규화 표준 패턴 (long table + 폴백)

```
bronze.monday_items_raw.column_values_jsonb  (JSONB 배열 그대로)
   │  explode → row per (item, column)
   ▼
type dispatch:
   status       → value_status_label_sk   (dim_status_label 조인)
   date         → value_date, value_time, value_changed_at
   people       → value_user_sks[]        (dim_user 조인)
   numbers      → value_numeric
   text/long_text → value_text
   board_relation → value_linked_item_ids[]  (fact_item 자기참조)
   tags         → value_tag_sks[]         (dim_tag 조인)
   mirror       → value_jsonb (폴백만)
   formula      → value_text (display_value만)
   dependency   → value_linked_item_ids[]
   기타/미지원   → value_jsonb (원본 보존)
   ▼
silver.fact_item_column_value (item_sk, column_id, version)
   - 항상 value_jsonb 폴백 컬럼 보유
   - CREATE INDEX ... USING GIN (value_jsonb jsonb_path_ops)
   - SCD2: (item_sk, column_id)별 effective_from/effective_to/is_current
```

`dim_status_label`((board, column, label_index, label) 사전)이 status 값을 의미있게 조인하기 위한 핵심 보조 차원 — status label set이 보드별로 다르므로 없으면 status 값을 해석할 수 없다.

## 관련

- [[decision-dwh-column-value-hybrid]] — 하이브리드 패턴 채택 결정
- [[entity-monday-com]] — column value의 원천
- [[concept-medallion-dwh-on-postgres]] — Bronze(JSONB 보존) → Silver(typed 정규화) 계층 적용
- [[decision-dwh-scd-strategy]] — column value 버전 이력
