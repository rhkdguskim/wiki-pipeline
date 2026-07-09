# LLM Wiki and Development Pipeline Future Plan

작성일: 2026-07-08
대상: LLM Wiki Pipeline, Requirements Collector, Development Pipeline, 기존 docu/manual automation의 다음 단계
참고 관점:

- Andrej Karpathy 계열의 "영어가 프로그래밍 인터페이스가 되는" 흐름
- 개인/팀 지식베이스가 반복 질의 비용을 줄이고 누적 지식으로 성능을 개선한다는 LLM Wiki/knowledge-base 관점
- vibe coding식 빠른 생성은 생산용 개발에서는 요구사항, 검증, 리뷰, 테스트 guardrail과 결합해야 한다는 관점

---

## 1. 핵심 판단

다음 단계에는 **요구사항 수집기(Requirements Collector)** 가 반드시 필요하다.

지금까지의 파이프라인은 이미 존재하는 코드, 릴리스, 앱 화면을 근거로 문서를 만든다. 하지만 개발 파이프라인까지 확장하려면 출발점이 달라진다. 개발은 대부분 "무엇을 만들 것인가"가 불명확한 상태에서 시작한다. 이 상태를 바로 coding agent에게 넘기면 산출물은 빨라져도 요구사항 누락, scope creep, 검증 불가, wiki 오염이 발생한다.

따라서 미래 단계의 첫 agent는 writer나 coder가 아니라 요구사항 수집기다.

```text
Stakeholder Intent
  -> Requirements Collector
  -> Requirements Evidence Pack
  -> Spec/RFC Writer
  -> LLM Wiki Update
  -> Development Planner
  -> Implementation Agents
  -> Verification/Manual Automation
  -> Wiki Feedback Loop
```

---

## 2. Karpathy-Inspired LLM Wiki 원칙

Karpathy가 강조해온 흐름을 이 프로젝트에 맞게 해석하면 핵심은 세 가지다.

### 2.1 English Becomes the Interface

개발자는 점점 더 자연어로 의도를 설명하고, agent가 코드/문서/테스트를 생성한다. 하지만 생산 시스템에서는 "영어로 말하면 코드가 나온다"가 아니라 "영어 요구사항이 검증 가능한 spec으로 변환된다"가 되어야 한다.

우리 파이프라인의 대응:

- 요구사항을 자연어 그대로 저장하지 않는다.
- 요구사항을 actor, problem, constraint, acceptance criteria, non-goal, risk로 구조화한다.
- 구조화된 요구사항만 development agent 입력으로 사용한다.

### 2.2 Knowledge Should Compound

매번 RAG로 문서를 긁어오는 방식은 반복 비용이 크다. LLM Wiki는 질문/답변/결정/코드 변경/운영 관측을 누적해 다음 작업의 context 비용을 낮춰야 한다.

우리 파이프라인의 대응:

- 요구사항 수집 결과를 wiki page와 knowledge graph로 저장한다.
- 개발 중 생긴 결정과 tradeoff를 ADR/RFC로 자동 반영한다.
- manual-automation observation과 release 결과를 wiki에 feedback한다.
- 반복 질문은 새 답변을 만들기보다 기존 verified wiki node를 갱신한다.

### 2.3 Vibe Coding Needs Production Guardrails

빠른 AI coding은 throwaway project에서는 유용하지만, 팀 운영 파이프라인에서는 diff review, test, security, maintainability, evidence trace가 필요하다.

우리 파이프라인의 대응:

- agent가 바로 구현하지 않고 requirements gate를 통과해야 한다.
- spec 없는 구현 PR은 생성하지 않는다.
- 구현 agent와 verifier agent를 분리한다.
- wiki/evidence/spec과 연결되지 않은 코드는 review blocker다.

---

## 3. Requirements Collector

### 3.1 역할

Requirements Collector는 사람의 모호한 요청을 개발 가능한 요구사항으로 바꾸는 agent다.

책임:

- stakeholder intent 수집
- 누락 질문 생성
- 기존 wiki/code/manual과 충돌 확인
- 범위와 non-goal 분리
- acceptance criteria 작성
- testability 검증
- risk/constraint 도출
- 개발 티켓과 wiki page 초안 생성

### 3.2 입력

입력 소스:

- 사용자 대화
- PM/운영자 요청
- GitLab/GitHub issue
- Slack/회의록 export
- 장애 리포트
- manual-automation observation
- reviewer feedback
- 기존 wiki page
- code index

### 3.3 출력 Schema

```json
{
  "requirement_id": "req-...",
  "source": {
    "kind": "chat|issue|meeting|incident|manual_observation|review_feedback",
    "uri": "...",
    "captured_at": "2026-07-08T00:00:00Z"
  },
  "status": "draft|needs_clarification|ready_for_spec|rejected|superseded",
  "problem": "...",
  "users": ["operator", "developer", "admin"],
  "goals": ["..."],
  "non_goals": ["..."],
  "functional_requirements": [
    {
      "id": "fr-1",
      "statement": "...",
      "priority": "must|should|could",
      "evidence_refs": ["ev1"],
      "acceptance_criteria": ["..."]
    }
  ],
  "non_functional_requirements": [
    {
      "id": "nfr-1",
      "kind": "security|performance|reliability|ux|cost|operability",
      "statement": "...",
      "acceptance_criteria": ["..."]
    }
  ],
  "open_questions": [
    {
      "id": "q1",
      "question": "...",
      "blocking": true,
      "owner": "..."
    }
  ],
  "constraints": ["..."],
  "risks": ["..."],
  "dependencies": ["..."],
  "wiki_targets": ["wiki/future/..."],
  "dev_ticket_candidates": ["..."]
}
```

### 3.4 질문 정책

Requirements Collector는 질문을 무작정 많이 하지 않는다.

질문 우선순위:

1. 구현 방향을 바꾸는 질문
2. 보안/데이터/권한 관련 질문
3. acceptance criteria를 결정하는 질문
4. scope boundary 질문
5. 운영 fallback 질문

비차단 질문은 assumption으로 기록하고 진행한다. 차단 질문은 `needs_clarification`으로 둔다.

### 3.5 품질 게이트

요구사항이 development pipeline으로 넘어가려면 아래를 만족해야 한다.

- 최소 1개 이상의 measurable acceptance criterion
- target user 또는 system actor 명시
- non-goal 명시
- security/privacy 영향 평가
- 기존 wiki/code와 충돌 여부 확인
- test strategy 초안 존재
- rollback 또는 failure handling 초안 존재

---

## 4. LLM Wiki Pipeline

### 4.1 Wiki의 역할

LLM Wiki는 사람이 읽는 문서 저장소이면서 agent가 사용하는 verified knowledge layer다.

저장 대상:

- requirement pages
- RFC/spec pages
- architecture pages
- API contract pages
- runbook pages
- manual pages
- test strategy pages
- decision records
- release notes
- known limitations

### 4.2 Wiki Page Types

`Requirement Page`

- problem
- user/stakeholder
- functional requirements
- non-functional requirements
- open questions
- acceptance criteria
- linked evidence
- status

`Spec/RFC Page`

- proposed solution
- alternatives
- API/UI/data model changes
- migration plan
- test plan
- rollout plan
- rollback plan

`Development Plan Page`

- task breakdown
- affected modules
- required tests
- verification owner
- dependencies
- implementation order

`Operational Knowledge Page`

- incidents
- manual observations
- run failures
- troubleshooting
- known limitations

### 4.3 Knowledge Graph

Wiki pages should not be isolated markdown files. They need stable links.

Graph edges:

- requirement -> spec
- spec -> implementation PR
- PR -> tests
- PR -> generated docs
- release -> manual observation
- manual observation -> wiki update
- incident -> requirement
- decision -> code module
- code module -> owner

### 4.4 LLM Wiki Information Architecture

LLM Wiki는 아래 폴더/페이지 체계를 기본으로 한다.

```text
wiki/
  requirements/
    req-<id>.md
  specs/
    spec-<id>.md
  decisions/
    adr-<id>.md
  architecture/
    system-overview.md
    module-<name>.md
  api/
    endpoint-<name>.md
    contract-<name>.md
  development/
    dev-plan-<id>.md
    test-plan-<id>.md
  operations/
    runbook-<name>.md
    incident-<id>.md
  releases/
    release-<version>.md
  manuals/
    user-manual-<version>.md
    operator-manual-<version>.md
  glossary/
    terms.md
  index/
    graph.json
    stale-report.json
    coverage-report.json
```

공통 frontmatter:

```yaml
id: wiki-...
type: requirement|spec|adr|architecture|api|dev-plan|test-plan|runbook|release|manual
status: draft|review|verified|stale|deprecated
owner: team-or-person
created_at: 2026-07-08
updated_at: 2026-07-08
source_refs:
  - kind: requirement|commit|mr|run|artifact|manual_observation|incident
    id: ...
evidence_refs:
  - ev-...
links:
  requirements: []
  specs: []
  decisions: []
  code_modules: []
  tests: []
  releases: []
quality:
  status: pass|warning|fail|not_evaluated
  reviewer: human-or-agent
  verified_at: ""
```

### 4.5 LLM Wiki Write Policy

Wiki write는 아래 4단계로만 수행한다.

1. `draft`
   - agent가 새 페이지 또는 수정안을 만든다.
   - evidence_refs가 없으면 draft만 가능하다.

2. `review`
   - human 또는 reviewer agent가 충돌, 범위, 근거를 확인한다.
   - 기존 verified page를 덮어쓰는 경우 diff review가 필수다.

3. `verified`
   - quality gate 통과 후 agent retrieval context에 사용 가능하다.
   - development agent는 verified page를 우선 context로 사용한다.

4. `stale/deprecated`
   - source commit, API contract, release, manual observation이 바뀌면 stale 후보가 된다.
   - deprecated page는 삭제하지 않고 redirect/superseded link를 남긴다.

금지:

- failed quality output을 verified wiki에 자동 반영 금지
- VNC live stream을 evidence로 직접 저장 금지
- raw secret, token, credential, VNC password 저장 금지
- requirement 없이 dev-plan page 생성 금지

### 4.6 LLM Wiki Retrieval Contract

agent가 wiki를 읽을 때는 전체 wiki를 RAG로 긁지 않는다.

Retrieval 순서:

1. requirement/spec linked pages
2. directly affected module pages
3. API contract pages
4. decisions/ADR
5. recent incidents/runbooks
6. release/manual observation pages

Context package schema:

```json
{
  "context_pack_id": "ctx-...",
  "task_id": "...",
  "wiki_pages": [
    {
      "id": "wiki-...",
      "type": "spec",
      "status": "verified",
      "summary": "...",
      "relevant_sections": ["..."],
      "evidence_refs": ["ev-..."]
    }
  ],
  "excluded_pages": [
    {
      "id": "wiki-...",
      "reason": "stale|deprecated|low_relevance|conflict"
    }
  ]
}
```

### 4.4 Wiki Quality Gate

Wiki update는 아래 조건을 통과해야 publish된다.

- evidence refs exist
- stale link 없음
- source commit/release/artifact 명시
- conflicting page detection
- owner/reviewer 지정
- frontmatter schema valid
- generated page가 기존 verified page를 무단 overwrite하지 않음

---

## 5. Development Pipeline

### 5.1 Pipeline

```text
Requirement Ready
  -> Spec/RFC
  -> Design Review
  -> Development Plan
  -> Implementation
  -> Unit/Integration/E2E Tests
  -> Security/Operability Review
  -> MR/PR
  -> Release
  -> Manual Automation
  -> Wiki Feedback
```

### 5.2 Agent Roles

`Requirements Collector`

- 모호한 요청을 구조화된 요구사항으로 변환

`Spec Writer`

- requirements를 RFC/spec으로 변환

`Architecture Critic`

- 기존 구조와 충돌, 과설계, migration risk 검토

`Development Planner`

- 파일/모듈 단위 task breakdown 생성

`Implementation Agent`

- 실제 코드 변경

`Test Planner`

- acceptance criteria 기반 테스트 설계

`Verifier`

- test/lint/type/security/manual automation 결과 확인

`Wiki Curator`

- 개발 결과와 운영 관측을 wiki에 반영

### 5.3 Agent Development Plan

Agent는 한 번에 거대한 autonomous system으로 만들지 않는다. 각 agent는 typed input, typed output, allowed tools, quality gate를 가진 작은 worker로 개발한다.

공통 구현 원칙:

- 모든 agent는 `run_id`, `task_id`, `source_refs`, `context_pack_id`를 입력으로 받는다.
- 모든 agent output은 JSON schema 검증을 통과해야 한다.
- 모든 agent는 `assumptions`, `open_questions`, `evidence_refs`, `confidence`를 출력한다.
- agent는 직접 publish/merge/deploy하지 않는다. 최종 mutation은 backend policy gate가 수행한다.
- writer agent와 critic/verifier agent는 분리한다.

#### 5.3.1 Requirements Collector Agent

입력:

- raw stakeholder request
- source metadata
- existing wiki context pack
- related code/manual/release evidence

출력:

- structured requirement
- open questions
- assumptions
- acceptance criteria
- risk list
- candidate wiki pages
- candidate dev tickets

도구:

- wiki search
- code index search
- issue/MR search
- manual observation search
- clarification question generator

품질 게이트:

- acceptance criteria measurable 여부
- actor/problem/non-goal 존재 여부
- blocking question 분리 여부
- 기존 wiki/spec과 충돌 여부

개발 순서:

1. JSON schema와 deterministic validator 작성
2. raw request -> structured requirement 변환 prompt 작성
3. existing wiki conflict checker 추가
4. clarification loop API 연결
5. frontend Requirements Inbox와 연결

#### 5.3.2 Spec Writer Agent

입력:

- ready requirement
- accepted assumptions
- wiki context pack
- constraints

출력:

- spec/RFC draft
- API/UI/data model change list
- alternatives
- rollout/rollback plan
- test strategy

도구:

- wiki read
- architecture page retrieval
- API contract retrieval
- dependency map retrieval

품질 게이트:

- requirement id와 acceptance criteria trace
- non-goal 유지
- migration/rollback 포함
- security/operability 영향 분석

#### 5.3.3 Architecture Critic Agent

입력:

- spec draft
- architecture wiki
- current code index
- prior decisions

출력:

- blocking findings
- non-blocking concerns
- suggested simplifications
- required decision records

도구:

- code graph search
- dependency analyzer
- ADR search
- security checklist

품질 게이트:

- 과설계 탐지
- 기존 module boundary 위반 탐지
- migration risk 탐지
- ownership ambiguity 탐지

#### 5.3.4 Development Planner Agent

입력:

- approved spec
- architecture critic result
- code index
- test inventory

출력:

- dev plan
- task graph
- file/module ownership
- test plan
- implementation order
- parallelization candidates

도구:

- code index
- test discovery
- dependency graph
- risk classifier

품질 게이트:

- task가 acceptance criteria에 연결됨
- 각 task에 verification method 존재
- disjoint write sets가 명확함
- rollback-impact task가 식별됨

#### 5.3.5 Implementation Agent

입력:

- single task
- approved spec
- local code context
- allowed write scope

출력:

- code patch
- changed files list
- self-check notes
- test commands

도구:

- repository edit tools
- local test runner
- formatter/linter

제한:

- requirement/spec 밖의 opportunistic refactor 금지
- 다른 agent write scope 수정 금지
- failing test를 삭제하거나 완화 금지
- secret/config 값 생성 금지

품질 게이트:

- patch applies cleanly
- tests relevant to task pass
- changed files are inside assigned scope
- implementation maps to acceptance criteria

#### 5.3.6 Test Planner and Verifier Agents

Test Planner 입력:

- acceptance criteria
- implementation plan
- existing tests

Test Planner 출력:

- required unit/integration/e2e/manual tests
- negative cases
- regression cases
- test data requirements

Verifier 입력:

- patch/MR
- test results
- quality reports
- manual automation results

Verifier 출력:

- pass/fail verdict
- blocking findings
- residual risks
- wiki feedback candidates

품질 게이트:

- acceptance criteria coverage
- failing tests classified
- untested risk explicitly listed
- manual automation results linked when applicable

#### 5.3.7 Wiki Curator Agent

입력:

- merged spec
- MR diff summary
- test results
- release/manual automation results
- reviewer feedback

출력:

- wiki page updates
- stale/deprecated page candidates
- graph edge updates
- release note candidates

도구:

- wiki writer
- graph updater
- stale detector
- evidence validator

품질 게이트:

- verified evidence only
- stale pages not silently overwritten
- generated wiki diff reviewable
- page status updated correctly

### 5.4 Agent Runtime Architecture

Backend services:

- `AgentRunService`: agent run lifecycle, status, heartbeat
- `ContextPackService`: wiki/code/evidence context pack creation
- `RequirementService`: requirement storage and clarification loop
- `WikiGraphService`: page graph, stale detection, page status
- `DevPlanService`: task graph and MR linkage
- `AgentArtifactService`: output bundle storage

Core tables:

- `agent_runs`
- `agent_run_events`
- `requirements`
- `requirement_questions`
- `wiki_pages`
- `wiki_page_versions`
- `wiki_edges`
- `context_packs`
- `dev_plans`
- `dev_tasks`
- `verification_reports`

Runtime rules:

- every agent run has heartbeat/reaper
- every agent output is immutable artifact
- mutable state is updated only after validator passes
- event stream uses server-assigned seq
- final status uses backend policy, not agent self-report

### 5.5 Agent Output Bundles

Every agent produces a bundle.

```text
agent-runs/<agent_run_id>/
  input.json
  context-pack.json
  output.json
  findings.json
  events.jsonl
  metrics.json
```

Bundle requirements:

- input and output schema version
- prompt template version
- model/provider metadata
- evidence refs
- elapsed time and token usage
- validation result
- downstream target ids

### 5.6 Agent Evaluation Harness

Agent 개발은 eval 없이 진행하지 않는다.

Eval suites:

- ambiguous requirement clarification
- conflicting requirement detection
- spec traceability
- architecture overreach detection
- task breakdown quality
- implementation scope discipline
- test coverage mapping
- wiki stale detection

Metrics:

- schema pass rate
- clarification precision
- acceptance criteria coverage
- false ready-for-spec rate
- hallucinated wiki link rate
- unsupported code claim rate
- verifier catch rate
- human rejection rate
- token cost per accepted requirement

### 5.7 Development Guardrails

- requirement 없는 implementation 금지
- acceptance criteria 없는 PR 금지
- wiki link 없는 large change 금지
- reviewer 없는 generated spec publish 금지
- failed quality gate 산출물은 development context로 자동 승격 금지
- agent가 만든 code는 test와 human review를 통과해야 merge 가능

---

## 6. Backend API Additions

### 6.1 Requirements API

`POST /api/requirements/intake`

- raw request 저장
- source metadata 저장
- collector run trigger

`GET /api/requirements/{requirement_id}`

- structured requirement 조회

`PATCH /api/requirements/{requirement_id}`

- status, owner, priority 수정

`POST /api/requirements/{requirement_id}/clarifications`

- 답변/추가 정보 반영

`POST /api/requirements/{requirement_id}/promote-to-spec`

- ready requirement를 spec pipeline으로 승격

### 6.2 Wiki API

`GET /api/wiki/pages`

`GET /api/wiki/pages/{page_id}`

`POST /api/wiki/pages/draft`

`POST /api/wiki/pages/{page_id}/review`

`POST /api/wiki/pages/{page_id}/publish`

`GET /api/wiki/graph?node=...`

### 6.3 Development Pipeline API

`POST /api/dev-plans`

`GET /api/dev-plans/{plan_id}`

`POST /api/dev-plans/{plan_id}/tasks`

`POST /api/dev-plans/{plan_id}/verify`

`POST /api/dev-plans/{plan_id}/link-mr`

### 6.4 Agent Runtime API

`POST /api/agent-runs`

- agent type과 input artifact로 agent run 생성

`GET /api/agent-runs/{agent_run_id}`

- status, heartbeat, output bundle, validation result 조회

`GET /api/agent-runs/{agent_run_id}/events`

- server-assigned seq 기반 event replay

`POST /api/agent-runs/{agent_run_id}/heartbeat`

- long-running agent stuck 방지

`POST /api/agent-runs/{agent_run_id}/complete`

- output bundle 제출
- backend validator 통과 후 terminal status 결정

`POST /api/context-packs`

- requirement/spec/dev task에 필요한 verified wiki/code/evidence context pack 생성

`GET /api/context-packs/{context_pack_id}`

- agent 입력에 쓰인 context pack 조회

---

## 7. Frontend Additions

### 7.1 Requirements Inbox

기능:

- raw request 목록
- collector status
- open questions
- owner/priority
- ready for spec button
- rejected/superseded handling

### 7.2 Requirement Detail

탭:

- Summary
- Evidence
- Questions
- Acceptance Criteria
- Risks
- Linked Wiki
- Dev Tickets

### 7.3 LLM Wiki Explorer

기능:

- graph view
- page status
- stale pages
- conflicting pages
- evidence coverage
- recent updates
- agent/human authored diff

### 7.4 Development Control Room

기능:

- requirement -> spec -> task -> MR trace
- implementation status
- verification status
- blocked criteria
- wiki feedback status

---

## 8. Phased Roadmap

### Phase 1: Requirements Collector MVP

- requirement intake API
- structured requirement schema
- clarification loop
- requirement quality gate
- frontend requirements inbox

완료 기준:

- 모호한 요청이 바로 dev task로 가지 않는다.
- open question과 assumption이 분리된다.
- acceptance criteria가 없는 requirement는 spec으로 승격되지 않는다.

### Phase 2: LLM Wiki Drafting

- requirement page 생성
- spec/RFC page 생성
- wiki graph metadata
- evidence link
- wiki quality gate

완료 기준:

- requirement와 spec이 wiki에 stable link로 남는다.
- wiki page가 evidence 없이 publish되지 않는다.

### Phase 3: Development Pipeline Integration

- dev plan 생성
- task breakdown
- MR link
- test plan link
- verification result ingest

완료 기준:

- PR/MR이 requirement/spec/wiki와 연결된다.
- 구현 결과가 acceptance criteria 기준으로 검증된다.

### Phase 4: Feedback Loop

- release/manual automation 결과를 wiki에 반영
- incident/reviewer feedback을 requirement로 재수집
- stale wiki detection
- knowledge reuse metrics

완료 기준:

- 운영 관측이 다음 개발 요구사항으로 돌아온다.
- 반복 질문/반복 context 비용이 줄어든다.

---

## 9. Metrics

- requirement clarification rate
- requirements promoted to spec
- requirements rejected/superseded
- acceptance criteria coverage
- wiki evidence coverage
- stale wiki page count
- requirement-to-MR lead time
- MR linked to verified requirement percentage
- post-release manual feedback count
- repeated question token reduction
- human review rejection rate

---

## 10. Acceptance Criteria

- 모든 development plan은 requirement id를 가진다.
- 모든 requirement는 acceptance criteria 또는 blocking question을 가진다.
- wiki publish는 evidence refs 없이는 불가능하다.
- agent implementation은 spec/RFC link 없이는 시작되지 않는다.
- MR은 requirement/spec/test/wiki trace를 포함한다.
- release/manual automation 결과는 wiki feedback 후보로 들어간다.
- warning/failed quality output은 자동으로 verified wiki에 반영되지 않는다.

---

## 11. Summary

미래 단계의 핵심은 LLM이 코드를 더 빨리 쓰게 하는 것이 아니라, 팀의 지식과 요구사항이 누적되어 다음 개발 비용을 낮추는 시스템을 만드는 것이다.

Requirements Collector가 사람의 모호한 의도를 구조화하고, LLM Wiki가 그 구조화된 지식을 검증된 형태로 누적하며, Development Pipeline이 그 지식을 근거로 구현과 검증을 수행한다. 이 구조가 있어야 AI coding이 throwaway 생산성이 아니라 팀 운영 자산으로 바뀐다.
