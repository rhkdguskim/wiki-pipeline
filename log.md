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
