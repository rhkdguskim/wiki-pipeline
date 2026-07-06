---
type: question
title: AI 호출 비용 예측치는?
tags: [phase-1, cost]
status: open
---

# ❓ AI 호출 비용은 얼마나 되는가?

과제 4개 × 일일 영향 문서 수 × 문서당 토큰량 × 단가 — 아직 산정 근거 데이터가 없다.
Phase 1 PoC에서 과제 1개로 실측한 뒤 산정한다.

- 블로킹 대상: 없음 (Phase 1 실측 후 답 나옴)
- 비용 구조에 유리한 결정들: [[decision-nightly-batch]] (병합 효과) · [[decision-pull-model]] (호출 최소화)

## 방침 (2026-07-05)

**Phase 1 PoC에서 과제 1개로 실측 후 산정**. 지금 대략 추정은 데이터가 없어 의미 없음. 실측 결과가 테마 2차 확장([[question-theme-expansion]])·변경 중요도 필터([[decision-change-filter-rule-based]])의 우선순위 재료가 됨.

## 갱신 (2026-07-06) — 실측 수단 확보

엔진의 API 자체 에이전트 전환([[decision-engine-api-agent]])으로 **호출 단위 usage 토큰이
응답에 포함**되고, 에이전트 스텝 로그와 함께 이력 DB에 적재된다
([[decision-agent-step-observability]]). PoC 실측이 별도 계측 없이 자동으로 쌓인다.
단일 계정 사용량 한도가 처리량 상한이 되던 축은 종량제(API 키)로 대체
([[decision-engine-api-key-auth]]).
