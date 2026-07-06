---
type: decision
title: 코드 인덱스 형상 관리 (버전 스냅샷 + 원자 교체)
tags: [code-index, versioning, availability, consistency]
status: superseded
---

> [!superseded] 이 결정은 대체됨 (2026-07-06)
> 코드 인덱스가 중앙 파이프라인 범위에서 제외되어 중앙 인덱스 형상 관리가 불필요해졌다
> → [[decision-code-index-out-of-pipeline]]

# 결정: 인덱스는 버전 단위로 형상 관리한다 — 재인덱싱 중에도 직전 버전으로 질의

인덱스를 제자리(in-place)에서 고치지 않고 **버전 스냅샷**으로 관리한다.
새 인덱스는 별도 버전으로 빌드하고, 완성된 후에만 **원자적으로 교체**한다.

## 규칙

- 인덱스 버전은 **소스 sha에 결부**된다 — "이 인덱스는 레포@sha의 상태" ([[concept-idempotent-sha]]의 sha 전진과 정합: 교체 성공 = sha 전진)
- 재인덱싱 **중에도** 직전 버전이 계속 질의를 서빙한다 — 쓰기가 읽기를 막지 않는다
- 교체는 빌드 완료 후 원자적으로 — 질의가 두 버전을 섞어 보지 않는다
- 문제 시 직전 버전으로 되돌릴 수 있다 (파생 데이터이므로 전체 재구축도 항상 가능)

## 기각 대안

- **단일 인덱스 in-place 갱신** — 저장 공간은 아끼지만 갱신 중 질의가 불완전한 상태를 보고,
  실패 시 복구 지점이 없다. MCP 상시 서빙([[decision-code-index-mcp-serving]]) 요구와 충돌

## 열린 부분

- **소유 평면 (답함)** — 인덱스 저장소는 **별도 질의 서비스 평면**(현재 MCP 서버)이 소유 → [[decision-code-index-store-plane]]. 본 decision의 원자 교체 규칙은 그 평면 안에서 그대로 적용.
- 보존 버전 개수·저장 위치(엔진)는 구현 시 확정

관련: [[decision-code-index-pipeline]] · 소스: [[2026-07-05-code-index-followup]]
