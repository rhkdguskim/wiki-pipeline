---
type: question
title: 사소한 변경은 재생성을 건너뛸까?
tags: [enhancement, cost, impact-analysis, phase-2]
status: open
---

# ❓ 오타·포맷팅 같은 변경까지 재생성해야 하나?

영향 분석은 변경 경로 ↔ frontmatter 매핑으로 영향 문서를 산출하지만,
그 변경이 **의미 있는지**(로직 변경 vs 오타·포맷팅·주석)는 구분하지 않는다 — 사소한 diff에도 AI를 호출할 수 있다.

- 후보 기능: **변경 중요도 필터** — 사소한 변경은 재생성 스킵 / 나아가 semantic diff로 "의미 있는 변경" 판단
- 효과: [[decision-nightly-batch]](병합)·[[decision-pull-model]](호출 최소화)에 이은 추가 비용 절감 → [[question-cost-estimation]]과 직결
- 주의: compare가 이미 커밋 N개를 파일 집합 1개로 병합하므로([[concept-idempotent-sha]]), 이 필터는 그 위에 얹는 2차 최적화
- 열린 부분: 중요도 판정 기준(규칙 기반 vs 모델 판단)의 오탐 위험(중요 변경을 스킵)
- 블로킹 대상: 없음 (Phase 2, 비용 실측 후 필요성 판단)

전체 그림: [[overview]] · 근거 분석: 브레인스토밍 query 2026-07-05
