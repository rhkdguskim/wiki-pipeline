---
type: question
title: headless Claude Code 실행의 인증/라이선스 방식은?
tags: [blocking, phase-1, claude-code, auth]
status: open
---

# ❓ headless Claude Code 실행의 인증/라이선스 방식은?

생성 엔진([[entity-docu-automatic]])은 Claude Code CLI 대화형 전제로 설계됐다.
CI 러너에서 `claude -p`(headless)로 돌릴 때 인증을 무엇으로 하는가 — API 키? 사내 게이트웨이?
그리고 headless에서 task-pipeline 스킬 + Agent 위임이 정상 동작하는가?

- **블로킹**: Phase 1 최우선 검증 항목. 실패 시 대안(에이전트 로직의 스크립트 포팅) 검토
- 이 검증 결과가 "Claude Code 재사용 vs 자체 에이전트" 갈림길의 첫 관문이다 → [[question-engine-runtime]]
- 관련: [[question-runner-ai-network]]

## 방침 (2026-07-05)

**Phase 1 첫 스프린트에서 즉시 검증**. 구체 인증 수단(API 키 vs 사내 게이트웨이)은 검증 시점에 시도해 보고 결정. 엔진은 하이브리드([[decision-engine-hybrid]])이므로, headless가 막히면 자체 에이전트(B)로 전환하는 driver가 된다.
