---
type: question
title: 진행 이벤트의 형태·granularity는?
tags: [phase-2, observability, contract]
status: answered
---

# ❓ 진행 이벤트의 형태·granularity는?

[[decision-pipeline-observability]]가 실시간 진행 모니터링을 요구한다. 그 **공통 진행 이벤트**의 구체가 미정
→ [[concept-observability-contract]].

- 이벤트 스키마 — 어떤 필드(파이프라인 id·단계·진척·타임스탬프·상태)?
- **granularity** — 이기종 파이프라인이 진척을 어떻게 통일하나? (테마 N/M / 순회 화면 N/M / 인덱싱 파일 N/M 등 서로 다른 단위)
- 전달 방식 — push(webhook/이벤트) vs poll? 기존 pipeline webhook + 완료 보고와 어떻게 합치나 → [[decision-control-data-plane-split]].
- 실시간성 수준 — 초 단위 스트림인가, 단계 전이마다인가?

관련: [[question-batch-observability]]
