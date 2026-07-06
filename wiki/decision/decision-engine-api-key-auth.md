---
type: decision
title: 엔진 인증 = API 키 등록 (계정 로그인 대체)
tags: [engine, auth, credential, api, phase-1]
status: active
---

# 결정: 엔진 인증은 API 키를 대시보드에 등록한다

생성 엔진이 자체 에이전트([[decision-engine-api-agent]])로 Messages API를 직접 호출하므로,
인증을 Claude Code 계정 로그인에서 **Anthropic API 키 등록**으로 바꾼다.
[[decision-engine-single-account-auth]]를 supersede한다.

## 무엇을

- **대시보드에 API 키 등록·저장** — 기존 결정의 등록 UI/백엔드·상태 표시 요구는 그대로
  유지하고, 저장 대상만 아이디/패스워드 → API 키로 교체한다. 저장 보안(암호화·접근 제어)은
  [[question-secret-storage-security]]의 운영 단계 과제로 계속 이어진다.
- **러너 주입** — 파이프라인 잡 시작 시 Control Plane이 키를 러너에 환경변수로 주입한다.
- **해지 감지 → 이메일 알림** — 키 무효(401) 감지 시 admin 담당자에게 이메일 알림
  ([[decision-email-alerting]]의 "인증 해지" 케이스를 그대로 계승).

## 근거

- API 키는 만료·재로그인·디바이스 확인이 없어 headless의 "무인 지속" 문제
  ([[question-headless-claude-auth]])가 **구조적으로 소멸**한다.
- 러너→AI 네트워크는 이미 확인됨([[question-runner-ai-network]] ✅) — 추가 전제 없음.
- 호출 단위 usage 토큰이 응답에 포함되어 사용량·비용을 이력 DB에 집계할 수 있다 —
  단일 계정 사용량 한도가 처리량 상한이 되던 문제를 종량제로 대체 ([[question-cost-estimation]]).

## 기각 대안

- **단일 Claude Code 계정 로그인 유지** — 무인 지속 불가 확정으로 만료 감지·재로그인
  운영 절차가 상시 부담이 된다. 야간 무인 배치와 상충.

소스: [[2026-07-06-engine-api-agent-architecture]] · 요약: [[summary-engine-api-agent-architecture]]
