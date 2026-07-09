# DataWarehouse 설계 논의 (2026-07-09)

> Monday.com(read-only API Key) + wiki_pipeline 산출물을 하나의 DataWarehouse로 통합하기 위한 설계 논의.
> 사용자 요청: "어떤 식으로 설계하는지 상세하게 계획을 진행해봐". 이 원본은 질문과 그에 대한 설계 답변을 그대로 보존한다 (raw 불변).

## 사용자 요청

> ETL 파이프라인으로 mondays API Key가 있어서 이를 사용해서 readonly 권한으로만 해서 DataWareHouse를 구축하려고합니다. 우리가 만드는 테스트/메뉴얼 생성 파이프라인도 이 DataWareHouse에 들어가게 되는데 DataWareHouse는 보통 어떤식으로 설계하는지 상세하게 계획을 진행해봐

## 조사 배경

이 설계는 두 갈래 사전 조사에 근거한다 (librarian 병렬 수행):

1. **Monday.com API 데이터 모델 조사** — GraphQL 전용(`api.monday.com/v2`), API-Version 헤더 분기(2026-04 current / 2026-07 RC), 복잡도·분·동시성·일일·IP 6종 독립 rate limit, 컬럼 타입별 column value JSON shape 상이, webhook은 30분 재시도만 보장, activity log은 plan tier 보존기간 한계, personal 토큰은 읽기 전용 강제 불가(UI 권한=토큰 권한, OAuth read scope만이 유일한 읽기 전용 강제 수단).
2. **DWH 설계 패턴 결정 공간 조사** — Kimball 차원 모델링 / Inmon / Data Vault 2.0 / Lakehouse(medallion), SCD Type 0~6, loading 전략(full/incremental/snapshot/CDC), conformed dimension, dbt-postgres, Airbyte Monday 커넥터(activity-log 기반 incremental + plan tier 보존 한계 주의), PostgreSQL 15+ MERGE, JSONB + GIN 인덱스, 읽기 복제본/RLS.

또한 wiki_pipeline control plane 데이터 모델(`backend/controlplane/models.py`)을 직접 확인해 source 2 모델링의 근거로 삼았다 — runs·run_events·run_model_usage·run_doc_outputs·run_quality_*·run_evidence_*·run_artifacts·run_coverage_reports 등.

## 설계 답변 — DataWarehouse 설계 계획

### TL;DR — 핵심 결정

| 항목 | 결정 | 한 줄 근거 |
|---|---|---|
| 전체 형태 | Kimball 차원 모델링 + Medallion(Bronze/Silver/Gold) 스키마 분리 | 소스 2개, BI 지향, 복수 소스 통합 → 차원 모델이 가장 가볍고 명확 |
| 저장소 | PostgreSQL 15+ (단일 인스턴스, 3개 스키마) | 이미 control plane이 PG. Inmon/Data Vault/Lakehouse는 오버스펙 |
| 적재 | Monday: webhook(실시간) + 야간 전수 조정(reconcile) / 우리 파이프라인: 직접 읽기(direct read) 또는 logical replication | Monday webhook은 30분 재시도만 보장 → 결국 폴링 보강 필요 |
| 변환 | dbt-postgres (snapshots로 SCD2, merge로 SCD1) | PG 15+ MERGE 지원, 선언적 테스트/신선도/lineage 확보 |
| 오케스트레이션 | cron + Python (MVP) → Airflow (10+ 태스크 시) | DAG 깊이가 얕고 소스가 2개 → 초기엔 systemd timer/cron으로 충분 |
| 반정형 처리 | Hybrid: 타입별 칼럼 + fact_item_column_value long table + JSONB 폴백 + GIN(jsonb_path_ops) | Monday column value는 타입별로 JSON shape가 다름 |
| SCD | items/users/boards = SCD2(dbt snapshot) / statuses = SCD1 / run·step = append-only fact | "그때 그 시점의 상태" 보존 필요 |
| 접근 제어 | etl_writer / analytics_reader 역할 분리, 스트리밍 복제 읽기 복제본(트래픽 격리), 다부서 시 RLS | ETL 쓰기와 분석 읽기 분리는 PG 표준 패턴 |

### 배경 · 목표 · 범위

**목표**: Monday.com의 과제/작업 데이터와 wiki_pipeline이 생성하는 문서·실행 이력을 하나의 분석용 저장소로 통합해 아래 질문에 답하게 한다.
- "이 과제(item)의 진행 상태 ↔ 그 과제에서 나온 문서/매뉴얼의 생성 이력·품질·비용" 교차 분석
- "팀별/담당자별 과제 처리량 ↔ 문서화 자동화 적용률·성공률"
- "파이프라인 run의 성공/실패·토큰 비용·소요 시간 추이"
- Monday 보드 구조 변화 이력 추적

**범위 안**: Monday.com(boards/items/subitems/groups/columns/users/teams/tags/updates/assets 메타/activity_logs), wiki_pipeline control plane(sources/runs/run_events 요약/run_model_usage/run_doc_outputs/run_quality_*/run_evidence_*/run_artifacts/run_coverage_reports/source_release_tags).

**범위 밖**: Monday.com 쓰기 금지(readonly 정책), Workdoc 블록 내용 전문(webhook 없음·ROI 낮음), automation recipe(API 미지원), 파일 바이너리 영구 보관(public_url 1시간 한계 → 메타만).

**핵심 가정**(사용자 확인 필요): Monday plan tier의 activity log 보존기간 ≥ 새벽 동기화 주기, Monday 사용자 ≒ wiki_pipeline 사용자(같은 사내 SSO) → dim_user 단일 통합 가능, 볼륨 items 수만~십만/run 일일 수백 건, 지연 목표 일 배치, PG 15+.

### 아키텍처 — 전체 그림

흐름: Monday.com(webhook + 야간 전수 폴링) + wiki_pipeline control plane(direct read) → ETL(webhook 수신기·Python 추출기·cron+Python 오케스트레이션·dbt 변환) → PostgreSQL DWH(bronze/silver/gold/_meta 4 스키마) → 소비(BI 도구·analytics_reader 역할).

핵심 설계 원리:
- **Medallion layering**: bronze(원본 불변) → silver(정제·통합) → gold(차원 모델·마트). lakehouse storage는 아니고 PG 스키마 3개로 이름만 빌린 것 — layering discipline만 채택.
- **Control Plane과 DWH 분리**: wiki_pipeline의 PG를 그대로 DWH로 쓰지 않는다 — 운영/분석 부하 분리, "원본(source of truth)"과 "파생(warehouse)" 구분 위해 별도 스키마/DB에 복제.
- **Monday webhook + nightly reconcile**: webhook은 30분 재시도만 보장하고 유실 가능 → 야간 전수 폴링이 진실의 보정 계층.

### 데이터 모델 — 3계층 스키마

**Bronze(원본 거울 — append/upsert, 변환 없음)** — PSA(Persistent Staging Area) 역할. 모든 테이블에 extracted_at·extraction_batch_id 추가, PK 외 값 변환 금지, _raw 접미사, 무기한 보존. 테이블: monday_boards_raw·monday_groups_raw·monday_columns_raw·monday_items_raw·monday_subitems_raw·monday_users_raw·monday_teams_raw·monday_tags_raw·monday_updates_raw·monday_assets_raw·monday_activity_logs_raw(17자리 Unix nanos 변환 주의)·monday_webhook_events_raw(idempotency=event_id)·pipeline_runs_raw·pipeline_run_events_raw(30일 보존 한계 인지)·pipeline_run_model_usage_raw·pipeline_doc_outputs_raw·pipeline_quality_*.raw·pipeline_sources_raw·pipeline_release_tags_raw.

**Silver(정제·통합·SCD 이력)**:
- Conformed dims: dim_user(Monday+pipeline 통합, SCD2+현재값=사실상 SCD6)·dim_date(Type 0)·dim_source_system(Type 0, monday|pipeline_static|pipeline_manual)·dim_team(SCD2)
- Monday dims: dim_board·dim_group·dim_column·dim_tag·dim_status_label((board,column,label_index,label) — status 라벨 사전) — 전부 SCD2
- Monday facts: fact_item(item × 상태스냅샷, accumulating snapshot 스타일)·fact_item_column_value((item_sk,column_id,version) long format, typed 추출+JSONB 폴백)·fact_item_lifecycle(activity log 기반 상태 변환 이벤트, transaction fact)·fact_update·fact_asset
- pipeline facts: fact_run(run 1건, accumulating snapshot, milestone 날짜 다수)·fact_run_step(run×step, transaction fact)·fact_run_model_usage·fact_run_doc·fact_run_quality_finding·fact_run_evidence·fact_run_artifact·fact_run_coverage·dim_pipeline_source(SCD2)
- 교차 팩트: fact_item_documentation(Monday item ↔ pipeline source/run/doc 브릿지) — 이 DWH의 핵심 가치. 조인 키 = repo 경로 또는 명시적 매핑 테이블.

**Gold(프레젠테이션·마트)**: mart_item_current·mart_item_history·mart_run_summary·mart_run_step_detail·mart_doc_summary·mart_cross_item_documentation(핵심 마트)·mart_kpi_overview(materialized view)·mart_cost_by_source.

**_meta(ETL 운영 메타)**: etl_runs·etl_watermarks·etl_table_stats·schema_drift_log·dbt_invocations.

### 반정형 데이터 처리 — Monday column values

모든 column value는 JSON string이고 타입별로 shape가 다름. 처리 파이프라인: bronze.column_values_jsonb → explode(row per item×column) → type dispatch(status→label_sk / date→date·time·changed_at / people→user_sks[] / numbers→numeric / text→text / board_relation→linked_item_ids[] / tags→tag_sks[] / mirror→JSONB 폴백[서버 필터 불가] / formula→display_value만 / dependency→linked_item_ids[] / 기타→JSONB) → silver.fact_item_column_value(항상 value_jsonb 폴백 보존).

주의점: date/time이 호출자(토큰 소유자) 타임존 기준(raw value.time은 UTC), status index vs label id 혼동(id와 index가 다름), mirror/formula는 서버 필터 불가, connect boards/subitems은 text/value가 항상 null(linked_item_ids로만), multi-level board의 status는 BatteryValue(StatusValue 아님), JSONB 인덱스는 GIN(jsonb_path_ops).

### ETL 파이프라인 설계

**Monday 적재 — 하이브리드(webhook + nightly reconcile)**: webhook 단독은 위험(30분 재시도만), 폴링만은 지연. webhook을 실시간 근사치로, nightly 전수 폴링을 진실 보정계층으로. webhook 수신기(FastAPI)는 event_id idempotency로 bronze에 적재만, 즉시 200 응답(Monday는 지연 응답에 민감). 변환은 dbt silver에서. 야간 02:00 KST 전수 폴링(items_page cursor 500/page, 보드/그룹/컬럼/유저/팀/태그 전수 refresh, updates/activity_logs는 from_date increment). 보정: webhook이 놓친 item을 nightly 폴링이 반영, state: deleted/archived는 soft delete, activity log 기반 lifecycle 복원.

**wiki_pipeline 추출 — direct read**: 같은 PG 클러스터에 DWH를 두면 가장 단순(dbt source 또는 postgres_fdw). 매 시간/일 control plane 신규 run/event를 silver로 변환 적재. 초기엔 같은 클러스터 다른 스키마 + analytics_reader 역할로 읽기 격리, 트래픽 커지면 읽기 복제본으로 이관.

**변환 — dbt 프로젝트**: staging(bronze→정제) / intermediate(조인·정규화) / marts/core(silver dim/fact) / marts/business(gold 마트). snapshots로 SCD2(dim_user·dim_board·dim_column·dim_tag·dim_pipeline_source), incremental merge로 SCD1+idempotent upsert(PG 15+ MERGE), generic tests(*_sk not_null+unique, relationships, accepted_values), source freshness SLA.

**삭제 감지**: Monday는 state: deleted/archived 노출하므로 비교적 쉬움 — nightly 폴맨스에서 state 변화 감지→soft delete, 한 번도 폴링에 안 나타난 item은 PG MERGE WHEN NOT MATCHED BY SOURCE로 비활성 마킹.

### 기술 스택

저장소 PostgreSQL 15+(사내 VM) / 추출 Monday는 Python 커스텀(httpx+GraphQL, cursor 페이지네이션, 대안 Airbyte OSS Monday 커넥터) / pipeline은 postgres_fdw 또는 dbt source(direct), 대안 logical replication / 변환 dbt-core+dbt-postgres / 오케스트레이션 cron+Python(MVP)→Airflow(10+ 태스크) / webhook 수신 FastAPI / 관측성 dbt artifacts+_meta 테이블+PG log / BI Metabase 또는 Apache Superset / 비밀 control plane Fernet SecretBox 패턴 재사용.

### 보안 · 접근 제어

역할 분리: etl_writer(bronze/silver/gold/_meta 소유, DDL+DML) / analytics_reader(gold SELECT only) / dbt_runner=etl_writer / bi_reader=analytics_reader. Monday 토큰 정책: 권장 OAuth 앱 read scope만 요청, 차선 personal V2 토큰이되 전용 서비스 계정 UI 권한 읽기 전용 세팅(personal 토큰은 scope 축소 불가). 비밀은 control plane SecretBox(Fernet) 암호화 저장. 네트워크: PG sslmode=verify-full, Monday API 사내 아웃바운드 프록시 경유, webhook 수신 mTLS 또는 Monday JWT 서명 검증(OAuth 앱 시). 다부서 확장 시 _meta.tenant + PG RLS — 초기엔 불필요.

### 관측성 · 데이터 품질

ETL 실행 메타(_meta.etl_runs 매 batch), 신선도 SLA(dbt source freshness), 행 수 드리프트(_meta.etl_table_stats 전일 대비), 스키마 드리프트(Monday 컬럼 추가/삭제/타입 변경 감지→담당자 이메일, wiki_pipeline 이메일 알림 패턴 재사용), 데이터 품질 테스트(dbt generic tests+커스텀, 모든 *_sk not_null+unique, status enum accepted_values, 관계형 무결성), lineage(dbt manifest.json), Monday API 헬스(complexity/rate-limit 헤더 모니터링).

### 단계적 구현 로드맵

- **Phase 0 기반(1~2주)**: DWH용 PG DB/스키마 생성, 역할 생성, Monday OAuth 앱 등록 또는 서비스 계정 세팅(read-only 검증), API 연결 테스트(visible boards/items 추출 가능 여부·private board 접근 범위 점검), control plane PG 접근 경로 확정, 열린 질문 해소
- **Phase 1 Monday 단방향 MVP(2~3주)**: Python 추출기, bronze 적재, dbt 셋업(staging+dim_user/dim_board/dim_item/fact_item), fact_item_column_value long table, gold.mart_item_current, _meta ETL 메타+watermark, nightly cron, Metabase/Superset 연결
- **Phase 2 wiki_pipeline 통합(2주)**: control plane→bronze 미러, silver.fact_run/fact_run_step/fact_run_model_usage/fact_run_doc, gold.mart_run_summary/mart_doc_summary, **silver.fact_item_documentation 브릿지 팩트**(Monday item↔pipeline source 매핑), gold.mart_cross_item_documentation(핵심 마트)
- **Phase 3 실시간 보강(1~2주)**: Monday webhook 수신기(FastAPI), webhook→bronze, silver webhook 처리 모델, activity log 기반 lifecycle 복원
- **Phase 4 품질·관측성·SCD 강화(지속)**: dbt snapshots SCD2 전면, 품질 테스트 커버리지, schema drift 감지+알림, 비용 환산(KRW), 필요시 읽기 복제본
- **Phase 5 확장(필요 시)**: Airflow 도입, 다부서 RLS, TimescaleDB, 추가 소스(GitLab 이슈·Jira 등)

### 열린 질문 — 설계 확정 전 사용자 결정 필요

1. Monday plan tier와 activity log 보존기간(보존기간 < 동기화 주기면 full refresh 강제)
2. Monday 사용자와 wiki_pipeline 사용자가 같은 SSO인가(dim_user 단일 통합 가능 여부)
3. Monday 과제(item)와 wiki_pipeline 소스(repo)를 잇는 키(Monday 커스텀 컬럼에 repo 경로 있는지, 별도 매핑 테이블 운영 여부)
4. 예상 데이터 볼륨(Monday items 총 건수, 일일 run 수 — 분할/파티션 필요성)
5. 지연 목표(일 배치/시간 단위/실시간 — webhook·오케스트레이션 범위 결정)
6. 분석 소비자(BI 도구/파이썬 노트북/셀프서브 대시보드)
7. 감사/보존 요구사항(bronze 무기한 보존 필요 여부 — 금융/규제 산업)
8. PG 버전(15+면 MERGE, 미만이면 ON CONFLICT)
9. 다부서 확장 가능성(RLS 도입 시기)
10. BI 도구 확정(각 도구마다 PG/RLS/SSL 취급 상이)

### 핵심 의사결정 요약(결정 페이지 후보)

1. DWH 형태 = Kimball 차원 모델링 + Medallion 스키마(Inmon/Data Vault/Lakehouse 기각 — 소스 2개에 오버스펙)
2. Monday 적재 = webhook + nightly reconcile 하이브리드(webhook만/폴링만 기각 — 각각 유실/지연 위험)
3. 반정형 처리 = typed long table + JSONB 폴백 + GIN 인덱스(pure JSONB/pure exploded/EAV 기각)
4. SCD = items/boards/users SCD2 + statuses SCD1 + runs append-only
5. 저장소 = PostgreSQL 단일, 같은 클러스터 다른 스키마(별제 클러스터/클라우드 DW 기각 — 초기 오버스펙)
6. 변환 = dbt-postgres(raw SQL/데이터프레임 기각 — 선언적 테스트·lineage 부족)
7. 오케스트레이션 = cron+Python → Airflow(처음부터 Airflow 기각 — 초기 복잡도)
