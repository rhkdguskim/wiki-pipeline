---
type: question
title: 코드 인덱스 질의 표면·서빙 경계
tags: [code-index, query, traversal, developer-facing, phase-2]
status: answered
---

# ❓ 개발자가 코드 인덱스에 무엇을 어떻게 묻는가

소비자는 **개발자 직접 조회**, query의 최소 요구는 **code traversal**(정의↔참조·호출·의존 순회)로
확정됐다 → [[decision-code-index-provider-abstraction]]. 남은 것:

- **연산 목록** — 심볼 검색·정의로 이동·참조 찾기·호출 그래프 외에 무엇이 필요한가? 레포 횡단(cross-repo) 질의는?
- **서빙 경계** — 질의 API/UI를 어느 평면이 제공하나? 관리 서버 대시보드 통합 vs 별도 질의 서비스
  ([[decision-control-data-plane-split]]의 서비스화 방향과 맞닿는 지점)
- **UI 형태** — 검색 화면? IDE 연동? 대시보드 페이지?

## 답

- **서빙 채널** = MCP 서버 → [[decision-code-index-mcp-serving]] (자체 UI·IDE 플러그인은 후순위)
- **질의 범위** = v1은 **단일 레포** 우선, cross-repo는 후순위 → [[decision-code-index-single-repo-scope]]
- **tool 표면** = 어댑터 정책을 따른다. cg-colby([[decision-code-index-adapter-cg-colby]])는 기본 `codegraph_explore`
  단일 tool 철학이며, 다중 tool 표면이 필요하면 환경변수 토글(`CODEGRAPH_MCP_TOOLS`) 또는 라이브러리 API 경로.

소스: [[2026-07-05-code-index-pipeline]] · [[2026-07-05-code-index-finalization]]
