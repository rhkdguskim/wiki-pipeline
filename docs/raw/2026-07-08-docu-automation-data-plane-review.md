---
title: Backend Data Plane Docu-Automation Review
date: 2026-07-08
scope: backend data plane, static docu-automation, control-plane events, frontend live monitoring
status: review
---

# Backend Data Plane Docu-Automation Review

이 리뷰는 `static` docu-automation 파이프라인을 팀 운영 파이프라인으로 쓰기 전 막아야 할 결함과 개선점을 정리한다. 범위는 Data Plane 실행 흐름(`backend/runner`, `backend/static_pipeline`, `backend/common_pipeline`), Control Plane webhook/DB/WS 경계(`backend/controlplane`), 프런트엔드 실시간 이벤트 소비(`frontend/src`)다.

## 현재 흐름

1. Control Plane이 `/api/runs/trigger`에서 `Run` row를 `pending`으로 만들고 runner subprocess를 띄운다.
   - `backend/controlplane/api.py:395`
   - `backend/controlplane/services/runs.py:41`

2. Runner는 `/api/runner/context`에서 source, branch, doc target을 가져오며 이 응답에는 복호화된 SCM/doc target token이 포함된다.
   - `backend/runner/job.py:121`
   - `backend/controlplane/api.py:1039`

3. `static` 실행은 `auto` 모드에서 `last_processed_sha` 유무로 `init` 또는 `diff`를 선택한다.
   - diff: compare -> theme mapping -> theme별 writer/critic/lint -> save -> local state advance
   - init: plan -> map summaries -> reduce docs -> local state advance
   - `backend/runner/job.py:40`
   - `backend/static_pipeline/runner.py:22`
   - `backend/static_pipeline/init_runner.py:181`

4. 실행 이벤트는 `Observer`가 local JSONL에 쓰고, `WebhookEventSink`가 `/api/webhook/events`로 batch push한다. Control Plane은 `run_events`에 적재하고 `Run` 상태와 token usage를 갱신한다.
   - `backend/common_pipeline/run_context.py:16`
   - `backend/common/observer.py:39`
   - `backend/runner/client.py:44`
   - `backend/controlplane/services/runs.py:115`

5. 생성 산출물은 `projection_summary()`를 거쳐 docs-hub MR/PR plan이 되고, 제출 성공 후 `/api/webhook/complete`가 DB run과 source branch pointer를 갱신한다.
   - `backend/runner/job.py:47`
   - `backend/common/docshub.py:109`
   - `backend/common/docshub.py:202`
   - `backend/controlplane/services/runs.py:179`

## Findings

### P0. Runner launch/crash leaves runs permanently pending or running

`RunService.launch_runner()`는 `Popen` 실패 시 `None`만 반환하고 run row를 실패로 바꾸지 않는다. 스케줄 경로는 반환값도 확인하지 않는다. runner가 context 조회 전 죽거나 complete webhook 전 죽으면 heartbeat/reaper가 없어 run이 영구 `pending` 또는 `running`으로 남는다.

근거:
- `backend/controlplane/services/runs.py:57`
- `backend/controlplane/api.py:412`
- `backend/controlplane/services/scheduler.py:229`
- `backend/runner/job.py:121`

영향:
- 대시보드는 계속 실행 중으로 보이고, 실제 배치는 멈춘다.
- `last_processed_sha`가 전진하지 않아 다음 배치가 계속 같은 구간을 다시 잡을 수 있다.

개선:
- `launch_runner()` 실패 시 즉시 `Run.status=failed`, `error=runner launch failed`로 complete 처리한다.
- `runs`에 `runner_pid`, `started_at`, `heartbeat_at`, `attempt`를 추가한다.
- `pending/running` timeout reaper를 스케줄러에 추가한다.
- runner는 context 조회 직후 heartbeat 또는 `run running` event를 보장한다.

Acceptance:
- `Popen` 실패 테스트에서 `/api/pipelines/status`가 failed를 즉시 보여야 한다.
- complete 없이 죽은 runner는 설정된 timeout 뒤 failed가 되어야 한다.

### P0. Init partial failure can be reported as done without sha advance

`init` reduce 단계는 theme 예외를 `summary["docs"][theme] = {"error": ...}`로 기록하고 계속 진행한다. 일부 theme만 성공하면 state advance를 skip하고도 `ctx.done()`을 호출한다. map summary 전멸도 `ctx.failed()` 후 summary를 반환한다. 이후 `job.execute()`는 `last_processed_sha`가 없어도 status `done`으로 complete한다.

근거:
- `backend/static_pipeline/init_runner.py:123`
- `backend/static_pipeline/init_runner.py:154`
- `backend/static_pipeline/init_runner.py:172`
- `backend/static_pipeline/init_runner.py:273`
- `backend/runner/job.py:142`

영향:
- 운영자는 성공으로 보지만 pointer가 전진하지 않는다.
- 다음 run이 같은 init 작업을 반복한다.
- docs-hub MR이 일부 문서만 포함되거나 아예 없는데도 done으로 기록될 수 있다.

개선:
- terminal status에 `partial`을 도입하거나, v1에서는 partial을 `failed`로 처리한다.
- `job.execute()`는 static 성공 조건을 명시적으로 검사해야 한다.
  - diff no-op: `changed/sources=0`이고 `last_processed_sha` 있음
  - generated success: `doc_count > 0`, 모든 requested theme saved, `last_processed_sha` 있음
  - init: 모든 requested theme이 error 없이 saved, `last_processed_sha` 있음
- `summary["errors"]`, `summary["partial"]`를 pipeline summary 계약에 추가한다.

Acceptance:
- init theme 1개 실패 시 complete payload가 `status=failed` 또는 `partial`이어야 한다.
- sha 미전진 run이 `done`으로 저장되지 않아야 한다.

### P0. Complete webhook has no terminal transition guard

`ingest_events()`는 done/failed 상태를 stale event가 덮지 못하게 보호하지만, `complete_run()`은 `run.status = status`를 무조건 수행한다. 늦게 도착한 complete webhook이나 재시도 오염이 `done -> failed`, `failed -> done`을 만들 수 있다.

근거:
- `backend/controlplane/services/runs.py:134`
- `backend/controlplane/services/runs.py:183`

영향:
- DB run row가 이벤트 스트림보다 더 권위 있으므로 화면과 집계가 잘못된다.
- stale complete가 `mr_url`, `doc_count`, `error`를 덮을 수 있다.

개선:
- complete에도 terminal transition guard를 둔다.
- `pending/running -> done/failed`만 허용한다.
- 같은 `run_id` complete 재호출은 idempotent response를 반환하되 기존 terminal data를 바꾸지 않는다.
- 장기적으로 `attempt` 또는 signed completion token을 도입한다.

Acceptance:
- done run에 failed complete를 보내도 status, mr_url, doc_count가 바뀌지 않아야 한다.
- failed run에 done complete를 보내도 사람이 명시적으로 retry run을 만들기 전에는 바뀌지 않아야 한다.

### P1. SHA advance uses lexicographic comparison, not Git ancestry/CAS

`complete_run()`은 `new_sha >= current` 문자열 비교로 pointer regression을 막는다. Git SHA 사전순은 커밋 위상이나 시간과 무관하다.

근거:
- `backend/controlplane/services/runs.py:201`
- `backend/tests/test_controlplane_api.py:446`

영향:
- 정상 최신 commit이 사전순으로 작으면 pointer 전진이 거부된다.
- 과거 commit이 사전순으로 크면 잘못 수락될 수 있다.
- 동시 run에서는 오래된 run이 최신 pointer를 덮는 문제가 남는다.

개선:
- run 생성 시 `from_sha_snapshot`을 저장한다.
- complete 시 현재 pointer가 `from_sha_snapshot`과 같은 경우에만 전진하는 CAS를 적용한다.
- pointer가 달라졌으면 run을 `stale_complete`로 기록하고 sha 전진 없이 완료한다.
- 필요 시 SCM connector의 compare/ancestry check로 fast-forward 관계를 확인한다.

Acceptance:
- 두 run이 같은 source/branch에서 동시에 생성되면 먼저 완료된 run만 pointer를 바꾸고, 늦은 run은 stale로 남아야 한다.
- 문자열 사전순 테스트 대신 CAS/ancestry 테스트가 있어야 한다.

### P1. Runner event delivery is at-most-once and not deduplicated

`push_events()`는 retry가 없고, `WebhookEventSink._flush()`는 실패 배치를 조용히 버린다. 반대로 재전송이 추가되면 현재 DB는 `(run_id,event_id)`가 없어 중복 row와 token usage 중복 누적이 발생한다.

근거:
- `backend/runner/client.py:28`
- `backend/runner/client.py:81`
- `backend/controlplane/services/runs.py:125`
- `backend/controlplane/services/runs.py:147`

영향:
- Control Plane DB와 frontend timeline이 local JSONL 감사 로그보다 작을 수 있다.
- token/cost 집계가 이벤트 유실 또는 중복에 취약하다.

개선:
- 모든 event에 `seq` 또는 `event_id`를 추가한다.
- `run_events`에 `(run_id, seq)` unique constraint를 둔다.
- runner sink는 retry/backoff를 적용하고 실패 batch를 local replay queue에 남긴다.
- complete 직전에 미전송 이벤트 flush 결과를 확인하거나, complete payload에 `last_event_seq`를 포함한다.

Acceptance:
- webhook events를 같은 batch로 두 번 보내도 DB row와 token usage가 한 번만 반영되어야 한다.
- 일시적 500/timeout 뒤 retry로 이벤트가 복구되어야 한다.

### P1. WebSocket overflow can silently strand the frontend in connected state

느린 WS 클라이언트 큐가 가득 차면 서버는 client를 `_clients` set에서 제거하지만 socket을 닫거나 overflow message를 보내지 않는다. 프런트는 여전히 `connected` 상태라 `useRunStream`이 이벤트 폴링을 중단한 채 이후 이벤트를 영구히 못 받는다.

근거:
- `backend/controlplane/ws.py:102`
- `backend/controlplane/ws.py:106`
- `frontend/src/store/liveSocket.js:3`
- `frontend/src/hooks/useRunStream.js:149`

영향:
- 장시간 실행되는 docu-automation run에서 가장 중요한 실시간 진행 화면이 멈춘다.
- 사용자는 연결이 정상이라고 오인한다.

개선:
- overflow 시 해당 websocket을 실제 close한다.
- 또는 per-client queue에 sentinel을 넣고 frontend가 fallback polling으로 전환하게 한다.
- 현재 frontend가 기대하는 `type: "overflow"` 메시지를 backend가 실제로 발행하도록 계약을 맞춘다.

Acceptance:
- queue overflow 테스트에서 브라우저가 fallback으로 전환하고 `/api/events`를 즉시 poll해야 한다.

### P1. WS events do not advance frontend polling offset, causing duplicate KPIs after fallback

`useRunStream`은 WS로 받은 events를 ingest하지만 DB offset은 갱신하지 않는다. 이후 WS가 끊기면 `/api/events?offset=0`부터 다시 읽고 이미 반영한 usage/tool events를 다시 ingest한다. `ingest()`는 idempotent하지 않아 token, tool calls, feed가 중복된다.

근거:
- `frontend/src/hooks/useRunStream.js:81`
- `frontend/src/hooks/useRunStream.js:115`
- `frontend/src/lib/ingest.js:89`

영향:
- Trace/Costs UI의 live KPI가 실제보다 커진다.
- fallback 전환이 잦은 환경에서 run 품질/비용 판단이 틀어진다.

개선:
- WS `events` message에 DB `offset` 또는 event `id/seq`를 포함한다.
- frontend state에 `seenEventIds`를 두고 idempotent ingest를 보장한다.
- fallback 진입 시 summary snapshot으로 상태를 리셋하고 서버 offset을 동기화한다.

Acceptance:
- WS로 usage event 수신 후 fallback poll을 해도 token count가 증가하지 않아야 한다.

### P1. `run_status` does not immediately refresh selected run summary

`useLiveSocket`은 `run_status` 수신 시 React Query `['runSummary', run_id]`를 invalidate하지만, `useRunStream`은 React Query가 아니라 수동 `getRunSummary()` interval을 쓴다. 즉시 refetch가 일어나지 않고 최대 30초 stale일 수 있다.

근거:
- `frontend/src/hooks/useLiveSocket.js:85`
- `frontend/src/hooks/useRunStream.js:43`

영향:
- run 완료/실패 표시, MR 버튼, overview narrative가 늦게 바뀐다.
- docu-automation이 끝났는데도 상세 화면은 running/stalled로 남을 수 있다.

개선:
- `useRunStream`이 `run_status` message를 직접 처리해 `runSummary`를 즉시 fetch한다.
- 더 나은 방향은 `runSummary`를 `useQuery(['runSummary', runId])`로 옮기고 live socket invalidation을 실제로 연결하는 것이다.

Acceptance:
- `/api/webhook/complete` 호출 직후 선택된 run 상세 상태가 done/failed로 바뀌어야 한다.

### P1. Local file state advances before MR submission

`static_pipeline.runner`는 `_state.json`을 MR 제출 전에 갱신한다. MR 제출 실패 시 Control Plane DB pointer는 전진하지 않지만 local state는 전진한다.

근거:
- `backend/static_pipeline/runner.py:95`
- `backend/runner/job.py:138`
- `backend/runner/job.py:150`

영향:
- DB SoT와 legacy/file-mode state가 갈라진다.
- CLI/local run을 같이 쓰면 누락 구간이 생길 수 있다.

개선:
- 운영 모드에서는 CP DB pointer만 진실로 둔다.
- local `_state.json`은 standalone CLI 전용으로 분리하거나, MR 성공 후 갱신한다.
- summary에는 proposed pointer만 넣고 실제 pointer advance는 Control Plane complete에서만 수행한다.

Acceptance:
- MR 제출 실패 시 DB와 local state 모두 전진하지 않아야 한다. standalone CLI는 별도 테스트로 유지한다.

### P1. Trigger path accepts invalid pipeline/mode/branch states

`/api/runs/trigger`는 `pipeline_id`, `mode`, `branch_role`을 느슨하게 받아 run을 만든다. runner는 unknown pipeline을 사실상 static 경로로 처리하고, disabled/missing branch도 context에 내려간다.

근거:
- `backend/controlplane/api.py:403`
- `backend/controlplane/api.py:1071`
- `backend/runner/job.py:132`

영향:
- 잘못된 pipeline id가 운영 run으로 남는다.
- release/manual/static 경계가 흐려져 docu-automation run 분석이 어려워진다.

개선:
- `create_run()` 또는 trigger API에 공통 validator를 둔다.
- allowed pipeline: `static`, `manual`
- static mode: `auto`, `init`, `diff`
- branch role: `dev`, `release`
- source branch가 없거나 disabled이면 400으로 거부한다.
- runner도 unknown pipeline을 fallback하지 말고 fail fast해야 한다.

Acceptance:
- invalid pipeline/mode/branch_role 요청은 run row를 만들지 않아야 한다.

### P2. WS publish occurs before transaction commit

서비스는 `db.flush()` 뒤 바로 `_publish()`를 호출하고, 실제 commit은 FastAPI dependency가 route 반환 후 수행한다. WS를 받은 프런트가 즉시 refetch하면 commit 전 DB를 읽어 stale data를 캐시할 수 있다.

근거:
- `backend/controlplane/api.py:61`
- `backend/controlplane/services/runs.py:152`
- `backend/controlplane/services/runs.py:231`

영향:
- 실시간 push가 오히려 stale query refresh를 유발할 수 있다.
- run_status 직후 pipeline status가 이전 값을 보여줄 수 있다.

개선:
- publish를 route commit 이후로 이동한다.
- 또는 service가 publish message를 반환하고 route가 commit 후 publish한다.
- transaction outbox 패턴을 쓰면 더 견고하다.

Acceptance:
- WS 수신 직후 refetch한 `/api/run-summary`와 `/api/pipelines/status`가 최신 DB 상태를 읽어야 한다.

### P2. Pipeline health/cost/overview queries are not invalidated on run events

프런트 주석은 `run_status/runs_changed`가 pipeline status refetch를 담당한다고 하지만 실제 `handleMessage`는 `pipelineStatus`, `overview`, `costs`를 invalidate하지 않는다.

근거:
- `frontend/src/hooks/queries.js:78`
- `frontend/src/hooks/useLiveSocket.js:85`

영향:
- PipelineStatusPage의 성공/실패/실행 중/토큰 집계가 WS connected 상태에서도 최대 60초 늦다.
- 비용 화면도 run completion 직후 최신 usage를 반영하지 않는다.

개선:
- `run_status`, `runs_changed`에서 `pipelineStatus`, `overview`, `costs`를 invalidate한다.
- `events` 중 usage event가 오면 costs는 debounce invalidation한다.

Acceptance:
- run 완료 직후 pipeline status table과 cost KPI가 갱신되어야 한다.

### P2. Verbose filtering is inconsistent between WS and run-summary

`verbose=0` WS는 `agent_step/thinking` 이벤트를 필터하지만, `run-summary` timeline은 thinking을 모두 포함한다. `stateFromRunSummary()`가 summary timeline을 feed로 다시 넣기 때문에 기본 모드에서 숨긴 thinking이 summary refresh 후 다시 표시된다.

근거:
- `backend/controlplane/ws.py:28`
- `backend/controlplane/projection.py:134`
- `frontend/src/lib/ingest.js:45`

영향:
- 사용자가 verbose off로 줄인 노이즈가 다시 나타난다.
- 실시간 feed와 summary feed가 다른 정책으로 보인다.

개선:
- `/api/run-summary`에 `verbose=0|1` query를 추가해 동일 필터를 적용한다.
- 또는 frontend에서 `wsVerbose=false`일 때 summary timeline의 thinking을 필터한다.

Acceptance:
- verbose off 상태에서 refresh 후에도 thinking event가 feed에 나타나지 않아야 한다.

### P2. Reconnect can be disabled after verbose toggle

`useLiveSocket` cleanup은 `closedByUsRef.current = true`로 설정하지만 다음 effect run에서 다시 `false`로 되돌리지 않는다. `wsVerbose` 변경 등으로 effect가 재실행된 뒤 새 socket이 예기치 않게 닫히면 `onclose`가 reconnect를 건너뛸 수 있다.

근거:
- `frontend/src/hooks/useLiveSocket.js:31`
- `frontend/src/hooks/useLiveSocket.js:57`
- `frontend/src/hooks/useLiveSocket.js:71`

영향:
- 설정 변경 후 live monitoring이 fallback으로 고정될 수 있다.

개선:
- `connect()` 시작 전에 `closedByUsRef.current = false`로 재설정한다.
- close code 4401은 retry하지 말고 auth toast를 띄운다.

Acceptance:
- verbose toggle 후 WS를 강제 종료해도 backoff reconnect가 수행되어야 한다.

## Docu-Automation Quality Gate 개선

현재 `verified_generate()`는 format/lint/critic이 계속 fail해도 hard cap 이후 `auto_generated_warning`을 붙이고 저장한다. 이는 MR 사람 리뷰 게이트와 맞지만, 운영 성공의 의미를 흐린다.

근거:
- `backend/common_pipeline/verify.py:72`
- `backend/common_pipeline/verify.py:184`
- `backend/static_pipeline/runner.py:84`
- `backend/runner/job.py:142`

개선 정책:
- `warned` 문서를 생성한 run은 `done_with_warnings` 또는 `done` + `quality=warning`으로 명시한다.
- MR 본문에 warned theme, critic feedback, lint errors, source_files, token usage를 넣는다.
- pipeline status는 warning count를 별도 KPI로 표시한다.

Acceptance:
- critic fail hard cap 문서는 MR에는 포함되지만 run summary와 pipeline status에서 warning으로 보여야 한다.
- warning 문서가 있는 run의 자동 머지 또는 자동 승인 경로는 없어야 한다.

## 권장 구현 순서

### 1단계: 상태 정합성

- runner launch 실패 즉시 failed 처리
- stale pending/running reaper
- init partial failure terminal status 정리
- complete webhook terminal guard
- trigger validator
- sha advance CAS

### 2단계: 이벤트 신뢰성

- event seq/id 추가
- event webhook retry + dedupe
- WS overflow close/fallback 계약 구현
- publish-after-commit 또는 outbox
- frontend offset/de-dupe 적용

### 3단계: 프런트 실시간성

- selected run `run_status` 즉시 summary refresh
- `pipelineStatus`, `overview`, `costs` invalidation
- verbose filtering 일관화
- reconnect lifecycle 수정

### 4단계: 품질/운영 게이트

- warning quality status 도입
- MR 본문에 근거/경고/비용/변경구간 포함
- daily digest, cost budget, token usage alert
- run retry/replay UX

## 테스트 보강 목록

- `test_launch_runner_failure_marks_run_failed`
- `test_running_run_without_heartbeat_is_reaped`
- `test_init_partial_failure_is_not_done`
- `test_complete_run_terminal_status_not_overwritten`
- `test_complete_run_uses_pointer_cas_not_lexicographic_sha`
- `test_webhook_events_deduplicates_by_sequence`
- `test_webhook_event_retry_replays_failed_batch`
- `test_ws_overflow_forces_client_fallback`
- `test_frontend_ws_to_fallback_does_not_duplicate_usage`
- `test_run_status_refreshes_selected_run_summary_immediately`
- `test_run_status_invalidates_pipeline_status_overview_costs`
- `test_verbose_filter_matches_summary_and_ws`

## 최종 판단

현재 구조는 Control/Data Plane 분리, DB source of truth, 진행 이벤트, MR 리뷰 게이트라는 큰 방향은 맞다. 다만 팀 운영 파이프라인으로 쓰기에는 terminal state, pointer advance, event delivery, frontend fallback의 정합성이 아직 약하다.

가장 먼저 막아야 할 것은 `done`의 의미다. sha가 전진하지 않았거나 partial failure인 run이 done으로 보이면 운영자가 신뢰할 수 없다. 그 다음은 이벤트 경로다. WS가 connected로 보이는데 실제로는 discard된 상태, fallback 후 KPI 중복 집계, event 중복/유실은 docu-automation 품질 판단과 비용 판단을 모두 흔든다.

## Cross-Document Review Updates

Frontend/API/AI-agent 계획과 대조한 결과, static docu-automation 리뷰에 아래 보강을 추가한다.

### Status and Quality Contract

- `done`은 실행 성공이 아니라 publish 가능한 산출물이 있을 때만 사용한다.
- critic hard-cap 이후 문서가 저장되면 run은 `done_with_warnings` 또는 `failed_quality_gate`로 normalize한다.
- quality 판정값은 `pass | warning | fail | not_evaluated`로 표준화한다.
- run summary에는 `publishable`, `blocked_reason`, `quality.status`, `quality.failed_gate`가 있어야 한다.

### Evidence as API Resource

Static pipeline의 diff/file/symbol 근거는 event payload와 markdown frontmatter에만 남기지 않는다.

추가 요구:

- Evidence Builder가 `run_evidence_packs`와 `run_evidence_items`에 저장 가능한 evidence manifest를 생성한다.
- Theme writer는 evidence id만 인용한다.
- generated doc별 `evidence_count`, `unsupported_claim_count`, `schema_status`, `mermaid_status`를 `run_doc_outputs`로 기록한다.
- `/api/runs/{run_id}/evidence`와 `/api/runs/{run_id}/quality`가 static run도 동일하게 지원해야 한다.

### Event Replay Contract

기존 offset 기반 `/api/events`는 호환용으로 유지하되, static pipeline 개선 기준은 seq 기반이다.

추가 요구:

- runner event는 `event_id`, `seq`, `kind`, `severity`, `role`, `dedupe_key`를 포함한다.
- Control Plane은 `(run_id, event_id)`와 `(run_id, seq)`를 dedupe한다.
- WebSocket은 `latest_seq`와 `snapshot_version`을 포함한다.
- frontend fallback은 마지막 seq 이후 replay로 복원한다.

### MR Guard

Static MR plan은 quality-aware여야 한다.

- `quality.status=fail` 문서는 기본적으로 MR 포함 금지
- `quality.status=warning` 문서는 `publish_state=review_required` 또는 policy 기반 `blocked`
- `publishable=false` run은 submit MR 기본 차단
- MR body에는 failed gate, warning count, evidence pack id, unsupported claim count를 포함

### Final Review Corrections

마지막 상호 리뷰 기준으로 static pipeline의 terminal 처리와 MR 정책을 아래처럼 정리한다.

- Runner는 quality warning을 run status로 직접 결정하지 않고 quality report를 먼저 제출한다.
- Control Plane이 quality report와 policy를 보고 `done`, `done_with_warnings`, `failed_quality_gate`를 normalize한다.
- `done_with_warnings`는 자동 성공이 아니라 `publish_state=review_required`로 표시한다.
- heartbeat/reaper는 P0이며, complete 없는 runner crash는 반드시 `timeout` 또는 `failed`로 수렴해야 한다.
- static final output은 `quality-report`, `evidence-manifest`, `doc-outputs`가 모두 ingest된 뒤에만 complete 가능하다.
