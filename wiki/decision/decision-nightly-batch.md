---
type: decision
title: 야간 배치 실행 (기본 평일 20:00)
tags: [schedule, batch, cost]
status: active
---

# 결정: 야간 배치

커밋마다 AI를 실행하지 않고, 하루치 변경을 모아 퇴근 후 1회 배치로 처리한다.

## 근거

- AI 호출 비용·러너 부하·문서 MR 리뷰 폭주 방지
- 하루치 커밋이 문서 단위로 자연 병합 → AI 호출이 커밋 수가 아닌 **영향 문서 수**에 비례
- 문서 갱신의 실시간성은 요구사항이 아님 (의도적 포기)

## 구현

- 스케줄러는 **관리 서버 내장 cron** (GitLab pipeline schedule 아님) — 스케줄·수동 트리거·상태를 대시보드 한 곳에서 통제
- 예외: Phase 1 PoC는 서버가 없으므로 GitLab pipeline schedule로 임시 운영
- 수동 트리거 병행: 특정 소스만 즉시 실행, full 재생성 옵션, 실행 중 중복 트리거 락
- 시각/요일·과제별 개별 스케줄은 미확정 → [[question-schedule-policy]]

관련: [[decision-pull-model]] · [[summary-design-session]] · 상세: `../../docs/features/scheduling.md`
