---
type: question
title: 러너 → AI API 네트워크 경로는?
tags: [phase-1, network, infra]
status: answered
---

# ❓ 러너 → AI API 네트워크 경로는?

사내 GitLab 러너([[entity-mirero-gitlab]])에서 AI API로 나가는 경로가 확인되지 않았다.
폐쇄망/프록시인가? AI 도메인 화이트리스트 등록이 가능한가? 사내 LLM 게이트웨이가 있는가?

## ✅ 답 (2026-07-05)

**네트워크는 뚫려 있다** — 러너에서 AI 서비스로 나가는 경로가 확보돼 있음(폐쇄망 차단 아님) → [[entity-mirero-gitlab]] 인프라 항목. **Phase 1 블로킹에서 해제**되며, 정적·매뉴얼 두 파이프라인 모두 해당.

남은 것은 **네트워크가 아니라 인증/실행 방식**(API 키·게이트웨이 등) → [[question-headless-claude-auth]] (별개 질문).

- 관련: [[question-headless-claude-auth]] · [[question-mcp-auth-network]]
