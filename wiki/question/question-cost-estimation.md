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
