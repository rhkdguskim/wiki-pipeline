---
type: question
title: 스케줄 시각/요일, 소스별 다중 스케줄, 파이프라인 선택?
tags: [phase-2, schedule, pipeline]
status: answered
---

# ❓ 스케줄 정책은 어떻게 정하는가?

기본안은 평일 20:00 1회([[decision-nightly-batch]]). 확정할 것: 정확한 시각/요일,
과제별로 다른 스케줄이 필요한지, run당 처리 시간·AI 호출 상한값.

## ✅ 답 (2026-07-05, 2026-07-07 구현 보강)

**소스별 다중 스케줄, 각 스케줄이 실행할 파이프라인을 선택, 대시보드에서 설정** → [[decision-schedule-per-source]].
평일 20:00은 기본값이고, 소스마다 여러 스케줄을 둘 수 있다. 스케줄 row는 `pipeline_id`, `mode`, `branch_role`,
요일/시간, 활성 여부를 저장한다. 현재 실제 실행 연결은 `static/auto|init|diff/dev|release`이며, 매뉴얼 파이프라인이
Control Plane trigger에 연결되면 같은 구조에 `manual` 스케줄을 추가한다.

단일 고정 스케줄·소스당 단일 cron·코드 관리는 기각.

- Phase 2 (스케줄러 이관 시점)
