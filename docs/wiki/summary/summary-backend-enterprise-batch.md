---
type: summary
title: 2026-07-08 백엔드 엔터프라이즈화 일괄 완료
tags: [backend, ops, enterprise, migration, security, observability]
status: active
---

# 요약: 2026-07-08 백엔드 엔터프라이즈화 — 일괄 완료

사전 감사([[summary-backend-state-audit]]) 결과로 도출된 4개 트랙 + 12개 엔터프라이즈 항목을
일괄 실행. 일관성·시간 처리·파이프라인 상태 I/F가 정합되어 운영 가능한 상태로 마무리.
소스: [[2026-07-08-backend-enterprise-batch]].

## 핵심 결정

- **Alembic 도입** (ENT-A): `create_all` 폴백을 유지하면서도 prod 는 `alembic upgrade head` 로
  스키마 진화. 두 마이그레이션(`0001_baseline` + `0002_audit_and_token_rotation`) 모두 검증됨.
- **WS 이벤트 필터 기본 OFF** (Track E): `?verbose=0` 기본으로 `agent_step.thinking` 드랍.
  프런트 토글로 opt-in. 대시보드 노이즈 대폭 감소.
- **run 상태 진실 = DB row** (Track F): `run_summary` 가 event 파생 status 를 더 이상 신뢰 안 함.
  webhook `complete_run` 의 DB row 가 권위.
- **시간 일관성** (Track G): `isoformat_z` / `as_utc` 공용 헬퍼. SQLite(naive) 도 Z 접미사 보장.
  비교 전 tz 정규화로 `TypeError: can't compare naive vs aware` 회피.

## 변경 요약

| 영역 | 결과 |
|---|---|
| 코드 | A/B/C/D/E/F/G 트랙 + ENT-A~L — 약 25 파일 변경/추가 |
| 인프라 | Dockerfile(멀티스테이지) · alembic(2개 마이그레이션) · dependabot · CI Windows 매트릭스 |
| 테스트 | 82 passing (75 unit/integration + 7 E2E) |
| 마이그레이션 | alembic upgrade head 검증 (0001 → 0002) |

## 신규·변경 파일 (요약)

- 신규: `controlplane/{health,middleware,observability,ratelimit,timeutil,schemas}.py`,
  `services/{tag_poller,audit}.py`, `scripts/backup.py`,
  `tests/test_e2e_pipeline.py`, `tests/test_timeutil.py`,
  `.github/dependabot.yml`, `backend/Dockerfile`, `backend/.dockerignore`,
  `controlplane/migrations/{alembic.ini,env.py,script.py.mako,versions/0001..0002}.py`
- 변경: `runner/job.py`, `manual_pipeline/runner.py`, `connectors/{base,gitlab,github}.py`,
  `controlplane/{app,api,models,settings}.py`, `services/{registration,scheduler,runs}.py`,
  `common/{logging_setup,events}.py`, `.github/workflows/ci.yml`,
  `frontend/src/{api/client.js,hooks/queries.js,hooks/useLiveSocket.js,store/ui.js}`,
  `backend/requirements.txt`, `backend/requirements-dev.txt`

## 운영 시 변경 필요한 항목 (.env)

- `CONTROL_DB_URL` — 운영 DB 가 있다면 설정
- `CONTROL_API_TOKENS` — 프로덕션 토큰 (현재 개발 기본값은 미설정)
- `CONTROL_SECRET_KEY` — Fernet 키 (없으면 토큰 평문 경고)
- `CONTROL_CORS_ORIGINS` — 명시적 origin 목록 (빈 값이면 *)
- `LOG_FORMAT=json` — 운영 (수집 친화)
- `RATE_LIMIT_PER_MIN=600` — API 분당 한도 (0=무제한)
- `GRACEFUL_SHUTDOWN_TIMEOUT_SEC=30`
- `DEEP_HEALTHCHECK_TIMEOUT_SEC=3`
- `TOKEN_ROTATION_WARN_DAYS=90` — 토큰 순환 경고 임계
- `MANUAL_TAG_POLL_CRON=0 */1 * * *` — 매뉴얼 태그 폴링(기본 1시간)
- `MANUAL_TAG_POLL_ENABLED=true`

## 검증

- `python -m pytest backend/tests/ -q` → **82 passed**
- `cd backend && alembic -c controlplane/migrations/alembic.ini upgrade head` → 0001 + 0002 성공
- `python -m compileall -q backend` → 무경고

## 미해결

- ⛔ `question-cloud-scm-network` — 클라우드 SCM 아웃바운드 경로 실측
- `question-cloud-scm-token-policy` — 토큰 발급 정책/순환 주기 runbook
- `question-batch-observability` — daily digest (Track C-3 skip)
- `question-cost-estimation` — 비용 임계값/예산 가드
- OTel 분산 추적 / E2E docker-compose smoke / OpenAPI 스키마 전면 확장 — 다음 세션

## 관련

- [[2026-07-08-backend-enterprise-batch]] (raw) · [[2026-07-08-backend-state-audit]] (사전 감사)
- [[summary-ops-backend-plan]] · [[decision-mvp-scope]] · [[decision-engine-orchestration-langgraph]]
