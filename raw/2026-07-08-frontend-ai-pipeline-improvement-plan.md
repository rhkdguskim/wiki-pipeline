# Frontend AI Pipeline Improvement Plan

작성일: 2026-07-08
대상: `docu-automation`, `manual-automation`, AI agent output-quality pipeline을 운영하는 프런트엔드
전제: backend data-plane의 실행/이벤트/품질 게이트 개선은 반영된 상태로 본다.

---

## 1. 목표

프런트엔드는 단순히 "실행 중/완료"를 보여주는 뷰가 아니라, AI 문서화 파이프라인의 품질, 근거, 커버리지, 배포 가능성을 운영자가 즉시 판단하는 control room이어야 한다.

이번 개선의 목표는 다음 4가지다.

1. `done`과 `good output`을 분리한다.
2. AI가 왜 해당 문서를 만들었는지 evidence와 critic verdict를 화면에서 추적 가능하게 한다.
3. manual-automation의 실행 환경, 시나리오, 커버리지, artifact/release 상태를 first-class UX로 승격한다.
4. backend 이벤트 개선을 프런트에서도 end-to-end로 소비해, stale UI와 false success를 없앤다.

---

## 2. 현재 프런트엔드 기준선

현재 구조는 다음 수준까지는 갖춰져 있다.

- `OverviewNarrative.jsx`: 현재 run의 진행률, 생성 문서, MR 버튼, LLM/token footnote 표시
- `MissionKpis.jsx`: 완료율, token, tool success, run status KPI 표시
- `PipelineStatusPage.jsx`: source x pipeline 상태 테이블, 최근 run, 성공/실패/진행, token, 평균 duration 표시
- `MonitorPage.jsx`: run 상세 탭 `overview`, `stages`, `feed`
- `StageChecklist.jsx`: stage 그룹화 및 진행 상태 표시
- `LiveFeed.jsx`, `AgentConversation.jsx`: 이벤트 피드 및 agent 로그 표시
- `SourceWizard.jsx`: repository/source 등록 및 static 설정
- `SourceSchedulesPanel.jsx`: static pipeline schedule 설정
- `useLiveSocket.js`, `useRunStream.js`, `ingest.js`: WebSocket 이벤트 수신 및 화면 상태 집계

하지만 새 data-plane/AI-agent 계획 기준으로는 핵심 정보가 빠져 있다.

- quality gate 결과가 화면 상태 모델에 없다.
- evidence pack, grounded citation, unsupported claim을 볼 수 없다.
- `done_with_warnings`, `failed_quality_gate`, `partial`, `stale` 같은 운영 상태를 표현하지 못한다.
- manual-automation의 MCP profile, scenario set, artifact selector, coverage threshold를 설정할 UX가 없다.
- run detail이 stage/feed 중심이라 critic, repair loop, coverage miss, MR readiness를 판단하기 어렵다.
- 이벤트 수신은 raw feed 중심이고, quality/coverage/artifact event를 semantic state로 집계하지 않는다.
- frontend query invalidation 범위가 좁아 overview, pipeline status, cost, selected run summary가 stale해질 수 있다.

---

## 3. 제품 원칙

### 3.1 Completion Is Not Success

`done`은 실행 엔진이 끝났다는 뜻이고, `publishable`은 품질 게이트를 통과했다는 뜻이다. 화면은 이 둘을 반드시 분리해야 한다.

필수 상태:

- `running`
- `done`
- `done_with_warnings`
- `failed`
- `failed_quality_gate`
- `partial`
- `stale`
- `cancelled`

UI에서는 `done_with_warnings`를 초록색 성공으로 보이면 안 된다. 운영자가 조치해야 하는 상태로 표시해야 한다.

### 3.2 Evidence First

AI 출력물은 "그럴듯한 설명"이 아니라 evidence 기반 결과물로 표시되어야 한다.

모든 generated doc, manual step, critic verdict는 다음으로 drill-down 가능해야 한다.

- 사용된 파일/라인/심볼
- 관련 run event
- tool call 결과
- scenario observation
- screenshot/log/artifact reference
- unsupported claim 여부

### 3.3 Operator-Friendly Manual Automation

manual-automation은 cron job이 아니라 운영 workflow다. 프런트는 다음을 지원해야 한다.

- 실행 전 환경 preflight
- scenario 작성/검증
- MCP tool allowlist 확인
- artifact/release version 선택
- coverage threshold 설정
- 실패 step, skipped step, warning step 분리
- deprecated candidate review

### 3.4 Live UI Must Be Reconstructable

WebSocket feed만 믿는 UI는 운영 도구로 부족하다. 프런트 상태는 언제든 API snapshot + event replay로 재구성 가능해야 한다.

필수 조건:

- event `id`/`seq` 기반 dedupe
- cursor/offset 기반 replay
- overflow 감지 시 snapshot 재조회
- `run_status` 수신 즉시 selected run summary 갱신
- pipeline status, overview, cost, audit query invalidation

---

## 4. Information Architecture

### 4.1 Pipelines Overview

`PipelineStatusPage`는 단순 최근 실행 테이블에서 운영 대시보드로 확장한다.

추가 컬럼:

- `Quality`: `pass`, `warning`, `fail`, `not_evaluated`
- `Gate`: 마지막 실패 gate 이름
- `Coverage`: manual scenario coverage percentage
- `Warnings`: warning count
- `Repair`: repair attempts
- `Evidence`: evidence item count
- `Artifact`: artifact/release version
- `MR`: opened, ready, blocked, not_created
- `Action`: review required, rerun, open MR, inspect coverage

필터:

- pipeline: static, manual, both
- status: running, failed, warning, quality failed, stale
- quality: pass, warning, fail, unevaluated
- coverage: below threshold, threshold met
- source group
- owner
- branch/release version

핵심 UX:

- 실패 run보다 `done_with_warnings`와 `failed_quality_gate`가 더 잘 보이게 한다.
- "성공률" 카드 옆에 "publishable rate"를 별도로 둔다.
- stale source는 마지막 성공 시간이 아니라 마지막 검증된 artifact/version 기준으로 표시한다.

### 4.2 Run Detail

`MonitorPage`의 run 상세 탭을 다음으로 재구성한다.

1. `Overview`
   - run status
   - publishable status
   - generated docs
   - MR readiness
   - top warnings
   - cost/token summary

2. `Stages`
   - stage checklist
   - quality gate stage
   - repair loop stage
   - manual preflight/staging/deploy/smoke stage

3. `Quality`
   - deterministic verifier result
   - grounding critic result
   - style/schema/mermaid validation
   - unsupported claims
   - warning/error list
   - repair attempts and remaining issues

4. `Evidence`
   - evidence pack tree
   - source file references
   - tool call observations
   - run events linked to claims
   - doc section to evidence mapping

5. `Coverage`
   - manual scenario coverage
   - reached/unreached features
   - scenario step result table
   - blocked/skipped/failed steps
   - screenshots/log references

6. `Artifacts`
   - selected artifact or release version
   - build/deploy/install result
   - smoke result
   - deprecated candidates
   - MR included files and blocked files

7. `Remote Monitor`
   - mcp-vnc session view-only screen
   - pipeline-provided host/port connection metadata
   - active control action timeline
   - scenario step to remote screen correlation
   - connection status and audit trail

8. `Feed`
   - raw event stream
   - role/event filters
   - replay cursor state

### 4.3 Source Detail

Source 설정은 static-only wizard에서 pipeline profile editor로 확장한다.

탭:

- `Repository`: SCM 연결, branch, docs path
- `Static Docs`: theme rules, trigger policy, generated doc targets
- `Manual Automation`: MCP profile, artifact selector, scenario set, coverage threshold
- `Schedules`: static/manual 별 trigger
- `Secrets`: secret reference만 표시하고 값은 숨김
- `Preflight`: 현재 설정으로 실행 가능 여부

### 4.4 Quality & Cost Dashboard

기존 costs 페이지와 연결해 AI 품질 비용을 분리해서 보여준다.

추가 지표:

- quality pass rate
- failed quality gate count
- average repair attempts
- cost per publishable doc
- cost per manual scenario
- critic rejection reason distribution
- unsupported claim trend
- coverage below threshold trend

---

## 5. Frontend State Model

### 5.1 Run Summary Contract

`getRunSummary` 응답은 다음 필드를 수용해야 한다.

```ts
type RunStatus =
  | "pending"
  | "running"
  | "done"
  | "done_with_warnings"
  | "failed"
  | "failed_quality_gate"
  | "partial"
  | "stale"
  | "cancelled";

type QualityStatus = "pass" | "warning" | "fail" | "not_evaluated";

type RunQuality = {
  status: QualityStatus;
  score: number | null;
  publishable: boolean;
  publishState: "publishable" | "review_required" | "blocked" | "unknown";
  failedGate: string | null;
  warningCount: number;
  errorCount: number;
  repairAttempts: number;
  gates: QualityGateResult[];
};

type EvidencePackSummary = {
  id: string;
  itemCount: number;
  sourceFileCount: number;
  observationCount: number;
  unsupportedClaimCount: number;
};

type ManualCoverage = {
  status: "pass" | "warning" | "fail" | "not_applicable";
  percentage: number | null;
  threshold: number | null;
  reached: number;
  expected: number;
  missed: CoverageMiss[];
};

type ArtifactSummary = {
  version: string | null;
  source: "release" | "tag" | "branch" | "build" | "manual" | null;
  buildStatus: "pass" | "fail" | "skipped" | "unknown";
  deployStatus: "pass" | "fail" | "skipped" | "unknown";
  smokeStatus: "pass" | "fail" | "skipped" | "unknown";
};
```

Backward compatibility:

- 필드가 없으면 `not_evaluated`, `not_applicable`, `unknown`으로 표시한다.
- 구버전 backend 응답에서 `done`만 있는 경우 `publishable`을 추정하지 않는다.
- 추정값은 화면에서 `unknown`으로 표현하고 성공처럼 보이지 않게 한다.

### 5.2 Ingest State Extension

`frontend/src/lib/ingest.js`의 내부 상태는 다음을 추가한다.

```ts
{
  qualityStatus: "not_evaluated",
  qualityScore: null,
  publishable: false,
  publishState: "unknown",
  failedGate: null,
  warningCount: 0,
  errorCount: 0,
  repairAttempts: 0,
  evidenceItemCount: 0,
  unsupportedClaimCount: 0,
  coveragePct: null,
  coverageThreshold: null,
  coverageMisses: [],
  artifactVersion: null,
  artifactStatus: "unknown",
  mrReadiness: "unknown",
  lastEventSeq: null,
  eventGapDetected: false
}
```

집계 대상 이벤트:

- `quality_gate.started`
- `quality_gate.completed`
- `quality_gate.failed`
- `critic.verdict`
- `repair.started`
- `repair.completed`
- `evidence.collected`
- `evidence.unsupported_claim`
- `coverage.updated`
- `scenario.step.completed`
- `artifact.selected`
- `artifact.build.completed`
- `artifact.deploy.completed`
- `mr.plan.ready`
- `mr.blocked`

### 5.3 Event Replay and Dedupe

이벤트 모델은 다음 필드를 요구한다.

```ts
type PipelineEvent = {
  id: string;
  runId: string;
  seq: number;
  ts: string;
  type: string;
  stage?: string;
  role?: string;
  severity?: "debug" | "info" | "warning" | "error";
  payload: Record<string, unknown>;
};
```

프런트 처리 원칙:

- 같은 `id`는 한 번만 반영한다.
- `seq` gap이 감지되면 `eventGapDetected=true` 후 snapshot을 재조회한다.
- overflow event를 받으면 feed를 "일부 생략" 상태로 표시하고 run summary를 재조회한다.
- `run_status` event는 feed에만 쌓지 않고 selected run summary query를 즉시 invalidate한다.
- reconnect 후에는 마지막 `seq` 이후 event replay를 요청한다.

---

## 6. Static Docu-Automation UX

### 6.1 Change Impact Panel

정적 문서화 run의 `Overview`에 change impact panel을 추가한다.

표시 항목:

- changed files
- affected themes
- skipped themes and reasons
- classifier confidence
- previous baseline SHA
- current commit SHA
- evidence pack link

운영자가 확인해야 할 것:

- 왜 특정 문서가 생성되었는가
- 왜 특정 문서가 생성되지 않았는가
- SHA가 정상적으로 advance 되었는가
- partial init failure가 없는가

### 6.2 Generated Docs Quality

`OverviewNarrative`의 generated docs list를 품질 중심으로 확장한다.

각 doc row:

- doc title/path
- status: generated, updated, skipped, blocked
- quality status
- warnings
- unsupported claims
- evidence count
- schema validation result
- Mermaid validation result
- MR inclusion status

`warned` pill은 `warning count`, `failed gate`, `not publishable`로 분해한다.

### 6.3 MR Readiness

MR 버튼은 단순 open action이 아니라 readiness 상태를 먼저 보여준다.

상태:

- `ready`: 모든 publishable 문서가 포함됨
- `blocked`: 품질 실패 문서가 있음
- `partial`: 일부 문서만 포함됨
- `not_created`: MR 미생성
- `stale`: run summary와 MR plan version 불일치
- `review_required`: warning 문서가 포함되어 explicit confirm이 필요함

MR summary panel:

- included files
- excluded files and reasons
- deprecated candidates
- warning docs
- reviewer checklist

---

## 7. Manual-Automation UX

### 7.1 Manual Profile Editor

`SourceWizard` 또는 Source detail에 `Manual Automation` 탭을 추가한다.

필드:

- pipeline mode: static, manual, both
- MCP endpoint
- transport type
- environment target
- tool allowlist
- secret references
- artifact selector policy
- release/tag/branch selector
- install command profile
- readiness check
- smoke check
- coverage threshold
- failure policy: fail fast, continue with warnings, block publish

검증:

- MCP endpoint reachable 여부
- required tools available 여부
- secret reference 존재 여부
- scenario가 최소 1개 이상인지
- artifact selector가 release/tag/build 중 하나를 명확히 지정하는지
- coverage threshold가 0-100 범위인지

### 7.2 Scenario Editor

scenario set은 UI에서 작성/검증/버전 관리할 수 있어야 한다.

지원 기능:

- YAML/JSON editor
- form editor
- scenario step reorder
- expected observation 설정
- required tool 지정
- timeout 설정
- screenshot required 여부
- cleanup step 지정
- scenario lint
- dry-run preflight

step result table:

- step name
- action
- tool used
- status
- duration
- observation summary
- screenshot/log link
- failure reason
- evidence reference

### 7.3 Artifact and Release Panel

manual run은 어떤 artifact를 기준으로 실행했는지가 핵심이다.

표시 항목:

- artifact version
- source: release/tag/branch/build
- commit SHA
- build status
- deploy status
- install status
- readiness status
- smoke status
- selected by policy or manual override

사용자 액션:

- artifact 재선택
- preflight 실행
- deploy 재시도
- smoke 재시도
- run 재실행

### 7.4 Coverage Panel

manual output의 품질은 coverage를 화면에 명확히 보여야 한다.

표시 항목:

- coverage percentage
- threshold
- reached feature map
- missed feature list
- skipped scenario reason
- failed scenario reason
- warning scenario reason
- screenshot/log/evidence links

coverage below threshold인 경우:

- run status는 `done_with_warnings` 또는 `failed_quality_gate`
- generated manual은 publishable=false
- MR action은 blocked 또는 partial

### 7.5 MCP-VNC Remote Monitor

manual-automation 실행 중에는 `mcp-vnc`가 원격 환경을 실제로 조작한다. 프런트엔드는 이 원격 제어 과정을 운영자가 실시간으로 볼 수 있도록 `react-vnc` 기반 view-only 모니터링을 제공한다.

목표:

- pipeline run이 받은 `ip`, `port`로 VNC 세션에 연결한다.
- 운영자는 화면을 볼 수만 있고 입력을 보낼 수 없다.
- 어떤 scenario step 또는 agent action이 현재 원격 화면을 만들었는지 함께 본다.
- VNC 연결 실패가 manual run 품질 판정과 혼동되지 않도록 별도 상태로 표시한다.

연결 모델:

- backend는 run summary 또는 별도 endpoint로 VNC connection metadata를 제공한다.
- 프런트는 `host`, `port`, `path`, `protocol`, `sessionId`, `expiresAt`, `viewOnly=true`를 받는다.
- browser에서 직접 VNC TCP 접속은 불가능하므로 backend 또는 gateway가 websocket endpoint를 제공해야 한다.
- 프런트는 원본 `ip:port`를 그대로 노출하지 않고, 필요 시 masked label과 gateway URL만 사용한다.

필수 UI:

- connection status: unavailable, connecting, connected, disconnected, expired, error
- view-only badge
- reconnect button
- fullscreen button
- screenshot capture link가 아니라 backend evidence screenshot link만 표시
- current scenario step
- current tool/action
- last input event from agent
- remote resolution and latency
- session expiry countdown

보안/운영 원칙:

- 키보드, 마우스, clipboard 입력은 항상 disabled
- view-only 모드가 깨지면 즉시 연결을 끊고 error로 표시
- VNC password/token은 프런트 상태나 log에 저장하지 않는다.
- connection URL은 단기 만료 token을 사용한다.
- audit log에 viewer open/close/reconnect만 남기고 화면 내용은 저장하지 않는다.
- secret/redacted 영역은 backend/mcp-vnc 측 masking 정책과 연동한다.

manual run 상태와의 관계:

- VNC monitor 연결 실패는 manual run 실패가 아니다.
- mcp-vnc 자체가 tool failure를 보고하면 scenario step failure로 표시한다.
- remote monitor는 observation/evidence를 보조하는 live view이며, 최종 manual 문서 근거는 저장된 scenario observation과 screenshot/log artifact를 기준으로 한다.

---

## 8. AI Agent Output Quality UX

### 8.1 Agent Role Timeline

AI pipeline stage를 역할 기반 timeline으로 보여준다.

공통 role:

- Evidence Builder
- Scope Planner
- Draft Writer
- Deterministic Verifier
- Grounding Critic
- Repair Writer
- Final Packager

static role:

- Change Classifier
- Static Evidence Collector
- Theme Writer
- Static Critic

manual role:

- Scenario Preflight Agent
- Safe Explorer
- Coverage Assessor
- Manual Writer
- Manual Critic

각 role row:

- status
- start/end time
- model
- token/cost
- input evidence count
- output artifacts
- warnings/errors
- retry/repair count

### 8.2 Critic Verdict Panel

`Quality` 탭에 critic verdict를 구조화해서 보여준다.

섹션:

- Unsupported claims
- Missing evidence
- Schema violations
- Broken links
- Mermaid/rendering failures
- Manual coverage gaps
- Unsafe tool usage
- Deprecated or stale references
- Style/format violations

각 finding:

- severity
- affected doc section
- evidence reference
- suggested repair
- repair status
- blocking 여부

### 8.3 Repair Loop Timeline

AI output은 첫 draft가 아니라 repair loop까지 포함해 품질을 판단해야 한다.

표시 항목:

- repair attempt number
- trigger finding
- changed sections
- remaining findings
- critic result after repair
- max repair attempts reached 여부

운영 원칙:

- repair 후에도 blocking finding이 남으면 `failed_quality_gate`
- non-blocking warning만 남으면 `done_with_warnings`
- repair attempt가 너무 많으면 cost dashboard에 별도 표시

### 8.4 Evidence Citation Viewer

문서 preview에서 section 단위 evidence를 확인할 수 있어야 한다.

기능:

- 문서 section 클릭 시 관련 evidence 표시
- source file line link
- scenario observation link
- tool call raw result toggle
- unsupported claim highlight
- evidence missing badge

주의:

- raw secret/log는 redaction된 상태만 표시
- long observation은 summary와 raw attachment를 분리한다
- truncated evidence는 "truncated" 상태를 명확히 표시한다

---

## 9. Live Monitoring and Event Handling

### 9.1 Query Invalidation

`useLiveSocket.js`는 다음 query를 event type별로 invalidate한다.

`run_status`:

- selected run summary
- runs list
- pipeline status
- overview

`quality_gate.*`, `critic.*`, `repair.*`:

- selected run summary
- quality report
- pipeline status
- overview

`coverage.*`, `scenario.*`:

- selected run summary
- coverage report
- pipeline status

`artifact.*`, `mr.*`:

- selected run summary
- artifact report
- pipeline status
- MR plan

`llm_usage`, `cost.updated`:

- cost summary
- selected run summary
- model usage

### 9.2 Snapshot Strategy

`useRunStream.js`는 manual interval 중심에서 snapshot + stream 모델로 바꾼다.

흐름:

1. run detail 진입 시 `getRunSummary(runId)` 호출
2. `getRunEvents(runId, afterSeq)`로 누락 이벤트 replay
3. WebSocket subscribe
4. event 반영
5. gap/overflow/reconnect 발생 시 summary 재조회

필수 UI 상태:

- live
- reconnecting
- replaying
- gap detected
- stale snapshot

### 9.3 Feed Filtering

`LiveFeed`와 `AgentConversation`은 raw log가 아니라 운영 가능한 trace viewer가 되어야 한다.

필터:

- severity
- stage
- agent role
- event type
- quality only
- manual only
- tool calls only
- warnings/errors only

이벤트 row 확장:

- role badge
- stage badge
- sequence number
- replayed/live marker
- evidence link
- payload detail drawer

---

## 10. Component-Level Plan

### 10.1 New Components

`QualityGatePanel.jsx`

- gate별 pass/warning/fail 표시
- blocking finding list
- repair status
- publishable 여부 표시

`EvidencePackPanel.jsx`

- evidence tree
- file/line reference
- scenario observation
- unsupported claim list
- doc section mapping

`CoveragePanel.jsx`

- coverage percentage
- scenario result table
- missed features
- screenshot/log links

`RemoteVncMonitor.jsx`

- `react-vnc` 기반 view-only remote screen
- run-provided VNC websocket endpoint 연결
- reconnect/fullscreen/status controls
- current scenario step/action metadata
- keyboard/mouse/clipboard input disabled

`VncSessionBadge.jsx`

- VNC session availability/status 표시
- expiry/reconnect state 표시
- monitor tab deep link 제공

`ManualProfilePanel.jsx`

- MCP profile form
- tool allowlist
- secret references
- failure policy

`ScenarioEditor.jsx`

- scenario CRUD
- step editor
- lint/preflight
- YAML/JSON import-export

`ArtifactSelectorPanel.jsx`

- release/tag/build selector
- artifact status
- deploy/install/readiness/smoke result

`AgentQualityTimeline.jsx`

- role-based stage timeline
- model/cost/repair metadata

`RunQualityBadge.jsx`

- reusable badge for `quality.status`, `publishable`, `failedGate`

### 10.2 Components to Update

`OverviewNarrative.jsx`

- generated docs row에 quality/evidence/MR readiness 추가
- `done_with_warnings`, `failed_quality_gate` 상태 표시
- top warnings와 blocking findings 노출

`MissionKpis.jsx`

- publishable rate
- quality score
- warning count
- coverage percentage
- repair attempts
- cost per publishable output

`PipelineStatusPage.jsx`

- quality/coverage/artifact/MR 컬럼 추가
- filter 추가
- action required 우선 정렬

`MonitorPage.jsx`

- `Quality`, `Evidence`, `Coverage`, `Artifacts`, `Remote Monitor` 탭 추가
- run status와 publishable status를 header에 동시 표시
- manual run에서 VNC session이 있으면 monitor tab badge 표시

`StageChecklist.jsx`

- quality gate, critic, repair loop stage 추가
- manual preflight/deploy/smoke stage 표시
- mcp-vnc connect/control/observe stage 표시
- warning terminal state 지원

`LiveFeed.jsx`, `AgentConversation.jsx`

- role/stage/severity/event type filter
- event seq 표시
- evidence/finding 링크
- replay/live marker
- mcp-vnc control action event를 scenario step과 연결

`SourceWizard.jsx`

- pipeline mode 선택
- manual profile setup
- scenario editor entry
- artifact selector setup
- VNC monitoring enable/disable 및 gateway policy 설정

`SourceSchedulesPanel.jsx`

- manual pipeline option 추가
- release trigger/polling schedule
- static/manual 별 schedule 분리

`frontend/src/api/client.js`

- quality report endpoint
- evidence pack endpoint
- coverage report endpoint
- VNC session endpoint
- manual profile CRUD
- scenario set CRUD
- artifact selector/preflight endpoint
- event replay endpoint

`frontend/src/lib/stageNarrative.js`

- AI role stage narrative 추가
- manual preflight/artifact/coverage stage narrative 정리
- quality gate failure message 추가

`frontend/src/lib/ingest.js`

- quality/coverage/artifact event 집계
- VNC session/control/observe event 집계
- seq dedupe
- gap detection
- publishable 계산

---

## 11. API Contract Plan

프런트가 요구하는 backend endpoint는 다음이다.

### 11.1 Run Quality

`GET /api/runs/:runId/quality`

반환:

- quality status
- gates
- findings
- repair attempts
- publishable
- doc-level quality

### 11.2 Evidence Pack

`GET /api/runs/:runId/evidence`

반환:

- evidence items
- source references
- scenario observations
- tool call references
- unsupported claims
- doc section mapping

### 11.3 Manual Coverage

`GET /api/runs/:runId/coverage`

반환:

- scenario result
- coverage summary
- missed features
- screenshot/log refs
- threshold result

### 11.4 Manual Profile

`GET /api/sources/:sourceId/manual-profile`
`PUT /api/sources/:sourceId/manual-profile`

반환/저장:

- MCP endpoint/profile
- tool allowlist
- secret refs
- artifact selector
- scenario set ref
- coverage threshold
- failure policy

### 11.5 Scenario Set

`GET /api/sources/:sourceId/scenarios`
`POST /api/sources/:sourceId/scenarios`
`PUT /api/sources/:sourceId/scenarios/:scenarioId`
`DELETE /api/sources/:sourceId/scenarios/:scenarioId`
`POST /api/sources/:sourceId/scenarios/lint`

### 11.6 Artifact Preflight

`POST /api/sources/:sourceId/artifacts/preflight`

반환:

- selected artifact
- build/deploy/install/readiness/smoke status
- blocking errors
- warnings

### 11.7 Event Replay

`GET /api/runs/:runId/events?afterSeq=123&limit=500`

반환:

- events
- latestSeq
- truncated
- hasMore

### 11.8 VNC Session

`GET /api/runs/:runId/vnc-session`

반환:

- available
- status
- websocketUrl 또는 gatewayUrl
- hostLabel
- portLabel
- sessionId
- expiresAt
- viewOnly=true
- currentScenarioStep
- currentAction
- latencyMs
- resolution
- error

주의:

- raw password/token은 반환하지 않는다.
- raw `ip`, `port`는 운영자가 꼭 알아야 하는 경우에만 masked label로 표시한다.
- browser가 직접 TCP VNC에 붙지 않도록 backend gateway websocket을 우선한다.
- view-only가 false인 session은 프런트가 연결을 거부한다.

---

## 12. Phased Roadmap

### Phase 1: Contract and State Readiness

목표: backend 개선 이벤트와 상태를 프런트가 깨지지 않고 수용한다.

작업:

- Run status enum 확장
- quality/coverage/artifact optional field 수용
- `RunQualityBadge` 추가
- `ingest.js`에 quality/coverage/artifact state 추가
- event id/seq dedupe 추가
- event gap/overflow state 추가
- `useLiveSocket.js` query invalidation 확장
- `useRunStream.js` snapshot + replay 구조 준비

완료 기준:

- 구버전 backend 응답에서도 화면이 깨지지 않는다.
- `done_with_warnings`와 `failed_quality_gate`가 성공처럼 표시되지 않는다.
- WebSocket reconnect 후 중복 event가 KPI를 왜곡하지 않는다.

### Phase 2: Run Detail Quality UX

목표: 운영자가 단일 run의 publishability를 판단할 수 있다.

작업:

- `Quality` 탭 추가
- `Evidence` 탭 추가
- `QualityGatePanel` 구현
- `EvidencePackPanel` 구현
- `OverviewNarrative` generated docs quality 표시
- `StageChecklist` quality gate/critic/repair loop 표시
- MR readiness panel 추가

완료 기준:

- generated doc별 warning/error/evidence count가 보인다.
- failed quality gate의 blocking reason이 보인다.
- repair loop 이후 남은 finding이 보인다.
- MR 생성 가능/불가 이유가 명확하다.

### Phase 3: Manual-Automation Setup UX

목표: manual pipeline을 UI에서 설정하고 실행 전 검증할 수 있다.

작업:

- `ManualProfilePanel` 추가
- `ScenarioEditor` 추가
- `ArtifactSelectorPanel` 추가
- `CoveragePanel` 추가
- `RemoteVncMonitor` 추가
- `SourceWizard`에 pipeline mode/manual setup 추가
- `SourceSchedulesPanel`에 manual schedule/release trigger 추가
- preflight 실행 action 추가
- mcp-vnc session endpoint와 view-only monitor 연결

완료 기준:

- source별 manual MCP profile을 저장할 수 있다.
- scenario lint/preflight 결과가 보인다.
- artifact/release version이 명확히 선택된다.
- coverage threshold 미달 시 publish가 block된다.
- manual run 중 원격 제어 화면을 view-only로 확인할 수 있다.
- monitor 연결 실패와 pipeline 실패가 UI에서 분리된다.

### Phase 4: AI Agent Output Quality UX

목표: AI agent의 output 생성/검증/수정 과정을 투명하게 보여준다.

작업:

- `AgentQualityTimeline` 추가
- critic verdict panel 고도화
- repair loop timeline 구현
- evidence citation viewer 구현
- unsupported claim highlight
- role/model/cost breakdown 표시

완료 기준:

- 어떤 agent role이 어떤 output을 만들었는지 보인다.
- critic이 무엇을 reject했는지 보인다.
- repair가 어떤 finding을 해결했는지 보인다.
- unsupported claim이 문서 section과 연결된다.

### Phase 5: Operations Polish

목표: 팀 내 운영 파이프라인으로 장기간 사용할 수 있는 완성도를 만든다.

작업:

- overview filters/saved views
- action required sorting
- quality/cost trend dashboard
- accessibility keyboard navigation
- empty/error/loading state 정리
- responsive layout 검증
- audit log link
- stale source banner

완료 기준:

- 운영자는 오늘 조치해야 할 source/run을 1분 안에 찾을 수 있다.
- warning 상태가 묻히지 않는다.
- 품질 실패와 비용 증가의 원인을 trend로 추적할 수 있다.

---

## 13. Testing Plan

### 13.1 Unit Tests

대상:

- `ingest.js`
- status normalization
- quality badge rendering
- event dedupe
- event gap detection
- publishable calculation

케이스:

- 같은 event id가 두 번 들어와도 KPI가 한 번만 증가한다.
- `seq` gap이 있으면 `eventGapDetected=true`가 된다.
- quality fail event 후 run status가 `failed_quality_gate`로 표시된다.
- coverage threshold 미달 시 publishable=false가 된다.
- backend field가 없으면 unknown/not_evaluated로 fallback한다.

### 13.2 Component Tests

대상:

- `OverviewNarrative`
- `MissionKpis`
- `PipelineStatusPage`
- `QualityGatePanel`
- `EvidencePackPanel`
- `CoveragePanel`
- `ManualProfilePanel`
- `ScenarioEditor`

케이스:

- `done_with_warnings` run이 green success로 표시되지 않는다.
- generated doc별 quality warning count가 표시된다.
- failed gate finding이 blocking으로 표시된다.
- evidence item 클릭 시 citation detail이 열린다.
- manual coverage below threshold가 MR action을 block한다.
- missing MCP tool이 preflight error로 표시된다.

### 13.3 Integration Tests

시나리오:

1. Static doc run success
   - event stream 수신
   - evidence pack 표시
   - quality pass
   - MR ready

2. Static doc run with unsupported claim
   - critic fail
   - repair attempt
   - still fail이면 `failed_quality_gate`
   - MR blocked

3. Manual run with scenario failure
   - preflight pass
   - scenario step fail
   - coverage below threshold
   - manual doc generated but publishable=false

4. Manual run with VNC monitor
   - run summary에 VNC session metadata 포함
   - Remote Monitor 탭 활성화
   - `viewOnly=true`인 경우에만 연결
   - keyboard/mouse/clipboard input disabled
   - current scenario step/action 표시
   - VNC 연결 실패가 run failure로 표시되지 않음

5. WebSocket overflow
   - overflow event 수신
   - snapshot 재조회
   - feed에 gap 표시
   - KPI가 중복 증가하지 않음

6. Reconnect and replay
   - last seq 이후 replay
   - duplicate event dedupe
   - selected run summary 갱신

### 13.4 Visual QA

검증 뷰포트:

- desktop 1440px
- laptop 1280px
- tablet 768px
- mobile 390px

검증 항목:

- quality badge text overflow 없음
- stage timeline row height 안정적
- evidence tree 긴 path 처리
- scenario table horizontal overflow 처리
- VNC monitor 16:9/4:3 화면 비율 처리
- fullscreen monitor에서 view-only badge 유지
- mobile에서 탭/필터 접근 가능
- warning/error 상태 색상 대비 충분

---

## 14. Rollout Plan

### 14.1 Backward Compatible Release

먼저 optional field 기반으로 프런트를 배포한다.

원칙:

- 새 field가 없으면 unknown으로 표시
- unknown은 success로 계산하지 않음
- 새 endpoint 실패 시 기존 run overview는 유지
- 품질 탭은 "not evaluated" 상태로 표시

### 14.2 Feature Flag

feature flag:

- `qualityTabs`
- `manualProfileEditor`
- `eventReplay`
- `agentTimeline`
- `coveragePanel`

점진 배포:

1. internal dogfood source
2. static-only source
3. manual-only source
4. static+manual combined source

### 14.3 Operational Migration

운영 전환 순서:

1. 기존 run status normalize
2. source별 manual profile 초안 생성
3. scenario set import
4. quality threshold 기본값 적용
5. dashboard saved view 생성
6. 팀 runbook 업데이트

---

## 15. Acceptance Criteria

프런트엔드 개선은 다음 조건을 만족해야 완료로 본다.

- 운영자는 pipeline overview에서 `failed_quality_gate`, `done_with_warnings`, `coverage below threshold`를 즉시 구분한다.
- run detail에서 생성 문서별 evidence, warning, unsupported claim, MR inclusion 상태를 확인할 수 있다.
- manual source는 UI에서 MCP profile, scenario set, artifact selector, coverage threshold를 설정할 수 있다.
- manual run은 artifact/release version, deploy/install/readiness/smoke 상태를 표시한다.
- manual run은 mcp-vnc 원격 제어 화면을 `react-vnc` 기반 view-only monitor로 볼 수 있다.
- VNC monitor는 pipeline이 제공한 host/port 기반 gateway endpoint로 연결하고, 사용자 입력을 절대 전달하지 않는다.
- AI agent role별 생성/검증/수정 과정이 timeline으로 보인다.
- WebSocket reconnect/overflow 후에도 KPI와 stage 상태가 중복되거나 stale하지 않다.
- `publish_state=blocked`이면 MR action이 block되고, `review_required`이면 explicit confirm UI가 표시된다.
- 구버전 backend 응답에서도 화면이 깨지지 않고 unknown 상태로 degrade된다.

---

## 16. Priority Backlog

### P0

- Run status enum 확장
- `RunQualityBadge`
- `ingest.js` quality/coverage/artifact state
- event id/seq dedupe
- `run_status` 수신 시 selected run summary invalidate
- `OverviewNarrative` warning/failed quality 표시
- `PipelineStatusPage` quality/status 컬럼
- `MonitorPage` Quality 탭

### P1

- Evidence 탭
- Coverage 탭
- Artifact 탭
- Remote Monitor 탭
- `react-vnc` 의존성 추가 및 `RemoteVncMonitor` 구현
- `ManualProfilePanel`
- `ScenarioEditor`
- `SourceWizard` manual mode
- `SourceSchedulesPanel` manual pipeline support
- MR readiness panel
- repair loop timeline

### P2

- evidence citation viewer
- cost per publishable output
- saved filters
- quality trend dashboard
- visual diff for repaired docs
- scenario result screenshot gallery
- audit log deep links

---

## 17. Non-Goals

이번 계획은 다음을 포함하지 않는다.

- backend quality evaluator 구현
- MCP server implementation
- AI prompt 본문 작성
- MR 생성 로직 변경
- artifact build/deploy runner 구현

다만 프런트는 위 기능들이 backend에서 제공될 때 즉시 소비할 수 있는 상태 모델과 화면 구조를 먼저 갖춰야 한다.

---

## 18. Summary

프런트엔드의 핵심 변화는 "실행 모니터"에서 "AI 문서 품질 운영 도구"로 전환하는 것이다.

가장 먼저 해야 할 일은 status/quality/evidence/coverage를 상태 모델에 넣는 것이다. 그 다음 run detail에서 quality gate와 evidence를 보여주고, manual profile/scenario/artifact setup을 UI로 끌어올린다. 마지막으로 agent role timeline과 repair loop를 붙이면, 팀은 AI 출력물을 신뢰 가능한 운영 파이프라인으로 관리할 수 있다.

---

## 19. Cross-Document Review Updates

다른 data-plane, AI-agent, backend API 계획과 대조한 뒤 아래를 추가 표준으로 확정한다.

### 19.1 Terminology Alignment

- quality status는 `pass | warning | fail | not_evaluated`만 사용한다.
- run status는 `done_with_warnings`와 `failed_quality_gate`를 분리해서 표시한다.
- `failed`는 실행 실패이고, `fail`은 quality/coverage/gate 판정값이다.
- `publish_state=blocked`인 run은 UI에서 성공 색상이나 성공률에 포함하지 않는다.
- `publish_state=review_required`인 run은 성공률이 아니라 review-required KPI로 집계한다.

### 19.2 Snapshot Version

Backend API 계획의 `snapshot_version`을 프런트 상태 모델에 추가한다.

프런트 처리:

- run summary 응답의 `snapshot_version`을 저장한다.
- WebSocket message의 `snapshot_version`이 더 크면 summary query를 invalidate한다.
- replay 후 summary의 `snapshot_version`이 event stream보다 낮으면 stale snapshot banner를 표시한다.

### 19.3 VNC and Evidence Boundary

VNC Remote Monitor는 live observation 보조 수단이고, 문서 근거는 아니다.

UI 원칙:

- VNC 화면 자체를 evidence로 취급하지 않는다.
- evidence는 backend가 저장한 screenshot/log/observation artifact만 사용한다.
- Remote Monitor 탭에는 "live view" 상태와 현재 scenario/action만 표시한다.
- 문서 citation viewer는 VNC stream이 아니라 evidence artifact endpoint로 연결한다.

### 19.4 API Dependency

아래 endpoint가 없으면 관련 UI는 disabled/unknown 상태로 degrade한다.

- `/api/runs/{run_id}/quality`
- `/api/runs/{run_id}/evidence`
- `/api/runs/{run_id}/coverage`
- `/api/runs/{run_id}/artifacts`
- `/api/runs/{run_id}/vnc-session`
- `/api/runs/{run_id}/events`

이 endpoint 실패는 run failure로 표시하지 않고, UI data availability 문제로 표시한다.

### 19.5 Final Review Corrections

마지막 상호 리뷰 기준으로 프런트는 boolean `publishable`보다 `publish_state`를 우선 표시한다.

표시 정책:

- `publishable`: MR ready
- `review_required`: warning badge + confirm-required MR action
- `blocked`: MR action disabled
- `unknown`: backend data unavailable

테스트 추가:

- warning quality run이 `review_required`로 표시되는지
- `blocked` run만 MR action이 완전히 disabled 되는지
- 구버전 run에서 `publish_state`가 없으면 `unknown`으로 degrade 되는지
- WebSocket `snapshot_version` 증가 후 summary refetch가 발생하는지
