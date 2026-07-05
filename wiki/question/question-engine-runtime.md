---
type: question
title: 생성 엔진 런타임 — Claude Code 재사용 vs 자체 에이전트 구축
tags: [engine, claude-code, agents, abstraction, phase-1]
status: answered
---

# ❓ 생성 엔진을 Claude Code로 계속 호출할까, 자체 에이전트로 만들까?

기존 생성 엔진([[entity-docu-automatic]])은 scout / docu-writer / critic이 **Claude Code CLI 위에서** 동작한다(스킬 4 + 에이전트 2, 완료 자산). wiki-pipeline은 이를 `claude -p` headless로 호출할 계획이다. 그런데 이를 재사용하는 대신 **우리 코드가 LLM API를 직접 호출하는 자체 에이전트**를 만들 수 있는가, 만든다면 언제인가?

## 선택지 3갈래

| | 무엇 | 재사용 자산 | Claude Code 의존 |
|---|---|---|---|
| **A. 현행 유지** | `claude -p` headless로 기존 스킬·에이전트 그대로 | 6개 산출물 전부 | 강함 |
| **B. 자체 에이전트** | 로직을 우리 코드가 LLM API 직접 호출 | 프롬프트·요구사항 로직만 이식 | 없음 |
| **C. 하이브리드** | 오케스트레이션(테마 루프·재시도·상태·sha)은 우리가, 리프 실행만 위임 | 대부분 + 제어권 | 부분 |

## 핵심 통찰 — 이미 정의된 패턴의 반복

이건 새 문제가 아니라 이 프로젝트가 이미 축복한 추상화의 재적용이다.

- 엔진은 Data Plane 부품이고 Control Plane과는 ①트리거/④완료보고 계약으로만 대화한다 → [[decision-control-data-plane-split]]. 엔진이 `claude -p`든 자체 에이전트든 **상위 계약을 건드리지 않는 Data Plane 내부 구현**이다.
- SCM을 커넥터 인터페이스 뒤로 숨긴 것과 똑같이 → [[decision-scm-connector-abstraction]], **`엔진 인터페이스`**(입력: 요구사항서+diff+테마+코드 / 출력: frontmatter 포함 .md + 검증 결과)를 정의하면 A·B는 그 뒤의 두 구현체가 된다.

## 자체 에이전트(B)의 득실

- **얻음**: Claude Code 가용성·인증·라이선스 의존 제거([[question-headless-claude-auth]]·[[question-runner-ai-network]] 우회) · 오케스트레이션 완전 제어(v4 1단계 평탄화는 Claude Code의 "서브에이전트가 서브에이전트 불가" 제약 탓 → [[2026-07-05-docu-automatic-notes]]) · 비용·관측성·모델 직접 통제 · 서비스화 시 단일 균질 엔진([[decision-control-data-plane-split]]의 LLM Wiki 통합 동기와 정합)
- **치름**: 에이전트 루프·tool use·컨텍스트 관리·Full Reset 격리를 직접 재구현 · 완료 자산 6개([[entity-docu-automatic]])의 매몰 가치와 프롬프트 재튜닝 · 유지보수 이관

## 현재 권고 (미확정)

1. **[[question-headless-claude-auth]] 검증 먼저** — 어차피 Phase 1 최우선 블로커. 싼 길(A)이 열리는지 확인.
2. **결과 무관하게 `엔진 인터페이스`를 지금 정의** — 러너↔엔진 경계를 `claude -p` 하드코딩이 아닌 계약으로. 비용 낮고 옵션 가치 큼(SCM 커넥터와 동형).
3. **자체 에이전트(B)는 driver 발생 시** 그 인터페이스 뒤에 삽입: headless 인증 막힘 / Claude Code 제약(중첩·병렬) 탈출 필요 / 비용 통제 이슈 / LLM Wiki 서비스화가 균질 엔진 요구.

→ "B로 갈아탄다"가 아니라 **"인터페이스 + 당분간 A, 필요 시 B"** (사실상 C의 사고방식). 결정되면 decision 페이지 신설 + 본 question `answered` 전환.

## ✅ 답 (2026-07-05)

**하이브리드**로 확정 → [[decision-engine-hybrid]]. 엔진 인터페이스를 지금 정의하고, 당분간 `claude -p` headless(A), driver 발생 시 자체 에이전트(B)로 교체. headless 검증([[question-headless-claude-auth]])이 A의 첫 관문.

관련: [[question-headless-claude-auth]] · [[decision-control-data-plane-split]] · [[decision-scm-connector-abstraction]] · [[entity-docu-automatic]] · [[overview]]
