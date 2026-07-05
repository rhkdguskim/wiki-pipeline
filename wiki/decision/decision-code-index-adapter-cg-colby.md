---
type: decision
title: 코드 인덱스 프로바이더 첫 어댑터 = cg-colby 확정
tags: [code-index, adapter, codegraph, provider]
status: active
---

# 결정: 첫 구현 어댑터는 cg-colby(`colbymchenry/codegraph`)로 간다

코드 인덱스 프로바이더([[decision-code-index-provider-abstraction]])의 첫 구현 어댑터로
**cg-colby(`colbymchenry/codegraph`)**를 확정한다 → [[entity-codegraph]].

## 근거

- **가벼운 의존** — 단일 SQLite 파일(`.codegraph/codegraph.db`, WAL+FTS5)에 외부 그래프 DB가 없다.
  Data Plane(Windows CI)에 Node 런타임만으로 올라간다.
- **자동 격리** — 레포별로 독립 `.codegraph/`가 생기므로 멀티 레포 정합성이 구조적으로 안전
  ([[decision-code-index-single-repo-scope]]의 단일 레포 모델과 정합).
- **증분 인덱싱 1급** — `sync`(content-hash) + 파일 감시 + 재연결 catch-up이 짧은 주기 폴링
  ([[decision-code-index-pipeline]])과 자연스럽게 맞는다.
- **성숙도** — 1.2.0 안정 버전, MIT, 문서 정합성 양호. traversal(`GraphTraverser`)이 우리 1급 연산 요구를
  초과 충족한다(traverseBFS/DFS·getCallers/getCallees·getImpactRadius·findPath).
- 30개 언어 지원(tree-sitter) — 사내 레포 다양성을 넉넉히 커버.

## 어댑터 매핑 (인터페이스 → cg-colby)

| 우리 인터페이스 | cg-colby 동작 |
|----------------|--------------|
| `index(repo, sha)` | `codegraph init`/`index`/`sync` + 와처. sha는 외부 sha 포인터가 관리 |
| `query(...)` | MCP `codegraph_explore` 또는 `GraphTraverser` 라이브러리 직접 호출 |
| `manage(...)` | `install`/`uninstall`/`status` + `CODEGRAPH_DIR` 격리 정책 노출 |

## 주의점 (어댑터가 흡수해야 할 제약)

- MCP 기본 노출이 `codegraph_explore` **단일 tool**로 고정돼 있다 → 다중 tool 표면을 원하면
  환경변수(`CODEGRAPH_MCP_TOOLS`) 토글 또는 라이브러리 API 경로로 간다. 우리 MCP 서빙
  ([[decision-code-index-mcp-serving]])의 tool 목록은 이 정책 위에서 결정된다.
- 저장소가 **레포 내부**라 어댑터 `manage`가 `CODEGRAPH_DIR`·WSL 분리 규칙을 그대로 노출해야 한다.

## 기각 대안

- **cgc(CodeGraphContext, B)** — traversal 기능성은 최상급(Cypher 직접 질의, 25 MCP tools)이나,
  (a) 그래프 DB 클라이언트(falkordb/kuzu/ladybug/neo4j)와 redis-py가 **전부 강제 설치**돼 의존이 heavy,
  (b) global 모드 기본값이라 멀티 레포 격리 보장이 어댑터 운영 부담,
  (c) Alpha(0.5.1)에 도구 개수 문서 불일치(21 vs 25)가 있어 어댑터 뒤에서도 내부 버전 드리프트 리스크.
  기능성은 우수하나 운영 부담·성숙도에서 열세.

관련: [[decision-code-index-provider-abstraction]] · [[entity-codegraph]] · 소스: [[2026-07-05-code-index-finalization]]
