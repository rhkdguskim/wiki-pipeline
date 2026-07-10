---
type: entity
title: Monday.com (데이터 소스)
tags: [monday-com, saas, graphql, external-source, dwh]
status: active
---

# Monday.com (데이터 소스)

## 개요

사내에서 **과제·작업 관리**로 사용하는 SaaS 플랫폼. 본 위키의 DataWarehouse 설계에서 **데이터 소스 1**. API 키(read-only 의도)로 ETL 적재한다. GraphQL 전용 API(`https://api.monday.com/v2`)를 제공하며 API-Version 헤더로 분기한다(2026-04 current / 2026-07 RC). REST 표면은 없다.

**데이터 모델 핵심 엔티티**: Account → Workspace(Main workspace의 id는 null 취급) → Board(board_kind: private/public/share, hierarchy: classic/multi-level) → Group → Item(행) → Subitem(classic은 별도 숨겨진 보드, multi-level은 같은 보드). Item은 ColumnValues(컬럼 타입별 JSON shape 상이 → [[concept-monday-column-value-modeling]])를 갖는다. 부가: User/Team/Subscriber, Tag(계정 전역), Update(대화·스레드), Asset(파일, public_url 1시간 한계), Activity Log(board log vs user log 분리, board log created_at은 17자리 Unix nanos), Workdoc(문서, webhook 없음).

**인증·권한 모델**:
- **Personal V2 토큰** — UI 권한을 그대로 미러. **scope 축소 불가**(토큰=사용자). 읽기 전용 강제 불가.
- **OAuth 앱 토큰** — 설치 시점에 read scope만 요청하면 **읽기 전용 강제 가능**(`boards:read`·`users:read`·`teams:read`·`updates:read`·`assets:read`·`tags:read`·`webhooks:read`·`webhooks:write[구독용]`).

> **정정(2026-07-10)**: 사내에서 실제 발급받은 토큰은 **read/write 모두 가능한 API 토큰**이다. OAuth read-scope 재발급이 (현시점) 전제되지 않으므로, 읽기 전용을 **우리 코드(래퍼)에서 강제**한다 — `MondayReadOnlyClient`가 mutation을 차단하고 query만 전송 → [[decision-monday-readonly-client-wrapper]]. 위 "OAuth read scope만이 읽기 전용 강제 수단"은 여전히 참이나(권한적 강제), 우리 상황에선 코드적 강제가 실질 방어다. 출처: [[2026-07-10-dwh-monday-ingestion-refinements]].

**Rate limit 6종(독립)**: 복잡도(5M~10M points/min) · 분(Enterprise 5000/Pro 2500/Other 1000 RPM) · 동시성(250/100/40) · 일일(1000/10000/25000 soft) · IP(5000/10sec) · 자원 보호. 모든 호출(실패 포함)이 한도에 합산. `RateLimit-Policy`/`RateLimit` 헤더로 자가 조절.

**페이지네이션**: 보드 아이템은 `items_page(limit 최대 500)` + cursor(60분 만료)가 정석. 최상위 boards 쿼리는 page+limit. items 직접 쿼리는 100 ID 한계. updates는 루트 쿼리에서 from_date/to_date窗口.

**Webhook**: `change_column_value`·`change_status_column_value`·`create_item`·`create_subitem`·`item_archived/deleted/moved`·`create_update`·`edit_update` 등 20+ 이벤트. **재시도 정책 = 1분 간격 30회(30분)** — 유실 가능성을 공식 인정. 이 한계 때문에 webhook은 정확성을 담보 못 해, 지연 목표=일 배치 확정 후 **적재에서 webhook 레인은 삭제**됨(폴링 단일 레인 → [[decision-monday-ingest-polling-only]]). 재시도 한계 사실은 근실시간 요구 시 하이브리드 복귀의 전제로 [[concept-readonly-saas-cdc]]에 보존. Workdoc 변경 이벤트는 없다.

## 이 시스템에서의 역할

- **데이터 수집 커넥터의 첫 구현체** — `IngestionConnector` 포트([[concept-ingestion-connector]])의 첫 어댑터(`MondayConnector`). 이후 Jira·Slack 등이 같은 포트로 추가된다. 전체 흐름은 [[decision-ingestion-connector-architecture]].
- **DWH의 외부 데이터 소스 1** — read-only로 적재(토큰은 read/write지만 [[decision-monday-readonly-client-wrapper]]로 코드적 강제). 자세한 적재 전략은 [[decision-monday-ingest-polling-only]](폴링 단일 레인), 자동 수집은 [[decision-monday-collector-langgraph-scheduled]].
- **item ↔ wiki_pipeline source 연결**: 이 연결고리가 `fact_item_documentation` 브릿지 팩트의 핵심. 매핑 키는 [[question-monday-item-source-key]]에서 확정 예정.
- **사용자 통합**: Monday user와 wiki_pipeline 사용자가 같은 SSO인지 여부가 `dim_user` 단일 통합 가능성을 결정 → [[question-monday-user-mapping]].
- **plan tier 한계**: activity log 보존기간이 동기화 주기보다 짧으면 full refresh 강제 → [[question-monday-plan-tier]].

## 관련

- [[entity-data-warehouse]] — 이 데이터가 흘러들어가는 통합 저장소
- [[concept-readonly-saas-cdc]] — 읽기 전용 SaaS의 CDC 패턴
- [[concept-monday-column-value-modeling]] — 컬럼 값 정규화
- [[decision-monday-ingest-polling-only]] — 적재 전략(폴링 단일 레인, webhook 삭제)
- [[decision-monday-readonly-client-wrapper]] — 읽기 전용 강제(래퍼)
- [[decision-monday-collector-langgraph-scheduled]] — 스케줄러 + LangGraph 자동 수집
- [[concept-ingestion-connector]] — 이 엔티티가 첫 구현체인 수집 커넥터 포트
- [[decision-ingestion-connector-architecture]] — 수집 → DWH → 파이프라인 AI 쿼리 흐름
- [[2026-07-09-dwh-design-plan]] — 설계 논의 원본
- [[2026-07-10-dwh-monday-ingestion-refinements]] — 인증 정정·수집·저장소 논의
- [[2026-07-10-ingestion-connector-architecture]] — 수집 커넥터 아키텍처 논의
