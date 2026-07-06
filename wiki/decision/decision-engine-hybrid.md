---
type: decision
title: 생성 엔진 = 하이브리드 (엔진 인터페이스 + 점진적 교체)
tags: [engine, claude-code, agents, abstraction, phase-1]
status: active
---

# 결정: 엔진 인터페이스를 지금 정의하고, 당분간 claude -p, 필요 시 자체 에이전트로 교체

생성 엔진([[entity-docu-automatic]])의 런타임을 **하이브리드**로 간다 — `claude -p` headless 재사용(A)과
자체 에이전트(B) 중 어느 한 쪽을 지금 고르는 대신, **엔진 인터페이스**를 먼저 정의하고 그 뒤의 구현체는
상황에 따라 바꾼다.

## 세 가지

- **엔진 인터페이스**를 지금 정의한다 — 입력: 요구사항서 + diff + 테마 + 코드 / 출력: frontmatter 포함 .md + 검증 결과. 러너↔엔진 경계를 `claude -p` 하드코딩이 아닌 **계약**으로.
- **당분간 A(claude -p headless)** — 기존 스킬 4 + 에이전트 2 자산을 그대로 재사용. [[question-headless-claude-auth]] 검증이 전제.
- **driver 발생 시 B(자체 에이전트)로 교체** — headless 인증 막힘 / Claude Code 중첩·병렬 제약 / 비용 통제 / LLM Wiki 서비스화가 균질 엔진을 요구할 때. 인터페이스 뒤에 삽입.

## 근거

- 엔진은 Data Plane 부품이고 Control Plane과는 ①트리거/④완료보고 계약으로만 대화한다 → [[decision-control-data-plane-split]]. A든 B든 상위 계약을 건드리지 않는 Data Plane 내부 구현이다.
- SCM을 커넥터 인터페이스 뒤로 숨긴 것과 동형 → [[decision-scm-connector-abstraction]]. "인터페이스 + 당분간 A, 필요 시 B"는 옵션 가치가 크고 비용이 낮다.
- v4 1단계 평탄화는 Claude Code의 "서브에이전트가 서브에이전트 불가" 제약 탓 → [[2026-07-05-docu-automatic-notes]]. B 전환 시 이 제약에서 벗어난다.

## 기각 대안

- **지금 B(자체 에이전트)로 전행** — 매몰 자산 6개 재튜닝·에이전트 루프 재구현 비용이 즉시 발생. driver가 아직 없으므로 조기.
- **A 하드코딩 (인터페이스 없음)** — 교체 시 러너까지 뜯어고쳐야 한다. 계약층이 없으면 B 전환이 프로젝트가 된다.

이 결정이 [[question-engine-runtime]]을 답한다. headless 검증([[question-headless-claude-auth]])이 A의 첫 관문이다.

## 갱신 (2026-07-06) — driver 발동, B 전환 확정

**headless 인증 막힘(driver 1번)이 실제로 발동**했다 — headless 로그인의 무인 지속 불가가
확정되어([[question-headless-claude-auth]]), A(`claude -p`)를 거치지 않고 **B(자체 에이전트)로
전환을 확정**한다 → [[decision-engine-api-agent]]. 이 페이지의 핵심인 **엔진 인터페이스
계약은 그대로 유효**하며(그 인터페이스 뒤에 B가 삽입된 것), "당분간 A" 부분만 효력을 다했다.
소스: [[2026-07-06-engine-api-agent-architecture]]
