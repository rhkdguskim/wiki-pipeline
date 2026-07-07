# Wiki Log

> append-only 연산 기록. 형식: `## [YYYY-MM-DD] <op> | <제목>` — 최근 이력: `grep "^## \[" log.md | tail -5`

## [2026-07-05] init | 위키 초기화 (schema.md 제정)
- Karpathy LLM Wiki 3계층(raw/ · wiki/ · schema.md) 구조 채택, 경량 frontmatter(4필드)
- 이전 시도(.omc/wiki, 스키마 없음)를 폐기하고 본 구조로 마이그레이션

## [2026-07-05] ingest | 설계 논의 기록
- raw: raw/2026-07-05-design-session.md (docs/01-design-summary.md에서 이동)
- 생성: summary-design-session, overview, decision-pull-model, decision-nightly-batch,
  decision-db-source-of-truth, decision-mr-review-gate, concept-idempotent-sha,
  entity-docs-hub, entity-mirero-gitlab, question-* 9건

## [2026-07-05] ingest | Docu-Automatic 레포 분석 노트
- raw: raw/2026-07-05-docu-automatic-notes.md
- 생성: summary-docu-automatic, entity-docu-automatic / 갱신: overview

## [2026-07-05] lint | 초기 구축 검증
- wiki 20페이지 + raw 2건: 깨진 링크 0 / 고아 0 / index 누락 0 / frontmatter 누락 0 / 파일명↔type 불일치 0 / 상대경로 깨짐 0 (PASS)

## [2026-07-05] schema | wiki 유형별 하위 폴더 구조 도입
- flat → `wiki/{summary,entity,concept,decision,question}/` 5개 폴더 (overview.md만 루트 고정)
- 파일명 접두사 유지 → `[[링크]]` 무변경, 파일명 전역 유일 보장. 하위 폴더 페이지의 raw/docs 상대경로는 `../../`
- schema.md 개정: 라우팅 표 경로, 링크 깊이 규칙, lint에 type↔폴더 일치 검사 추가

## [2026-07-05] lint | 폴더 구조 마이그레이션 검증
- wiki 20페이지 + raw 2건: 깨진 링크 0 / 고아 0 / index 누락 0 / frontmatter 누락 0 / 접두사·폴더 불일치 0 / 상대경로 깨짐 0 (PASS)

## [2026-07-05] query | concept-idempotent-sha 설명 요청
- 질문: "패턴이 감이 안 온다" → 책갈피 비유 + 3일 시나리오 표로 답변
- 갱신: concept-idempotent-sha (한 줄 요약·시나리오 표 추가, 규칙·방어 로직은 유지)

## [2026-07-05] schema | PRD·docs 계층 제거 (사용자 지시: 아직 작성하지 않음)
- 삭제: PRD.md + docs/ 19파일 (git 이력에 보존, 추후 위키 기반 재작성 예정)
- 갱신: wiki 8페이지의 docs 상세 링크 제거, overview·index·schema.md·CLAUDE.md의 PRD 참조 정리
- 현재 지식 소스는 raw/ + wiki/가 유일

## [2026-07-05] ingest | 다중 SCM 커넥터 도입 (GitLab 운영 + GitHub 테스트)
- raw: raw/2026-07-05-multi-scm-connector.md
- 생성: decision-scm-connector-abstraction, question-github-connector-scope
- 갱신: decision-pull-model, decision-mr-review-gate, entity-mirero-gitlab, overview, index
- 형상관리를 커넥터 인터페이스(compare·submit·auth)로 추상화. GitLab=운영 필수, GitHub=github.com 개인 레포 테스트용(Enterprise 불필요)
- 사용자 지시 반영: 기각 대안 섹션 없음(GitLab·GitHub 둘 다 지원이 목표). 요약 페이지 생략(1지시 → decision이 곧 합성)

## [2026-07-05] lint | SCM 커넥터 ingest 검증
- wiki 22페이지 + raw 3건: 깨진 링크 0 / 고아 0 / index 누락 0 / frontmatter 누락 0 / type↔폴더 불일치 0 / raw 상대경로 깨짐 0 (PASS)

## [2026-07-05] ingest | SCM 커넥터 정정 + 미확정 콘텐츠 정리 (사용자 지시)
- 정정: GitLab·GitHub는 위계 없는 **동등 1급 연동 대상**(이전 "GitLab 운영 / GitHub 테스트" 프레이밍 폐기). decision-scm-connector-abstraction·raw·entity-mirero-gitlab 재작성
- 삭제(질문 3): question-github-connector-scope(잘못된 테스트 프레이밍 산물), question-server-stack-db(스택 제안 미확정), question-existing-site-relation(110.110.10.70 사내 서버)
- 갱신: decision-db-source-of-truth(SQLite/Postgres·스택 링크 제거), entity-docs-hub(기존 사이트 링크 제거), overview·index(링크·카운트 22→19)
- raw 2건(design-session·docu-automatic-notes)의 서버·스택 언급은 불변 원본이라 보존, 위키 지식층에서만 제거

## [2026-07-05] schema | raw 참조를 wikilink로 통일 + Obsidian CLI 연동 (사용자 지시)
- 링크 규약 개정: raw 참조도 wiki 페이지처럼 `[[파일명]]` wikilink 사용 (기존 `../../raw/…` 상대경로 마크다운 링크 폐기). raw 파일명이 전역 유일해 폴더 깊이 무관하게 Obsidian이 해석·백링크 연결
- 정리: 4개 페이지의 상대경로 링크 5건 → `[[…]]` (summary-design-session, summary-docu-automatic, decision-scm-connector-abstraction, index[schema·overview 2건])
- schema.md 개정: 링크 규약(raw=wikilink), lint 항목(상대경로 마크다운 링크 잔존 검사로 교체), log 형식 예시
- 도구: Yakitrak obsidian-cli(현 notesmd-cli 0.3.6, Homebrew) 설치·vault 등록·default 지정. `search-content`로 `../../raw` 잔존 0건 검증
- overview: Control/Data Plane ASCII → mermaid flowchart 교체 (Mermaid Chart로 렌더 검증)

## [2026-07-05] ingest | 기술 스택 콘텐츠 제거 (요구사항 정의 단계 원칙)
- 원칙(사용자 지시): 위키는 요구사항 정의 단계 — 기술 스택(프레임워크·DB·언어·CI) 제안 보류
- raw 예외 삭제(사용자 명시 승인): design-session §7 기술스택표·§8 "스택 최종확정" 항목·"SQLite→Postgres" 문구 제거(§ 재번호 ~8), docu-automatic-notes의 110.110.10.70 사이트 줄 제거
- 갱신: entity-docs-hub 스택 중립화 — 파일트리(.py/.gitlab-ci.yml/config) → 파이프라인 4단계 서술, MR→MR/PR, Docusaurus는 확정 문서 사이트로 유지

## [2026-07-05] schema | concept↔decision 판별 테스트 명문화 + Control/Data Plane 분리 decision 신설 (사용자 지시)
- schema.md: 라우팅 표 뒤 "concept vs decision — 헷갈릴 때" 절 추가 (번복·이식성·기각 대안 3축 표 + 운영 규칙 2개: concept엔 '택했다' 금지, decision은 메커니즘을 concept 링크로 위임)
- 신설: decision-control-data-plane-split — 관리 서버/러너 평면 분리. 기각 대안=단일 프로세스(모놀리식), 핵심 동기=추후 LLM Wiki 통합·서비스화 포석
- 갱신: overview(분리 이유 문단 + 핵심 결정 목록에 링크), index(decision 등재, 카운트 19→20)

## [2026-07-05] schema | 인덱스 lazy-loading 2계층화 (사용자 지시)
- 단일 루트 index.md(전 페이지 카탈로그) → 허브 wiki/index.md + 폴더별 <type>-index.md 5개(summary/entity/concept/decision/question)
- 파일명 <type>-index.md로 전역 유일 유지([[decision-index]] 등), 허브는 wiki/index.md로 이동(루트 index.md 삭제)
- 카탈로그 파일(index.md·*-index.md)은 네비게이션 전용 — frontmatter·접두사·고아·type↔폴더 검사 제외
- schema.md 개정: 보조파일·등재 규약·ingest step4·query step1·lint 항목 2계층 반영. CLAUDE.md 위키 유지 규칙 갱신

## [2026-07-05] lint | 인덱스 2계층화 검증
- 지식 20 + 허브1 + 폴더 인덱스5: 폴더 인덱스 등재 누락 0 / 폴더→허브 링크 0누락 / 깨진 [[링크]] 0 / 상대경로 마크다운 링크 0 (PASS)

## [2026-07-05] query | 생성 엔진을 Claude Code 재사용 vs 자체 에이전트로 만들까
- 참조: entity-docu-automatic, summary-docu-automatic, overview, decision-control-data-plane-split, decision-scm-connector-abstraction, question-headless-claude-auth, 2026-07-05-docu-automatic-notes
- 합성: 엔진은 Data Plane 부품 → SCM 커넥터와 동형의 `엔진 인터페이스` 추상화 문제. A(현행 headless)/B(자체 에이전트)/C(하이브리드) 3갈래. 권고=인터페이스 먼저 정의 + 당분간 A + driver 시 B
- 신설: question-engine-runtime (status: open). 백링크: question-headless-claude-auth에 갈림길 링크 추가
- 갱신: question-index(등재), wiki/index 허브(question 7→8·총 20→21)

## [2026-07-05] lint | 2계층 인덱스 후속 중복 정리 (사용자 지시)
- 검사(지식 21 + 허브1 + 폴더인덱스5): 깨진 [[링크]] 0 / 고아 0 / 폴더 인덱스 등재 누락 0(engine-runtime 포함) / 상대경로 마크다운 링크 0 / type↔폴더·접두사·frontmatter 0불일치 (PASS)
- 중복 제거: overview "페이지 안내" 전체 카탈로그 삭제 → [[index]] 위임. 5개 폴더 인덱스와 이중 유지되던 것(이미 engine-runtime 누락 드리프트 발생)을 해소, Phase 1 블로킹 질문 3건 하이라이트만 유지. 제거 후 고아 0 재확인(폴더 인덱스가 inbound 보장)
- schema.md: overview 정의를 "서사 중심 · 전체 카탈로그는 index 위임"으로 갱신(라우팅 표)
- 허브 카운트(question 8·총 21)는 사용자 갱신분과 일치 확인

## [2026-07-05] query | 전체 기능 리뷰 + 추가 기능 브레인스토밍 (사용자 요청)
- 읽음: overview, entity/decision/concept/question 폴더 인덱스 + entity 3·decision 6·concept 1 전체
- 합성: 골격(감지→생성→제출)·신뢰성(멱등성·리뷰 게이트)은 촘촘, "생성 이후의 삶"(관측·피드백·활용)이 공백으로 진단
- 생성(유망 후보 4건, status:open): question-batch-observability, question-change-significance-filter,
  question-review-feedback-loop, question-doc-qa-rag
- 갱신: question-index(향후 기능 후보 섹션 추가), 허브 index(question 8→12·총 21→25). overview는 index 위임 구조라 미수정(드리프트 아님)

## [2026-07-05] ingest | 사용자/엔지니어 매뉴얼 추출 파이프라인 (신규, Docu-Automatic과 별개)
- raw: [[2026-07-05-manual-extraction-pipeline]]
- 생성: summary-manual-extraction-pipeline, entity-manual-pipeline, entity-remote-control-mcp,
  decision-manual-pipeline-separate, decision-artifact-consumption, decision-release-tag-trigger,
  decision-hybrid-app-traversal, decision-commit-history-manual-diff,
  concept-observation-grounding, concept-manual-lifecycle-diff,
  question-app-exec-environment, question-ui-coverage-completeness, question-manual-delete-safety,
  question-scenario-set-ownership, question-manual-theme-taxonomy, question-mcp-auth-network
- 갱신: overview(2차 모달리티 섹션 + Windows CI 명시 + 더보기 선행질문), summary/entity/concept/decision/question 폴더 인덱스, 허브 index(카운트 25→41·raw 3→4)
- 결정: MCP UI자동화(좌표 fallback)·하이브리드 순회·릴리스 태그 트리거·아티팩트 소비(빌드 안 함)·커밋히스토리+관측 기반 add/update/delete(삭제는 MR 제안)·docs-hub MR
- 정정 반영: 실행 기반=사내 Windows CI(기존 재사용, "신규 Linux 러너 필요" 판단 폐기), MCP가 파일전송으로 배포까지 담당

## [2026-07-05] lint | 매뉴얼 파이프라인 ingest 검증
- 지식 40 + 허브1 + 폴더인덱스5 + raw4: 깨진 [[링크]] 0 / 고아 0(신규 17건 전부 폴더 인덱스 등재) / 상대경로 마크다운 링크 0 / frontmatter 4필드 누락 0 / type↔폴더 불일치 0 (PASS)
- 허브 index 카운트 실측 일치: summary3·entity5·concept3·decision11·question18·overview1 = 41, raw4
- grep 오탐 4건 확인·기각: [[schema]](루트 schema.md 존재), [[링크]]·[[파일명]]·[[…]](log.md 규약 설명 프로즈, 실제 링크 아님)

## [2026-07-05] ingest | 앱 실행 호스트·연결·시크릿 모델 (Phase 1 게이트 답변)
- 소스: 사용자 답변(별도 호스트 / IP·port로 세션 MCP sw-rcs-session-mcp 제어 / app 등록 시 시크릿[로그인] 저장)
- 생성: decision-app-host-connection, question-secret-storage-security
- 갱신: question-app-exec-environment(open→**answered**, 답 링크), question-mcp-auth-network(MCP↔호스트 축 확정·AI 축 open 유지), entity-remote-control-mcp(연결 모델 섹션), entity-manual-pipeline(app 등록 필드 IP/port·시크릿), summary-manual-extraction-pipeline, decision/question 인덱스, overview(선행 확인 갱신), 허브 index(decision 11→12·question 18→19·총 41→43)
- 라이프사이클: question-app-exec-environment answered(decision-app-host-connection가 답). 시크릿 저장이 새 보안 질문 파생

## [2026-07-05] lint | 호스트·연결 모델 ingest 검증
- 지식 42 + 허브1 + 폴더인덱스5 + raw4: 깨진 [[링크]] 0(오탐 4 기각) / 고아 0 / answered 질문의 답 링크 존재(question-app-exec-environment→decision-app-host-connection) / 상대경로 링크 0 / frontmatter 0누락 / type↔폴더 0불일치 (PASS)
- 허브 index 카운트 실측 일치: summary3·entity5·concept3·decision12·question19·overview1 = 43, raw4

## [2026-07-05] ingest | overview 2모달리티 재구성 (사용자 지시: overview 개선)
- 도입부: 단일 정적 파이프라인 서술 → **정적(코드→기술문서·야간) + 행위(앱 관측→매뉴얼·릴리스)** 2모달리티로 재프레이밍
- 구조 ① 정적(기존 다이어그램, DP 라벨에 Windows·야간 명시) / 구조 ② 매뉴얼 파이프라인 **신규 mermaid** 추가: 릴리스 태그→관리서버(공유)→Windows CI 파이프라인→세션 MCP(IP/port)→별도 앱 호스트, 아티팩트·커밋히스토리·docs-hub MR·버전 전진 흐름
- 본문에 별도 호스트·IP/port·시크릿·하이브리드 순회·라이프사이클 diff 반영. Mermaid Chart 렌더 검증 PASS
- 갱신 파일: overview.md만 (인덱스·카운트 불변)

## [2026-07-05] ingest | 시크릿 보안 우선순위 하향 + AI 경로 질문 명확화 (사용자 판단)
- question-secret-storage-security: tags phase-2 → **deferred**, 본문에 "우선순위 낮음(게이트 아님)" 명시. question-index 라벨 갱신
- question-mcp-auth-network: "AI 호출 경로"를 자기설명적으로 재서술 — 생성 단계에서 LLM 호출 경로(폐쇄망/프록시/사내 게이트웨이), MCP 제어 채널과 별개 축임을 명시
- 카운트 불변(43). 사용자 확인: 시크릿 저장 보안은 현 설계 단계에서 중요하지 않음

## [2026-07-05] ingest | 코드 인덱싱 파이프라인 (codegraph 은닉 프로바이더 추상화)
- raw: [[2026-07-05-code-index-pipeline]]
- 생성: summary-code-index-pipeline, decision-code-index-pipeline, decision-code-index-provider-abstraction,
  concept-port-adapter, entity-codegraph, question-code-index-query-surface, question-scm-checkout, question-code-index-store
- 갱신: decision-pull-model·decision-nightly-batch(적용 범위 한정 — push 기각 근거는 AI 워크로드 전제, 번복 아님),
  decision-scm-connector-abstraction(checkout 질문 + port-adapter 링크), overview(구조 ③ 코드 인덱스 섹션),
  summary/entity/concept/decision/question 폴더 인덱스, 허브 index(카운트 43→51 · raw 4→5)
- 결정: 개발자 직접 조회용 코드 인덱스 파이프라인, 비-AI·빠름 → 짧은 주기 폴링(commit 수준 신선도; 야간 배치·webhook·소스 CI job 기각),
  프로바이더 인터페이스(index/query/manage)로 codegraph 은닉·교체 가능, code traversal 1급 연산, sha 포인터 파이프라인별 독립

## [2026-07-05] lint | 코드 인덱스 파이프라인 ingest 검증
- 지식 50 + 허브1 + 폴더인덱스5 + raw5: 깨진 [[링크]] 0 / 고아 0 / 폴더 인덱스 등재 누락 0 / frontmatter 4필드 누락 0 / 접두사·type↔폴더 불일치 0 / 상대경로 마크다운 링크 0 (PASS)
- 허브 카운트 실측 일치: summary4·entity6·concept4·decision14·question22·overview1 = 51, raw5
- answered 3건 답 링크 확인: app-exec-environment·mcp-auth-network=decision 링크, runner-ai-network=entity-mirero-gitlab 링크(사실 확인형 답 — 기각 대안 없어 decision 아님, 답 링크 존재로 판정)
- overview 드리프트 없음(구조 ③ 반영 확인) / 모순·중복 없음(pull·야간배치와의 긴장은 양쪽 "적용 범위" 절로 해소)

## [2026-07-05] ingest | AI 네트워크 경로 확보 확인 → 블로킹 질문 해제 (사용자 확인)
- 사용자 확인: 러너 → AI 서비스 네트워크가 뚫려 있음(폐쇄망 차단 아님). ※ 위 코드인덱스 lint(직전 항목)에 본 변경이 이미 포함·검증됨
- entity-mirero-gitlab: "러너→AI 네트워크 미확인 ⛔" → "확보됨 ✅"
- answered 전환: question-runner-ai-network(blocking 태그 제거·Phase 1 블로킹 해제), question-mcp-auth-network(MCP·AI 두 네트워크 축 모두 확정). 남은 AI 인증/실행 세부는 [[question-headless-claude-auth]]로 위임
- 갱신: overview 더보기(Phase 1 블로킹 3→2건), question-index(✅ 표기). 카운트 불변(51)

## [2026-07-05] ingest | 파이프라인 실시간 모니터링 (cross-cutting 요구사항)
- raw: [[2026-07-05-pipeline-monitoring]]
- 지시: 3개 파이프라인 + 향후 모든 파이프라인은 대시보드에서 진행상황 실시간 모니터링 필수, 설계 시 1급 제약으로 고려
- 생성: decision-pipeline-observability, concept-observability-contract, question-progress-event-contract
- 갱신: question-batch-observability(대시보드 축 요구사항 확정 → decision 링크, 알림/리포트만 open 잔존), decision-control-data-plane-split(④ 계약에 실시간 진행 추가), overview(공통 모니터링 섹션), decision/concept/question 폴더 인덱스, 허브 index(decision 14→15·concept 4→5·question 22→23·총 51→54·raw 5→6)
- 요약 생략(cross-cutting 지시 → decision이 곧 합성). concept↔decision: decision=우리 요구(대시보드 실시간·기각 대안 있음), concept=이식성 있는 관측성 계약 패턴

## [2026-07-05] lint | 모니터링 ingest 검증
- 지식 53 + 허브1 + 폴더인덱스5 + raw6: 깨진 [[링크]] 0(오탐 제외) / 고아 0(신규 3건 폴더 인덱스 등재) / frontmatter 4필드 0누락 / type↔폴더 0불일치 (PASS)
- 허브 카운트 실측 일치: summary4·entity6·concept5·decision15·question23·overview1 = 54, raw6

## [2026-07-05] ingest | 코드 인덱스 후속 확정 + codegraph 후보 조사 (세션 리밋 중단분 인계 완료)
- raw: [[2026-07-05-code-index-followup]] (직전 세션에서 열린 질문 3건에 대한 사용자 답)
- 생성(직전 세션): summary-code-index-followup, decision-code-index-mcp-serving(질의=MCP 서버),
  decision-runner-git-clone(checkout=러너 직접, 커넥터 4책임 기각), decision-code-index-versioning(버전 스냅샷+원자 교체)
- 보강(본 세션): entity-codegraph — codegraph-research 서브에이전트 결과(cg-colby·cgc 계약)를 반영, "조사 필요" → 두 후보 비교표로 교체. A(cg-colby) 권장 근거(가벼운 의존·자동 격리·폴링 정합·성숙도) 명시
- 갱신(본 세션, 직전 세션이 세션 리밋으로 누락한 후처리): overview(구조 ③에 MCP 서빙·git clone·형상관리 3항목+entity-codegraph 링크),
  decision/summary/question 폴더 인덱스(결정 3건·summary·scm-checkout ✅ 등재), 허브 index(카운트 54→57 · summary4→5·decision15→18·answered3→4)
- answered 전환: question-scm-checkout(open→answered, 답=decision-runner-git-clone)
- 결정: 질의 채널 MCP 서버(우선), 인덱싱 소스는 러너 git clone(커넥터 3책임 유지), 인덱스 형상 관리는 버전 스냅샷+원자 교체(in-place 기각)

## [2026-07-05] lint | 코드 인덱스 후속 ingest 검증
- 지식 57 + 허브1 + 폴더인덱스5 + raw7: 깨진 [[링크]] 0(schema 오탐 제외) / 고아 0(신규·갱신 전부 폴더 인덱스 등재) /
  frontmatter 4필드 0누락 / type↔폴더 0불일치 / 상대경로 마크다운 링크 0 (PASS)
- 허브 카운트 실측 일치: summary5·entity6·concept5·decision18·question23·overview1 = 58, raw7
- 부수 수정: question-ui-coverage-completeness frontmatter title 큰따옴표 이스케이프 결함(사전 존재) → single-quote로 정정(YAML 파싱 정상화)
- answered 4건 답 링크 확인: app-exec-environment·mcp-auth-network=decision 링크, runner-ai-network=entity-mirero-gitlab, scm-checkout=decision-runner-git-clone(본 세션 answered 전환)

## [2026-07-05] ingest | 코드 인덱스 파이프라인 최종 확정 (어댑터·질의 범위·저장소 평면)
- raw: [[2026-07-05-code-index-finalization]]
- 생성: summary-code-index-finalization, decision-code-index-adapter-cg-colby(어댑터 cg-colby 확정, cgc 기각),
  decision-code-index-single-repo-scope(v1 단일 레포, cross-repo 후순위), decision-code-index-store-plane(별도 질의 서비스 평면, Control Plane·이력 DB와 분리)
- 갱신: entity-codegraph(후보 조사 → "cg-colby 확정" 상태 전환, 열린 부분 닫음), overview(구조 ③에 어댑터·질의 범위·저장소 평면 3항목 추가),
  decision/summary/question 폴더 인덱스(결정 3건·summary·query-surface·code-index-store ✅ 등재), 허브 index(카운트 58→61 · summary5→6·decision18→21·answered4→6, raw7→8)
- answered 전환: question-code-index-query-surface(MCP 서빙·단일 레포 우선), question-code-index-store(별도 서비스 평면·버전 스냅샷)
- 결정: 어댑터=cg-colby(SQLite·자동 격리·증분 1급·1.2.0 안정), v1 질의=단일 레포, 인덱스 저장소=별도 질의 서비스 평면(MCP 서버가 소유)
- 코드 인덱스 파이프라인 결정 전목(8건) 확정 완료 — 쓰기/읽기/저장/형상/어댑터/범위 축 마무리

## [2026-07-05] query | 전체 open 질문 20건 사용자 결정 회수 + 위키 축적
- 사용자에게 20개 open 질문을 4개씩 5라운드로 질문 → 전건 답변 획득
- 생성(신규 decision 8): decision-engine-hybrid(엔진 하이브리드, 인터페이스+점진적 교체),
  decision-server-vm-self-token(사내 VM+자체 토큰), decision-schedule-per-source(과제별 대시보드 설정),
  decision-manual-delete-grace(deprecated 유예 후 삭제), decision-scenario-owner-dashboard(과제 담당자 대시보드 정의),
  decision-manual-taxonomy-two-reader(사용자/운영파트 2축), decision-coverage-metric-gap(커버리지 지표+누락 표시),
  decision-observability-event-contract(표준 스키마+가변 단위+webhook push), decision-change-filter-rule-based(규칙 기반 먼저)
- 확정(기존 decision 갱신): decision-mr-review-gate("최종 확정 필요" → 확정 전환, docs-hub 직접 MR),
  decision-code-index-versioning(열린 부분 소유 평면 → store-plane 링크로 닫음)
- answered 전환(11): question-engine-runtime·mr-vs-docs-auto·server-deploy-auth·schedule-policy·
  scenario-set-ownership·manual-theme-taxonomy·manual-delete-safety·ui-coverage-completeness·
  progress-event-contract·change-significance-filter (코드 인덱스 3건은 다른 세션이 이미 answered 처리)
- open 유지 + 방침 명시(8): question-headless-claude-auth(Phase 1 즉시 검증)·batch-observability(digest+알림+대시보드)·
  cost-estimation(PoC 실측)·theme-expansion(실측 후 우선순위)·review-feedback-loop(사람 큐레이션)·
  doc-qa-rag(Phase 3+ 도입)·secret-storage-security(운영 단계 연기)
- 충돌 해결: 코드 인덱스 3건(query-dual·incremental·store 보탬)은 다른 세션의 기존 decision(mcp-serving·runner-git-clone·store-plane)과 모순 → 사용자 판단으로 기존 decision 유지, 내가 만든 2개 decision 삭제 + versioning 보탠 내용 되돌림
- 인덱스 갱신: decision-index(신규 8 + incremental 항목 제거), question-index(11건 ✅ + 방침 명시), overview(Phase 1/2 결정 요약 추가)

## [2026-07-06] lint | 전체 위키 건강 점검 (71 페이지)
- 리포트: [[lint-report-2026-07-06]] (wiki/meta/)
- 통과: 깨진 링크 0 · frontmatter 4필드 71/71 · type↔폴더·접두사 전부 일치 · 폴더 인덱스 등재 정합 · stale 인덱스 0 · 상대경로 링크 0 · count 정합(71 페이지, question 16 answered)
- 발견 3건(승인 대기, 미수정): HIGH 1 · MEDIUM 1 · LOW 1
  - H1: question-progress-event-contract(answered)가 답 decision-observability-event-contract를 본문 역링크 안 함 → schema 위반 + 해당 decision이 약한 고아
  - M1: overview 모니터링 절이 decision-observability-event-contract 미언급(드리프트)
  - L1: 코드인덱스 summary 계보 미연결(약한 고아, 설계상 허용 — 개선 제안)
- 오탐 아님 처리: question-runner-ai-network(답이 entity로 귀결, decision 불요) · open question 7건(인바운드 부재 정상)
- 수정 완료(2026-07-06, 사용자 승인 자동 수정 3건):
  - H1: question-progress-event-contract에 "✅ 답" 블록 + [[decision-observability-event-contract]] 역링크 → 고아 해소
  - M1: overview 모니터링 절에 [[decision-observability-event-contract]] 문장 추가
  - L1: 코드인덱스 summary 3부작 시간순 계보 상호연결(pipeline↔followup↔finalization)
  - 재검증: 깨진 링크 0 · 고아 해소 · answered 링크 정합. runner-ai-network는 답이 entity 귀결로 정상.

## [2026-07-06] ingest | wish GitLab API 실측 조사
- raw: [[2026-07-06-wish-gitlab-api-survey]]
- 생성:
  - summary-wish-gitlab-api-survey
  - question-release-object-vs-tag-trigger (트리거 = 태그 vs Release 객체)
  - question-ci-less-source-policy (CI/릴리스 없는 방치 소스)
  - question-existing-ci-docs-stage (기존 CI docs stage 공존/대체)
  - question-blob-search-vs-code-index (내장 검색·CodeScene vs 코드 인덱스)
  - question-artifact-type-dispatch (아티팩트 타입 소스별 대응)
  - question-group-token-provisioning (최소 권한 group access token 발급)
- 갱신:
  - entity-mirero-gitlab (16.3 CE·KAS·OIDC scope·610 프로젝트·API 표면표·소스별 권한·5과제 프로파일 실측 확장)
  - entity-remote-control-mcp (MCP 컨테이너 실물 존재 근거)
  - decision-scm-connector-abstraction (GitLab 3책임 200 실증)
  - decision-mr-review-gate (CE approval 404 = 관례 기반 근거 보강, 모순 아님)
  - decision-artifact-consumption (아티팩트 실체 = Generic Package Registry 확인)
  - decision-release-tag-trigger (태그≫릴리스·규칙 4종 → Release 객체 검토 승격)
  - decision-runner-git-clone (러너 Windows·LFS 확인)
  - decision-code-index-pipeline (blob 검색·CodeScene 경계·웹훅 0개 배경)
  - 인덱스: summary-index, question-index, index(허브 카운트 7/29·78페이지·raw 9·2026-07-06)
- 판단: 사실 확정(CE approval 404·아티팩트=Generic Package·러너 Windows/LFS·MCP 컨테이너 실물·compare/MR 200)은
  question이 아니라 entity/decision에 fact로 반영. 결정 번복 없음 — 실측이 기존 결정을 실증. 미해결 6건만 신규 question.
  overview는 시스템 구조 무변경이라 드리프트 없음(narrative 유지).

## [2026-07-06] lint | wish GitLab 실측 ingest 후 전체 점검 — clean (off-schema meta/ 1건만 보고)
- 범위: 위키 전체(78 지식페이지 + 6 카탈로그 + raw 9). 10개 검사 항목 전부 점검.
- 카운트 재검증(핵심): 허브 index.md 표기가 실측과 전부 일치 — summary 7·entity 6·concept 5·decision 30·question 29(answered 16)·overview 1 = 총 78, raw 9. ingestor 수동 갱신 정확, 수정 불필요.
- 깨진 링크 0: 위키 전체 wikilink 대상(95개)이 모두 실재 파일로 해소(wiki+raw+schema). (`[[wikilink]]`는 meta 리포트 내 설명용 플레이스홀더 — 오탐 아님)
- 고아 0: 모든 지식페이지가 최소 1 inbound(폴더 인덱스 등재 포함). 신규 question 6건은 전부 카탈로그 외 실 inbound(summary·decision·entity) 보유. summary-wish-gitlab-api-survey는 카탈로그만 inbound이나 summary 유형 특성상 정상.
- frontmatter 4필드: 78/78 충족. type↔폴더·파일명 접두사↔type: 전부 일치. 폴더 인덱스 등재: decision 30/entity 6/concept 5/summary 7/question 29 완전 일치, stale 0.
- 상대경로 마크다운 링크(`](../…)`·`](./…)`): 0.
- answered question 답 링크: 16건 중 15건 답 decision 링크 보유. question-runner-ai-network는 답이 인프라 사실이라 entity-mirero-gitlab로 귀결(정상 예외).
- 모순·중복: 없음. 실측은 기존 결정을 실증하는 성격(CE approval 404 = decision-mr-review-gate 근거 보강 등) — superseded 처리 대상 아님. entity-mirero-gitlab vs entity-docs-hub 관심사 분리 정상.
- 보고(수정 안 함, 판단 필요):
  - [LOW·off-schema] wiki/meta/lint-report-2026-07-06.md — schema 유형 표에 없는 meta/ 폴더·type:meta·status:developing(비표준). schema는 lint 결과를 log.md에 남기도록 규정하고 별도 리포트 파일을 정의하지 않음. 미추적(untracked) 상태. 삭제/유지는 호출자 판단.
  - [LOW·명명] question-blob-search-vs-code-index.md 파일명이 `-index.md`로 끝나 카탈로그 글롭(`*-index.md`)과 충돌 — 실제 지식페이지가 카탈로그로 오분류될 위험. 등재·frontmatter는 정상이라 기능 영향 없음. 리네임은 링크 8곳 갱신 동반이라 판단 필요.
  - [LOW·선택] overview가 신규 entity-mirero-gitlab/실측 summary를 서사에 미참조(파생 decision 3종은 이미 참조). 구조 무변경이라 드리프트로 보긴 약함 — 서사 보강은 선택.
- 자동 수정: 없음(기계적 결함 0건).

## [2026-07-06] ingest | 레포 등록 시나리오 decision
- 근거 raw: [[2026-07-06-wish-gitlab-api-survey]] (불변, 앞선 실측 ingest 위에 얹는 후속)
- 생성: decision-repo-registration-flow — 레포별 project access token(read_repository+api)으로 등록 + 브랜치 1개 스코프.
  기각 대안 4종: 사용자 PAT(사람에 묶임)·그룹 토큰(Owner 필요·실측 401)·별도 프로젝트 선택 단계(토큰이 이미 스코프)·레포당 다중 브랜치(이번에 브랜치 1개로 기각, 변종은 등록 분리).
  자동 조회값(project id·default_branch·scm·git URL) + 소스별 정책 입력 + compare dry-run 검증 서술. 파생효과=compare 단일 브랜치 추적·트리거 축소.
- 갱신:
  - question-group-token-provisioning — status **open 유지**(answered 아님). "부분 답" 블록 추가: 소스 read 발급 주체 축은 레포별 토큰으로 확정(→decision-repo-registration-flow), 그러나 docs-hub write 토큰·소스별 최소권한 조합·아티팩트 registry read 편차는 미해결로 남음. 관련 footer에 새 decision 링크.
  - overview — 실행 흐름(정적)에 등록 서술 추가, Phase 2 인프라 결정 단락에 decision-repo-registration-flow 등재 + 실측 근거 문단(entity-mirero-gitlab·summary-wish-gitlab-api-survey 서사 참조 → 직전 lint의 LOW 드리프트 해소).
  - decision-index(정적 파이프라인 상세에 등재), 허브 index(decision 30→31·총 78→79·날짜 2026-07-06 유지).
- 판단(question 라이프사이클): group-token-provisioning은 **부분 답**이라 answered로 넘기지 않음 — 이 decision은 소스 read 등록만 스코프하고, question이 원래 묶은 docs-hub write·최소권한 조합·아티팩트 read 축은 그대로 열려 있음. schema의 answered 조건(답이 확정)을 충족하는 부분만 본문에 명시 링크하고 status는 open 유지.
- concept↔decision: 이번 건은 decision(기각 대안 4종 존재·우리 대시보드 맥락 한정·다르게 택하면 supersede 가능). 신규 개념 없음.
- 결정 번복 없음(신규 추가). raw 무수정. blob-vs-code-index 리네임 완료분·삭제된 meta/는 미접촉.

## [2026-07-06] ingest | 레포 등록·docs-hub grilling 확정 (grill-me 결정 회수)
- raw: [[2026-07-06-registration-grilling]] (grill-me 인터뷰 문답 요약 보존, 불변)
- 생성(신규 decision 2 + question 1 + summary 1):
  - decision-docs-hub-folder-rule — docs-hub 소스별 폴더 = `full_namespace_path/branch` 자동 규칙(슬래시 `-` 치환). 기각: 사람 입력·네임스페이스만·과제1폴더
  - decision-branch-loss-policy — 브랜치 등록 정책 C(전부 노출+비기본 경고) + compare 404 자동 비활성화(삭제 아님) + 재활성화 protected 분기(protected=자동, 비-protected=수동). 기각: 브랜치 제한 A/B·즉시 삭제·flapping
  - question-initial-backfill-baseline — 첫 문서화 baseline(A 전체/B HEAD/C 지정) **미확정**(status: open). A+backfill 분리안 제안됐으나 사용자 승인 전
  - summary-registration-grilling — grilling 요약(확정 4·미확정 1)
- 갱신:
  - entity-docs-hub("과제별 instance"→소스별 폴더 규칙으로 구체화), decision-db-source-of-truth(doc_dir 자동 규칙·enabled 좀비 비활성화 의미론 명시)
  - decision-repo-registration-flow(브랜치 선택=정책 C·다중 브랜치 등록 허용 명확화, 기각 대안 "레포당 다중 브랜치"→"한 등록에 여러 브랜치 묶기"로 정정), decision-pull-model(404 실패 경로 추가)
  - question-ci-less-source-policy(소실 vs 방치 구분 + branch-loss-policy 링크)
  - overview(등록 서사에 폴더 규칙·다중 브랜치·404 비활성화), decision-index·question-index·summary-index, 허브 index(decision 31→33·question 29→30·summary 7→8·총 79→83·raw 9→10)
- 판단: grilling 확정 4건은 우리 대시보드 맥락 한정·기각 대안 있음 → decision. baseline은 사용자 미승인이라 question(open)으로만 남김(결정 아님). 결정 번복 없음(신규 추가·기존 명확화). raw 무수정.

## [2026-07-06] schema | answered 전환 시 blocking 태그 제거 규약 명문화
- 계기: lint에서 question-mr-vs-docs-auto(answered)가 blocking 태그 잔존 → 활성 블로커 조회 오염(규약 공백)
- schema.md: question 라이프사이클 규칙에 "answered 전환 시 blocking 태그 제거" 추가, lint 검사 항목에 "answered에 blocking 잔존" 추가
- 적용: question-mr-vs-docs-auto tags [blocking,phase-1,mr]→[phase-1,mr]. question-headless-claude-auth는 status:open이라 blocking 정상 유지(위반 아님)

## [2026-07-06] lint | 전체 md 중복·낡음·미갱신 점검 (84 파일, 다차원 병렬 + 오탐 검증)
- 범위: 위키 전체(지식 78→82 + 카탈로그 6 + raw 9). 4차원(stale·링크/고아·중복·frontmatter/드리프트) 병렬 스캔 → 발견별 원본 대조 검증(21 에이전트)
- 무결성 clean: 깨진 링크 0 · frontmatter 4필드 0누락 · type↔폴더·접두사 0불일치 · 빈 섹션 0 · 상대경로 링크 0 · 허브 카운트 정합(question 29·answered 16)
- 확정 8건 전부 수정(사용자 승인 자동 수정):
  - [MED] decision-scm-connector-abstraction auth 셀 — group token 전제 낡음 → 소스 read(레포별 토큰 확정)/docs-hub write(미확정) 두 축 분리 + 링크
  - [MED] question-review-feedback-loop 고아 → decision-mr-review-gate 관련줄에 back-link (해소 확인)
  - [MED] entity-codegraph 중복 — 어댑터 기각 근거가 decision과 near-verbatim → 판단은 decision 위임, 객관 스펙표만 유지
  - [LOW] question-doc-qa-rag 약한 고아 → decision-control-data-plane-split 열린부분에 back-link (해소 확인)
  - [LOW] decision-code-index-store-plane:29 versioning 메커니즘 재서술 → 위임 링크로 축약
  - [LOW] summary-code-index-finalization 결정 8건 카탈로그가 decision-index와 중복 → 서사 계보로 축소, 전목은 index 위임
  - [LOW] question-release-object-vs-tag-trigger → decision-repo-registration-flow forward-link 추가(트리거=등록 단일 브랜치 스코프)
  - [LOW] question-mr-vs-docs-auto blocking 태그 → 위 schema 규약 신설 후 제거
- 오탐 9건 기각: stale 차원의 BLOCKER/HIGH 주장(다중 브랜치 등록·doc_dir 규칙·좀비 비활성화 미반영)은 전부 환각 — 그 결정들이 아직 위키에 없어 "미반영 낡음"이 성립 안 함. (본 세션 앞 ingest로 실제 결정을 추가해 근본 해소). schedule-per-source·observability-event-contract 중복 주장도 정상 분리로 판정
- 재검증: 신규 4페이지 링크 전부 해소·폴더 인덱스 등재·고아 아님, 두 고아 해소 확인, 카운트 83 정합

## [2026-07-06] ingest | 등록 모델 전환 — 레포 1개 + 개발/배포 브랜치 (supersede)
- 사용자 지시: "레포지토리는 하나만 등록하고 개발브랜치·배포브랜치를 등록하는 흐름으로". 앞서 확정한 "레포×브랜치 1개=원자단위" 모델을 뒤집음
- raw: [[2026-07-06-repo-dev-release-branches]] (전환 기록, 불변)
- grill-me 확정: (1) 브랜치 역할이 문서 산출을 가름(개발=최신 기술문서·compare 야간 / 배포=릴리스 문서·매뉴얼·태그 트리거), (2) 개수=개발 1+배포 1 고정 2, (3) docs-hub 폴더=레포 1폴더+`dev`/`release` 하위폴더
- 생성: decision-repo-dev-release-registration — 등록 원자=레포 1개, 개발/배포 브랜치 2개, 역할별 문서·트리거·폴더. 기각: 레포×브랜치 원자단위(옛)·아무 브랜치 N개(옛 정책 C)·역할 라벨 없는 브랜치
- superseded: decision-repo-registration-flow — status active→superseded + supersede 배너(토큰=스코프 메커니즘은 새 결정이 계승, 뒤집힌 건 원자단위·다중등록). schema 결정번복 규칙(덮어쓰기 금지·새 페이지+옛 superseded+상호링크) 준수
- 개정(부분 유효): decision-branch-loss-policy(등록 정책 C 섹션 → 개발/배포 선택으로 교체, 좀비 비활성화·protected 재활성화는 유지), decision-docs-hub-folder-rule(평면 `full_namespace_path/branch` → 레포1폴더+`dev`/`release` 하위폴더, 슬래시 치환 문제 소멸), decision-db-source-of-truth(sources 레포단위 1행 + source_branches 개발/배포 2행, sha 추적 브랜치별)
- 갱신: entity-docs-hub(역할 하위폴더), overview(실행흐름·Phase 2 결정 새 모델), question-release-object-vs-tag-trigger(트리거=배포 브랜치)·question-initial-backfill-baseline(source_branches·브랜치별 baseline)·question-group-token-provisioning(3링크)·decision-scm-connector-abstraction(auth 링크) → 옛 superseded 페이지 대신 새 결정 지목. summary-registration-grilling(후속 전환 note 배너, 이력 보존)
- 인덱스: decision-index(새 결정 등재+옛 superseded 표기), 허브 index(decision 33→34[1 superseded]·총 83→84·raw 10→11)
- 판단: superseded 페이지로 향하던 inbound 중 "현재 등록 모델" 지시는 새 결정으로 교체, grilling 이력 참조(summary)는 배너로 안내하고 유지. 미확정(개발/배포 필수2 vs 선택·배포 N 변종)은 새 결정 열린부분에 기록

## [2026-07-06] ingest | 원격제어 MCP 소스 실측 (MiVncManagerMcpServer)
- 사용자 지시: "D:/project/ros-sw-rcs-windows의 MiVncManagerMcpServer로 MCP 환경 구성" → 확인 결과 목표=wiki-pipeline에 설계 반영(서버는 이미 세션에 연결·작동 중)
- raw: [[2026-07-06-mivnc-mcp-server-survey]] (소스 + 실행 인스턴스 조사, 불변)
- 확인: 정확한 "MiRcsMcpSessionServer" 이름 없음 → 실체는 MiVncMcpServer(단일,:9100)·MiVncManagerMcpServer(다중,:9200) 계열. 둘 다 vnc-mcp-lib 단일 도구 정의 위 wrapping. Manager=60공통(withSessionId)+6세션관리+4 alias. 전송 SSE/stdio, 모드 remote(MiRcsServer TCP)/local(in-process). 외부 의존 OmniParser. 배포 Docker(8081→9200)/Windows 서비스
- 실증: 세션의 mcp__mi-vnc__* 도구가 원격 화면(1920×1080, uia·terminal·file_transfer·hwnd) 연결·작동 확인(vnc_screen_info)
- 갱신: entity-remote-control-mcp — "소스 실측(2026-07-06)" 절 추가(서버 2종·도구 세트·전송·모드·OmniParser·배포·동시성·실행 실증). "sw-rcs-session-mcp"의 실체를 이 계열로 명시, remote 모드가 decision-app-host-connection의 IP/port 연결에 해당함을 연결
- 허브 index(raw 11→12·페이지 84 불변)
- 판단: 실측 사실이라 신규 결정·번복 아님 — 기존 entity에 fact 보강(직전 wish-gitlab-survey와 동형). raw가 단일 컴포넌트 조사라 summary 생략(entity 갱신이 곧 증류, raw는 entity에서 2회 inbound 확보). raw 무수정

## [2026-07-06] schema | 폴더 인덱스 기능(파이프라인) 그룹핑 규약 명문화
- 사용자 요청: "decision 안에서도 기능별로 구분 필요, 다른 폴더도 마찬가지" → 확인: 물리 하위 폴더가 아니라 인덱스 그룹핑 강화(폴더명=type 규약 유지)
- schema.md: "폴더 인덱스 안의 기능 그룹핑" 절 추가 — 파일은 유형 폴더 평면 유지, `<type>-index.md`를 파이프라인 축 `###` 소제목으로 드릴다운. 표준 그룹 축 표(공통·정적[+등록 하위 #### ]·매뉴얼·코드인덱스·향후/실측). 그룹 소제목은 네비게이션이라 링크·고아 검사 제외 명시
- 재구성: decision-index(34) → 공통 7 / 정적 5 + 등록하위 4 / 매뉴얼 10 / 코드인덱스 8. question-index(30) → 공통 7 / 정적 3 + 등록하위 6 / 매뉴얼 7 / 코드인덱스 4 / 향후 3. summary-index(8) → 정적·공통 3 / 매뉴얼 1 / 코드인덱스 3 / 실측 1
- entity(6)·concept(5)는 규모 작아 평면 유지
- 검증: 세 인덱스 모두 파일↔링크 완전 정합(decision 34=34·question 30=30·summary 8=8), 중복·유령 0. 파일 이동 없음 → 링크·카운트 불변(페이지 84·raw 12)

## [2026-07-06] query | MVP를 뽑는다면 어떤 기능들인가
- 드릴다운: index → decision-index·question-index·concept-index·summary-index + overview, 정밀 읽기: summary-design-session·decision-engine-hybrid·question-headless-claude-auth
- 답: 공식 MVP 결정은 위키에 없음 — Phase 1·2 확정 결정에서 후보 절단선 합성(정적 파이프라인 + 최소 Control Plane, 매뉴얼·코드인덱스·Phase 3+ 제외)
- 생성: question-mvp-scope (open — 포함 기능 9·제외 4·열린 항목, 확정 시 decision 승격)
- 갱신: question-index(공통 그룹 등재), overview(Phase 2 문단 뒤 MVP 절단선 링크 — inbound 확보), 허브 index(question 30→31·페이지 84→85)

## [2026-07-06] ingest | 테마 1차 스코프 확장 (4→6) — 개발환경·개발가이드 + API & 프로토콜
- raw: [[2026-07-06-theme-scope-expansion]] (query 후속 사용자 지시 원문 + 확인 문답)
- 생성: decision-theme-scope-expansion (⑤ dev-guide 모든 소스 · ⑥ api-protocol 백엔드 소스; 근거 온보딩·환경 재현성; "실측 후 확장" 방침의 예외), summary-theme-scope-expansion
- 갱신: entity-docu-automatic(테마 4→6), question-theme-expansion(후보 2개 1차 승격 기록·남은 후보 3개로 open 유지), decision-index·summary-index·question-index, 허브 index(summary 8→9·decision 34→35·raw 12→13·페이지 →87)
- 정정: 허브 index의 question 30→31·페이지 84→85가 직전 query(MVP) 로그와 달리 미반영 상태였음 — 이번 갱신에 합산 반영(실측 카운트로 검증: decision 35·question 31·summary 9·entity 6·concept 5·overview 1 = 87)

## [2026-07-06] ingest | 엔진 인증 — 단일 계정 로그인 (아이디/패스워드 등록)
- 사용자 지시: 다중 계정 라운드 로빈(로그아웃/로그인 회전 + 만료 fallback)은 보류 → MVP는 단일 계정. "단일 아이디니까 아이디/패스워드 설정은 있어야겠네 확인" → 등록 UI/백엔드에 계정 크리덴셜 항목 필요. 약관 관련 서술은 넣지 않음(사용자 요청)
- raw: [[2026-07-06-engine-single-account]] (논의 기록, 불변)
- 생성: summary-engine-single-account, decision-engine-single-account-auth — 엔진 인증=단일 Claude Code 계정 로그인, 대시보드 아이디/패스워드 등록·상태 표시. 기각/보류: 다중 계정 라운드 로빈 풀. 열린 항목: headless 로그인 무인 지속 검증([[question-headless-claude-auth]])·단일 계정 처리량 상한([[question-cost-estimation]])
- 갱신: question-headless-claude-auth(방침 갱신 2026-07-06 — 인증 수단은 단일 계정 로그인으로 확정, 단 무인 지속 검증 남아 open·blocking 유지), question-mvp-scope(엔진 인증 항목=단일 계정+아이디/패스워드), question-secret-storage-security(엔진 계정 크리덴셜도 at-rest 보안 대상 링크), overview(Phase 1 결정 문단에 단일 계정 인증)
- 인덱스: decision-index(공통·cross-cutting 그룹 등재), summary-index(정적·공통 그룹 등재), 허브 index(decision 35→36·summary 9→10·raw 13→14·페이지 87→89)
- 판단: "우리가 택했다"+기각 대안 있음 → decision. question-headless-claude-auth는 인증 수단이 확정됐어도 무인 지속 검증이 미완이라 answered 전환 대신 방침 갱신으로 open 유지(정직한 상태 표기)

## [2026-07-06] lint | clean — 결함 0 (오탐 2건 기각)
- 10개 항목 전수 점검. 대상: wiki 지식 83 + overview + 카탈로그 6, raw 14
- 1 깨진 링크: 없음 ([[schema]] 6건은 루트 schema.md 정상 링크 — 스캔 범위 오탐). 2 고아: 없음(raw inbound도 전부 확보). 3 폴더 인덱스 멤버십: summary10·entity6·concept5·decision36·question31 파일=링크 완전 일치, 유령 0. 4 frontmatter 4필드: 누락 0. 5 접두사·6 type↔폴더: 불일치 0. 7 상대경로 링크: 0
- 8 overview 드리프트: 신규 decision-engine-single-account-auth 반영됨, 구조 변화 없음. 9 모순·중복: 없음(단일계정 인증 vs 엔진 하이브리드는 축 다름). 10 answered 답 링크: answered 16건 중 question-runner-ai-network만 decision 링크 부재로 잡혔으나 실측 사실로 답한 질문(근거 entity-mirero-gitlab 링크 보유) → 오탐 기각
- 허브 카운트 대조: 페이지 89(overview 1+summary10+entity6+concept5+decision36+question31)·raw14·answered16 전부 정합

## [2026-07-06] ingest | 신규 테마 2종 상세 설계 grilling (dev-guide · api-protocol)
- raw: [[2026-07-06-theme-detail-grilling]] (grilling 문답 6건 — 선택·기각 대안 병기)
- 생성: decision-theme-activation-checklist (테마 활성화 = 소스별 체크리스트, 기본 5 on · api-protocol opt-in; 성격 분류·scout 판단 기각), decision-critic-grounding-secrets (critic 확장 = 근거 대조 + 시크릿 기재 금지, 두 테마 한정; 외부 결정적 검증은 Phase 3+ 보류), summary-theme-detail-grilling
- 갱신: decision-theme-scope-expansion (상세 설계 절 — dev-guide 1문서·코드 근거만 / api-protocol 외부 노출 API만 / 둘 다 dev 전용; 표에 opt-in 링크), entity-docu-automatic (조정점 표에 critic 확장 행), decision-index (정적 +1 · 등록 하위 +1), summary-index (+1), 허브 index (summary 10→11 · decision 36→38 · raw 14→15 · 페이지 89→92)

## [2026-07-06] query | requirements와 dev-guide 테마가 비슷하지 않은가
- 드릴다운: entity-docu-automatic·decision-theme-scope-expansion(세션 내 기독) + raw 2026-07-05-docu-automatic-notes(requirements 원 정의 실측)
- 답: 겹침 실재 — requirements="설치/실행 환경과 조건"(설치자·운영자)과 dev-guide ①환경 구성 절이 소재·source_files 트리거 겹침. 단 독자·관점 축이 달라(운영 vs 개발) 통합보다 경계 명시가 방향 (manual-taxonomy-two-reader와 동일 원리)
- 생성: question-requirements-devguide-boundary (open — 잠정 방향: 분리 유지 + 테마 정의에 경계 문장, 상세는 한쪽+참조)
- 갱신: question-index(정적 그룹 등재), decision-theme-scope-expansion(영향 절에 경계 질문 링크), 허브 index(question 31→32·페이지 92→93)

## [2026-07-06] query | dev-guide에 코딩 컨벤션·개발 규칙이 포함되는가 — 확인
- 답: 아니오 — grilling에서 "코드 근거만"으로 확정, 조직 규칙 제외가 현행. 단 코드로 실체화된 규칙(.editorconfig·analyzer·CI lint)은 코드 근거 범위라 포함
- 사용자 확인: "조직 규칙 포함으로 수정" 대안 제시 → 현재 결정 유지 선택 (번복 없음)
- 갱신: decision-theme-scope-expansion (상세 설계의 dev-guide 항목에 실체화된 규칙 포함 경계 명확화 한 줄 — 결정 변경 아님)

## [2026-07-06] ingest | dev-guide 근거 범위 번복 — 코드만 → 코드 + 레포 내 문서 (코딩 규칙 포함)
- raw: [[2026-07-06-devguide-docs-grounding]] (번복 지시 원문 + 해석 전제: 탐색 대상은 레포 내 문서, 외부 시스템 제외)
- 생성: decision-devguide-grounding-scope (grilling Q2 "코드 근거만"의 당일 번복을 전용 결정으로 승격 — 기각 대안에 번복 이력 명기; 근거 대조 원칙은 유지), summary-devguide-docs-grounding
- 갱신: decision-theme-scope-expansion (상세 설계의 dev-guide 항목 = 레포 근거〈코드+문서〉·④코딩 규칙 추가·새 결정으로 위임), decision-critic-grounding-secrets (근거 파일에 레포 문서 포함 명시), decision-index (정적 +1), summary-index (+1), 허브 index (summary 11→12·decision 38→39·raw 15→16·페이지 93→95)

## [2026-07-06] lint | overview 가독성 재구성 (지식·링크 불변)
- 대상: wiki/overview.md — "한눈에 안 들어온다" 피드백으로 구조만 재편
- 변경: ① 도입부에 파이프라인 3종 요약 표 신설 ② 공통 뼈대(평면 분리·SCM 커넥터·관측성)를 도입부 불릿으로 승격 ③ 각 파이프라인 절의 서술 문단을 축별 불릿/표로 전환 (③ 코드 인덱스는 결정 축 표) ④ "더 보기" 속 Phase 1·2·미해결 서술 벽을 "지금 어디까지 왔나" 절의 그룹별 불릿으로 분해
- 불변: wikilink 39개 전수 보존 (grep 대조 확인) · mermaid 다이어그램 2개 유지 · 지식 추가/삭제 없음

## [2026-07-06] lint | 전수 점검 — 발견 2건 수정, clean
- 검사 10항목 전수: 깨진 링크 0 · 고아 0 · 인덱스 등재 완전 · 허브 카운트 정합(95페이지·raw 16·answered 16) · frontmatter 4필드 완비 · 접두사/type↔폴더 불일치 0 · 상대경로 링크 0 · answered 답 링크 완비(runner-ai-network는 사실-답 패턴으로 entity 링크가 답 근거 — 결함 아님) · superseded 1건(기존)
- 수정 1 (overview 드리프트): "지금 어디까지 왔나" Phase 1 목록에 테마 4→6 확장·체크리스트 활성화·dev-guide 근거 범위 한 줄 추가
- 수정 2 (모순 방지): summary-theme-detail-grilling의 dev-guide 항목에 당일 번복 포인터 추가 (raw 요약으로는 정확하나 현행 오독 위험 → decision-devguide-grounding-scope 링크)
- 결론: clean (남은 이슈 0)

## [2026-07-06] ingest | 실시간 이메일 알림 (인증 해지·파이프라인 실패) + headless 무인 지속 안 됨 확정
- raw: [[2026-07-06-failure-alerting-email]] (지시 원문 + 확인 문답: 수신자=역할 기반, 무인 지속 안 됨=확인된 사실)
- 생성: decision-email-alerting (관리 서버 이메일 발송 기능 신설 · 실시간 푸시 · 역할 기반 수신 — 인증 해지/인프라→admin, 과제 실패→담당자+admin 참조; 대시보드 풀·admin 단일·구독 설정 기각; 발송 스택은 요구사항 수준만), summary-failure-alerting-email
- 갱신: question-headless-claude-auth (무인 지속 안 됨 확정 — 초점을 만료 감지·재로그인 절차로 이동, open·blocking 유지), question-batch-observability (실패 알림 축 확정 — daily digest 구체만 남음), decision-engine-single-account-auth (상태 표시→이메일 알림 연계, 열린 항목 사실 반영), overview (공유 뼈대 관측성에 이메일 푸시 + 미해결 항목 갱신), decision-index(공통 +1)·summary-index(+1)·question-index(2행 갱신), 허브 index (summary 12→13·decision 39→40·raw 16→17·페이지 95→97)

## [2026-07-06] ingest | 코드 인덱스 — 파이프라인 범위 제외 (개인 관리 이관)
- 발단: 커밋 되돌리기 시 중앙 인덱스 불일치 질문 → 분석(revert=폴링 소화·force-push=HEAD 전체 재인덱싱) → 사용자 결정: "code indexing은 개인이 관리하는 편이 나을 거 같아서 파이프라인에서 빼도록 하자"
- raw: [[2026-07-06-code-index-out-of-pipeline]] (논의 기록, 불변)
- 생성: summary-code-index-out-of-pipeline, decision-code-index-out-of-pipeline — 코드 인덱스=중앙 파이프라인 범위 제외·개발자 개인 로컬 도구 이관. 근거: 소비 지점이 개인 로컬 작업 트리(원격 동기화 문제 자체가 없음)·비-AI라 중앙화 근거 부재·기존 실물(blob 검색·CodeScene) 중복 우려·MVP 절단선 단순화. 재검토 조건: cross-repo 등 개인이 못 푸는 요구 실증 시
- 갱신(superseded 8건): decision-code-index-pipeline·provider-abstraction·mcp-serving·runner-git-clone·versioning·adapter-cg-colby·single-repo-scope·store-plane — 각각 supersede 콜아웃 + 상호 링크 (유효 잔존분 명기: 실측 사실→entity-mirero-gitlab, 도구 조사→entity-codegraph, cross-repo 축→재검토 조건)
- 갱신(question): blob-vs-code-index-overlap open→answered(질문 자체 해소), code-index-query-surface·code-index-store·scm-checkout에 supersede 주석 (answered 유지 — 당시 결론의 기록)
- 갱신(주변 드리프트): entity-codegraph(개인 도구 참고 자료로 재규정·열린 부분 닫힘), overview(파이프라인 3종→2종·③절→"범위 제외" 절), decision-pull-model·decision-nightly-batch(적용 범위 사례 무효 주석), decision-pipeline-observability(3개→2개), concept-port-adapter(실체화 취소 표기), question-mvp-scope(절단선 단순화)
- 인덱스: decision-index(코드 인덱스 그룹 재구성 — 새 결정 + ⛔ 8건), question-index(그룹 헤더 + ✅ 4건), summary-index(+1), entity-index(codegraph 설명), 허브 index(summary 13→14·decision 40→41〈superseded 1→9〉·answered 16→17·raw 17→18·페이지 97→99)
- 판단: "우리가 택했다"+기각 대안(중앙 유지) 있음 → decision. 8건 개별 페이지를 덮어쓰지 않고 status 전환+콜아웃으로 번복 이력 보존 (schema "결정 번복" 규칙)

## [2026-07-06] lint | 범위 제외 ingest 직후 전수 점검 — 결함 2건 수정, clean
- 10개 항목 전수 점검 (스크립트 + 판단). 대상: wiki 지식 93 + overview + 카탈로그 6, raw 18
- 1 깨진 링크: 0. 2 고아: 0 (raw inbound 전부 확보). 3 폴더 인덱스: summary14·entity6·concept5·decision41·question32 파일=링크 완전 일치, 허브 카운트(페이지 99·raw 18·superseded 9·answered 17) 실측 정합. 4 frontmatter: 누락 0. 5 접두사·6 type↔폴더: 불일치 0. 7 상대경로 링크: 0
- 8 overview 드리프트: 없음 — 코드 인덱스 범위 제외(2종 표+범위 제외 절)·email-alerting 모두 반영 확인
- 9 모순 2건 발견·수정: decision-scm-connector-abstraction(checkout 4책임 "미확정" 잔존 — 07-05 답변+07-06 수요 소멸로 종결 표기), entity-mirero-gitlab(CodeScene "중복 가능성" — 해소로 갱신)
- 10 answered 17건: blocking 잔존 0. question-runner-ai-network 답 링크 부재 플래그는 기존 판정대로 오탐(실측 답변, entity 근거 링크 보유)
- 결론: clean (수정 후 잔존 이슈 0)

## [2026-07-06] ingest | 엔진 API 자체 에이전트 전환 (B 확정) + 에이전트 스텝 관측
- raw: [[2026-07-06-engine-api-agent-architecture]]
- 생성: summary-engine-api-agent-architecture, decision-engine-api-agent, decision-engine-api-key-auth, decision-agent-step-observability
- 갱신: decision-engine-hybrid(B 확정), decision-engine-single-account-auth(superseded), decision-observability-event-contract(스텝 계층), question-headless-claude-auth(answered·blocking 해제), question-engine-runtime, question-cost-estimation, entity-docu-automatic, overview, decision-index, question-index, summary-index

## [2026-07-06] lint | 엔진 API 에이전트 ingest 직후 전수 점검 — 드리프트 4건 수정, clean
- 기계 검사 10종: 깨진 링크·고아·인덱스 누락·frontmatter·접두사·폴더·상대경로 링크·blocking 잔존 — 모두 0건
- 수정 4건 (B 전환 드리프트, 살아있는 페이지만): question-mvp-scope(엔진 항목·블로커 해소 반영), entity-docs-hub(headless→에이전트 루프), entity-mirero-gitlab(인증 확정 반영), question-secret-storage-security(API 키로 갱신)
- 허용 예외: question-runner-ai-network는 답이 사실 확인이라 decision 링크 대신 entity 링크 (기존 lint 판정 유지)
- 비수정 (역사 기록 보존): decision-email-alerting·decision-manual-pipeline-separate의 headless 언급은 결정 당시 근거 서술, superseded·summary 페이지 원문 유지

## [2026-07-07] ingest | 열린 질문 결정 4건
- raw: [[2026-07-07-open-questions-decisions]]
- 생성: summary-open-questions-decisions, decision-mvp-scope, decision-registration-baseline, decision-source-manual-curation, decision-requirements-devguide-boundary
- 갱신(question open→answered + 답 링크): question-mvp-scope, question-initial-backfill-baseline, question-ci-less-source-policy, question-requirements-devguide-boundary
- 갱신(인덱스): decision-index(공통에 MVP·baseline, 소스 등록에 수동 큐레이션, 정적에 테마 경계), question-index(4건 ✅ + 답 링크), summary-index(신규 요약 등재), index(카운트·최종 갱신일 2026-07-07)
- 갱신(overview): MVP 절단선 open→decision 반영(정적+매뉴얼 둘 다), 매뉴얼 open 질문이 MVP 블로커로 승격, 파이프라인 2종 서두에 MVP 범위 명시
- 후보안 분기 기록: question-mvp-scope 후보안은 "정적만"이었고 사용자가 매뉴얼 포함으로 확대 → decision-mvp-scope에 "후보안에서 갈라진 지점" 절로 명시(번복이 아니라 확대, 후보안이 decision으로 굳지 않아 supersede 대상 아님)
- blocking 태그: 4건 모두 frontmatter에 blocking 태그 없었음(제거 대상 없음)
- 카운트 정정: 허브 index가 실제 파일 수와 드리프트 상태였어 실측값으로 동기화(decision 41→48, summary 14→16, question answered 17→22, raw 18→20, 총 99→108)

## [2026-07-07] lint | 열린 질문 결정 4건 ingest 직후 전수 점검 — clean (log 내 과거 링크 1건만 보고)
- 범위: 위키 전체(107 지식페이지 + 6 카탈로그 + overview + raw 20). 10개 검사 항목 전부 점검.
- 카운트 재검증(핵심): 허브 index.md 표기가 실측과 전부 일치 — summary 16·entity 6·concept 5·decision 48·question 32·overview 1 = 총 108, raw 20. superseded 10(decision status 실측 10)·answered 22(question status 실측 22)·open 10 모두 정합. ingestor 동기화 정확, 수정 불필요.
- 깨진 링크 0(위키): 위키 전체 wikilink 대상이 모두 실재 파일로 해소(wiki+raw+schema). PowerShell 전수 스캔.
- 고아 0: 모든 지식페이지가 자기 <type>-index.md에 등재(concept 5/decision 48/entity 6/question 32/summary 16 미등재 0) → 최소 1 inbound 보장.
- frontmatter 4필드: 107/107 충족. type↔폴더·파일명 접두사↔type: 전부 일치(위반 0).
- 상대경로 마크다운 링크(`](../…)`·`](./…)`): 0.
- 신규 decision 4건(mvp-scope·registration-baseline·source-manual-curation·requirements-devguide-boundary): frontmatter 4필드·접두사·폴더 일치, inbound(index+overview+summary 다중) 보유, decision-index 적정 그룹 등재 확인.
- answered 전환 question 4건(mvp-scope·initial-backfill-baseline·ci-less-source-policy·requirements-devguide-boundary): 전부 status=answered·답 [[decision-*]] 링크 본문 보유·blocking 태그 없음. open 목록(10건)에 미혼입 확인.
- answered 답 링크 전수(22건): 21건 [[decision-*]] 보유. question-runner-ai-network만 답이 인프라 사실이라 entity-mirero-gitlab 귀결 — 2026-07-06 lint에서 정상 예외로 확정된 건(재확인).
- overview 드리프트: 없음. 신규 decision 4·answered question 4 모두 "MVP 절단선 확정" 절에 반영(✅ 표기).
- 모순·중복: 없음. decision-mvp-scope는 후보안 대비 "확대(번복 아님)"로 명시, decision-source-manual-curation은 compare 404 자동 비활성화(decision-branch-loss-policy)와 경계 명시 → 상충 회피.
- [[schema]] 참조(정책 판단, 오탐): [[schema]]는 6개 카탈로그 파일(index+5개 *-index)의 헤더 "규약: [[schema]]"에만 존재. schema.md는 wiki/ 밖 루트 파일이나 실재하므로 파일-존재 기준 깨진 링크 아님. 링크 규약(schema.md L74-75)이 wiki↔raw만 명시하고 루트 파일 참조 예외를 규정하지 않는 점은 규약 공백 — 카탈로그 헤더의 관례적 [[schema]]는 허용 예외로 두되, 필요 시 schema.md 링크 규약에 "루트 문서(schema/overview) 참조 허용"을 명문화할 여지로 보고.
- 보고(수정 안 함, 판단 필요): log.md L217 `[[lint-report-2026-07-06]]` — 대상 파일(wiki/meta/lint-report-2026-07-06.md)이 6861098에서 추가, 26f9f42에서 off-schema로 삭제됨. 현재 대상 없음이나 이는 append-only 감사 로그의 과거 이력 항목이라 당시엔 유효했음. 소급 수정은 이력 왜곡이므로 미수정, 보고만.

## [2026-07-07] ingest | 아티팩트 타입 dispatch 결정
- raw: [[2026-07-07-artifact-type-dispatch-decision]] (기존 raw 재사용, 불변)
- 생성: summary-artifact-type-dispatch, decision-artifact-type-dispatch
- 갱신: question-artifact-type-dispatch (open→answered · 답 링크 + 검토항목 인라인 답 · blocking 태그 없음 확인), overview (② 매뉴얼 절에 exe/msi·담당자 자산 선택·MCP 설치 실행 구체화 · MVP 절단선에 블로커 해소 항목 추가 · 미해결 절에서 제거), index (decision 48→49·summary 16→17·answered 22→23·raw 20→21·총 108→110), decision-index (매뉴얼 추출 파이프라인 그룹 등재), summary-index (매뉴얼 추출 파이프라인 그룹 등재), question-index (artifact-type-dispatch ✅ answered + 답 링크)
- 3건 처리: exe/msi 한정 · 담당자 대시보드 자산 선택 · MCP 설치 실행까지 — 세 답이 밀접(담당자 명시 + Windows 설치본 집중)해 단일 decision 페이지 decision-artifact-type-dispatch로 묶음(메커니즘은 decision-artifact-consumption·decision-scenario-owner-dashboard·entity-remote-control-mcp 링크로 위임). container 제외 경계를 question-ci-less-source-policy와 "MVP 매뉴얼 대상 밖"으로 연결.
