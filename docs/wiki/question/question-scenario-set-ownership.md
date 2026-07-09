---
type: question
title: 시나리오 세트는 누가 정의·유지하나?
tags: [phase-2, scenario, ownership]
status: answered
---

# ❓ 시나리오 세트는 누가 정의·유지하나?

[[decision-hybrid-app-traversal]]의 결정적 뼈대인 시나리오 세트의 소유·유지 주체가 미정.

- 과제 담당자가 정의하나, 기존 QA/테스트 자산을 재사용하나?
- 앱이 바뀌면 시나리오도 갱신돼야 한다 — 유지 부담을 누가 지나?
- 시나리오 형식·저장 위치(app 등록의 일부 → [[entity-manual-pipeline]])는?

## ✅ 답 (2026-07-05)

**과제 담당자가 대시보드에서 정의·유지** → [[decision-scenario-owner-dashboard]]. 저장은 app 등록의 일부로 서버 DB. 기존 QA 자산 재사용·시나리오 최소화는 기각(후자는 보조로만).

관련: [[question-ui-coverage-completeness]]
