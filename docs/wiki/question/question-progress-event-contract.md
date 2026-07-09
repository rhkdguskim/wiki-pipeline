---
type: question
title: 진행 이벤트의 형태·granularity는?
tags: [phase-2, observability, contract]
status: answered
---

# ❓ 진행 이벤트의 형태·granularity는?

[[decision-pipeline-observability]]가 실시간 진행 모니터링을 요구한다. 그 **공통 진행 이벤트**의 구체가 미정
→ [[concept-observability-contract]].

## ✅ 답 (2026-07-05)

**표준 스키마 + 가변 단위(unit) + webhook push**로 확정 → [[decision-observability-event-contract]]. 모든 이벤트가 공통 필드(파이프라인 id·단계·진척 N/M·타임스탬프·상태)를 갖되, granularity는 %로 강제 통일하지 않고 `unit` 필드로 원 단위(테마·순회 화면·인덱싱 파일)를 살려 전달한다. 전달은 단계 전이·진척 변화 시 webhook push, poll은 보조.

- 이벤트 스키마 — 어떤 필드(파이프라인 id·단계·진척·타임스탬프·상태)?
- **granularity** — 이기종 파이프라인이 진척을 어떻게 통일하나? (테마 N/M / 순회 화면 N/M / 인덱싱 파일 N/M 등 서로 다른 단위)
- 전달 방식 — push(webhook/이벤트) vs poll? 기존 pipeline webhook + 완료 보고와 어떻게 합치나 → [[decision-control-data-plane-split]].
- 실시간성 수준 — 초 단위 스트림인가, 단계 전이마다인가?

관련: [[question-batch-observability]]
