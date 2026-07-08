---
type: summary
title: 2026-07-08 백엔드 구현 상태 감사 요약
tags: [backend, audit, ops, drift]
status: active
---

# 요약: 2026-07-08 백엔드 구현 상태 감사

2026-07-07 [[summary-ops-backend-plan]] 이후 위키는 멈춘 채 코드가 구현됐다. 백엔드
개선 계획의 기준선을 잡기 위해 코드를 직독해 Phase 1~4 + 매뉴얼 병행 트랙 상태를
실측했다. 소스: [[2026-07-08-backend-state-audit]].

## 진단 — Phase별 상태

| Phase | 상태 | 핵심 증거 |
|---|---|---|
| 1. SCM 커넥터 | ✅ DONE | `connectors/{base,gitlab,github,factory}.py` 실측 · 계약 테스트 12·rate limit 8·factory 5 |
| 2. Control Plane | ✅ DONE | `app.py` lifespan/scheduler/notifier/crypto/broadcaster 실측 · API 테스트 14건 |
| 3. Data Plane 러너 | 🟡 정적만 DONE | `runner/job.py:123-132`가 `run_init`/`run_static`만 호출, `run_manual` 없음 |
| 4. 신뢰성/보안 | 🟡 PARTIAL | 암호화·rate-limit·retention·CI는 DONE. daily digest·토큰 순환·E2E·Windows 매트릭스 미비 |
| 매뉴얼 MCP 병행 | 🟡 bridge·runner 존재, 미통합 | `mcp_bridge.py`·`manual_pipeline/runner.py` 실측. runner/job.py에 run_manual 브랜치 없음 |

## 코드 부채 — 실측 4건

1. **CORS `allow_origins=["*"]`** (`controlplane/app.py:92`) — 프로덕션 보안 위험
2. **레거시 `submit_mr_stub` 3종** (`static_pipeline/init_runner.py:117`·
   `static_pipeline/runner.py:83`·`manual_pipeline/runner.py:149`) — Control Plane
   `submit_change_request` 경로와 이중 경로
3. **`_seed_from_env` 레거시 시딩** — `SCM_SOURCES_JSON`에서 DB 시딩. 프로덕션 게이트 필요
4. **CI Ubuntu 매트릭스 only** (`.github/workflows/ci.yml`) — 프로덕션 Data Plane이 Windows라 매트릭스 추가 필요

## 결정적 갭

**매뉴얼 파이프라인이 Control Plane에서 트리거 불가**하다. [[decision-mvp-scope]]가
정적+매뉴얼 둘 다를 MVP로 잡았기에 현재 MVP 절반만 동작. `runner/job.py:execute()`에
`run_manual` 분기가 없고, `schedule.py`에 태그 트리거([[decision-release-tag-trigger]])가
통합 안 됐다.

## 위키 드리프트

- `log.md` 마지막 항목이 2026-07-07 ops-backend-plan ingest. 그 이후 구현 진척이
  위키에 0 반영 → CLAUDE.md "위키 유지 규칙" 위반 상태.

## 새로 열리는 질문

- 매뉴얼 파이프라인 통합 시 run.pipeline_id 분기 방식 (run_manual 통합) — 본 감사 파생
- 클라우드 SCM 게이트 해소 전 사내 GitLab만 먼저 운영할지 — [[question-cloud-scm-network]] 우회
- 레거시 standalone CLI(`static_pipeline/main.py` 등)를 계속 유지할지, Control Plane 표준화할지

## 후속 계획 — 4개 트랙

사용자 지시("모든 기능을 개발하라")에 따라 본 감사를 기준선으로 아래 4트랙을 실행한다:

- **Track A** — 매뉴얼 파이프라인 Control Plane 통합 (가장 큰 기능 갭)
  - `runner/job.py`에 run_manual 분기 · `schedule.py` 태그 트리거 · stub 경로 통합 · 테스트
- **Track B** — 클라우드 SCM 게이트 해소 준비
  - 토큰 순환 인프라(`scm_instances.token_rotated_at` + notifier) · 네트워크 probe runbook
- **Track C** — 신뢰성·보안 마무리 (Phase 4 잔량)
  - CORS hardening · stub 제거 · daily digest · E2E 테스트 · CI Windows 매트릭스 · Settings 감사
- **Track D** — 위키 동기화 (본 summary가 1차 산출물, 코드 완료 후 최종 갱신)

## 관련

- 원본: [[2026-07-08-backend-state-audit]] · 선행 계획: [[summary-ops-backend-plan]]
- 결정: [[decision-mvp-scope]] · [[decision-control-data-plane-split]] ·
  [[decision-control-plane-fastapi]] · [[decision-control-plane-postgresql]] ·
  [[decision-scm-multi-instance-github-mvp]] · [[decision-release-tag-trigger]] ·
  [[decision-artifact-type-dispatch]] · [[decision-engine-orchestration-langgraph]]
- 오픈: [[question-cloud-scm-network]] ⛔ · [[question-cloud-scm-token-policy]] ·
  [[question-batch-observability]] · [[question-secret-storage-security]] ·
  [[question-cost-estimation]] · [[question-release-object-vs-tag-trigger]]
