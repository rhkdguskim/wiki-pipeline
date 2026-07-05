---
type: entity
title: codegraph (코드 인덱싱 도구 — 첫 어댑터 cg-colby 확정)
tags: [code-index, external-tool, adapter]
status: active
---

# codegraph — 코드 인덱싱 도구

"codegraph"는 사내 파이프라인이 도입한 코드 인덱싱 기술의 통칭이다. 프로바이더 인터페이스
([[decision-code-index-provider-abstraction]]) 뒤에 숨겨지므로, 구체 제품이 무엇이든 index/query/manage
세 동작으로 환원된다. 후보 2종을 조사한 끝에 **cg-colby(A)를 첫 어댑터로 확정**했다 (2026-07-05)
→ [[decision-code-index-adapter-cg-colby]].

## 시스템과의 관계

- 파이프라인·MCP 서버는 codegraph에 **직접 의존하지 않는다** — 프로바이더 인터페이스(index/query/manage)
  뒤에서만 동작하며, codegraph의 타입·질의 API·저장 형식은 어댑터 내부에 갇힌다 → [[concept-port-adapter]]
- 교체 시나리오: 다른 인덱싱 기술로 갈아 끼워도 파이프라인·질의 경로(MCP 서빙 포함)는 무변경
  → [[decision-code-index-mcp-serving]]
- 인덱스 산출물은 코드 sha에 결부된 버전 스냅샷으로 형상 관리된다 → [[decision-code-index-versioning]]

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

**어댑터 적합성**: 거의 1:1 매핑 — `index`(init/index/sync+와처) · `query`(MCP explore 또는 GraphTraverser 직접) ·
`manage`(install/uninstall/status). traversal 요구 초과 충족. 주의점: 저장소가 레포 내부라 어댑터 `manage`가
격리 정책(`CODEGRAPH_DIR`·WSL 분리)을 노출해야 하고, MCP 기본 노출이 단일 tool로 고정돼 다중 tool 표면을
원하면 환경변수 토글 또는 라이브러리 경로로 가야 함.

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

**어댑터 적합성**: traversal 기능성은 후보 최상급. 단 (a) 임베디드라 해도 falkordb/kuzu/ladybug/neo4j 클라이언트와
redis-py가 **전부 강제 설치**돼 의존이 heavy, (b) global 모드 기본값이라 멀티 레포 격리 보장이 어댑터 운영 책임,
(c) Alpha 버전(0.5.1)에 도구 개수 문서 불일치(21 vs 25)가 있어 어댑터 뒤에서도 내부 버전 드리프트 리스크.

## 비교 — 어댑터 설계에 미치는 차이

| 축 | cg-colby (A) | cgc (B) | 파이프라인 영향 |
|----|--------------|---------|----------------|
| 저장 형식 | 단일 SQLite 파일 (레포 내부) | 그래프 DB (글로벌 홈, 멀티 백엔드) | A는 sha별 스냅샷([[decision-code-index-versioning]])이 파일 복사로 단순; B는 DB 덤프/컨텍스트 분리 필요 |
| 외부 의존 | Node 런타임만 | 그래프 DB 클라이언트 다수 + (운영 시) Neo4j 서버 | A가 Data Plane(Windows CI)에 가볍게 올라감 |
| 격리 기본값 | 레포별 물리 분리 (자동) | global 모드(섞임) — per-repo로 고정해야 | A가 멀티 레포 정합성에 안전 |
| MCP 표면 | 단일 tool 기본(환경변수로 다중) | 25개 tool | 우리 MCP 질의 표면([[question-code-index-query-surface]]) 설계 입력 |
| 성숙도 | 1.2.0 (안정) | 0.5.1 Alpha | 어댑터 안정성·문서 정합성은 A 우위 |
| 트리거 적합성 | 와처+증분 기본 — 우리 폴링 트리거와 정합 | 와처는 옵션 — 폴링 주도 시 어댑터가 index 명령을 풀 스캔으로 부를 수 있음 | A가 짧은 주기 폴링([[decision-code-index-pipeline]])과 더 자연스럽게 맞음 |

## 열린 부분 (어댑터 설계 입력)

- ~~최종 어댑터 후보 선택~~ → **확정: cg-colby(A)** → [[decision-code-index-adapter-cg-colby]]
- MCP tool 목록(= 우리 질의 표면) — 단일 레포 우선 범위([[decision-code-index-single-repo-scope]]) 안에서
  cg-colby 정책(기본 단일 tool + 환경변수 다중 노출) 위에서 결정 → [[question-code-index-query-surface]] answered
- 인덱스 저장소 소유 평면 — 별도 질의 서비스 평면 확정 → [[decision-code-index-store-plane]] ·
  [[question-code-index-store]] answered. 보존 버전 수는 여전히 미정(구현 시 결정).

소스: [[2026-07-05-code-index-pipeline]] · [[2026-07-05-code-index-followup]] · [[2026-07-05-code-index-finalization]] (후보 조사 2026-07-05, scratchpad clone 기반)
