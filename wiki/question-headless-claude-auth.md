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
- 관련: [[question-runner-ai-network]]
