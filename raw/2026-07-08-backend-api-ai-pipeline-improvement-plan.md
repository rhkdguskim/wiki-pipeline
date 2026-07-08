# Backend API Improvement Plan for AI Documentation Pipelines

작성일: 2026-07-08
대상: Control Plane API, Runner webhook, WebSocket event channel, frontend-facing query contract
기반 문서:

- `raw/2026-07-08-docu-automation-data-plane-review.md`
- `raw/2026-07-08-manual-automation-data-plane-review.md`
- `raw/2026-07-08-ai-agent-output-quality-plan.md`
- `raw/2026-07-08-frontend-ai-pipeline-improvement-plan.md`

---

## 1. 목표

백엔드 API는 이제 단순 run trigger/event log API가 아니라, AI 문서화 파이프라인의 품질, 근거, manual 실행 환경, 원격 모니터링, MR publishability를 신뢰 가능한 계약으로 제공해야 한다.

이번 개선 목표는 다음이다.

1. `done`과 `publishable`을 API 레벨에서 분리한다.
2. quality/evidence/coverage/artifact/VNC 상태를 event payload가 아니라 first-class resource로 저장하고 조회한다.
3. runner webhook은 idempotent하고 replay 가능한 event stream을 만든다.
4. frontend는 snapshot API + event replay + WebSocket으로 언제든 동일한 화면 상태를 복원할 수 있다.
5. manual-automation은 source별 profile/scenario/artifact/VNC 세션을 API로 관리한다.
6. secret은 runner context에서만 복호화되고, frontend API에는 절대 노출되지 않는다.

---

## 2. 현재 API 기준선

현재 Control Plane은 다음 구조를 가진다.

- `/api/runs/trigger`
  - `Run` row 생성 후 runner subprocess 실행
  - `pipeline_id`는 `static|manual` 수용

- `/api/run-summary?run=...`
  - DB run row + `run_events` projection을 병합해 요약 반환
  - status, stages, timeline, kpi 중심

- `/api/events?run=...&offset=...`
  - DB event id를 offset으로 사용하는 polling API

- `/api/ws`
  - `events`, `run_status`, `runs_changed`, `sources_changed` push
  - verbose 필터만 존재

- `/api/pipelines/status`
  - source x pipeline 최근 상태, window 집계

- `/api/runner/context`
  - runner 전용
  - source, branch, doc target token을 복호화해 내려줌

- `/api/webhook/events`
  - runner가 event batch를 push
  - 현재 event idempotency/dedupe 계약 없음

- `/api/webhook/complete`
  - terminal status, sha advance, mr_url/doc_count 반영

- `/api/sources`, `/api/schedules`
  - source registration, static/manual schedule 일부 지원

현재 모델은 `runs`, `run_events`, `run_model_usage` 중심이다. AI 품질과 manual 자동화 운영에 필요한 다음 리소스가 없다.

- quality report
- quality finding
- evidence pack
- generated doc output metadata
- manual profile
- scenario set/version
- artifact selector
- run artifact/deploy/install/smoke result
- coverage report
- VNC monitor session
- run heartbeat/attempt
- event idempotency key

---

## 3. API 설계 원칙

### 3.1 Resource First, Event Second

중요한 운영 상태는 event payload 안에만 남기지 않는다. event는 timeline이고, resource table은 snapshot의 source of truth다.

예:

- `critic.verdict` event는 timeline에 남긴다.
- 최종 critic 결과는 `run_quality_reports`와 `run_quality_findings`에 저장한다.

### 3.2 Runner Webhook과 Frontend API 분리

runner가 쓰는 API와 frontend가 읽는 API는 분리한다.

- Runner API: secret-bearing, write-heavy, idempotent webhook
- Frontend API: redacted, read-optimized, typed response

Frontend는 절대 runner context를 호출하지 않는다.

### 3.3 Publishability Is a Contract

API는 `status=done`만 반환하면 안 된다. 모든 run summary는 다음을 포함해야 한다.

- `status`: 실행 상태
- `quality.status`: 산출물 품질
- `publishable`: MR/배포 가능 여부
- `blocked_reason`: publish를 막는 가장 중요한 이유

### 3.4 Reconstructable Live State

WebSocket은 편의 채널이다. 진실은 API snapshot + event replay로 재구성 가능해야 한다.

필수:

- event `seq`
- event `id`
- event idempotency key
- replay API
- overflow signal
- snapshot version

### 3.5 Backward Compatible Expansion

기존 frontend와 테스트를 깨지 않도록 다음을 지킨다.

- 기존 `/api/run-summary`, `/api/events`, `/api/pipelines/status`는 유지
- 새 필드는 optional로 추가
- 구버전 run은 `quality.status=not_evaluated`
- manual profile이 없으면 manual trigger/preflight에서 명확한 validation error 반환

---

## 4. Status Contract

### 4.1 Run Status

`runs.status`는 아래 값을 수용해야 한다.

```text
pending
running
done
done_with_warnings
failed
failed_quality_gate
partial
stale
cancelled
timeout
```

의미:

- `done`: 실행과 품질 게이트 모두 통과
- `done_with_warnings`: 산출물은 생성됐지만 운영자 확인 필요
- `failed_quality_gate`: 실행은 끝났지만 publishable=false
- `partial`: 일부 산출물만 유효하거나 일부 stage만 성공
- `stale`: 늦은 complete, CAS 실패, 오래된 artifact/version 기반
- `timeout`: heartbeat/reaper가 종료 처리

### 4.2 Quality Status

```text
pass
warning
fail
not_evaluated
```

`quality.status=fail`이면 run status는 `failed_quality_gate` 또는 `partial`이어야 한다.

### 4.3 Publishable Rule

`publishable=true` 조건:

- run terminal status가 `done`
- quality status가 `pass`
- blocking finding 없음
- evidence pack 존재
- generated doc output이 schema 검증 통과
- manual pipeline이면 coverage threshold 통과
- manual pipeline이면 artifact/deploy/install/readiness/smoke 정책 통과
- MR plan이 모든 publishable doc을 포함

`done_with_warnings`는 자동 승인/자동 머지 대상이 아니다. 다만 warning 문서를 MR에 올려 reviewer가 확인해야 하는 경우가 있으므로, API는 boolean `publishable`만으로 판단하지 않고 `publish_state`를 함께 제공한다.

`publish_state`:

- `publishable`: 자동 제출 가능
- `review_required`: MR 제출은 가능하지만 explicit confirm과 audit이 필요
- `blocked`: 제출 차단
- `unknown`: 구버전 run 또는 데이터 부족

기본 정책은 `warning_publish_policy=review_required`로 두되, 조직 정책에 따라 `block`으로 바꿀 수 있다.

---

## 5. Database Model Plan

### 5.1 runs 확장

추가 컬럼:

- `attempt`: int
- `runner_pid`: string nullable
- `started_at`: datetime nullable
- `heartbeat_at`: datetime nullable
- `terminal_at`: datetime nullable
- `status_reason`: text
- `publishable`: boolean default false
- `blocked_reason`: text
- `quality_status`: string default `not_evaluated`
- `quality_score`: int nullable
- `publish_state`: string default `unknown`
- `warning_publish_policy`: string default `review_required`
- `artifact_version`: string
- `release_tag`: string
- `source_version_ref`: string
- `snapshot_version`: int

목적:

- stuck run reaper
- frontend summary 고속 조회
- publishability 판단
- static/manual 공통 version trace

### 5.2 run_events 확장

현재 `run_events.id`가 DB offset 역할을 한다. 여기에 논리 event contract를 추가한다.

추가 컬럼:

- `event_id`: string
- `seq`: int
- `kind`: string
- `severity`: string
- `role`: string
- `dedupe_key`: string
- `received_at`: datetime

제약:

- unique `(run_id, event_id)`
- unique `(run_id, seq)`
- index `(run_id, seq)`
- index `(run_id, kind)`

마이그레이션:

- 기존 row는 `event_id = "legacy-" + id`
- 기존 row는 `seq = id` 또는 run별 row_number
- 기존 `layer/stage/status/payload`는 유지

### 5.3 run_quality_reports

run당 최종 quality snapshot.

컬럼:

- `run_id`
- `status`: pass|warning|fail|not_evaluated
- `score`
- `publishable`
- `failed_gate`
- `warning_count`
- `error_count`
- `repair_attempts`
- `deterministic_verifier_status`
- `grounding_critic_status`
- `schema_status`
- `mermaid_status`
- `redaction_status`
- `created_at`
- `updated_at`

### 5.4 run_quality_findings

critic/verifier finding 목록.

컬럼:

- `id`
- `run_id`
- `doc_id`
- `gate`
- `code`
- `severity`
- `blocking`
- `message`
- `location`
- `evidence_ref`
- `repair_status`
- `metadata_json`

### 5.5 run_evidence_packs

Evidence Builder 결과.

컬럼:

- `id`
- `run_id`
- `source_id`
- `pipeline_id`
- `version_ref`
- `item_count`
- `source_file_count`
- `observation_count`
- `unsupported_claim_count`
- `truncated`
- `omitted_count`
- `created_at`

### 5.6 run_evidence_items

개별 evidence item.

컬럼:

- `id`
- `pack_id`
- `run_id`
- `kind`
- `title`
- `path`
- `line_start`
- `line_end`
- `observation_id`
- `scenario_id`
- `artifact_ref`
- `content_preview`
- `content_uri`
- `metadata_json`

주의:

- 큰 screenshot/log/raw observation은 DB에 직접 저장하지 않고 artifact URI만 저장한다.
- secret pattern은 저장 전 redaction한다.

### 5.7 run_doc_outputs

생성 문서 단위 metadata.

컬럼:

- `id`
- `run_id`
- `theme`
- `path`
- `title`
- `action`: create|update|skip|blocked|deprecate_candidate
- `quality_status`
- `publishable`
- `warning_count`
- `error_count`
- `unsupported_claim_count`
- `evidence_count`
- `schema_status`
- `mermaid_status`
- `mr_inclusion_status`
- `content_sha256`
- `metadata_json`

### 5.8 source_manual_profiles

source별 manual automation profile.

컬럼:

- `source_id`
- `enabled`
- `mcp_endpoint_url`
- `mcp_transport`
- `host_label`
- `host_ip`
- `host_port`
- `vnc_enabled`
- `vnc_host`
- `vnc_port`
- `vnc_gateway_policy`
- `tool_allowlist_json`
- `secret_refs_json`
- `artifact_selector_json`
- `install_profile_json`
- `readiness_check_json`
- `smoke_check_json`
- `coverage_threshold`
- `failure_policy`
- `updated_at`
- `updated_by`

보안:

- secret value는 저장하지 않는다.
- `secret_refs_json`만 저장한다.
- frontend 응답에서는 host/ip/port를 policy에 따라 masked 처리한다.

### 5.9 manual_scenario_sets

scenario set version 관리.

컬럼:

- `id`
- `source_id`
- `name`
- `version`
- `status`: draft|active|archived
- `scenario_json`
- `lint_status`
- `lint_errors_json`
- `created_at`
- `updated_at`
- `updated_by`

제약:

- source당 active scenario set은 1개
- scenario id는 set 내부 unique

### 5.10 run_artifacts

manual artifact/deploy/install/smoke 결과.

컬럼:

- `run_id`
- `source_id`
- `release_tag`
- `artifact_name`
- `artifact_url`
- `artifact_sha256`
- `artifact_type`: exe|msi|zip|web|unknown
- `selected_by`: policy|manual_override
- `build_status`
- `download_status`
- `deploy_status`
- `install_status`
- `readiness_status`
- `smoke_status`
- `installed_version`
- `error`
- `metadata_json`

### 5.11 run_coverage_reports

manual coverage summary.

컬럼:

- `run_id`
- `status`: pass|warning|fail|not_applicable
- `percentage`
- `threshold`
- `reached`
- `expected`
- `missed_count`
- `misses_json`
- `scenario_results_json`
- `created_at`

### 5.12 run_vnc_sessions

mcp-vnc monitoring session.

컬럼:

- `run_id`
- `session_id`
- `status`: unavailable|pending|connecting|connected|disconnected|expired|error
- `host_label`
- `host_ip_encrypted`
- `host_port`
- `gateway_url`
- `view_only`
- `current_scenario_step`
- `current_action`
- `latency_ms`
- `resolution`
- `expires_at`
- `created_at`
- `updated_at`
- `error`

주의:

- frontend API는 raw password/token을 반환하지 않는다.
- raw `host_ip`는 필요하면 암호화 저장한다.
- browser는 TCP VNC에 직접 붙지 않고 backend gateway websocket에 붙는다.

---

## 6. Frontend-Facing API

### 6.1 Run Summary v2

기존:

`GET /api/run-summary?run=:runId`

유지하되 응답에 새 필드를 추가한다.

추가 응답:

```json
{
  "run_id": "manual-demo-ab12cd34",
  "status": "failed_quality_gate",
  "publishable": false,
  "blocked_reason": "coverage below threshold",
  "snapshot_version": 17,
  "quality": {
    "status": "fail",
    "score": 61,
    "failed_gate": "manual_coverage",
    "warning_count": 3,
    "error_count": 1,
    "repair_attempts": 2,
    "publishable": false
  },
  "evidence": {
    "pack_id": "evpack-...",
    "item_count": 42,
    "unsupported_claim_count": 1,
    "truncated": false
  },
  "coverage": {
    "status": "fail",
    "percentage": 58,
    "threshold": 80,
    "reached": 14,
    "expected": 24,
    "missed_count": 10
  },
  "artifact": {
    "release_tag": "v1.8.0",
    "artifact_name": "app-1.8.0.msi",
    "artifact_sha256": "redacted-preview",
    "install_status": "pass",
    "readiness_status": "pass",
    "smoke_status": "pass"
  },
  "vnc": {
    "available": true,
    "status": "connected",
    "session_id": "vnc-...",
    "view_only": true,
    "expires_at": "2026-07-08T10:30:00Z"
  },
  "mr": {
    "readiness": "blocked",
    "blocked_reason": "quality gate failed",
    "included_files": 2,
    "excluded_files": 1
  }
}
```

### 6.2 Run Quality

`GET /api/runs/{run_id}/quality`

반환:

- run quality summary
- gate results
- findings
- repair attempts
- doc-level quality

쿼리:

- `severity=warning|error`
- `blocking=true|false`
- `doc_id=...`

### 6.3 Evidence Pack

`GET /api/runs/{run_id}/evidence`

반환:

- evidence pack summary
- evidence item list
- doc section mapping
- unsupported claim list

쿼리:

- `kind=source_file|diff_hunk|observation|screenshot|scenario|coverage`
- `doc_id=...`
- `limit`
- `cursor`

### 6.4 Evidence Item Detail

`GET /api/runs/{run_id}/evidence/{item_id}`

반환:

- redacted content
- source file reference
- observation reference
- artifact URI
- metadata

주의:

- content가 크면 signed artifact URL 또는 download endpoint로 분리한다.
- secret pattern은 항상 redacted response만 반환한다.

### 6.5 Manual Coverage

`GET /api/runs/{run_id}/coverage`

반환:

- coverage summary
- scenario result table
- missed feature list
- screenshots/log references
- threshold result

### 6.6 Run Artifacts

`GET /api/runs/{run_id}/artifacts`

반환:

- selected artifact
- release/tag/version
- build/download/deploy/install/readiness/smoke status
- deprecated candidates
- error/warnings

### 6.7 VNC Session

`GET /api/runs/{run_id}/vnc-session`

반환:

```json
{
  "available": true,
  "status": "connected",
  "websocket_url": "/api/runs/manual-demo/vnc/ws?token=short-lived",
  "host_label": "manual-host-01:5901",
  "port_label": "5901",
  "session_id": "vnc-abc",
  "expires_at": "2026-07-08T10:30:00Z",
  "view_only": true,
  "current_scenario_step": "login-with-valid-user",
  "current_action": "click login button",
  "latency_ms": 42,
  "resolution": "1920x1080",
  "error": ""
}
```

보안 조건:

- `view_only=false`이면 409 또는 403
- raw password/token 미반환
- raw IP는 policy에 따라 masked
- short-lived signed token 사용

### 6.8 VNC WebSocket Gateway

`WebSocket /api/runs/{run_id}/vnc/ws?token=...`

역할:

- browser `react-vnc`와 mcp-vnc/noVNC gateway 사이 websocket proxy
- view-only enforcement
- keyboard/mouse/clipboard frame drop
- session expiry enforcement

운영 원칙:

- frontend가 직접 `ip:port` TCP VNC에 붙지 않는다.
- pipeline에서 주어진 ip/port는 backend gateway가 사용한다.
- gateway는 audit log에 open/close/reconnect만 기록한다.

### 6.9 Event Replay

신규:

`GET /api/runs/{run_id}/events?after_seq=0&limit=500`

기존:

`GET /api/events?run=...&offset=...`

기존 API는 유지하고, 새 API는 seq 기반으로 제공한다.

반환:

```json
{
  "run_id": "static-demo-ab12cd34",
  "events": [],
  "after_seq": 0,
  "latest_seq": 128,
  "has_more": false,
  "truncated": false,
  "snapshot_version": 17
}
```

### 6.10 Pipeline Status v2

기존:

`GET /api/pipelines/status`

추가 필드:

- `quality_status`
- `quality_score`
- `publishable`
- `blocked_reason`
- `warning_count`
- `error_count`
- `coverage_percentage`
- `coverage_threshold`
- `artifact_version`
- `release_tag`
- `vnc_status`
- `mr_readiness`
- `last_failed_gate`
- `repair_attempts`

### 6.11 Overview v2

`GET /api/overview`

추가 totals:

- `publishable`
- `done_with_warnings`
- `failed_quality_gate`
- `quality_failures`
- `coverage_failures`
- `unsupported_claims`
- `repair_attempts`

---

## 7. Source Manual Automation API

### 7.1 Manual Profile 조회/저장

`GET /api/sources/{source_id}/manual-profile`

`PUT /api/sources/{source_id}/manual-profile`

저장 필드:

- enabled
- MCP endpoint URL
- MCP transport
- host label/IP/port
- VNC monitoring enabled
- VNC host/port
- tool allowlist
- secret refs
- artifact selector
- install profile
- readiness check
- smoke check
- coverage threshold
- failure policy

응답은 secret value 없이 반환한다.

### 7.2 Manual Profile Preflight

`POST /api/sources/{source_id}/manual-profile/preflight`

검증:

- MCP endpoint reachable
- required tools available
- tool allowlist satisfies scenarios
- secret refs exist
- artifact selector resolvable
- VNC endpoint/gateway readiness
- install/readiness/smoke commands valid
- active scenario set exists

반환:

- `ok`
- `errors`
- `warnings`
- `resolved_tools`
- `selected_artifact_preview`
- `vnc_available`

### 7.3 Scenario Set CRUD

`GET /api/sources/{source_id}/scenarios`

`POST /api/sources/{source_id}/scenarios`

`PUT /api/sources/{source_id}/scenarios/{scenario_set_id}`

`DELETE /api/sources/{source_id}/scenarios/{scenario_set_id}`

`POST /api/sources/{source_id}/scenarios/{scenario_set_id}/activate`

### 7.4 Scenario Lint

`POST /api/sources/{source_id}/scenarios/lint`

검증:

- JSON/YAML schema
- step id unique
- required tool exists
- timeout valid
- cleanup step valid
- expected observation shape valid
- secret ref only, no raw secret

### 7.5 Artifact Preflight

`POST /api/sources/{source_id}/artifacts/preflight`

입력:

- release tag 또는 branch/build ref
- optional manual override

반환:

- selected artifact
- asset match reason
- checksum availability
- installer type
- install command preview
- blocking errors
- warnings

---

## 8. Runner API and Webhook Contract

### 8.1 Runner Context v2

기존:

`GET /api/runner/context?run=:runId`

추가 응답:

```json
{
  "run": {
    "run_id": "...",
    "pipeline_id": "manual",
    "attempt": 1,
    "status_contract": ["done", "done_with_warnings", "failed_quality_gate", "partial", "failed"]
  },
  "manual_profile": {
    "mcp_endpoint_url": "...",
    "mcp_transport": "sse",
    "tool_allowlist": [],
    "secret_values": {},
    "artifact_selector": {},
    "install_profile": {},
    "readiness_check": {},
    "smoke_check": {},
    "coverage_threshold": 80,
    "vnc": {
      "enabled": true,
      "host": "10.0.0.12",
      "port": 5901,
      "view_only": true
    }
  },
  "scenario_set": {
    "id": "scset-...",
    "version": 3,
    "scenarios": []
  },
  "output_contract": {
    "requires_evidence_pack": true,
    "requires_quality_report": true,
    "requires_coverage_report": true
  }
}
```

주의:

- runner context만 secret value를 포함할 수 있다.
- frontend-facing manual profile에는 secret value가 없다.

### 8.2 Heartbeat

`POST /api/webhook/heartbeat`

입력:

- run_id
- attempt
- stage
- pid
- timestamp

효과:

- `runs.heartbeat_at` 갱신
- stale reaper가 timeout 판단에 사용
- WebSocket `run_heartbeat`는 verbose 채널에서만 broadcast

### 8.3 Events v2

기존:

`POST /api/webhook/events`

확장 contract:

```json
{
  "run_id": "...",
  "attempt": 1,
  "events": [
    {
      "event_id": "evt-...",
      "seq": 42,
      "ts": "2026-07-08T10:00:00Z",
      "kind": "quality_gate.completed",
      "layer": "stage",
      "stage": "grounding-critic",
      "status": "failed",
      "severity": "error",
      "role": "Grounding Critic",
      "dedupe_key": "grounding-critic-final",
      "detail": {}
    }
  ]
}
```

처리:

- `(run_id, event_id)` 중복은 idempotent success
- `(run_id, seq)` 중복은 같은 payload면 idempotent, 다르면 409
- seq gap은 허용하되 `event_gap_detected` marker를 남긴다.
- event 저장 후 WebSocket message에는 `latest_seq`, `snapshot_version` 포함

### 8.4 Quality Report Webhook

`POST /api/webhook/quality`

runner가 deterministic verifier/critic/repair 최종 결과를 저장한다.

입력:

- run_id
- status
- score
- publishable
- failed_gate
- warning_count
- error_count
- repair_attempts
- gates
- findings
- doc_quality

효과:

- `run_quality_reports` upsert
- `run_quality_findings` replace/upsert
- `run_doc_outputs` quality fields update
- `runs.quality_status`, `runs.publishable`, `runs.blocked_reason` update
- `quality_updated` WebSocket broadcast

### 8.5 Evidence Webhook

`POST /api/webhook/evidence`

입력:

- run_id
- evidence pack summary
- evidence items
- doc section mapping
- unsupported claims

효과:

- evidence pack upsert
- items bulk insert/upsert
- `run_doc_outputs.evidence_count` update

### 8.6 Coverage Webhook

`POST /api/webhook/coverage`

manual runner가 scenario/coverage 결과를 저장한다.

입력:

- run_id
- status
- percentage
- threshold
- reached
- expected
- misses
- scenario_results

효과:

- `run_coverage_reports` upsert
- coverage threshold fail이면 `publishable=false`
- WebSocket `coverage_updated`

### 8.7 Artifact Webhook

`POST /api/webhook/artifact`

입력:

- run_id
- release_tag
- artifact metadata
- build/download/deploy/install/readiness/smoke status
- installed_version

효과:

- `run_artifacts` upsert
- `runs.artifact_version`, `runs.release_tag` update
- blocking artifact/deploy failure면 run cannot proceed to manual generation

### 8.8 VNC Session Webhook

`POST /api/webhook/vnc-session`

입력:

- run_id
- session_id
- status
- host/ip/port
- gateway info
- view_only
- current scenario step/action
- expires_at
- latency/resolution
- error

효과:

- `run_vnc_sessions` upsert
- frontend-facing endpoint에는 token/password 없는 redacted view만 반환
- `vnc_session_updated` WebSocket broadcast

### 8.9 Complete Webhook v2

기존:

`POST /api/webhook/complete`

확장 입력:

- status
- quality_status
- publishable
- blocked_reason
- doc_count
- mr_url
- last_processed_sha
- release_tag
- artifact_version
- output_contract_result

처리 규칙:

- terminal guard 유지
- same-status complete도 terminal data를 무제한 덮어쓰지 않는다.
- `done` 요청이어도 quality fail이면 서버가 `failed_quality_gate`로 normalize한다.
- manual coverage fail이면 `failed_quality_gate` 또는 `done_with_warnings`로 normalize한다.
- static sha advance는 CAS 기반으로만 수행한다.
- manual release processed pointer는 MR submit/merge 정책과 분리해 명확히 저장한다.

---

## 9. WebSocket Contract

### 9.1 Message Envelope

모든 WebSocket message는 envelope를 가진다.

```json
{
  "message_id": "msg-...",
  "type": "events",
  "run_id": "...",
  "latest_seq": 42,
  "snapshot_version": 17,
  "ts": "2026-07-08T10:00:00Z",
  "payload": {}
}
```

### 9.2 Message Types

- `events`
- `run_status`
- `quality_updated`
- `evidence_updated`
- `coverage_updated`
- `artifact_updated`
- `vnc_session_updated`
- `mr_plan_updated`
- `runs_changed`
- `sources_changed`
- `pipeline_status_changed`
- `costs_changed`
- `overflow`

### 9.3 Overflow

현재 broadcaster는 client queue overflow 시 client를 조용히 버린다. 개선 후에는 가능한 경우 `overflow` message를 먼저 보내고 연결을 닫는다.

프런트 동작:

- `overflow` 수신 또는 disconnect 후 replay
- snapshot 재조회
- duplicate event dedupe

### 9.4 Subscription Filter

기존 `verbose=0|1`은 유지하되 아래 필터를 추가한다.

- `run_id`
- `pipeline_id`
- `source_id`
- `types=quality,coverage,vnc`

예:

`/api/ws?run_id=manual-demo-ab12cd34&types=events,run_status,vnc_session_updated`

---

## 10. MR Plan API 개선

### 10.1 MR Plan은 Quality-Aware여야 한다

기존 `/api/docs-hub/mr-plan`은 run summary와 filesystem artifact를 기반으로 파일 목록을 만든다.

추가해야 할 판단:

- publishable doc만 기본 포함
- failed quality doc은 excluded
- warning doc은 policy에 따라 blocked 또는 review required
- deprecated candidates 포함
- unsupported claim이 있으면 blocked
- manual coverage fail이면 blocked

### 10.2 응답 확장

`GET /api/docs-hub/mr-plan?run=...`

추가 필드:

- `readiness`: ready|blocked|partial|not_created|stale
- `blocked_reason`
- `quality_summary`
- `included_files`
- `excluded_files`
- `deprecated_candidates`
- `review_checklist`
- `requires_override`

### 10.3 Submit Guard

`POST /api/docs-hub/submit-mr`

추가 정책:

- `readiness=blocked`면 기본 제출 거부
- override는 별도 권한/confirm 필요
- override audit detail에 quality findings 요약 기록

---

## 11. Cost and Quality API

### 11.1 Costs 확장

`GET /api/costs`

추가 집계:

- cost per publishable doc
- cost per quality failed run
- average repair attempts
- tokens by agent role
- tokens by quality gate
- unsupported claim count by model

### 11.2 Quality Dashboard

신규:

`GET /api/quality/summary?window=168`

반환:

- pass rate
- publishable rate
- failed gate distribution
- warning trend
- repair attempt trend
- coverage fail trend
- unsupported claim trend
- top failing sources

---

## 12. Security and Audit

### 12.1 Secret Handling

원칙:

- frontend API는 secret value 미반환
- runner context만 secret value 복호화
- audit detail에 secret, token, VNC password 저장 금지
- evidence item 저장 전 redaction
- VNC session token은 단기 만료

### 12.2 VNC Security

필수:

- `view_only=true` session만 frontend 연결 허용
- gateway에서 keyboard/mouse/clipboard frame 차단
- session expiry 강제
- raw VNC password 미반환
- raw IP/port는 masked label로 표시
- viewer open/close/reconnect audit 기록

### 12.3 Audit Actions

추가 audit action:

- `manual_profile.update`
- `manual_profile.preflight`
- `scenario_set.create`
- `scenario_set.update`
- `scenario_set.activate`
- `artifact.preflight`
- `vnc_session.open`
- `vnc_session.close`
- `mr_submit.override`
- `quality_override.apply`

---

## 13. Implementation Phases

### Phase 1: Contract Foundation

목표: frontend가 새 상태를 안전하게 읽을 수 있게 한다.

작업:

- run status enum 확장
- `runs.publishable`, `publish_state`, `quality_status`, `blocked_reason`, `snapshot_version` 추가
- `run_events`에 `event_id`, `seq`, `kind`, `severity`, `role` 추가
- `/api/runs/{run_id}/events` seq replay API 추가
- `/api/run-summary` optional quality/evidence/coverage/artifact/vnc/mr 필드 추가
- `/api/pipelines/status` quality/publishable 필드 추가
- WebSocket envelope에 `latest_seq`, `snapshot_version` 추가
- heartbeat webhook과 stuck run reaper 추가

완료 기준:

- 구버전 run도 summary가 깨지지 않는다.
- frontend는 `failed_quality_gate`를 표시할 수 있다.
- duplicate event가 DB에 중복 저장되지 않는다.
- runner가 complete 없이 죽어도 timeout 뒤 `timeout` 또는 `failed`로 수렴한다.

### Phase 2: Quality and Evidence Resources

목표: AI output quality를 API resource로 만든다.

작업:

- `run_quality_reports`
- `run_quality_findings`
- `run_evidence_packs`
- `run_evidence_items`
- `run_doc_outputs`
- `/api/webhook/quality`
- `/api/webhook/evidence`
- `/api/runs/{run_id}/quality`
- `/api/runs/{run_id}/evidence`
- MR plan quality guard

완료 기준:

- critic/verifier 결과가 run summary와 quality endpoint에 남는다.
- evidence item을 doc section에서 역추적할 수 있다.
- quality fail run은 MR submit이 기본 차단된다.

### Phase 3: Manual Profile, Scenario, Artifact, Coverage

목표: manual-automation을 source별 운영 설정으로 관리한다.

작업:

- `source_manual_profiles`
- `manual_scenario_sets`
- `run_artifacts`
- `run_coverage_reports`
- manual profile CRUD
- scenario CRUD/lint/activate
- artifact preflight
- coverage webhook/query
- runner context에 manual profile/scenario/artifact config 추가

완료 기준:

- source별 MCP endpoint/scenario/artifact 설정이 가능하다.
- manual run은 global env 대신 source profile을 사용한다.
- coverage threshold fail이 publishability에 반영된다.

### Phase 4: VNC Monitoring API

목표: mcp-vnc remote control을 frontend에서 view-only로 모니터링한다.

작업:

- `run_vnc_sessions`
- `/api/webhook/vnc-session`
- `/api/runs/{run_id}/vnc-session`
- `/api/runs/{run_id}/vnc/ws`
- VNC gateway token 발급
- view-only frame enforcement
- audit open/close/reconnect

완료 기준:

- pipeline이 제공한 ip/port로 backend gateway가 VNC에 연결한다.
- frontend는 `react-vnc`로 view-only 모니터링한다.
- 사용자 입력은 gateway에서 차단된다.
- VNC 연결 실패가 pipeline failure로 오인되지 않는다.

### Phase 5: Operations Hardening

목표: 장기 운영 가능한 API 안정성을 확보한다.

작업:

- heartbeat webhook
- stuck run reaper
- terminal transition guard 강화
- static sha advance CAS
- manual processed release pointer
- quality/cost summary API
- OpenAPI schema response_model 정리
- pagination/cursor 표준화
- audit coverage 확대

완료 기준:

- pending/running stuck run이 timeout 처리된다.
- late complete가 terminal data를 오염시키지 않는다.
- pipeline dashboard와 run detail이 snapshot+replay로 복원된다.

---

## 14. Test Plan

### 14.1 API Contract Tests

추가 테스트:

- `/api/run-summary`가 quality/evidence/coverage/artifact/vnc 필드를 optional로 반환
- 구버전 run은 `not_evaluated` fallback
- `failed_quality_gate` status가 pipeline status에 반영
- pipeline status에 publishable/window quality 집계 반영

### 14.2 Event Idempotency Tests

추가 테스트:

- 같은 `(run_id, event_id)` 재전송은 중복 저장하지 않음
- 같은 `(run_id, seq)` 다른 payload는 409
- replay API가 `after_seq` 이후 event만 반환
- WebSocket message에 latest_seq 포함

### 14.3 Quality/Evidence Tests

추가 테스트:

- quality webhook upsert
- blocking finding이 run publishable=false로 반영
- evidence item pagination
- unsupported claim count가 summary에 반영
- MR plan이 quality fail doc을 제외 또는 block

### 14.4 Manual Tests

추가 테스트:

- manual profile CRUD는 secret value를 반환하지 않음
- preflight가 missing MCP endpoint를 error로 반환
- scenario lint가 unknown tool을 error로 반환
- artifact preflight가 asset mismatch를 warning/error로 반환
- coverage fail이 `failed_quality_gate`로 반영

### 14.5 VNC Tests

추가 테스트:

- VNC session endpoint는 `view_only=true`만 websocket URL 반환
- `view_only=false` session은 403/409
- VNC token 만료 후 연결 거부
- keyboard/mouse/clipboard frame drop
- VNC 연결 error가 run status를 failed로 바꾸지 않음
- audit에 viewer open/close 기록

### 14.6 Runner Context Tests

추가 테스트:

- manual run context에 source별 manual profile 포함
- 두 source가 서로 다른 MCP endpoint/scenario set을 받음
- frontend API에는 secret value 없음
- runner context에는 필요한 secret value만 포함

---

## 15. Acceptance Criteria

백엔드 API 개선은 다음 조건을 만족해야 한다.

- frontend는 단일 run summary 호출만으로 run status, publishability, quality, evidence, coverage, artifact, VNC availability를 판단할 수 있다.
- quality/evidence/coverage/artifact/VNC 정보는 event replay 없이도 별도 endpoint로 조회 가능하다.
- runner event webhook은 idempotent하고 seq replay가 가능하다.
- WebSocket overflow/reconnect 후 frontend가 snapshot+replay로 동일 상태를 복원할 수 있다.
- manual source는 API로 MCP profile, scenario set, artifact selector, coverage threshold, VNC monitor 설정을 관리한다.
- mcp-vnc는 backend gateway를 통해 view-only로만 frontend에 노출된다.
- quality fail 또는 coverage fail run은 `done`으로 publish되지 않는다.
- MR submit은 publishable=false run을 기본 차단한다.
- secret/token/VNC password는 frontend API와 audit log에 노출되지 않는다.

---

## 16. Priority Backlog

### P0

- run status enum 확장
- run summary에 `publishable`, `publish_state`, `quality`, `blocked_reason` 추가
- event `event_id`/`seq` 저장 및 dedupe
- seq replay API
- heartbeat webhook
- stuck run reaper
- quality report/finding DB + webhook/query
- MR plan quality guard
- runner context output contract

### P1

- evidence pack DB + webhook/query
- doc output metadata
- pipeline status quality fields
- manual profile CRUD
- scenario set CRUD/lint
- artifact preflight/run artifact API
- coverage webhook/query

### P2

- VNC session DB
- VNC session webhook/query
- VNC websocket gateway
- quality/cost summary API
- audit expansion

### P3

- manual processed release pointer
- static sha CAS/ancestry API integration
- quality override workflow
- advanced WS subscription filters
- cursor pagination standardization

---

## 17. Summary

백엔드 API의 핵심 변화는 `run_events` 중심의 관측 로그 시스템에서, 품질과 근거가 구조화된 운영 API로 전환하는 것이다.

가장 먼저 해야 할 일은 run summary/status contract를 확장하고 event idempotency/replay를 보장하는 것이다. 그 다음 quality/evidence를 first-class resource로 만들고, manual profile/scenario/artifact/coverage를 source별 API로 승격한다. 마지막으로 mcp-vnc view-only gateway와 heartbeat/reaper를 붙이면, 프런트엔드는 AI 문서화 파이프라인을 신뢰 가능한 운영 화면으로 제공할 수 있다.

---

## 18. Cross-Document Review Updates

Frontend, data-plane, AI-agent 계획과 대조한 결과, backend API 계획에 아래 보강을 추가한다.

### 18.1 Server-Assigned Seq Policy

runner가 `seq`를 보내더라도 최종 ordering source of truth는 Control Plane이어야 한다.

정책:

- runner가 보낸 `seq`는 `runner_seq`로 보존한다.
- Control Plane은 DB insert 시 run별 monotonic `seq`를 할당한다.
- runner 재시도 dedupe는 `event_id`와 `dedupe_key`로 처리한다.
- replay API의 `after_seq`는 server-assigned seq 기준이다.

이렇게 해야 다중 batch retry, runner 재시작, out-of-order webhook이 frontend replay 순서를 깨지 않는다.

### 18.2 Warning Publish Policy

boolean `publishable`만으로는 warning 문서를 "차단"과 "review 필요"로 구분하기 어렵다. 다른 문서와 대조하면 warning 문서를 MR에 포함하되 review-required로 둘 필요가 있다.

수정 정책:

- `quality.status=pass`: publishable=true
- `quality.status=warning`: `warning_publish_policy`에 따라 `review_required` 또는 `blocked`
- `quality.status=fail`: publishable=false
- `done_with_warnings`는 자동 승인/자동 머지 금지
- MR submit은 warning publish 시 explicit confirm과 audit detail을 요구

추가 필드:

- `publish_state`: publishable|review_required|blocked|unknown
- `warning_publish_policy`: block|review_required

### 18.3 VNC Gateway Boundary

VNC gateway는 frontend-facing API가 아니라 streaming control boundary다.

보강:

- `/api/runs/{run_id}/vnc-session`은 signed websocket URL만 발급한다.
- `/api/runs/{run_id}/vnc/ws`는 FastAPI WebSocket route로 분리한다.
- gateway는 input frame을 drop하는 것에 더해, upstream이 view-only를 지원하지 않으면 연결 자체를 거부한다.
- VNC frame은 evidence DB에 저장하지 않는다.
- evidence screenshot은 runner가 별도 artifact로 저장한 것만 등록한다.

### 18.4 Agent Bundle Ingestion

AI-agent 계획의 Final Packager output bundle을 API가 직접 받을 수 있어야 한다.

추가 endpoint 옵션:

- `POST /api/webhook/final-pack`

역할:

- evidence manifest
- quality report
- doc outputs
- coverage report
- artifact report
- MR summary

를 한 번에 검증하고 부분 실패를 명확히 반환한다.

정책:

- bundle 내부 item은 개별 resource webhook schema와 동일해야 한다.
- partial ingest가 발생하면 run은 `partial` 또는 `failed_quality_gate`로 normalize한다.
- 개별 webhook은 유지하되, final pack은 runner 완료 직전 consistency check로 사용한다.

### 18.5 Frontend Degrade Contract

Frontend 계획과 맞추기 위해 조회 API 실패는 run failure와 분리한다.

응답 정책:

- quality resource 없음: `quality.status=not_evaluated`
- coverage 없음: `coverage.status=not_applicable`
- VNC 없음: `vnc.available=false`
- evidence 없음: `evidence.item_count=0`, `evidence.missing=true`
- API read failure: 5xx와 함께 run status는 변경하지 않음

UI가 run failure로 오인하지 않도록 `data_availability` 필드를 summary에 추가한다.

### 18.6 Final Priority Reconciliation

마지막 상호 리뷰 기준으로 priority를 아래처럼 확정한다.

- heartbeat/reaper는 P0이다. runner launch/crash가 pending/running으로 고착되는 문제는 운영 신뢰성의 선행 조건이다.
- `publish_state`는 P0이다. frontend와 MR submit guard가 warning/review/block 상태를 같은 방식으로 해석해야 한다.
- `final-pack` webhook은 P1이다. quality/evidence/doc output을 한 번에 consistency check해야 MR guard가 견고해진다.
- VNC gateway는 P2다. remote monitor는 중요하지만 문서 품질과 run terminal 정합성보다 뒤에 둔다.
