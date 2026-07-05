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
