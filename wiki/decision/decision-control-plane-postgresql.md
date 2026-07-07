---
type: decision
title: Control Plane DB = PostgreSQL
tags: [database, control-plane, postgresql, state]
status: active
---

# 결정: 관리 서버 DB를 PostgreSQL로 한다

[[decision-db-source-of-truth]]가 "서버 DB가 source of truth"임을 정했다면, 이 결정은 그 DB의 **엔진을
PostgreSQL로 확정**한다. POC의 SQLite(store.py 스키마)에서 이관한다.

## 근거 — 동시 쓰기·트랜잭션 요구

- **동시 쓰기 주체가 셋** — API 서버(소스 등록), 스케줄러(야간 배치의 sha 갱신), webhook 수신(러너 완료 보고)이
  동시에 DB에 쓴다([[decision-observability-event-contract]]의 webhook push · [[decision-schedule-per-source]]의 cron).
  SQLite의 단일 라이터 잠금으로는 이 동시성을 감당하기 어렵다.
- **트랜잭션** — sha 전진(MR 성공 후에만, [[concept-idempotent-sha]])과 run/run_items 이력 기록을 원자적으로 묶어야 한다.

## 기각 대안

- **SQLite 유지** (POC 상태) — 파일 하나로 단순하지만 위 **동시성 한계**로 API·스케줄러·webhook 동시 쓰기에서 잠금 경합. 기각.
- **SQL Server** — 사내 Windows 인프라 정합은 있으나, Control Plane 스택을 FastAPI(Python)로 택했으므로
  (ASP.NET Core + SQL Server) 조합의 이점이 소멸 → [[decision-control-plane-fastapi]]. 기각.

## 함의

- [[2026-07-07-ops-backend-plan]] Phase 2에서 `_state.json`의 `last_processed_sha`를 `source_branches`로 이관하고
  `SCM_SOURCES_JSON`(.env)을 폐기한다 — 파일 분산 상태를 DB SoT로 수렴 → [[decision-db-source-of-truth]]
- 스키마는 [[decision-db-source-of-truth]]의 테이블(sources·source_branches·runs·run_items)에
  [[decision-scm-multi-instance-github-mvp]]의 `scm_instances`가 더해진다.

관련: [[decision-db-source-of-truth]] · [[decision-control-plane-fastapi]] · [[decision-control-data-plane-split]] · [[decision-scm-multi-instance-github-mvp]] · [[overview]]
소스: [[2026-07-07-ops-backend-plan]] · 요약: [[summary-ops-backend-plan]]
