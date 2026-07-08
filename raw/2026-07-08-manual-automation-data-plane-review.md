---
title: Manual-Automation Data Plane Review
date: 2026-07-08
scope: manual pipeline, MCP observation, release trigger, control-plane events, docs-hub submission
status: review
---

# Manual-Automation Data Plane Review

이 리뷰는 `manual` 파이프라인을 팀 운영용 manual-automation data plane으로 쓰기 전 막아야 할 결함과 개선점을 정리한다. 정적 docu-automation과 공유하는 Control Plane/runner/event 경계는 이전 리뷰(`2026-07-08-docu-automation-data-plane-review.md`)의 결론을 따르되, 여기서는 manual 고유 영역인 릴리스 트리거, 아티팩트/배포, MCP 세션, 관측 근거, 순회 커버리지, 매뉴얼 라이프사이클을 중점으로 본다.

## 현재 흐름

1. Manual run은 `runner.job.execute()`에서 `pipeline_id == "manual"`일 때 `_run_manual_pipeline()`로 분기한다.
   - `backend/runner/job.py:132`
   - `backend/runner/job.py:173`

2. `_run_manual_pipeline()`은 `MCP_ENDPOINT_URL` 존재만 확인한 뒤 `manual_pipeline.runner.run_manual()`을 호출한다. 현재 MCP endpoint, scenario file, manual themes는 source별 DB 값이 아니라 global `.env` 설정에 의존한다.
   - `backend/runner/job.py:181`
   - `backend/common/config.py:96`
   - `backend/common/config.py:103`

3. `run_manual()`은 `RunContext("manual")`로 공통 run/event 골격을 만들고, `out/<source>/runs/<run_id>/manual` 하위에 관측 로그, screenshots, coverage, manual docs를 저장한다.
   - `backend/manual_pipeline/runner.py:73`
   - `backend/manual_pipeline/runner.py:76`
   - `backend/manual_pipeline/runner.py:79`

4. 실행 단계는 현재 artifact -> deploy -> connect -> traverse-scenario -> traverse-explore -> coverage -> manual generation -> lifecycle 순이다. artifact/deploy는 PoC stub이고 실제 릴리스 아티팩트 획득, 전송, 설치 실행은 구현되어 있지 않다.
   - `backend/manual_pipeline/runner.py:87`
   - `backend/manual_pipeline/runner.py:93`
   - `backend/manual_pipeline/runner.py:141`

5. MCP bridge는 SSE/stdio session을 background event loop에 열고, 모든 MCP tool call 결과를 `ObservationLog`에 기록한다. 대형 base64 screenshot은 파일로 분리한다.
   - `backend/common/mcp_bridge.py:40`
   - `backend/common/mcp_bridge.py:116`
   - `backend/common/mcp_bridge.py:202`

6. 시나리오 단계는 JSON scenario file을 읽어 LLM 없이 MCP tool을 순서대로 실행한다. 실패 step은 ERR로 기록하고 다음 step을 계속 실행한다.
   - `backend/manual_pipeline/scenarios.py:40`
   - `backend/manual_pipeline/traversal.py:28`
   - `backend/manual_pipeline/traversal.py:48`

7. 자율 탐색은 LangGraph explorer가 MCP tools를 사용하고, coverage JSON은 explorer의 최종 JSON 자기보고에서 추출한다.
   - `backend/manual_pipeline/traversal.py:56`
   - `backend/manual_pipeline/traversal.py:80`

8. 매뉴얼 writer/critic은 관측 로그를 유일한 사실 근거로 사용한다. critic fail hard cap 이후에도 `auto_generated_warning`이 붙은 문서가 저장될 수 있다.
   - `backend/manual_pipeline/generate.py:46`
   - `backend/common_pipeline/verify.py:184`
   - `backend/manual_pipeline/prompts.py:113`

9. docs-hub 제출은 runner 공통 `submit_to_targets()` 경로를 통해 수행된다. manual pipeline은 sha pointer를 쓰지 않고 complete payload의 `last_processed_sha`는 빈 값이다.
   - `backend/runner/job.py:138`
   - `backend/runner/job.py:140`
   - `backend/tests/test_runner_job.py:231`

10. Release/tag 자동 트리거는 `TagPoller`가 `SourceReleaseTag` 북마크와 manual `Run` 생성을 담당한다. 현재 poller는 run 생성과 bookmark update만 수행하고 runner launch는 하지 않는다.
   - `backend/controlplane/services/tag_poller.py:45`
   - `backend/controlplane/services/tag_poller.py:63`
   - `backend/controlplane/services/scheduler.py:93`

## Findings

### P0. Release/tag poller creates manual runs but does not launch the runner

`TagPoller.poll_once()`는 새 태그를 찾으면 `RunService.create_run(... pipeline_id="manual")`을 호출하고 `SourceReleaseTag` bookmark를 갱신한다. 그러나 생성한 run을 `launch_runner()`로 넘기지 않는다. `SourceScheduler._poll_release_tags()`도 `poll_once()` count만 로그로 남긴다.

근거:
- `backend/controlplane/services/tag_poller.py:63`
- `backend/controlplane/services/tag_poller.py:68`
- `backend/controlplane/services/scheduler.py:93`
- `backend/controlplane/services/scheduler.py:96`

영향:
- 자동 trigger가 켜져도 manual pipeline이 실제 실행되지 않고 `pending` run만 쌓인다.
- 더 치명적으로 bookmark는 이미 새 태그로 전진하므로, 이후 poll에서는 같은 태그를 다시 실행하지 않는다. 즉, 자동화가 실행 없이 태그를 소비한다.

개선:
- poller가 run 생성 후 runner launch까지 수행해야 한다.
- launch 실패 시 bookmark를 전진하지 않거나, bookmark에 `last_run_id`와 `launch_status`를 저장하고 failed run으로 남긴다.
- `SourceReleaseTag` 정책을 "run 생성 후 mark seen"이 아니라 "runner launch 성공 또는 terminal completion 후 mark processed"로 재정의한다.

Acceptance:
- 새 태그 발견 시 `Run.status`가 `pending -> running/done/failed`로 진행해야 한다.
- `Popen` 실패 또는 launch 실패 시 `last_seen_tag`가 전진하지 않거나 실패 상태가 명시되어야 한다.

### P0. Artifact acquisition and deploy are stubs, but decisions require exe/msi transfer and silent install

Manual pipeline 결정문은 릴리스 아티팩트를 소비하고, exe/msi를 담당자가 선택하며, MCP가 전송과 설치 실행까지 수행해야 한다고 정한다. 현재 `run_manual()`의 `artifact`와 `deploy` stage는 note만 남기는 stub이다.

근거:
- `backend/manual_pipeline/runner.py:87`
- `backend/manual_pipeline/runner.py:90`
- `wiki/decision/decision-artifact-consumption.md:8`
- `wiki/decision/decision-artifact-type-dispatch.md:32`

영향:
- 현재 manual run은 "새 릴리스 버전의 앱"을 문서화한다는 보장이 없다.
- 이미 떠 있는 세션 호스트 앱을 관측하므로 tag/release trigger와 실제 관측 대상 버전이 어긋날 수 있다.
- generated manual의 `generated_from`은 run id일 뿐 릴리스 버전/아티팩트 digest와 연결되지 않는다.

개선:
- source registration에 artifact selector를 추가한다.
  - package registry URL 또는 release asset link
  - allowed asset pattern
  - installer type: exe/msi
  - silent install command/template
  - app launch/readiness probe
- run context에 release tag, release object, artifact URL, checksum, install command를 포함한다.
- `artifact` stage는 다운로드와 checksum 검증을 수행해야 한다.
- `deploy` stage는 MCP file transfer, install, launch, readiness observation까지 끝내야 done이다.

Acceptance:
- manual run summary에 `release_tag`, `artifact_name`, `artifact_sha256`, `installed_version`이 남아야 한다.
- artifact/deploy 실패는 terminal `failed`여야 하며, manual generation으로 넘어가면 안 된다.

### P0. Manual pipeline uses global MCP/scenario settings instead of per-source app registration

결정문은 app host IP/port, UI secret, scenario set이 app/source registration의 일부로 DB에 저장되어야 한다고 정한다. 현재 runner는 global `.env`의 `MCP_ENDPOINT_URL`, `MANUAL_SCENARIO_FILE`, `MANUAL_THEMES`를 사용한다.

근거:
- `backend/runner/job.py:181`
- `backend/common/config.py:96`
- `backend/common/config.py:103`
- `backend/manual_pipeline/scenarios.py:3`
- `wiki/decision/decision-app-host-connection.md:14`
- `wiki/decision/decision-scenario-owner-dashboard.md:15`

영향:
- 여러 source/manual app을 동시에 운영할 수 없다.
- source A release tag가 source B MCP host를 관측하는 오염이 가능하다.
- UI login secret, scenario ownership, host readiness가 source별로 감사되지 않는다.

개선:
- DB에 manual app profile을 추가한다.
  - `source_id`
  - `mcp_endpoint_url`, `mcp_transport`
  - host label/IP/port
  - scenario set JSON
  - secret references
  - artifact selector
  - enabled/readiness status
- `/api/runner/context`가 manual run일 때 source별 manual profile을 내려줘야 한다.
- global env는 local CLI/dev fallback으로만 남긴다.

Acceptance:
- 두 source가 서로 다른 MCP endpoint/scenario set으로 manual run을 동시에 실행할 수 있어야 한다.
- MCP endpoint가 없는 manual-enabled source는 trigger 단계에서 400 또는 failed preflight가 되어야 한다.

### P0. Manual completion has no version pointer or processed-release state

Static pipeline은 `last_processed_sha`로 멱등성을 확보하지만 manual pipeline은 `last_processed_sha`를 쓰지 않는다. 주석상 "버전 포인터 전진은 MR 머지 후"라고 되어 있으나 DB 모델과 completion 경로에는 processed release/version pointer가 없다. tag poller bookmark는 "seen"일 뿐 "processed/manual generated/MR submitted/merged"와 다르다.

근거:
- `backend/manual_pipeline/runner.py:175`
- `backend/runner/job.py:140`
- `backend/controlplane/models.py:186`
- `backend/controlplane/services/tag_poller.py:143`

영향:
- 같은 release에 대해 run 재시도/재생성/MR 갱신 정책을 안정적으로 정의할 수 없다.
- failed run도 tag bookmark가 전진하면 자동 재처리되지 않는다.
- MR merge 후 어떤 앱 버전까지 manual docs에 반영됐는지 DB SoT가 없다.

개선:
- `source_manual_versions` 또는 `source_release_tags` 확장:
  - `last_seen_tag`
  - `last_triggered_tag`
  - `last_submitted_tag`
  - `last_merged_tag`
  - `last_successful_run_id`
  - `artifact_digest`
- complete webhook은 manual run의 `release_tag`, `artifact_digest`, `mr_url`, `doc_count`, `warning_count`를 기록한다.
- MR merge feedback 또는 사람 확인 후 `last_merged_tag`를 전진한다.

Acceptance:
- failed manual run 후 같은 release를 재시도할 수 있어야 한다.
- pipeline status에서 source별 마지막 manual documented version이 보여야 한다.

### P1. Scenario step failures continue and can still produce manuals as successful

`run_scenarios()`는 step 실패를 `ok_all=False`로 표시하지만 다음 step을 계속 실행한다. scenario가 failed로 끝나도 `run_manual()`은 exploration과 generation으로 계속 진행한다. 관측 로그에는 ERR가 남지만 terminal status는 done이 될 수 있다.

근거:
- `backend/manual_pipeline/traversal.py:48`
- `backend/manual_pipeline/traversal.py:51`
- `backend/manual_pipeline/runner.py:104`
- `backend/manual_pipeline/runner.py:141`

영향:
- 로그인, 앱 기동, 필수 화면 진입 같은 critical scenario가 실패해도 manual이 생성된다.
- writer가 "관측되지 않음"을 쓰더라도 run status는 성공으로 보일 수 있다.
- 운영자는 핵심 시나리오 실패와 coverage 부족을 pipeline failure로 인지하지 못한다.

개선:
- scenario에 `required`, `continue_on_failure`, `critical_step` 필드를 추가한다.
- required scenario 실패 시 generation을 막고 run을 failed 또는 partial로 종료한다.
- non-critical 실패는 `done_with_warnings`로 표시하고 MR 본문에 failed scenario를 넣는다.

Acceptance:
- required login/bootstrap scenario 실패 시 manual docs가 생성되지 않아야 한다.
- non-critical scenario 실패는 run summary와 pipeline status에 warning/failure count로 보여야 한다.

### P1. Coverage is explorer self-report, not a measured denominator

결정문은 시나리오 도달 + 탐색 도달을 합산해 커버리지 지표와 누락 표시를 요구한다. 현재 coverage는 scenario result와 explorer가 마지막에 출력한 `visited/unreached` JSON 자기보고를 그대로 저장한다. 전체 기능 denominator는 없다.

근거:
- `backend/manual_pipeline/traversal.py:80`
- `backend/manual_pipeline/runner.py:121`
- `backend/manual_pipeline/runner.py:126`
- `wiki/decision/decision-coverage-metric-gap.md:15`

영향:
- "전수 순회" 또는 "모든 기능"에 대한 운영 지표가 없다.
- explorer가 JSON을 못 내면 빈 visited/unreached가 들어가도 pipeline은 계속 진행한다.
- 대시보드는 미도달 기능을 실제 목록으로 표시할 수 없다.

개선:
- coverage denominator를 구성한다.
  - scenario registry의 expected screens/features
  - MCP UIA tree/menu scrape에서 발견한 candidates
  - release/app profile의 route/menu manifest
- observation log에서 visited screen/control IDs를 정규화해 측정한다.
- `coverage_pct`, `expected_count`, `visited_count`, `unreached_count`, `unknown_count`를 run summary에 넣는다.
- coverage가 threshold 미만이면 generation을 막거나 warning status로 둔다.

Acceptance:
- manual run summary에 coverage denominator와 percentage가 있어야 한다.
- coverage threshold 미만 run은 `done` 단독 상태로 표시되면 안 된다.

### P1. MCP bridge exposes all tools by default, including potentially destructive tools

`McpBridge.sync_tools()`는 allowlist가 비어 있으면 MCP 도구 전체를 explorer에게 노출한다. prompt는 삭제/저장/터미널 명령 등을 금지하지만, 도구 레벨 enforcement는 없다. `manual_tool_allowlist` 기본값은 빈 값이다.

근거:
- `backend/common/config.py:107`
- `backend/common/mcp_bridge.py:138`
- `backend/common/mcp_bridge.py:144`
- `backend/manual_pipeline/prompts.py:28`

영향:
- 모델이 실수로 destructive tool을 호출할 수 있다.
- MCP server가 terminal/file transfer/window close 같은 도구를 노출하면 prompt-only guard로는 부족하다.
- 실제 UI 테스트 호스트 상태를 오염시켜 다음 run 재현성이 깨질 수 있다.

개선:
- allowlist를 기본 필수로 바꾼다.
- tool metadata에 위험 등급을 두고 `read_observe`, `navigate_safe`, `write_destructive` 등을 분리한다.
- scenario step은 담당자 승인된 도구만 허용하고, explorer는 observe/click/read 계열만 허용한다.
- destructive tool 호출은 bridge level에서 차단하고 event로 기록한다.

Acceptance:
- allowlist 없이 production manual run을 시작하면 preflight failed가 되어야 한다.
- 차단 도구 호출은 MCP까지 전달되지 않아야 한다.

### P1. Observation grounding can be truncated and lose cited evidence

`ObservationLog.evidence_block()`은 전체 block이 80k를 넘으면 preview를 줄이고, 그래도 넘으면 head/tail만 남긴다. writer는 `[oN]` 관측 태그를 인용하도록 요구하지만 중간 관측이 생략되면 writer/critic context에는 일부 tag 근거가 없다.

근거:
- `backend/manual_pipeline/observation.py:68`
- `backend/manual_pipeline/observation.py:83`
- `backend/manual_pipeline/prompts.py:47`
- `backend/manual_pipeline/prompts.py:98`

영향:
- 실제 observation JSONL에는 근거가 있어도 writer/critic prompt에는 없을 수 있다.
- critic이 근거 누락으로 fail하거나, 반대로 문서가 생략된 관측을 인용해도 critic이 검증하지 못할 수 있다.

개선:
- evidence block을 전량 prompt에 넣는 방식 대신 retrieval/index 방식으로 바꾼다.
- theme별로 relevant observations를 선택하는 deterministic prefilter를 둔다.
- generated doc의 `source_observations`를 parse한 뒤 해당 observation 원문을 critic에 반드시 제공한다.
- coverage/observation artifact를 docs-hub MR에 첨부 또는 링크한다.

Acceptance:
- 문서가 인용한 모든 `[oN]`은 critic prompt 또는 deterministic verifier에서 원문 확인 가능해야 한다.

### P1. Manual critic only sees first 9k chars of the generated document

`manual_critic_prompt()`는 검증 대상 문서를 `doc_markdown[:9000]`으로 자른다. 긴 operator manual이나 user manual의 후반부 hallucination, missing marker 근처 문제, 후반 source_observations 오염은 LLM critic이 보지 못한다. format verifier는 전체 doc을 보지만 grounding critic은 일부만 본다.

근거:
- `backend/manual_pipeline/prompts.py:93`
- `backend/manual_pipeline/prompts.py:95`
- `backend/manual_pipeline/generate.py:36`

영향:
- 긴 문서 후반부의 잘못된 절차가 pass될 수 있다.
- operator troubleshooting 표가 길어질수록 critic coverage가 약해진다.

개선:
- critic을 chunked verification으로 바꾼다.
- section별 grounding verdict를 합산한다.
- frontmatter의 source_observations 전체와 각 section cited observation을 deterministic하게 검사한다.

Acceptance:
- 9k 이후에 로그에 없는 UI claim을 삽입한 fixture가 critic fail되어야 한다.

### P1. Hard-cap warning documents are submitted as normal done runs

`verified_generate()`는 검증 실패가 max retry를 넘으면 warning frontmatter를 붙이고 문서를 반환한다. `run_manual()`은 warned theme을 summary에 담지만 terminal status는 done이다. MR 제출도 계속된다.

근거:
- `backend/common_pipeline/verify.py:72`
- `backend/common_pipeline/verify.py:184`
- `backend/manual_pipeline/runner.py:159`
- `backend/manual_pipeline/runner.py:176`

영향:
- 사람 리뷰 게이트는 유지되지만 pipeline health는 품질 저하를 성공으로 집계한다.
- manual docs 신뢰도를 추적하기 어렵다.

개선:
- manual run quality status를 추가한다.
  - `done`
  - `done_with_warnings`
  - `partial`
  - `failed`
- warning count, failed scenario count, coverage threshold를 pipeline status에 노출한다.
- MR body에 warning themes와 critic feedback을 넣는다.

Acceptance:
- warned manual doc이 있는 run은 pipeline status에서 warning으로 표시되어야 한다.

### P1. Deprecated lifecycle mutates local files outside generated summary and can be lost from MR projection

`mark_deprecated_candidates()`는 `out_dir/*.md` 중 keep set에 없는 문서에 deprecated frontmatter를 직접 쓴다. 그러나 `summary["themes"]`에는 이번 생성 theme만 들어가며, `projection_summary()`는 `summary["themes"]` file만 docs-hub MR 대상으로 삼는다. deprecated로 수정된 기존 문서가 MR에 포함되지 않을 수 있다.

근거:
- `backend/manual_pipeline/lifecycle.py:29`
- `backend/manual_pipeline/runner.py:170`
- `backend/manual_pipeline/runner.py:172`
- `backend/runner/job.py:54`

영향:
- local file에는 deprecated 표시가 생기지만 docs-hub에는 전달되지 않는다.
- 삭제 유예 정책이 review gate까지 도달하지 않는다.

개선:
- lifecycle mutation을 `summary["themes"]` 또는 별도 `summary["artifacts"]`에 포함한다.
- MR plan이 deprecated candidates를 upsert 대상에 포함해야 한다.
- deprecated 후보는 run summary와 MR body에 명시한다.

Acceptance:
- deprecated candidate가 생긴 run의 MR plan에 해당 file change가 포함되어야 한다.

### P1. Manual run output paths are not source/version isolated within the manual subdirectory

`run_manual()`은 run별 out root 아래 `manual/`을 쓰므로 Control Plane runner 경로에서는 run isolation이 된다. 그러나 manual CLI/resume 또는 local mode에서는 같은 `out/manual/user-manual.md`를 반복 갱신한다. lifecycle 판단도 기존 file 존재 여부만으로 add/update를 결정한다.

근거:
- `backend/manual_pipeline/runner.py:76`
- `backend/manual_pipeline/lifecycle.py:24`
- `backend/manual_pipeline/main.py:48`

영향:
- local CLI와 Control Plane run 결과가 다른 lifecycle 의미를 갖는다.
- release version별 비교가 아니라 같은 파일 존재 여부만으로 add/update가 결정된다.

개선:
- manual output에 release/version dimension을 명시한다.
- lifecycle 판단은 docs-hub target current state와 previous successful manual version을 기준으로 해야 한다.
- local CLI도 `out/manual/runs/<run_id>` 구조로 맞춘다.

Acceptance:
- 같은 source의 v1/v2 manual run이 서로 다른 run artifact와 명확한 docs-hub target diff를 가져야 한다.

### P2. `connect()` can leave a background thread/session if ready times out

`McpBridge.connect()`는 background thread를 시작하고 `_run_session()` ready future를 기다린다. `ready.result(timeout=60)`이 timeout되면 호출부로 예외가 올라가지만 session coroutine/thread 정리는 `RunContext.__exit__`의 `bridge.close()`에 의존한다. `_stop`이 아직 설정되지 않은 구간이면 close가 loop stop만 시도하고 session future 상태는 불명확하다.

근거:
- `backend/common/mcp_bridge.py:67`
- `backend/common/mcp_bridge.py:75`
- `backend/common/mcp_bridge.py:94`

영향:
- MCP endpoint 장애 시 dangling thread/session 가능성이 있다.
- 반복 실패 시 runner process 종료 지연 또는 resource leak이 생길 수 있다.

개선:
- `connect()` timeout 시 `_session_fut.cancel()`과 loop shutdown을 명시한다.
- connect timeout을 settings로 분리한다.
- connect 실패 event detail에 endpoint, transport, timeout을 남긴다.

Acceptance:
- MCP connect timeout 테스트 후 background thread가 남지 않아야 한다.

### P2. MCP observation stores tool args/previews without secret redaction

ObservationLog는 tool args와 preview를 JSONL과 evidence prompt에 그대로 저장한다. app login secret을 scenario/MCP args로 주입하게 되면 비밀이 observation log, prompt, generated docs 근거에 노출될 수 있다.

근거:
- `backend/manual_pipeline/observation.py:22`
- `backend/manual_pipeline/observation.py:52`
- `backend/manual_pipeline/observation.py:74`
- `wiki/decision/decision-app-host-connection.md:16`

영향:
- UI credential, token, endpoint secret이 out artifacts와 model prompt에 남을 수 있다.
- docs-hub MR에 근거 관측을 첨부할 경우 secret leak 위험이 커진다.

개선:
- ObservationLog 기록 전 redaction filter를 적용한다.
- secret-bearing scenario step은 `secret_ref`를 사용하고 실제 값은 bridge call 직전에 주입한 뒤 record에는 mask한다.
- preview에도 credential-like pattern masking을 적용한다.

Acceptance:
- scenario args에 password/token이 있어도 observation JSONL, event payload, generated doc에 평문이 없어야 한다.

### P2. Release trigger still uses latest tag, despite decision note that Release object is safer

`TagPoller`는 `conn.list_tags()`의 첫 항목을 latest로 사용한다. 결정문은 태그 naming이 불안정하고 Release 객체가 artifact link를 직접 물기 때문에 Release 객체로 좁힐지 미해결이라고 기록한다.

근거:
- `backend/controlplane/services/tag_poller.py:126`
- `backend/controlplane/services/tag_poller.py:133`
- `wiki/decision/decision-release-tag-trigger.md:23`

영향:
- 태그가 많은 repo에서 manual run 폭주 또는 잘못된 tag 선택이 가능하다.
- artifact selector와 release asset 연결이 약하다.

개선:
- connector에 `list_releases()`와 release asset API를 추가한다.
- manual schedule 설정에서 trigger source를 `release` 또는 `tag`로 명시하되 production default는 release로 둔다.
- tag mode는 allowlist pattern이 있을 때만 허용한다.

Acceptance:
- release asset이 있는 repo에서는 Release object 기반으로 artifact URL을 가져와야 한다.

### P2. Frontend event issues from docu-automation review also affect manual runs

Manual pipeline도 동일한 `progress.v1` event, WS broadcaster, `useRunStream` ingest 경로를 쓴다. 따라서 아래 공통 결함은 manual run에도 그대로 적용된다.

공통 영향:
- WS overflow가 frontend를 connected 상태로 고립시킬 수 있다.
- WS event 후 fallback polling이 token/tool usage를 중복 집계할 수 있다.
- `run_status`가 selected run summary를 즉시 갱신하지 않는다.
- `pipelineStatus`, `overview`, `costs` invalidation이 늦다.

근거:
- `backend/manual_pipeline/runner.py:73`
- `backend/common_pipeline/run_context.py:16`
- `frontend/src/hooks/useRunStream.js:81`
- `frontend/src/hooks/useLiveSocket.js:85`

개선:
- 이전 docu-automation 리뷰의 event reliability 개선을 manual에도 공통 적용한다.

## Manual Data Plane에 필요한 추가 계약

### Run Context

Manual runner context는 최소한 아래 값을 포함해야 한다.

- `manual_profile_id`
- `mcp_endpoint_url`
- `mcp_transport`
- `scenario_set`
- `artifact_selector`
- `release_tag` or `release_id`
- `artifact_url`
- `artifact_digest`
- `install_command`
- `launch_command`
- `readiness_probe`
- secret references, not secret literals

### Run Summary

Manual run summary는 static과 다르게 아래 필드가 필요하다.

- `release_tag`
- `artifact_name`
- `artifact_digest`
- `installed_version`
- `observations`
- `coverage_pct`
- `scenario_completed`
- `scenario_failed`
- `manual_warning_count`
- `deprecated_candidates`
- `last_successful_manual_version`

### MR Body

Manual MR body에는 아래 항목이 들어가야 한다.

- 대상 source/app/version
- artifact URL/checksum
- scenario set version
- coverage summary
- failed/ skipped scenarios
- unreached screens/features
- generated manuals
- warning themes and critic feedback
- deprecated candidates
- observation log artifact link

## 권장 구현 순서

### 1단계: 자동 실행 최소 정합성

- TagPoller run 생성 후 runner launch 연결
- launch 실패 시 bookmark 전진 금지
- manual profile DB 모델 추가
- `/api/runner/context` manual profile 포함
- global MCP/scenario env는 local fallback으로 축소

### 2단계: 아티팩트/배포 실체화

- release object/asset API 확정
- artifact selector 등록 UI/API
- download/checksum stage 구현
- MCP file transfer/install/launch/readiness stage 구현
- installed version observation 기록

### 3단계: 순회/근거 신뢰성

- scenario required/critical flag
- safe tool allowlist 기본 필수화
- secret redaction
- deterministic coverage denominator
- cited observation verifier
- chunked critic

### 4단계: 운영 상태와 MR 품질

- manual version pointer 모델
- warning/partial terminal status
- deprecated candidate MR inclusion
- manual pipeline status KPI
- event reliability 공통 개선 적용

## 테스트 보강 목록

- `test_tag_poller_launches_manual_runner`
- `test_tag_poller_does_not_mark_seen_when_launch_fails`
- `test_manual_context_uses_source_manual_profile`
- `test_manual_fails_without_source_mcp_profile`
- `test_manual_artifact_download_checksum_failure_blocks_generation`
- `test_manual_deploy_failure_blocks_generation`
- `test_required_scenario_failure_blocks_generation`
- `test_noncritical_scenario_failure_marks_warning`
- `test_manual_tool_allowlist_blocks_destructive_tools`
- `test_observation_log_redacts_secret_args_and_preview`
- `test_manual_critic_checks_claim_after_9000_chars`
- `test_cited_observations_are_all_available_to_verifier`
- `test_deprecated_candidates_are_included_in_mr_plan`
- `test_manual_warning_status_is_visible_in_pipeline_status`

## 최종 판단

Manual pipeline은 구조적으로는 맞는 방향이다. 정적 파이프라인과 분리되어 있고, 관측 로그를 유일 근거로 삼으며, 시나리오와 자율 탐색을 나눈 점은 좋다. 하지만 현재 구현은 아직 PoC에 가깝다.

운영 자동화로 보기 어려운 핵심 이유는 세 가지다.

1. release/tag poller가 run을 만들 뿐 실행하지 않고, bookmark를 먼저 전진시킬 수 있다.
2. artifact acquisition/deploy/install이 stub이라 관측 대상 앱 버전이 release와 연결되지 않는다.
3. source별 MCP host/scenario/secret/artifact profile이 DB SoT가 아니라 global env에 묶여 있다.

따라서 manual-automation data plane의 첫 목표는 "관측해서 문서를 만든다"가 아니라 "어떤 release의 어떤 artifact를 어떤 host에 설치했고, 어떤 scenario/coverage로 관측했으며, 어떤 manual MR을 만들었는가"를 DB와 MR에서 끝까지 추적 가능하게 만드는 것이다. 이 추적성이 생기기 전까지는 manual output을 팀 운영 파이프라인의 견고한 산출물로 보기 어렵다.

## Cross-Document Review Updates

Frontend/API/AI-agent 계획과 대조한 결과, manual-automation 리뷰에 아래 보강을 추가한다.

### MCP-VNC Monitoring Contract

manual run에서 `mcp-vnc`가 원격 환경을 제어하므로, Control Plane은 VNC session을 first-class 상태로 관리해야 한다.

추가 요구:

- source manual profile에 `vnc_enabled`, `vnc_host`, `vnc_port`, `vnc_gateway_policy`를 추가한다.
- runner는 mcp-vnc 연결/제어/관측 상태를 `/api/webhook/vnc-session`으로 보고한다.
- frontend는 `/api/runs/{run_id}/vnc-session`으로 view-only session metadata를 조회한다.
- browser는 직접 `ip:port` TCP VNC에 붙지 않고 backend gateway websocket을 사용한다.
- VNC 연결 실패는 manual run 실패가 아니라 monitor availability 문제로 분리한다.
- mcp-vnc tool failure는 scenario step failure로 기록한다.

### Live View vs Evidence

VNC 화면은 운영자가 현재 원격 제어를 보는 live view일 뿐, 최종 문서 근거가 아니다.

품질 기준:

- 문서 인용 근거는 저장된 observation id, screenshot artifact, log artifact만 허용한다.
- VNC stream frame은 evidence pack에 직접 저장하지 않는다.
- screenshot이 필요하면 runner/mcp-vnc가 redaction 후 artifact로 저장하고 evidence item으로 등록한다.
- critic은 VNC session 존재가 아니라 evidence artifact 존재를 검증한다.

### Manual Profile API Contract

manual profile은 global `.env` fallback이 아니라 source registration의 일부다.

필수 API:

- `GET/PUT /api/sources/{source_id}/manual-profile`
- `POST /api/sources/{source_id}/manual-profile/preflight`
- scenario CRUD/lint/activate API
- artifact preflight API

Acceptance 추가:

- 두 source가 다른 MCP endpoint와 VNC endpoint를 사용해 동시에 manual run을 실행할 수 있어야 한다.
- frontend-facing profile에는 secret value와 VNC password가 노출되지 않아야 한다.
- runner context에만 필요한 secret value가 내려가야 한다.

### Terminal Status Alignment

- required scenario failure: `failed` 또는 `failed_quality_gate`
- non-critical scenario failure: `done_with_warnings`
- coverage threshold 미달: `failed_quality_gate` 또는 policy 기반 `done_with_warnings`
- VNC monitor 연결 실패: run status 유지, `vnc.status=error`
- artifact/deploy/install/readiness failure: generation 전 `failed`

### Final Review Corrections

마지막 상호 리뷰 기준으로 manual pipeline의 책임 경계를 아래처럼 확정한다.

- Manual runner는 scenario/coverage/artifact/VNC 결과를 각각 webhook으로 먼저 제출한다.
- Final Packager bundle이 backend consistency check를 통과한 뒤에만 complete webhook을 보낸다.
- `done_with_warnings`는 runner가 임의로 결정하지 않고 backend가 `quality.status=warning`, coverage policy, scenario criticality를 보고 normalize한다.
- warning manual은 `publish_state=review_required`, critical coverage/scenario fail은 `publish_state=blocked`가 기본이다.
- VNC session availability는 `publish_state` 계산에 참여하지 않는다.
