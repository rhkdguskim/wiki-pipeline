---
type: question
title: MCP·앱·AI 인증/네트워크 경로는?
tags: [network, auth, mcp]
status: answered
---

# ❓ MCP·앱·AI 인증/네트워크 경로는?

[[entity-remote-control-mcp]] 구동에는 두 개의 "바깥으로 나가는 채널"이 얽힌다 — 둘 다 확정됐다.

- **MCP ↔ 앱 실행 환경** — ✅ 앱 실행 호스트의 **IP/port**로 세션 MCP(`sw-rcs-session-mcp`)를 제어 → [[decision-app-host-connection]].
- **파이프라인 ↔ AI** — ✅ 매뉴얼 생성 단계의 LLM 호출 경로. **네트워크는 뚫려 있음**(2026-07-05 확인, 폐쇄망 아님) → [[question-runner-ai-network]].

## ✅ 정리

두 네트워크 축 모두 확정(MCP=IP/port, AI=뚫림). 남은 세부는 별개 질문으로 위임 — AI 인증/실행 방식 → [[question-headless-claude-auth]], 시크릿 저장 보안(우선순위 낮음) → [[question-secret-storage-security]].

관련: [[question-app-exec-environment]]
