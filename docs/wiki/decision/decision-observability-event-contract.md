---
type: decision
title: 진행 이벤트 = 표준 스키마 + 가변 단위 + webhook push
tags: [observability, contract, event, phase-2]
status: active
---

# 결정: 진행 이벤트는 표준 스키마 + 가변 단위 + webhook push로 보고한다

[[concept-observability-contract]]의 공통 진행 이벤트 구체형을 확정한다.
이기종 파이프라인이 **같은 스키마**를 쓰되, granularity는 파이프라인별 **단위** 필드로 가변 처리한다.

## 세 가지

- **표준 스키마** — 모든 진행 이벤트가 공통 필드를 갖는다: `파이프라인 id` · `단계(stage)` · `진척(N/M)` · `타임스탬프` · `상태(running|done|failed)`.
- **가변 단위(unit)** — granularity 강제 통일(모두 %로) 대신, N/M의 **M이 뭔지**를 `unit` 필드로 전달(예: `테마` · `순회 화면` · `인덱싱 파일`). 각 파이프라인이 자기 단위를 그대로 보고, 지휘 계층이 표시 시 해석.
- **webhook push** — 단계 전이·진척 변화 시 이벤트를 webhook으로 push. 기존 완료 보고([[decision-control-data-plane-split]]) 채널과 합친다. poll은 보조.

## 근거

- 스키마 표준은 한 대시보드에서 이기종 파이프라인을 나란히 보게 한다 → [[decision-pipeline-observability]].
- 가변 단위는 "테마 3/4"와 "화면 12/30"을 억지로 %로 깎지 않는다 — 의미 손실 없이 원 단위를 살려 표시.
- webhook push는 단계 전이마다 즉시 전달 → 실시간 모니터링 요구([[decision-pipeline-observability]]) 충족. poll은 클라이언트 폴백.

## 기각 대안

- **granularity % 정규화 통일** — 단순하지만 테마/화면/파일 등 단위의 의미가 손실. "70%인데 뭘 하는 중?"이 된다.
- **poll 전용** — 단순하지만 실시간성이 떨어져 진행 모니터링 목적에 안 맞는다.

이 결정이 [[question-progress-event-contract]]을 답하고 [[concept-observability-contract]]를 실체화한다.

## 갱신 (2026-07-06) — 에이전트 스텝 계층 확장

엔진의 자체 에이전트 전환([[decision-engine-api-agent]])에 따라, 이 계약의 granularity가
한 단계 아래로 확장됐다 — `파이프라인 실행 > 단계 > 엔진 호출 > 에이전트 스텝(사고 요약·
도구 호출·토큰)` 4단 계층. 스키마·webhook push 채널은 그대로 쓴다 → [[decision-agent-step-observability]].
