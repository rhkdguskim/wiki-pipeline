---
type: concept
title: Read-only SaaS CDC (webhook + nightly reconcile)
tags: [dwh, cdc, webhook, saas, etl, incremental, reconcile]
status: active
---

# Read-only SaaS CDC (webhook + nightly reconcile)

## 정의

**쓰기가 없는(read-only) SaaS 소스**에서 변경 데이터를 포착(CDC, Change Data Capture)하기 위한 패턴. 데이터베이스의 logical replication 같은 네이티브 CDC가 불가능하고, SaaS 제공자의 webhook도 **유실 가능성을 공식적으로 인정**하는 경우가 많아, **webhook(실시간 근사) + 야간 전수 폴링(진실 보정)**의 하이브리드가 정석이다.

## 작동 원리

**1. Webhook 레인(실시간 근사)**
- SaaS webhook 이벤트를 수신기(FastAPI endpoint)가 받아 **bronze의 원본 이벤트 테이블에 idempotency key(event_id)로 upsert**.
- 변환은 하지 않고 원본 보존만. 즉시 200 응답(SaaS는 지연 응답에 민감 — Monday는 webhook 재시도 정책이 1분 간격 30회=30분).
- silver/gold 변환은 dbt가 주기적으로 원본 이벤트 테이블에서 소비.

**2. Nightly 전수 폴링 레인(진실 보정)**
- 매일 정해진 시간(예: 02:00 KST, 트래픽 적은 시간)에 SaaS API를 cursor 기반으로 전수 순회.
- `watermarks` 테이블에 (소스, 테이블)별 high-watermark를 저장해 다음 실행의 시작점으로 사용.
- 전수 결과를 bronze의 같은 원본 테이블에 upsert(extracted_at·extraction_batch_id 추가).

**3. 보정(reconcile) 로직(silver에서)**
- webhook이 놓친 변경을 nightly 폴링이 발견하면 → 해당 fact/dim에 반영.
- `state: deleted/archived` 같은 소프트 삭제 플래그를 감지해 soft delete(`is_deleted=true`, `deleted_at`).
- 한 번도 폴링에 나타나지 않은 row는 PG 15+ `MERGE ... WHEN NOT MATCHED BY SOURCE`로 비활성 마킹.
- activity log 같은 감사 스트림이 있으면 누락된 lifecycle 이벤트 복원에 활용.

## 왜 중요한가

- **webhook만으로는 부족하다**: Monday 문서는 webhook 한계를 명시적으로 인정(재시도 30분만 보장). 다른 SaaS도 대부분 비슷. 단독 사용은 조용한 데이터 유실로 이어진다.
- **폴링만으로는 부족하다**: 지연이 커지고(일 배치), API 호출 비용·rate limit 한도 소모가 크다.
- **하이브리드가 양쪽 단점 보완**: webhook으로 근실시간 근사치를 제공하고, nightly 폴링이 진실의 보정 계층이 돼 유실을 복구. SLA는 "야간 1회 보정 후 정확"으로 선언 가능.
- **idempotency가 필수**: 두 레인이 같은 이벤트를 중복 전달할 수 있으므로, event_id(또는 (item_id, updated_at)) 기반 idempotent upsert가 없으면 더블 카운팅 발생.
- **PSA(원본 불변)와 결합**: bronze가 원본을 그대로 보존하므로, 보정 로직이 틀려도 언제든 재생 가능(→ [[concept-medallion-dwh-on-postgres]]).

## 전제 조건 및 한계

- **SaaS의 activity log 보존기간 ≥ 동기화 주기**여야 incremental 폴링이 안전. 보존기간이 짧으면 full refresh 강제. (Monday의 plan tier가 이 한계를 결정 → [[question-monday-plan-tier]])
- **삭제 감지는 근사**: SaaS가 삭제 이벤트를 webhook로 주지 않으면, "폴맨스에 안 나타남"으로만 추론 → "삭제" vs "일시적 비활성" 구분이 안 될 수 있다. soft delete 플래그로 보수적 처리.
- **activity log가 있으면 큰 도움**: Monday activity log는 item 생성/이동/상태변경/삭제 등을 이벤트로 제공해 lifecycle fact를 복원하는 근거가 됨.

## 관련

- [[decision-monday-ingest-hybrid]] — 이 패턴을 Monday에 적용한 결정
- [[entity-monday-com]] — webhook 30분 재시도 한계의 원천
- [[concept-medallion-dwh-on-postgres]] — bronze PSA가 재생 가능성의 기반
- [[decision-dwh-transform-dbt]] — 보정 로직을 dbt로 구현
