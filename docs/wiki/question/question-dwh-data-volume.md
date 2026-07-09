---
type: question
title: DWH 예상 데이터 볼륨 (분할·복제본 이관 시점)
tags: [dwh, data-volume, partitioning, read-replica, dwh]
status: open
---

# DWH 예상 데이터 볼륨 (분할·복제본 이관 시점)

## 질문

Monday.com의 총 item 수와 wiki_pipeline의 일일 run 수가 **대략 어느 정도**인가?

## 맥락

볼륨이 [[decision-dwh-storage-postgres-single]]의 "같은 클러스터 다른 스키마" 전략이 유효한 범위인지, 아니면 읽기 복제본·파티셔닝으로 조기 이관해야 하는지를 결정한다.

가정(설계 계획): items 수만~십만 건, 일일 run 수백 건. 이 범위면:
- **단일 PG 인스턴스 충분** — 선언적 파티셔닝·materialized view 없이도 일반 인덱스·스케일업으로 커버.
- **run_step/run_event는 append-only라 시계열로 빠르게 증가** — run_events는 control plane이 30일 보존하지만, DWH bronze는 무기한 보존(PSA)이므로 장기 누적. 수년 운영 시 백만 건 단위 가능.

볼륨이 가정보다 크면(예: items 백만+ 또는 run 일일 수천):
- **run_event/run_step에 선언적 RANGE 파티셔닝(월별)** — PG 기능, 파티션 drop/detach로 bulk 관리 용이.
- **TimescaleDB hypertable** — 시계열 최적화. run lifecycle 분석에 적합.
- **읽기 복제본 조기 도입** — 운영/분석 부하 격리 가속.
- **bronze 보존 기간 재검토** — PSA 영구 보존 비용 vs 가치.

정확한 볼륨은 운영 데이터가 쌓여야 확정되므로, 초기엔 가정으로 진행하고 3~6개월 후 실측해 이관 조건을 재평가하는 것이 합리적.

## 답

<!-- answered로 전환 시: 대략 볼륨 + 파티셔닝/복제본 필요성 판정 + 관련 decision 링크 -->
