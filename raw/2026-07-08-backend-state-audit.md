# 2026-07-08 백엔드 구현 상태 감사 — 2026-07-07 계획 대비 실측

## 배경

2026-07-07 ops-backend-plan(→ [[summary-ops-backend-plan]]) 이후 위키는 갱신이 멈춘 채
코드가 구현됐다. 백엔드 개선 계획을 세우기 위해 코드를 직접 읽어 Phase 1~4 + 매뉴얼
병행 트랙의 실제 상태를 실측했다.

## 감사 방법

- 디렉터리 트리 + README.md 읽기 (구조 파악)
- 핵심 파일 직독: `controlplane/app.py`, `runner/job.py`, `common/docshub.py`,
  `static_pipeline/main.py`, `connectors/` (grep)
- TODO/stub/mock grep: 총 7건 (전부 `submit_mr_stub` 호출 1개 소스)
- 테스트 함수 grep: 48건 (커넥터 계약 12 + 러너 7 + Control Plane API 14 + rate limit 8 + factory 5 + state advance 2)
- CI 워크플로우: `.github/workflows/ci.yml` (Ubuntu 매트릭스 only, Windows 결여)

## Phase 1 — SCM 커넥터 계층: ✅ DONE

- `connectors/base.py` ScmConnector 포트 실측 (read/write/auth 3축)
- `gitlab.py`·`github.py` 실측, base_url 주입식 (사내·gitlab.com 동일 구현)
- `factory.py`·`tests/test_connectors_contract.py`(12)·`test_connector_factory.py`(5)·
  `test_scm_rate_limit.py`(8) 통과 기반

## Phase 2 — Control Plane: ✅ DONE

- `controlplane/app.py`: FastAPI lifespan, CORS(⚠ `allow_origins=["*"]`),
  예외 핸들러(`error`+`detail`), `_seed_from_env`(레거시 SCM_SOURCES_JSON 시딩)
- DB: `init_db`·`make_engine`·`session_scope` (PostgreSQL/SQLite 양쪽)
- Crypto: `SecretBox`(Fernet at-rest 암호화) 실측
- Services: `registration`(자동 조회+dry-run), `scheduler`(APScheduler per source),
  `notifier`(역할 기반 이메일), `runs`(수명주기)
- WS: `Broadcaster` (실시간 이벤트 push)
- 테스트 14건 (`test_controlplane_api.py`) — 인증·등록·스케줄·lifecycle·compare 404·
  rate limit·websocket·secret encryption 전부 커버

## Phase 3 — Data Plane 러너: 🟡 정적 DONE, 매뉴얼 미연결

- `runner/job.py`: execute() 함수가 컨텍스트 조회 → init/diff 분기 → MR 제출 →
  완료 보고(sha 전진) 흐름 실측 (line 111-149)
- `submit_to_targets`: `submit_change_request` 경유 실제 MR/PR 제출 (line 67-98)
- `classify_error`: ScmNotFoundError/ScmRateLimitError/ScmAuthError 분류 (line 101-108)
- **GAP**: `execute()`가 `run_init`·`run_static`만 호출 (line 123-132).
  `run_manual` 브랜치 없음 → 매뉴얼 파이프라인이 Control Plane에서 트리거 불가.
  MVP 절단선([[decision-mvp-scope]])이 정적+매뉴얼 둘 다인데 현재 절반만 동작.

## Phase 4 — 신뢰성/보안: 🟡 PARTIAL

DONE:
- 시크릿 at-rest 암호화 (Fernet)
- API 자체 토큰 인증
- Rate limit 감지 + 테스트 (8건)
- 이벤트 보존 기한 (`EVENT_RETENTION_DAYS`, retention 테스트)
- usage 토큰 적재 + `/api/costs` 엔드포인트

미비:
- daily digest 이벤트 보고서 (→ [[question-batch-observability]] 잔량)
- 토큰 순환 정책/기능 (`scm_instances`에 rotated_at 없음)
- E2E 통합 테스트 (Control Plane → runner → stubbed SCM → MR 제출까지 1개)
- CI Windows 매트릭스 (현재 `ubuntu-latest` only, 프로덕션은 Windows Data Plane)

## 병행 트랙 — 매뉴얼 MCP: 🟡 bridge·runner 존재, 미통합

- `common/mcp_bridge.py`: SSE 연결 + 도구 로드 + 동기 래핑, 실측 (line 1-158)
- `manual_pipeline/runner.py`: `run_manual`·`run_smoke` 존재
- **GAP 1**: 위 Phase 3 GAP과 동일 — runner/job.py가 run_manual을 호출 안 함
- **GAP 2**: `manual_pipeline/runner.py:149`가 여전히 `submit_mr_stub` 호출
  → Control Plane 경로와 분산. 비슷한 이중 경로가 `static_pipeline/init_runner.py:117`·
  `static_pipeline/runner.py:83`에도 있음

## 코드 부채 — 실측 4건

1. **CORS 와일드카드** — `app.py:92`가 `allow_origins=["*"]`. 프로덕션 보안 위험.
2. **레거시 stub 3종** — `init_runner.py:117`·`static_pipeline/runner.py:83`·
   `manual_pipeline/runner.py:149`가 `submit_mr_stub` 호출. Control Plane 경로
   (`submit_change_request`)와 공존하는 이중 경로.
3. **레거시 시딩** — `_seed_from_env`가 여전히 `SCM_SOURCES_JSON`에서 읽어 DB 시딩.
   DB-SoT([[decision-db-source-of-truth]])와 부분 충돌, 프로덕션에선 게이트 필요.
4. **CI 매트릭스** — `.github/workflows/ci.yml`이 Ubuntu만. 프로덕션 Data Plane이
   Windows라 매트릭스 추가 필요.

## 위키 드리프트

- `log.md` 마지막 항목이 2026-07-07 ops-backend-plan ingest (line 488-496).
- 그 이후 구현 진척이 위키에 0 반영. Phase 1~4 완료/잔량이 overview에 안 잡힘.
- CLAUDE.md "위키 유지 규칙" 위반 상태.

## 새로 열리는 질문 (본 감사에서 파생)

- 매뉴얼 파이프라인 Control Plane 통합 시 run.pipeline_id 분기 방식 (run_manual 통합)
- 클라우드 SCM 네트워크 게이트 해소 전 사내 GitLab만 먼저 운영할지 (Track B 우회)
- 레거시 CLI 경로(`static_pipeline/main.py` 등)를 계속 유지할지, Control Plane 표준화할지

## 관련

- 구 계획: [[summary-ops-backend-plan]] · [[2026-07-07-ops-backend-plan]]
- 결정: [[decision-mvp-scope]] (정적+매뉴언 둘 다) · [[decision-control-plane-fastapi]]
  · [[decision-control-plane-postgresql]] · [[decision-scm-multi-instance-github-mvp]]
  · [[decision-release-tag-trigger]] (매뉴얼 트리거) · [[decision-artifact-type-dispatch]]
- 오픈 블로커: [[question-cloud-scm-network]] ⛔ · [[question-cloud-scm-token-policy]]
- 잔량 질문: [[question-batch-observability]] (daily digest) · [[question-secret-storage-security]]
  · [[question-cost-estimation]] · [[question-release-object-vs-tag-trigger]]
