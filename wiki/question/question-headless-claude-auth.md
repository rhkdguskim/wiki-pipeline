---
type: question
title: headless Claude Code 실행의 인증/라이선스 방식은?
tags: [phase-1, claude-code, auth]
status: answered
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

## 방침 갱신 (2026-07-06)

인증 수단은 **단일 Claude Code 계정 로그인 방식**으로 확정 → [[decision-engine-single-account-auth]] (대시보드에 아이디/패스워드 등록). 다만 이 결정은 "무엇으로 인증하는가"를 고정할 뿐, **"headless에서 로그인이 무인으로 지속되는가(토큰 갱신·재로그인·디바이스 확인)"는 여전히 검증 대상**이라 이 질문은 open·blocking을 유지한다.

## 갱신 (2026-07-06) — 무인 지속 안 됨 확정

**headless 로그인은 무인으로 지속되지 않는다** — 확인된 사실로 기록 ([[2026-07-06-failure-alerting-email]]).
이에 따라 검증 초점이 "지속 여부"에서 **만료 감지·재로그인 운영 절차**(+ headless에서 task-pipeline
스킬·Agent 위임 동작 검증)로 이동한다. 인증 해지/만료 감지 시 admin 담당자에게 이메일로 알린다
→ [[decision-email-alerting]]. headless 동작 검증이 남아 open·blocking 유지.

## ✅ 답 (2026-07-06) — 질문 자체가 해소

무인 지속 불가 확정이 [[decision-engine-hybrid]]의 B 전환 driver를 발동시켜, 엔진이
**자체 에이전트(API 직접 호출)로 전환**됐다 → [[decision-engine-api-agent]]. 인증은
**API 키 등록**으로 대체되어([[decision-engine-api-key-auth]]) 만료·재로그인·디바이스 확인이
없는 방식이 됐고, "headless Claude Code의 인증"이라는 질문 자체가 무의미해졌다.
남은 운영 항목(키 해지 401 감지 → admin 이메일)은 새 결정이 담는다.
