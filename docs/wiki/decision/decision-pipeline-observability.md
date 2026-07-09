---
type: decision
title: 모든 파이프라인은 대시보드 실시간 진행 모니터링을 갖춘다
tags: [observability, monitoring, dashboard, cross-cutting]
status: active
---

# 결정: 모든 파이프라인은 실시간 진행 모니터링을 1급 요구사항으로 설계한다

현재의 2개 파이프라인 — 정적 문서([[entity-docs-hub]]·[[entity-docu-automatic]]), 매뉴얼 추출([[entity-manual-pipeline]]) — 과 **앞으로 추가될 모든 파이프라인**은 관리 서버 대시보드에서 **진행상황이 실시간으로** 보여야 한다. (코드 인덱스도 대상이었으나 2026-07-06 범위 제외 → [[decision-code-index-out-of-pipeline]])

## 무엇을 요구하나

- **실시간 진행** — 완료 보고뿐 아니라 실행 중 단계·진척이 실시간으로 표시된다(사후 로그만으론 불충분).
- **공통 계약** — 이기종 파이프라인(AI 무거움 / MCP 구동 / 비-AI 폴링)이라도 지휘 계층이 **동일한 형태로 집계·표시**한다 → [[concept-observability-contract]].
- **설계 시 반영** — 모니터링은 파이프라인 개발의 **1급 제약**이다. 나중에 부착하지 않고 처음부터 진행 이벤트를 내보내도록 설계한다.

## 근거

- 파이프라인이 계속 추가된다 → 공통 계약이 없으면 각자 다른 방식이 되어 통합 대시보드가 불가능.
- 관리 서버는 이미 이력 DB(SoT)와 대시보드를 가진다 → [[decision-db-source-of-truth]]. 실시간 진행은 그 위의 자연스러운 확장.
- Control/Data Plane의 ④ 완료 보고·webhook 계약을 **실시간 진행**으로 넓히는 것 → [[decision-control-data-plane-split]].

## 기각 대안

- **완료(사후)만 보고** — 긴 실행(야간 배치·UI 전수 순회) 중 "지금 어디쯤인지"를 알 수 없어 운영·디버깅이 어렵다.
- **파이프라인별 제각각 모니터링** — 통합 대시보드 불가, 신규 파이프라인마다 재발명.

이 결정은 기존 [[question-batch-observability]]의 대시보드 축을 요구사항으로 확정한다. 진행 이벤트의 구체 형태·granularity는 [[question-progress-event-contract]].

원본: [[2026-07-05-pipeline-monitoring]] · 전체 그림: [[overview]]
