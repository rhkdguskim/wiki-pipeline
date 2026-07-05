---
type: summary
title: 설계 논의 기록 요약 (2026-07-05)
tags: [design, history]
status: active
---

# 설계 논의 기록 요약

> 원본: `../../raw/2026-07-05-design-session.md`

wiki-pipeline의 설계가 확정되기까지의 논의 기록. 대안 3개를 검토했고 마지막 안이 채택됐다.

## 설계 진화

1. **push 즉시 실행** — 커밋마다 trigger job으로 AI 실행 → ❌ 비용·부하·리뷰 폭주
2. **push 수집 + 야간 배치(큐)** — 낮엔 큐 적재, 밤에 소비 → ❌ 큐 인프라 관리 부담 + 소스 레포 CI 수정 필요
3. **pull 모델 + 야간 배치** — docs-hub가 compare API로 직접 조회 → ✅ 채택 ([[decision-pull-model]], [[decision-nightly-batch]])
4. 이후 **관리 서버(Control Plane)** 추가 — 등록/수동 트리거/대시보드, DB가 source of truth ([[decision-db-source-of-truth]])

## 이 소스에서 파생된 페이지

- 결정: [[decision-pull-model]] · [[decision-nightly-batch]] · [[decision-db-source-of-truth]] · [[decision-mr-review-gate]]
- 패턴: [[concept-idempotent-sha]]
- 구성 요소: [[entity-docs-hub]] · [[entity-mirero-gitlab]]
- 미해결: [[question-runner-ai-network]] 외 8건 ([[overview]] 참조)

전체 그림 → [[overview]]
