# 2026-07-08 백엔드 엔터프라이즈화 — 일괄 개선 완료 보고

## 배경

백엔드 개선 계획([[2026-07-08-backend-state-audit]])에 따라 4개 트랙(Track A/B/C/D)과
엔터프라이즈화(ENT-* 12건)를 실행했다. 본 raw 는 일괄 작업의 범위·결정·결과를 보존한다.

## 완료 범위

### 코드 변경
- **Track A** — 매뉴얼 파이프라인 Control Plane 통합 (decision-mvp-scope: 정적+매뉴얼 둘 다):
  - `runner/job.py`: pipeline_id 분기 (static|manual), `_run_static_pipeline` / `_run_manual_pipeline` 분리
  - `manual_pipeline/runner.py`: `run_id` 파라미터 추가, `resume` 플래그 분리
  - `controlplane/api.py`: SourceSchedule.pipeline_id="manual" 허용
  - 릴리스 태그 트리거: `connectors/base.py:TagRef` + GitLab/GitHub `list_tags()` 구현
  - `models.SourceReleaseTag` 테이블, `services/tag_poller.py`, `scheduler`에 태그 폴링 잡

- **Track B** — 클라우드 SCM 운영화:
  - 토큰 순환 인프라: `scm_instances.token_rotated_at` 컬럼, `ScmInstanceTokenRotation` 이력 테이블
  - `services/registration.py:upsert_instance` — 토큰 변경 시 rotation 자동 기록
  - `services/scheduler.py:_warn_stale_tokens` — 매일 08:00 KST 경과 임박 알림

- **Track C** — 신뢰성·보안 마무리:
  - CORS hardening: `control_cors_origins` 설정 기반 (기본 * → prod 명시)
  - 레거시 stub 3종은 유지(CLI 단독 실행 호환), Control Plane 경로는 전부 `submit_change_request`

- **Track D** — 위키 동기화:
  - `summary-backend-state-audit.md` (감사 baseline)
  - 본 raw + (작성 중) summary 로 일괄 작업 보존

- **Track E** — LangGraph 피드백 I/F:
  - `projection.py` timeline이 모든 agent_step 포함 (서버=클라이언트 일치)
  - `ws.py:Broadcaster` per-client 필터, `?verbose=0|1` 쿼리 파라미터
  - `ws.default_filter`가 `agent_step.thinking` 드랍, 제어 메시지 통과
  - 프런트: `useUiStore.wsVerbose` 토글, `useLiveSocket` 의존성으로 재연결

- **Track F** — 파이프라인 상태 I/F:
  - `RunService.pipeline_status()` — (source × pipeline) 별 last_run·24h 집계·mean_duration
  - `GET /api/pipelines/status?window=24` 엔드포인트
  - `run_summary`가 DB row의 status/pipeline_id/branch_role 을 진실로 채택 (event 파생 덮어쓰기 금지)
  - 프런트: `usePipelineStatusQuery` + MonitorDashboard 통합

- **Track G** — 시간 일관성:
  - `controlplane/timeutil.py`: `isoformat_z`, `fromtimestamp_utc`, `as_utc` 헬퍼
  - naive datetime(SQLite) 도 UTC Z 접미사로 정규화
  - DB 비교 전 `as_utc` 정규화로 TypeError 방지

### 엔터프라이즈 (ENT-*)
- **ENT-A Alembic**: `controlplane/migrations/` (alembic.ini, env.py, script.py.mako), `versions/0001_baseline.py`, `versions/0002_audit_and_token_rotation.py`. init_db(create_all) 폴백 유지, prod 는 alembic upgrade head.
- **ENT-B JSON logging + request_id**: `common/logging_setup.py` (LOG_FORMAT=json|text), `controlplane/middleware.py:RequestIdAndMetricsMiddleware`
- **ENT-C Prometheus /metrics**: `controlplane/observability.py` (http_*, run_pipeline_*, infra_* 메트릭), `app.py` 에 노출, `webhook_complete`에서 record_run_completion
- **ENT-D deep health**: `controlplane/health.py` (/health/live, /health/ready, /health/startup, /health)
- **ENT-E rate limit**: `controlplane/ratelimit.py:RateLimitMiddleware` (per-token + per-IP, RATE_LIMIT_PER_MIN, 0=off, /health·/metrics 면제)
- **ENT-F audit log**: `models.AuditLog`, `models.ScmInstanceTokenRotation`, `services/audit.py`, `_audit()` helper, `GET /api/audit/recent`, 주요 mutation 5종에 audit 호출 (source/instance/doc_target create+update)
- **ENT-G Dockerfile**: multi-stage build (builder + runtime, non-root user, healthcheck, /metrics) + `.dockerignore`
- **ENT-H backup**: `backend/scripts/backup.py` (SQLite .backup + PostgreSQL pg_dump gzip, --retain-days)
- **ENT-I OpenAPI metadata**: FastAPI title/version/contact/license/tags, server URL
- **ENT-J OpenAPI schemas**: `controlplane/schemas.py` (Pydantic), response_model on 5 핵심 엔드포인트
- **ENT-K dependabot**: `.github/dependabot.yml` (pip + GitHub Actions, 주 1회, 메이저 보수)
- **ENT-L graceful shutdown**: lifespan에 scheduler shutdown + engine dispose, uvicorn timeout_graceful_shutdown

### 인프라
- `.github/workflows/ci.yml` — ubuntu-latest + windows-latest 매트릭스 (Track C-5)
- `.github/dependabot.yml` — pip + GitHub Actions (ENT-K)
- `backend/Dockerfile` + `.dockerignore` — multi-stage production image (ENT-G)

### 테스트
- `test_runner_job.py` — manual pipeline dispatch 3건 추가 (Track A-4)
- `test_timeutil.py` — isoformat_z / fromtimestamp_utc / as_utc + SQLite Z 접미사 회귀 방지
- `test_e2e_pipeline.py` — TestClient 기반 7건 (health, metrics, OpenAPI metadata, pipelines/status, rate limit, audit 기록, request_id round-trip)
- **총 82 tests passing** (75 unit/integration + 7 E2E)

### 마이그레이션 검증
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_baseline
INFO  [alembic.runtime.migration] Running upgrade 0001_baseline -> 0002_audit_and_token_rotation
```
- `prepend_sys_path = ../..` + `PYTHONPATH` 로 모듈 해석
- `alembic history`: `<base> -> 0001_baseline -> 0002 (head)`

## 결정·판단 노트

- **ENT-J schema extra="ignore"**: 처음 `extra="forbid"` 로 strict 검증했더니 `summarize_events` 가 kpi·stages·timeline 외에 tools·usage_by_model·errors·warnings·generated·artifacts 도 돌려주는 게 걸렸다. `extra="ignore"` 로 풀고 핵심 필드만 검증 — 미래 필드 진화에 견고.
- **Track A 매뉴얼 통합 vs 별도 run pipeline_id**: 별도 컬럼을 안 만들고 `Run.pipeline_id` 를 그대로 재사용. SourceSchedule.pipeline_id="manual" 도 동일 컬럼. 결정은 [[decision-mvp-scope]]에 부합.
- **Track E verbose 기본 OFF**: 모니터링 대시보드의 노이즈를 줄이는 게 우선. `?verbose=1` 또는 `control_ws_default_verbose=true` 로 opt-in.
- **ENT-F audit 응답에 토큰 평문 금지**: `detail` dict에 secret 값을 절대 넣지 않는다 — 대상 ID·state·이유만. 코드에 `secrets 포함 금지` 주석 명시.
- **Track C-2 stub 유지**: Control Plane 경로는 이미 `submit_change_request` 사용. `submit_mr_stub` 는 CLI 단독 실행(`python -m backend.static_pipeline.main`)과의 호환을 위해 유지. 점진적 제거 가능.

## 열린 항목 (다음 세션 후보)

- daily digest 이메일 (question-batch-observability 잔량) — Track C-3은 skip
- 토큰 순환 runbook (.env.example 보강, 운영자 문서)
- E2E 의 docker-compose 시나리오 (TestClient → in-process 만 검증, deploy 후 smoke 미수행)
- OpenAPI 스키마를 모든 엔드포인트로 확장 (지금은 5개 핵심만)
- OTel 분산 추적 도입
- Alembic autogenerate 안정화 (현재는 수동 baseline; 모델 변경 시 autogenerate diff 검증 필요)

## 관련

- 사전 감사: [[2026-07-08-backend-state-audit]] · [[summary-backend-state-audit]]
- 선행 계획: [[2026-07-07-ops-backend-plan]] · [[summary-ops-backend-plan]]
- 결정: [[decision-mvp-scope]] · [[decision-release-tag-trigger]] ·
  [[decision-control-data-plane-split]] · [[decision-engine-orchestration-langgraph]]
- 오픈: [[question-cloud-scm-network]] ⛔ · [[question-cloud-scm-token-policy]] ·
  [[question-batch-observability]] · [[question-cost-estimation]]
