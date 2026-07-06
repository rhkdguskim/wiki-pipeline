---
type: decision
title: 에이전트 스텝 관측 — 사고·동작·진행을 대시보드에 실시간 출력
tags: [observability, agents, dashboard, contract]
status: active
---

# 결정: 에이전트의 사고·동작·진행을 진행 이벤트의 하위 계층으로 대시보드에 출력한다

자체 에이전트([[decision-engine-api-agent]])가 **무슨 생각을 하고, 무슨 동작을 하고,
어디까지 왔는지**를 대시보드에서 실시간으로 볼 수 있어야 한다(사용자 1급 요구).
기존 진행 이벤트 계약([[decision-observability-event-contract]])의 granularity를
한 단계 아래 — **에이전트 스텝** — 로 확장한다.

## 무엇을

- **이벤트 계층 4단** — `파이프라인 실행 > 단계(stage) > 엔진 호출(테마/순회 세션) >
  에이전트 스텝`. 상위 3단은 기존 계약 그대로, 에이전트 스텝이 신설 계층이다.
  대시보드는 접기/펼치기로 드릴다운한다.
- **스텝 이벤트의 내용** — 에이전트 루프의 스트리밍 출력에서 그대로 얻는다:

| 대시보드 표시 | 원천 |
|---|---|
| 지금 무슨 생각 중 | thinking 스트림 — **사고 요약**(adaptive + summarized display) |
| 지금 무슨 동작 중 | tool_use 이벤트 (도구명 + 입력: "diff 조회", "화면 캡처", "버튼 클릭") |
| 동작 결과 | tool_result (루프를 직접 소유하므로 전부 보유) |
| 진척도 | 상위 계층의 N/M(테마·순회 화면) + 루프 내 스텝 카운트 |
| 사용량 | 응답 usage(입출력·캐시 토큰) |

- **전달·저장** — 스텝 이벤트도 기존 webhook push 채널로 Control Plane에 보내고,
  **이력 DB에 스텝 로그로 적재**한다. 실시간 표시와 사후 감사 추적("이 문서가 왜 이렇게
  생성됐나")을 한 저장으로 해결한다. 토큰 usage 적재는 [[question-cost-estimation]]의
  실측 데이터가 된다.

## 근거

- [[decision-pipeline-observability]]가 실시간 진행을 1급 제약으로 요구하고,
  [[decision-observability-event-contract]]의 "가변 단위" 설계가 이미 계층 확장을
  수용한다 — 스텝은 새 스키마가 아니라 새 unit·계층일 뿐.
- 자체 에이전트 전환의 최대 부수 이득 — `claude -p`는 블랙박스였지만 API 루프는
  사고·도구 호출·토큰이 전부 러너 손에 들어온다. 관측을 위해 추가 비용이 거의 없다.
- 스텝 로그는 MR 리뷰 게이트([[decision-mr-review-gate]])에서 리뷰어가 생성 근거를
  추적하는 자료도 된다.

## 제약 · 유의

- **사고는 요약본이다** — API는 원문 사고 전체가 아닌 요약(summarized)을 제공한다.
  대시보드 요구사항에 "사고 = 요약 수준"임을 명시해 기대치를 맞춘다.
- 스텝 이벤트는 빈도가 높다 — webhook 부하가 문제 되면 스텝 계층만 batch/버퍼 전송으로
  완화한다(상위 계층은 즉시 push 유지).

## 기각 대안

- **엔진 호출 단위까지만 관측 (스텝 생략)** — "지금 무슨 생각/동작 중인지"라는 요구를
  충족하지 못한다. 긴 루프(UI 전수 순회)에서 무진행처럼 보이는 문제 재발.
- **스텝 로그를 러너 로컬 로그로만** — 사후 디버깅은 되지만 실시간 대시보드 요구 미충족,
  이력 DB SoT([[decision-db-source-of-truth]])와도 어긋난다.

소스: [[2026-07-06-engine-api-agent-architecture]] · 요약: [[summary-engine-api-agent-architecture]]
