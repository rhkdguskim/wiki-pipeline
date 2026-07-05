---
type: question
title: 스케줄 시각/요일, 과제별 개별 스케줄?
tags: [phase-2, schedule]
status: answered
---

# ❓ 스케줄 정책은 어떻게 정하는가?

기본안은 평일 20:00 1회([[decision-nightly-batch]]). 확정할 것: 정확한 시각/요일,
과제별로 다른 스케줄이 필요한지, run당 처리 시간·AI 호출 상한값.

## ✅ 답 (2026-07-05)

**과제별 개별 스케줄, 대시보드에서 설정** → [[decision-schedule-per-source]]. 평일 20:00은 기본값이고 과제마다 대시보드에서 시각/요일/주기·run당 상한을 덮어쓴다. 단일 고정 스케줄·코드 관리는 기각.

- Phase 2 (스케줄러 이관 시점)
