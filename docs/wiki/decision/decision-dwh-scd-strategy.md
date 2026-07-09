---
type: decision
title: DWH SCD 전략 = entity별 0/1/2/append 혼합
tags: [dwh, scd, kimball, dbt-snapshots, slowly-changing-dimension]
status: active
---

# DWH SCD 전략 = entity별 0/1/2/append 혼합

## 결정

DataWarehouse의 차원·팩트에 **엔티티 성격에 따라 다른 SCD(Slowly Changing Dimension) 타입**을 적용한다:

| 엔티티 | SCD 타입 | 이유 |
|---|---|---|
| Monday items(상태·담당자·그룹·마감일) | **SCD2**(dbt snapshot) | "3월에 완료된 item을 *그때* 담당자 기준으로" 같은 시점 보고에 이력 필요 |
| Monday users | **SCD2 + 현재값 컬럼**(사실상 SCD6) | 역할 변경·퇴사·팀 이동. 현재 이름과 이벤트 시점 이름 모두 필요 |
| Monday board 구조(board·group·column) | **SCD2** | 컬럼 추가/삭제/이름 변경 추적 |
| Monday tags·status labels | **SCD2** | 라벨 변경·추가 이력 |
| Monday statuses(현재값 차원) | **SCD1** | 현재 상태만 의미있는 용도는 overwrite |
| wiki_pipeline `dim_pipeline_source` | **SCD2** | schedule·themes 변화 추적 |
| wiki_pipeline `run` 기록 | **accumulating snapshot**(milestone 날짜 다수) + 주요 속성 일부 SCD2 | run 상태는 가변이나 메트릭은 fact |
| wiki_pipeline `run_step`·`run_event`·`run_doc`·토큰 사용량 | **append-only fact** | 한 번 기록되면 불변. step/run_event는 사실상 transaction fact |
| conformed `dim_date`·`dim_source_system` | **Type 0** | 재구축/lookup |

**구현**: SCD2는 **dbt snapshots**(`dbt_valid_from`/`dbt_valid_to`/`dbt_is_current` 자동 부여). SCD1은 dbt incremental **merge**(PG 15+ `MERGE` 전략). accumulating snapshot은 dbt incremental 모델로 milestone 날짜 갱신.

## 근거

- **"그때 그 시점" 보고 수요 존재** — "지난 분기 완료 item을 당시 담당자 팀 기준으로" 같은 질문은 SCD2 없이 불가능. Monday 과제 추적과 문서화 교차 분석에서 시점 정확성이 핵심 가치.
- **SCD2의 비용 관리** — 모든 차원을 SCD2로 하면 행 폭발·조인 복잡도. 변동이 드물거나 현재값만 의미있는 엔티티(statuses·dim_date)는 SCD1/Type 0으로 비용 절감.
- **fact는 append가 자연스럽다** — run_step·run_event·run_doc·토큰 사용량은 "한 번 일어난 사건"이라 불변. fact 테이블은 append-only가 가장 단순하고 정확.
- **accumulating snapshot으로 run lifecycle 추적** — run 하나가 pending→running→done 등 다수 milestone을 거침. 매 milestone마다 날짜 컬럼을 갱신하는 accumulating snapshot이 run 단위 분석(소요 시간·단계별 지연)에 적합.
- **dbt snapshot이 SCD2의 표준 구현** — dbt 공식 권장(snapshots로 SCD2, merge로 SCD1, 같은 모델에서 섞지 말 것). PG 15+ `MERGE`가 idempotent upsert를 깔끔하게 지원.

## 기각 대안

- **모든 차원 SCD2** — 이력 정확도는 최상이나 행 폭발·조인 비용·운영 복잡도. 변동 드문 차원(dim_date·dim_source_system)까지 SCD2는 비효율.
- **모든 차원 SCD1 (overwrite)** — 가장 단순하나 시점 보고 불가. "그때 담당자" 질문에 못 답함.
- **Data Vault 2.0 스타일 satellite historization** — entity별 source satellite로 완전 이력. 강력하나 hub/link/satellite 조인 비용·복잡도. 차원 모델 + dbt snapshot이 같은 효과를 더 단순하게.
- **순수 Type 6(모든 SCD2 차원에 현재값 컬럼)** — "현재 이름으로 group by, 과거 값으로 filter"를 동시에. 강력하나 모든 차원에 적용하면 write 비용·드리프트. 핵심인 `dim_user`에만 적용(사실상 SCD6).

## 관련

- [[decision-dwh-shape-kimball-medallion]] — SCD가 적용되는 차원 모델의 전체 형태
- [[decision-dwh-transform-dbt]] — SCD2는 dbt snapshot, SCD1은 dbt merge로 구현
- [[concept-monday-column-value-modeling]] — column value의 SCD2 (item_sk, column_id, version)
- [[concept-readonly-saas-cdc]] — lifecycle fact의 원천(activity log)
- [[entity-data-warehouse]] — 이 전략이 적용되는 차원·팩트 목록
