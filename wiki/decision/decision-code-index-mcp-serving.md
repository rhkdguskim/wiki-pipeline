---
type: decision
title: 코드 인덱스 질의는 MCP 서버로 제공 (우선 채널)
tags: [code-index, mcp, query, serving, developer-facing]
status: active
---

# 결정: 질의 채널은 MCP 서버 — 개발자가 붙어서 코드베이스를 빠르게 스캔한다

코드 인덱스의 읽기 경로([[decision-code-index-pipeline]])를 **MCP 서버**로 제공한다.
개발자(와 그들의 AI 코딩 도구)가 MCP에 붙어 코드베이스를 빠르게 스캔·순회한다.

## 근거

- 소비자가 개발자 — 이미 쓰는 AI 도구(Claude Code 등)에 MCP로 붙이면 **자체 UI 개발 없이** 즉시 소비 가능
- 프로바이더 query의 code traversal 연산([[decision-code-index-provider-abstraction]])이 MCP tool로 자연스럽게 매핑
- 사내에 MCP 운용 경험이 이미 있다 → [[entity-remote-control-mcp]]

## 경계

- MCP 서버는 프로바이더 인터페이스 **위의 껍데기**다 — codegraph 타입·API는 여기서도 새어나오지 않는다 ([[concept-port-adapter]])
- MCP tool 목록(= 질의 표면 구체화)은 미확정 → [[question-code-index-query-surface]]

## 보류 대안 (기각 아님 — 후순위)

- 자체 웹 UI·대시보드 통합·IDE 플러그인 — "우선은 MCP". 프로바이더 위 어댑터이므로 추후 추가해도 구조 변화 없음

관련: [[decision-code-index-pipeline]] · 소스: [[2026-07-05-code-index-followup]]
