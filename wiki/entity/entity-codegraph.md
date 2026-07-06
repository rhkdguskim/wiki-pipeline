---
type: entity
title: codegraph (코드 인덱싱 도구 — 개인 도구 참고 자료)
tags: [code-index, external-tool, personal-tooling]
status: active
---

# codegraph — 코드 인덱싱 도구

"codegraph"는 코드 인덱싱 기술의 통칭으로, 후보 2종(cg-colby·cgc)을 2026-07-05에 실측 조사했다.
당시 중앙 파이프라인의 첫 어댑터로 cg-colby(A)를 확정했으나([[decision-code-index-adapter-cg-colby]]),
**2026-07-06 코드 인덱스가 중앙 파이프라인 범위에서 제외**되면서([[decision-code-index-out-of-pipeline]])
이 조사는 **개발자가 개인 로컬 도구를 고를 때의 참고 자료**로 남는다.

## 시스템과의 관계 (2026-07-06 이후)

- 중앙 파이프라인·서버는 코드 인덱싱을 **하지 않는다** — 코드 검색·traversal은 개발자 개인이
  로컬 도구로 해결한다 → [[decision-code-index-out-of-pipeline]]
- 개인 관리 관점에서는 **cg-colby가 그대로 적합**하다 — 레포 내부 `.codegraph/` 저장(격리 자동),
  와처 기반 증분, content-hash `sync`(revert/reset 등 어떤 경로로 상태가 바뀌어도 작업 트리에 수렴),
  로컬 MCP 서빙까지 자체 완결
- 아래 실측 표와 비교는 조사 시점(2026-07-05)의 사실 기록이다 — 어댑터 관련 서술은 superseded 결정
  ([[decision-code-index-provider-abstraction]] 등)의 맥락에서 읽을 것

## 후보 A — CodeGraph (`colbymchenry/codegraph`, 일명 cg-colby)

로컬 코드 인텔리전스 도구. tree-sitter 기반 심볼·호출 엣지·의존성을 SQLite(`.codegraph/codegraph.db`)에
저장하고 MCP로 노출해 AI 에이전트가 한 번의 질의로 컨텍스트를 얻게 한다.

| 항목 | 값 |
|------|----|
| 구현 언어 | TypeScript (Node.js ≥20) |
| 라이선스 / 버전 | MIT / 1.2.0 (2026-07-02) |
| 배포 | 자체 완결 번들(install.sh, Node 불필요) · npm · npx |
| 지원 언어 | 30종 (TS/JS/Python/Go/Rust/Java/C#/PHP/Ruby/C·C++/Swift/Kotlin/Scala/… Terraform 포함) |
| 인덱스 저장 | **프로젝트 내부** `.codegraph/codegraph.db` (SQLite + WAL + FTS5, 외부 DB 无) |
| 질의 | CLI · MCP server · 라이브러리(`GraphTraverser`) 삼축 |
| traversal | `GraphTraverser.traverseBFS/DFS`(방향·엣지·깊이 제어) · `getCallers/getCallees` · `getImpactRadius` · `findPath` — **정의↔참조·호출·의존을 네이티브 1급 지원** |
| 증분 인덱싱 | 1급 — `sync`(content-hash) + 파일 감시(FSEvents/inotify, 2s 디바운스) + 재연결 시 catch-up |
| MCP | `codegraph serve --mcp`. 기본 = `codegraph_explore` 단일 tool(철학). 환경변수로 search/node/callers/callees/impact/files/status 개별 노출 가능 |
| 멀티 레포 | 프로젝트별 독립 `.codegraph/` (`CODEGRAPH_DIR` 오버라이드, monorepo 부분 색인 지원) |

**어댑터 매핑(사실)**: 세 동작에 거의 1:1 — `index`(init/index/sync+와처) · `query`(MCP explore 또는
GraphTraverser 직접) · `manage`(install/uninstall/status). 제약: 저장소가 레포 내부라 어댑터 `manage`가
격리 정책(`CODEGRAPH_DIR`·WSL 분리)을 노출해야 하고, MCP 기본 노출이 단일 tool로 고정된다(다중 tool은
환경변수 토글·라이브러리 경로). 이 사실들이 왜 A를 첫 어댑터로 택하게 했는지(선택·기각 근거)는
[[decision-code-index-adapter-cg-colby]]가 소유한다.

## 후보 B — CodeGraphContext (`CodeGraphContext/CodeGraphContext`, 일명 cgc)

코드 저장소를 "AI 에이전트가 질의 가능한 그래프"로 만드는 Python 도구. tree-sitter로 파싱해
그래프 DB(멀티 백엔드)에 Cypher로 영속화한다.

| 항목 | 값 |
|------|----|
| 구현 언어 | Python (≥3.10) |
| 라이선스 / 버전 | MIT / 0.5.1 (**Alpha**, 2026) |
| 배포 | PyPI (`pip install codegraphcontext`, 명령 `cgc`) |
| 지원 언어 | 21종 모듈 (Python/JS/TS/TSX/Go/Rust/C·C++/Java/Ruby/C#/PHP/Kotlin/Scala/Swift/Haskell/Dart/Perl/Elixir/Lua/HTML/CSS). SCIP 정밀 옵션(C/C++/C#) |
| 인덱스 저장 | **그래프 DB** — FalkorDB Lite(기본)·KuzuDB·LadybugDB(임베디드) · FalkorDB Remote·Neo4j(서버). 17 노드 라벨 + 7 릴레이션. 글로벌 `~/.codegraphcontext/` |
| 질의 | CLI · MCP server · FastAPI/SSE 삼축 |
| traversal | `analyze_code_relationships`의 15개 query_type(callers/callees/call_chain/class_hierarchy/module_deps…) + `find_code` + `execute_cypher_query` — **정의↔참조·호출·의존 1급 지원, Cypher 직접 질의까지** |
| 증분 인덱싱 | 와처 동작 시에만(`_handle_modification` INCREMENTAL 경로). 일회성 index 명령은 풀 스캔. SCIP 경로는 항상 풀 리인덱스 |
| MCP | `cgc mcp start`. tool 25개(add_code_to_graph/watch/find_code/analyze_code_relationships/list_indexed_repositories/delete_repository/switch_context/execute_cypher_query/…) |
| 멀티 레포 | global(기본, 한 DB에 섞임)·per-repo(독립 DB)·named 모드. 진정한 격리는 per-repo/named로 고정 운영 시에만 |

**어댑터 매핑(사실)**: traversal 기능성은 후보 최상급. 제약(사실): 임베디드라도 그래프 DB 클라이언트
다수 + redis-py를 함께 설치하고, 격리는 global 모드가 기본이며, 버전은 0.5.1 Alpha다(위 표 참조).
이 사실들을 근거로 B를 기각한 판단은 [[decision-code-index-adapter-cg-colby]]가 소유한다.

## 비교 — 두 도구의 스펙 대조 (사실)

두 후보의 객관 스펙 대조다. 이 대조를 근거로 **cg-colby(A)를 택한 선택·기각 판단**은
[[decision-code-index-adapter-cg-colby]]가 소유한다(우열 결론은 여기 두지 않는다).

| 축 | cg-colby (A) | cgc (B) |
|----|--------------|---------|
| 저장 형식 | 단일 SQLite 파일 (레포 내부) | 그래프 DB (글로벌 홈, 멀티 백엔드) |
| 외부 의존 | Node 런타임만 | 그래프 DB 클라이언트 다수 + (운영 시) Neo4j 서버 |
| 격리 기본값 | 레포별 물리 분리 (자동) | global 모드(섞임) — per-repo로 고정해야 |
| MCP 표면 | 단일 tool 기본(환경변수로 다중) | 25개 tool |
| 성숙도 | 1.2.0 (안정) | 0.5.1 Alpha |
| 증분/와처 | 와처+증분 기본 | 와처는 옵션 — 일회성 index는 풀 스캔 |

관련 설계 입력: 저장 형식은 sha 스냅샷 형상관리([[decision-code-index-versioning]]),
MCP 표면은 질의 표면([[question-code-index-query-surface]]), 증분은 폴링 주기([[decision-code-index-pipeline]]).

## 열린 부분 — 닫힘 (2026-07-06)

어댑터 설계 입력으로 열려 있던 항목들(어댑터 선택·MCP tool 목록·저장소 평면·보존 버전 수)은
코드 인덱스의 파이프라인 범위 제외([[decision-code-index-out-of-pipeline]])로 전부 무의미해졌다.
당시 결론의 기록은 [[decision-code-index-adapter-cg-colby]] · [[question-code-index-query-surface]] ·
[[question-code-index-store]] 참조.

소스: [[2026-07-05-code-index-pipeline]] · [[2026-07-05-code-index-followup]] · [[2026-07-05-code-index-finalization]] (후보 조사 2026-07-05, scratchpad clone 기반)
