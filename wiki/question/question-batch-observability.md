---
type: question
title: 배치 관측성·알림을 어떻게 제공할까?
tags: [enhancement, observability, alerting, phase-2]
status: open
---

# ❓ 밤사이 무슨 일이 있었나 — 사람에게 도달하는 경로가 없다

이력 DB(`runs`/`run_items`)에 데이터는 쌓이지만, 그 결과가 **사람에게 도달하는 경로**가 아직 없다.
배치가 조용히 실패해도(3연속 FAIL 중단 등) 아무도 모른다.

- 후보 기능: **아침 배치 리포트(daily digest)** — 성공/실패·생성 문서·경고 요약 / **실패 알림** — 배치 실패·중단·MR 생성 시 사내 메신저·메일 푸시 / **운영 대시보드** — 소스별 상태·머지율·리뷰 소요시간 시각화
- 가성비: 데이터는 이미 [[decision-db-source-of-truth]]에 있으므로 신규 인프라 부담이 작다 (가장 저비용 다음 걸음)

## 갱신 (2026-07-05)

이 중 **운영 대시보드(실시간 진행 표시)** 축은 이제 요구사항으로 확정됐다 — 모든 파이프라인 공통 → [[decision-pipeline-observability]] · [[concept-observability-contract]]. 남은 열린 부분은 **알림/리포트**(daily digest·실패 푸시·채널·수신 대상·주기).

- 블로킹 대상: 없음 (Phase 2, 골격 동작 후 우선 착수 후보)

## 방침 (2026-07-05)

세 기능 모두 도입 — **아침 daily digest + 실패/MR 즉시 알림 + 운영 대시보드(머지율·소요시간)**. 채널·수신 대상·주기 구체는 Phase 2 설계 시 확정.

전체 그림: [[overview]] · 근거 분석: 브레인스토밍 query 2026-07-05
