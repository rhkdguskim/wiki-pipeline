---
type: decision
title: Monday.com 적재 = webhook(실시간 근사) + 야간 전수 폴링(보정) 하이브리드
tags: [dwh, monday-com, etl, cdc, webhook, polling, hybrid]
status: active
---

# Monday.com 적재 = webhook(실시간 근사) + 야간 전수 폴링(보정) 하이브리드

## 결정

Monday.com 데이터를 DWH로 적재할 때 **두 레인을 병렬 운영**한다.

1. **Webhook 레인(실시간 근사)** — Monday webhook 이벤트를 FastAPI endpoint가 받아 `bronze.monday_webhook_events_raw`에 `event_id` 기반 idempotent upsert. 변환 없이 원본만 보존, 즉시 200 응답(Monday는 지연 응답에 민감). dbt가 주기적으로 이벤트를 silver로 변환.
2. **야간 전수 폴링 레인(진실 보정)** — 매일 02:00 KST에 Monday GraphQL API를 `items_page` cursor(500/page)로 전수 순회, boards/groups/columns/users/teams/tags는 전수 refresh, updates/activity_logs는 `from_date` 증분. 결과를 같은 bronze 원본 테이블에 upsert(`extracted_at`·`extraction_batch_id` 추가).
3. **보정(reconcile)** — silver에서 webhook이 놓친 변경을 nightly 폴링이 발견하면 반영. `state: deleted/archived`는 soft delete. PG 15+ `MERGE WHEN NOT MATCHED BY SOURCE`로 사라진 row 비활성 마킹. activity log 기반 lifecycle 복원.

## 근거

- **webhook 재시도 한계** — Monday 문서가 webhook 신뢰성 한계를 명시적 인정(1분 간격 30회 재시도 = 30분만 보장). 단독 사용은 조용한 데이터 유실 위험. webhook은 근실시간 근사치로만 취급.
- **폴링만의 단점** — 일 배치 지연 + API 호출 비용·rate limit 소모. 단독 사용은 "오늘 데이터를 내일 봄"의 UX 저하.
- **하이브리드로 상호 보완** — webhook으로 즉시성을, nightly 폴링으로 정확성을. 두 레인이 같은 이벤트를 중복 전달할 수 있으므로 `event_id`/`(item_id, updated_at)` 기반 idempotent upsert가 필수.
- **PSA와 결합해 재생 가능** — bronze가 원본을 불변 보존하므로, 보정 로직이 틀려도 언제든 재생.
- **Monday activity log의 활용** — item 생성/이동/상태변환/삭제 이벤트를 activity log가 제공. nightly 폴맨스와 조합해 lifecycle fact 복원의 신뢰할 수 있는 근거.

## 기각 대안

- **webhook만** — 30분 재시도만 보장. 워크플로우에서 잦은 변경·대량 이벤트 시 유실 위험. 단독 사용은 위험.
- **전수 폴링만** — 일 배치 지연. Monday plan tier의 activity log 보존 한계 내에서는 증분도 안전하지만, "오늘 진행 상황"을 오늘 볼 수 없어 분석 가치 저하. API 호출량·rate limit 소모도 큼.
- **Airbyte OSS Monday 커넥터 단독** — activity log 기반 incremental로 잘 동작하지만, *plan tier의 activity log 보존 기간 < 동기화 주기*면 일부 변경 누락 경고(Airbyte 문서 명시). 또한 webhook 실시간 근사치가 없어 지연이 큼. 검토 가치는 있으나(Phase 5 후보), 초기는 제어 가능한 커스텀 추출기가 단순.
- **read 전용 API polling + logical replication 흉내** — Monday는 logical replication을 제공하지 않아 불가능.

## 관련

- [[concept-readonly-saas-cdc]] — 이 패턴의 일반화
- [[entity-monday-com]] — webhook 30분 재시도 한계의 원천
- [[decision-dwh-transform-dbt]] — webhook 이벤트·폴링 결과의 변환을 dbt로
- [[decision-dwh-scd-strategy]] — lifecycle 이력으로 SCD2 적용
- [[question-monday-plan-tier]] — activity log 보존 한계가 증분 폴링 안전성을 결정
- [[question-dwh-latency-target]] — webhook 필요성·야간 주기를 지연 목표가 결정
