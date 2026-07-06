---
type: decision
title: 생성 엔진 = API 자체 에이전트 (Messages API + tool use, Data Plane 내 루프)
tags: [engine, agents, api, architecture, phase-1]
status: active
---

# 결정: 생성 엔진을 Anthropic API 자체 에이전트로 전환한다

두 파이프라인(정적·매뉴얼 추출)의 생성 엔진을 `claude -p` headless 재사용(A)이 아닌
**Anthropic Messages API + tool use로 직접 구현한 자체 에이전트 루프(B)**로 간다.
[[decision-engine-hybrid]]가 예고한 B 전환 driver 1번("headless 인증 막힘")이
무인 지속 불가 확정([[question-headless-claude-auth]])으로 발동된 결과다.

## 무엇을

- **자체 에이전트 루프** — 러너 코드가 Messages API를 직접 호출하고, 도구 실행→결과
  회신을 반복하는 루프를 소유한다. 루프는 기존 **Data Plane(CI 러너) 안**에서 돈다 —
  Control Plane과의 ①트리거/④완료보고 계약([[decision-control-data-plane-split]])은 불변.
- **엔진 인터페이스 유지** — 입력(요구사항서+diff+테마+코드)/출력(frontmatter 포함 .md +
  검증 결과) 계약은 [[decision-engine-hybrid]] 그대로. 뒤의 구현체만 A→B 교체.
- **공통 런타임 + 파이프라인별 도구 세트** — SDK 클라이언트·루프·스트리밍 수신·관측
  이벤트 방출([[decision-agent-step-observability]])·토큰 집계·재시도는 두 파이프라인이
  공유하는 단일 모듈. 파이프라인별로는 도구 세트와 시스템 프롬프트만 교체한다:
  - ① 정적: 읽기 전용 코드 탐색 도구(read_file·grep·diff 조회) + structured output으로
    frontmatter 스키마 강제
  - ② 매뉴얼: 세션 MCP([[entity-remote-control-mcp]]) 도구를 API tool로 변환 + 스크린샷
    vision 입력 ([[concept-observation-grounding]] 정합)
- **루프 단위 = 기존 엔진 호출 단위** — 정적은 테마당 1루프, 매뉴얼은 순회 세션당 1루프.
  compare·테마 매핑·MR 제출·sha 전진 같은 결정적 오케스트레이션은 러너의 일반 코드로
  유지한다 (판단이 필요한 부분만 에이전트).
- **기존 자산 이식** — Claude Code 스킬 4 + 에이전트 2([[entity-docu-automatic]])의 내용물을
  시스템 프롬프트·도구 설명으로 이관. 하이브리드 결정이 예고한 재튜닝 비용을 치르는 대신
  "서브에이전트 중첩 불가" 제약(v4 평탄화의 원인)에서 벗어난다.

## 근거

- **driver 발동** — headless 로그인 무인 지속 불가 확정(2026-07-06)으로 A의 첫 관문이
  닫혔다. [[decision-engine-hybrid]]가 이 상황을 B 전환 조건으로 미리 못박아 두었다.
- **관측성 요구와 정합** — `claude -p`는 블랙박스지만 자체 루프는 사고 요약·도구 호출·토큰
  사용이 전부 손에 들어와, "에이전트의 사고·동작·진행을 대시보드에 전부 출력" 요구
  ([[decision-agent-step-observability]])를 구조적으로 충족한다.
- **인증 블로커 소멸** — API 키 방식([[decision-engine-api-key-auth]])은 만료·재로그인이
  없어 무인 운영 문제가 사라진다.
- **비용·모델 직접 통제** — 호출 단위 usage 토큰이 응답에 포함되어 실행당 비용 집계가
  가능 → [[question-cost-estimation]]의 실측 수단.

## 기각 대안

- **Anthropic Managed Agents (호스팅형 에이전트)** — 소스가 사내 GitLab([[entity-mirero-gitlab]])에
  있고, 매뉴얼 파이프라인은 사내 UI 테스트 호스트를 세션 MCP로 제어해야 한다. Anthropic
  클라우드 컨테이너는 사내망에 닿지 못하고, 소스를 외부 컨테이너에 올리는 부담도 있다.
- **`claude -p` headless 유지(A)** — 무인 지속 불가가 확정되어 만료 감지·수동 재로그인
  운영을 계속 짊어져야 한다. 야간 무인 배치라는 실행 형태와 근본적으로 상충.
- **파이프라인 전체를 하나의 거대 에이전트로** — 비용·관측성·재시도 격리 모두에서 불리.
  결정적 오케스트레이션까지 LLM에 맡길 이유가 없다.

## 열린 항목

- 기존 스킬·에이전트 프롬프트의 이식·재튜닝 품질 검증 (Phase 1 PoC).
- 단발 생성 스텝의 Batch API(50% 할인) 활용은 후순위 최적화로 보류.

소스: [[2026-07-06-engine-api-agent-architecture]] · 요약: [[summary-engine-api-agent-architecture]]
