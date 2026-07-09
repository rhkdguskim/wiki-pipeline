---
title: AI Agent Output Quality Strengthening Plan
date: 2026-07-08
scope: static docu-automation, manual-automation, shared AI agent runtime
status: plan
---

# AI Agent Output Quality Strengthening Plan

전제: data-plane의 run 상태, 이벤트 신뢰성, frontend live monitoring, manual artifact/deploy/profile 경계는 별도 개선으로 정리됐다고 본다. 이 문서는 그 위에서 **AI 에이전트가 더 좋은 산출물을 안정적으로 만들도록** agent 역할, evidence contract, prompt/output schema, 검증 루프, 평가 체계를 강화하는 계획이다.

핵심 방향은 단순하다.

1. LLM에게 “문서를 잘 써라”를 맡기지 않는다.
2. 입력 근거를 구조화하고, agent별 책임을 좁힌다.
3. writer와 critic을 분리하되, critic 결과가 다음 writer 입력으로 정확히 들어가게 한다.
4. 최종 산출물은 deterministic verifier와 LLM critic을 모두 통과해야 한다.
5. 품질 점수와 실패 사유가 run summary/MR에 남아야 한다.

## 목표 품질

### Static Docu-Automation

좋은 static 문서는 아래 조건을 만족해야 한다.

- diff 또는 init scan에서 실제로 관측한 파일/심볼/설정만 말한다.
- 변경의 의미를 사용자/운영자/개발자 관점으로 번역한다.
- 테마별 계약을 어기지 않는다.
- Mermaid, frontmatter, source_files, generated_from이 항상 유효하다.
- “무슨 파일을 근거로 이 문장을 썼는지” 추적 가능하다.
- 변경 없음, minor change, risky change를 구분해 과잉 문서 생성을 줄인다.

### Manual-Automation

좋은 manual 문서는 아래 조건을 만족해야 한다.

- 실제 실행 앱에서 관측한 화면, 버튼, 문구, 전이만 말한다.
- 절차형 문장은 모두 observation id를 인용한다.
- 사용자 매뉴얼과 운영자 매뉴얼의 독자 축이 섞이지 않는다.
- 미도달/실패/관측 불가 영역을 숨기지 않는다.
- critical scenario 실패나 낮은 coverage를 성공 문서처럼 포장하지 않는다.
- release artifact/version과 관측 대상 앱 버전이 문서 frontmatter에 남는다.

## 공통 Agent Pipeline

기존 구조는 writer -> format/lint -> critic -> retry 중심이다. 이를 아래 7단계로 확장한다.

```text
Evidence Builder
  -> Scope Planner
  -> Draft Writer
  -> Deterministic Verifier
  -> Grounding Critic
  -> Repair Writer
  -> Final Packager
```

### 1. Evidence Builder

책임:
- LLM 입력 전에 근거를 구조화한다.
- raw diff, source file snippets, observation logs, screenshots, scenario results를 agent가 먹기 좋은 evidence pack으로 만든다.

출력 schema:

```json
{
  "evidence_id": "evpack-...",
  "pipeline_id": "static|manual",
  "run_id": "...",
  "source_id": "...",
  "version_ref": "sha|release_tag|artifact_digest",
  "items": [
    {
      "id": "e1",
      "kind": "source_file|diff_hunk|config|observation|screenshot|scenario|coverage",
      "path": "optional/path",
      "title": "short label",
      "content": "bounded text",
      "metadata": {}
    }
  ],
  "limits": {
    "truncated": false,
    "omitted_count": 0
  }
}
```

규칙:
- writer/critic은 raw repository나 raw observation JSONL 전체를 직접 받지 않는다.
- 모든 주장 가능한 근거는 `evidence_id`로 참조된다.
- 긴 근거는 chunking하고, 문서 theme별 evidence subset을 만든다.

### 2. Scope Planner

책임:
- 어떤 문서를 생성/수정/스킵할지 결정한다.
- 문서별 목적, 독자, 필수 근거, 생성 위험도를 만든다.

Static planner 출력:

```json
{
  "docs": [
    {
      "theme": "architecture-overview",
      "action": "create|update|skip",
      "reason": "why this theme is affected",
      "required_evidence": ["e1", "e4"],
      "risk": "low|medium|high",
      "focus": ["changed dependency boundary", "new runtime setting"]
    }
  ]
}
```

Manual planner 출력:

```json
{
  "docs": [
    {
      "theme": "user-manual",
      "action": "create|update|skip|deprecate-candidate",
      "required_evidence": ["o1", "o7", "coverage"],
      "coverage_gate": "pass|warning|fail",
      "focus": ["main workflow", "unreached import dialog"]
    }
  ]
}
```

품질 효과:
- writer가 모든 것을 다 쓰려 하지 않고 좁은 목적에 집중한다.
- skip이 가능한 구조가 생겨 불필요한 hallucination과 비용을 줄인다.

### 3. Draft Writer

책임:
- planner가 준 scope와 evidence pack만 사용해 초안을 만든다.
- 문장마다 가능한 한 근거 id를 유지한다.
- 모르면 추측하지 않고 “관측되지 않음” 또는 “근거 없음”으로 남긴다.

공통 writer 규칙:
- 문서 마지막 줄은 `<!-- DOC-END -->`.
- frontmatter는 schema와 정확히 일치.
- 근거 없는 명령어, API endpoint, UI label, 설정값 금지.
- “일반적으로”, “보통”, “아마” 같은 추측어 금지.
- 긴 문서는 섹션 단위로 작성한다. 한 번에 전체 문서를 쓰지 않는다.

### 4. Deterministic Verifier

LLM critic 전에 반드시 실행한다.

검증 항목:
- frontmatter schema
- DOC-END 존재
- markdown fence 닫힘
- Mermaid parse
- source/evidence id 존재 여부
- cited observation id 존재 여부
- secret/token pattern redaction
- forbidden words/phrases
- minimum section coverage
- theme별 required sections

출력:

```json
{
  "result": "pass|fail",
  "errors": [
    {
      "code": "missing_evidence_id",
      "location": "section:Install",
      "message": "cited evidence o99 does not exist"
    }
  ]
}
```

품질 효과:
- 비싼 critic 전에 기계적으로 잡을 수 있는 오류를 제거한다.
- LLM critic이 문법/형식이 아니라 사실성과 적합성에 집중한다.

### 5. Grounding Critic

책임:
- 문서 claim이 evidence pack에 의해 지지되는지 판단한다.
- writer와 별도 agent identity/prompt를 사용한다.
- JSON verdict만 출력한다.

공통 verdict schema:

```json
{
  "result": "pass|fail",
  "score": 0.0,
  "stage1_schema": "pass|fail",
  "stage2_theme_fit": "pass|fail",
  "stage3_grounding": "pass|fail",
  "stage4_usefulness": "pass|fail",
  "blocking_findings": [
    {
      "severity": "blocker|major|minor",
      "claim": "document claim",
      "reason": "why unsupported or wrong",
      "required_fix": "specific edit instruction",
      "evidence_refs": ["e1", "o2"]
    }
  ],
  "nonblocking_notes": []
}
```

Critic 기준:
- `blocker`: hallucination, wrong procedure, secret leak, unsupported config/API/UI claim
- `major`: required section missing, theme mixed, coverage limitation hidden
- `minor`: wording, structure, redundant text

통과 기준:
- blocker 0
- major 0
- score >= 0.82
- deterministic verifier pass

### 6. Repair Writer

책임:
- critic findings만 수정한다.
- 전체 재작성 금지.
- 기존 valid sections와 evidence references를 유지한다.

Repair input:

```json
{
  "previous_doc": "...",
  "verifier_errors": [],
  "critic_findings": [],
  "repair_policy": {
    "preserve_valid_sections": true,
    "do_not_expand_scope": true
  }
}
```

재시도 정책:
- format fail: 최대 2회 repair
- grounding fail: 최대 2회 repair
- 같은 blocker가 2회 반복되면 `done_with_warnings`가 아니라 `failed_quality_gate`
- nonblocking minor만 남으면 `done_with_warnings` 가능

현재 hard-cap warning 방식은 유지하되, 성공으로 숨기지 않는다.

### 7. Final Packager

책임:
- 문서, evidence manifest, quality report, MR summary를 묶는다.

산출물:

```text
manual/user-manual.md
manual/operator-manual.md
quality/manual-user-manual.quality.json
quality/evidence-manifest.json
quality/coverage.json
quality/mr-summary.md
```

MR summary에는 아래를 포함한다.

- 생성/수정/스킵 문서
- quality score
- warning/failure 사유
- evidence coverage
- token/cost
- static: changed files and commit range
- manual: release artifact, scenario result, coverage, unreached screens

## Static Agent 강화

### Static Agent Roles

#### Change Classifier

입력:
- compare result
- changed file list
- diff hunks
- file metadata

출력:

```json
{
  "change_units": [
    {
      "id": "cu1",
      "files": ["backend/controlplane/api.py"],
      "change_type": "api|config|architecture|ui|test|docs|build",
      "significance": "trivial|minor|material|risky",
      "summary": "what changed",
      "doc_impact": ["architecture-overview", "requirements"]
    }
  ],
  "skip_reason": ""
}
```

강화 포인트:
- trivial/test-only/doc-only 변경은 문서 생성 skip 가능.
- risky change는 critic 기준을 높인다.

#### Static Evidence Collector

책임:
- changed file만이 아니라 인접 근거를 모은다.
- import 대상, config, README, public API, migration file을 포함한다.

규칙:
- source file raw read는 bounded.
- file별 evidence summary를 만든다.
- `source_files` frontmatter에 실제 사용한 파일만 넣는다.

#### Theme Writer

테마별 writer를 분리한다.

- `intro`: 제품/모듈 목적, 사용 맥락
- `requirements`: external behavior, env, dependency, constraints
- `architecture-overview`: components, boundaries, data flow
- `component-diagram`: Mermaid graph
- `dev-guide`: setup/build/test/dev workflow
- `api-protocol`: endpoint, event schema, auth, error behavior

각 writer는 theme contract만 본다. 다른 테마 내용을 끌어오면 critic fail.

#### Static Critic

추가 검증:
- code claim은 evidence source와 연결되어야 한다.
- API endpoint claim은 route definition evidence가 필요하다.
- env var claim은 config/settings evidence가 필요하다.
- Mermaid node/edge는 실제 component evidence가 필요하다.
- “지원한다”는 claim은 test 또는 implementation evidence가 필요하다.

### Static 품질 Gate

```text
Gate S1: Change classifier produced non-empty or valid skip
Gate S2: Evidence pack has all required files
Gate S3: Draft schema/markdown valid
Gate S4: Mermaid valid if diagram theme
Gate S5: Grounding critic pass
Gate S6: MR summary includes commit range and generated docs
```

Fail policy:
- S1 fail: run failed
- S2 fail: run failed
- S3/S4 fail after retry: failed_quality_gate
- S5 fail after retry: failed_quality_gate
- minor warnings only: done_with_warnings

## Manual Agent 강화

### Manual Agent Roles

#### Scenario Preflight Agent

LLM이 아니라 deterministic checker가 우선이다.

검증:
- scenario JSON schema
- tool names exist in connected MCP
- required scenarios present
- destructive tools blocked
- secret refs resolved but not logged
- app readiness probe exists

출력:

```json
{
  "result": "pass|fail",
  "scenario_count": 5,
  "required_count": 2,
  "missing_tools": [],
  "blocked_tools": [],
  "warnings": []
}
```

#### Safe Explorer

현재 explorer는 prompt로 안전 규칙을 준다. 이를 tool policy로 강화한다.

도구 등급:

```json
{
  "observe": ["screenshot", "screen_info", "uia_tree", "window_list"],
  "safe_navigation": ["click", "hotkey", "scroll"],
  "guarded": ["type_text", "open_file_dialog"],
  "blocked": ["delete", "save", "terminal", "file_write", "close_app", "install"]
}
```

Explorer는 `observe`와 제한된 `safe_navigation`만 쓴다. `guarded`는 scenario에서만 허용한다.

#### Coverage Assessor

책임:
- scenario result, UIA/menu scrape, explorer visited list를 합산한다.
- denominator와 numerator를 만든다.

출력:

```json
{
  "expected": [
    {"id": "screen-main", "name": "Main", "source": "scenario|uia|menu"}
  ],
  "visited": ["screen-main"],
  "unreached": [
    {"id": "screen-settings", "reason": "visible menu but not entered"}
  ],
  "coverage_pct": 74.2,
  "confidence": "low|medium|high"
}
```

Gate:
- required scenario coverage 100%
- overall coverage threshold configurable, default 70%
- below threshold => `done_with_warnings` or `failed_quality_gate` depending on required path

#### Manual Writer

문서별 강화:

`user-manual`:
- 절차 중심
- 모든 step에 `[oN]`
- 실패한 scenario는 성공 절차로 쓰지 않음
- unreached 기능은 “관측 범위와 한계”에 명시

`operator-manual`:
- 설치/기동/연결/설정/트러블슈팅 중심
- artifact/install/readiness evidence 필요
- 관측되지 않은 설정은 “관측되지 않음”
- user workflow 세부 사용법 금지

#### Manual Critic

추가 검증:
- 모든 procedure step에 observation ref가 있는가
- observation ref가 실제 log에 존재하는가
- ERR observation을 성공으로 서술하지 않았는가
- unreached를 숨기지 않았는가
- user/operator 내용이 섞였는가
- release/artifact/version frontmatter가 있는가

### Manual 품질 Gate

```text
Gate M1: Manual profile valid
Gate M2: Artifact/download/install/readiness valid
Gate M3: Scenario preflight pass
Gate M4: Required scenarios pass
Gate M5: Coverage threshold pass or warning
Gate M6: Draft schema/markdown valid
Gate M7: Observation citation verifier pass
Gate M8: Grounding critic pass
Gate M9: MR summary includes release/artifact/coverage/warnings
```

Fail policy:
- M1/M2/M3 fail: run failed before generation
- M4 fail: run failed unless explicitly noncritical
- M5 warning: done_with_warnings
- M6/M7/M8 fail after retry: failed_quality_gate

## Prompt Contract 개선

모든 writer prompt는 아래 구조를 강제한다.

```text
ROLE
You are ...

TASK
Write only the requested document/theme.

EVIDENCE CONTRACT
Use only evidence ids listed below.
Every factual claim must be grounded.

THEME CONTRACT
Perspective, audience, must_cover, do_not_cover.

OUTPUT CONTRACT
Frontmatter schema.
Required sections.
DOC-END marker.

FORBIDDEN
No guesses.
No uncited UI/API/config claims.
No secrets.
No tool-call text.
```

Critic prompt는 writer와 반대로 설계한다.

```text
ROLE
You are an adversarial documentation QA critic.

TASK
Find unsupported claims and contract violations.

PASS CRITERIA
Pass only if all gates pass.

OUTPUT
JSON only, schema fixed.
```

## Output Schema

### Static Frontmatter

```yaml
---
theme: architecture-overview
source_id: demo
generated_from:
  from_sha: abc
  to_sha: def
source_files:
  - backend/controlplane/api.py
evidence_pack: evpack-static-demo-def
quality:
  status: pass|warning
  score: 0.91
---
```

### Manual Frontmatter

```yaml
---
theme: manual/user-guide
source_id: demo
release:
  tag: v1.2.3
  artifact: DemoSetup.msi
  artifact_sha256: ...
manual_profile: profile-demo
source_observations:
  - o1
  - o2
coverage:
  pct: 82.5
  unreached_count: 3
quality:
  status: pass|warning
  score: 0.88
---
```

## Evaluation Plan

품질은 느낌이 아니라 fixture 기반으로 본다.

### Static Eval Fixtures

- config env var 변경
- API endpoint 추가
- auth behavior 변경
- UI-only frontend change
- docs-only change
- risky migration change
- no source change
- Mermaid-heavy architecture change

각 fixture 기대값:
- 생성해야 할 theme
- skip해야 할 theme
- required evidence files
- forbidden claims
- expected summary facts

### Manual Eval Fixtures

- happy path scenario
- login failure
- missing MCP tool
- screenshot-only evidence
- ERR observation
- unreached settings screen
- destructive tool attempt
- long manual over 9k chars
- deprecated candidate

각 fixture 기대값:
- run status
- coverage status
- generated docs
- required warnings
- forbidden claims
- citation coverage

### Metrics

Run마다 아래를 저장한다.

- `quality_score_avg`
- `quality_score_min`
- `critic_pass_rate`
- `repair_attempts`
- `grounding_failures`
- `schema_failures`
- `warning_count`
- `coverage_pct` for manual
- `skip_rate` for static
- `token_per_doc`
- `cost_per_passed_doc`

## Implementation Roadmap

### Phase 1: Contract First

- Evidence pack schema 추가
- Quality verdict schema 추가
- Deterministic verifier 결과 schema 추가
- Static/manual frontmatter 확장
- MR summary template 추가

Deliverable:
- fixture 없이도 writer/critic 입출력 계약이 고정된다.

### Phase 2: Agent Split

- Static Change Classifier 추가
- Static Evidence Collector 추가
- Manual Scenario Preflight 추가
- Manual Coverage Assessor 추가
- Writer/Repair Writer 분리
- Critic JSON schema 엄격화

Deliverable:
- writer가 넓은 판단을 하지 않고, 좁은 writing만 담당한다.

### Phase 3: Quality Gates

- deterministic verifier 강화
- citation verifier 추가
- chunked critic 추가
- fail/warning terminal status 연결
- quality report artifact 저장

Deliverable:
- 나쁜 문서가 조용히 done으로 통과하지 않는다.

### Phase 4: Eval Harness

- static eval fixtures
- manual eval fixtures
- golden expected verdicts
- CI에서 no-LLM deterministic tests
- optional nightly LLM eval

Deliverable:
- prompt 변경이 산출물 품질을 올렸는지/망쳤는지 회귀 판단 가능.

### Phase 5: Feedback Loop

- MR reviewer feedback 수집
- warning/fail findings 분류
- prompt/evidence selection 개선
- theme별 quality dashboard

Deliverable:
- 운영 데이터로 agent를 계속 개선한다.

## 우선순위 Backlog

### P0

- Evidence pack schema
- Quality verdict schema
- Static/manual deterministic verifier
- Manual citation verifier
- Writer/critic JSON output contract 고정
- failed_quality_gate/done_with_warnings 상태 모델

### P1

- Static Change Classifier
- Manual Scenario Preflight
- Manual Coverage Assessor
- chunked critic
- repair writer partial edit policy
- MR quality summary
- Final Packager `final-pack` bundle 생성

### P2

- Eval fixture suite
- token/cost quality dashboard
- reviewer feedback ingestion
- model A/B comparison
- theme-specific prompt tuning

## 최종 설계 판단

출력물이 좋아지려면 LLM 자체를 더 강하게 믿는 방향이 아니라, LLM이 실패하기 어려운 좁은 역할을 주는 방향이어야 한다.

Static은 “diff를 문서화”가 아니라 **변경 의미를 근거 파일에 묶어 theme별로 설명**하는 시스템이어야 한다. Manual은 “앱을 보고 매뉴얼 작성”이 아니라 **release artifact를 설치한 앱에서 수집한 observation evidence를 절차 문서로 변환**하는 시스템이어야 한다.

따라서 핵심 투자 지점은 agent prompt보다 앞단의 evidence pack과 뒷단의 verifier다. Prompt는 그 계약을 잘 지키게 만드는 얇은 계층이어야 하고, 품질은 deterministic verifier + grounding critic + eval fixture로 관리해야 한다.

## Cross-Document Review Updates

Data-plane, frontend, backend API 계획과 대조한 결과, AI agent 설계에 아래 실행 계약을 추가한다.

### Agent Output Must Be API-Writable

Agent가 만든 산출물은 파일로만 남기지 않고 Control Plane API resource로 저장 가능해야 한다.

필수 output bundle:

- `evidence-manifest.json`: `/api/webhook/evidence` 입력과 동일한 schema
- `quality-report.json`: `/api/webhook/quality` 입력과 동일한 schema
- `doc-outputs.json`: generated doc별 status, evidence count, schema/mermaid status
- manual run이면 `coverage.json`: `/api/webhook/coverage` 입력과 동일한 schema
- manual run이면 `artifact.json`: `/api/webhook/artifact` 입력과 동일한 schema

Final Packager는 위 bundle이 없으면 successful output으로 취급하지 않는다.

### Stable IDs

Writer/critic/reviewer가 같은 대상을 일관되게 참조하려면 stable id가 필요하다.

규칙:

- evidence id는 run 안에서 stable해야 한다.
- doc id는 theme/path 기반 deterministic id를 사용한다.
- finding id는 `gate + doc_id + code + location_hash` 기반으로 만든다.
- scenario step id는 scenario set version 안에서 stable해야 한다.
- repair attempt는 `repair_attempt` 번호와 previous finding id를 보존한다.

### Quality Status Normalization

Agent 내부 verdict와 backend/frontend status를 아래로 맞춘다.

- deterministic verifier result: `pass | fail`
- grounding critic result: `pass | fail`
- quality status: `pass | warning | fail | not_evaluated`
- run status: `done | done_with_warnings | failed_quality_gate | failed | partial`

`failed`는 실행 실패, `fail`은 quality/gate 판정값으로만 사용한다.

### VNC Boundary for Manual Agents

Manual agent는 VNC live stream을 직접 근거로 삼지 않는다.

규칙:

- Safe Explorer는 mcp-vnc를 사용할 수 있지만, writer에게 전달되는 근거는 observation/screenshot/log evidence item이어야 한다.
- VNC session metadata는 troubleshooting/context 용도이며 citation source가 아니다.
- screenshot evidence는 redaction과 artifact registration 후에만 evidence pack에 포함한다.

### Repair Loop Persistence

Repair loop 결과는 frontend/backend가 추적할 수 있어야 한다.

추가 output:

- repair attempt count
- repaired sections
- resolved finding ids
- remaining finding ids
- max attempts reached 여부

이 값은 quality report와 event stream 모두에 남긴다.

### Final Review Corrections

마지막 상호 리뷰 기준으로 AI agent output contract는 아래를 추가로 고정한다.

- Final Packager는 `publish_state`를 계산하지 않는다. `quality.status`, blocking findings, warning findings, coverage result만 제공하고, 최종 `publish_state`는 backend policy가 계산한다.
- Agent는 `done_with_warnings`를 직접 결정하지 않고 `quality.status=warning`과 findings severity를 보고한다.
- Runner는 Final Packager bundle을 `/api/webhook/final-pack`으로 제출해 backend consistency check를 받는다.
- final-pack ingest가 실패하면 complete webhook을 `done`으로 보내면 안 된다.
