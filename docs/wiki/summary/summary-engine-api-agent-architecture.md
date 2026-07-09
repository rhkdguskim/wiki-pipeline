---
type: summary
title: 엔진 API 자체 에이전트 전환 요약 — B 경로 확정 · API 키 인증 · 스텝 관측
tags: [engine, agents, api, auth, observability]
status: active
---

# 요약: 엔진 = API 자체 에이전트 전환 + 에이전트 스텝 대시보드 관측

원본: [[2026-07-06-engine-api-agent-architecture]]

headless 무인 지속 불가 확정([[2026-07-06-failure-alerting-email]])이 [[decision-engine-hybrid]]가
명시해 둔 B 전환 driver를 발동시켰다. 두 파이프라인(정적·매뉴얼 추출)의 생성 엔진을
`claude -p` 재사용(A) 대신 **Anthropic Messages API + tool use 자체 에이전트 루프(B)**로
전환 확정하고, 에이전트의 사고·동작·진행을 대시보드에 전부 출력하는 요구가 추가됐다.

## 확정 사항

- **자체 에이전트 아키텍처** → [[decision-engine-api-agent]]
  - 루프는 기존 Data Plane(CI 러너) 안에서 실행 — Control/Data Plane 계약 불변
  - 공통 에이전트 런타임 1개 + 파이프라인별 도구 세트·프롬프트만 교체
  - 정적=테마당 1루프 · 매뉴얼=순회 세션당 1루프 (거대 단일 에이전트 기각)
  - Anthropic 호스팅형(Managed Agents) 기각 — 사내 GitLab·사내 UI 호스트 접근 불가
- **엔진 인증 = API 키 등록** → [[decision-engine-api-key-auth]]
  ([[decision-engine-single-account-auth]] supersede — 무인 지속 문제 구조적 소멸)
- **에이전트 스텝 관측** → [[decision-agent-step-observability]]
  - 사고 요약·도구 호출·도구 결과·토큰 사용을 진행 이벤트 계약([[decision-observability-event-contract]])의
    하위 계층으로 대시보드 실시간 출력 + 이력 DB 스텝 로그(감사 추적)

## 파생 갱신

- [[decision-engine-hybrid]] — driver 발동으로 B 확정 (엔진 인터페이스는 유지)
- [[question-headless-claude-auth]] — answered (질문 자체가 해소)
- [[question-engine-runtime]] — B 전환 확정 갱신
- [[question-cost-estimation]] — 호출 단위 usage 토큰으로 실측 수단 확보
- [[entity-docu-automatic]] — 실행 방식 조정점 갱신
