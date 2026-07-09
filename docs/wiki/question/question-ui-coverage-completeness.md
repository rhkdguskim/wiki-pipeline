---
type: question
title: '모든 기능 완전 순회 보장·측정'
tags: [phase-2, coverage, traversal]
status: answered
---

# ❓ "모든 기능" 완전 순회를 어떻게 보장·측정하나?

[[decision-hybrid-app-traversal]]의 자율 탐색이 앱의 모든 기능에 실제로 도달했는지 보장·측정할 방법이 필요하다.

- 미도달 화면/기능을 어떻게 감지하나 (커버리지 지표)?
- 시나리오가 커버하는 부분 + 탐색이 커버하는 부분을 합쳐 "누락"을 계산할 수 있나?
- 관측은 도달한 범위에서만 근거가 된다 → [[concept-observation-grounding]]의 한계와 직결.

## ✅ 답 (2026-07-05)

**커버리지 지표 + 누락 표시** → [[decision-coverage-metric-gap]]. 시나리오 도달 + 탐색 도달 합산으로 측정하고 미도달을 대시보드에 표시. "전체 기능" 추정 방식은 구현 시 확정. 보장 포기·로그만은 기각.

관련: [[question-scenario-set-ownership]] · [[question-manual-delete-safety]]
