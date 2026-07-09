---
type: decision
title: 모델 공급자 = 중립 설계, PoC는 MiniMax M3 (Anthropic 확정 → 공급자 중립 전환)
tags: [engine, model-provider, minimax, neutral, poc, phase-1]
status: active
---

# 결정: 모델 공급자는 중립으로 설계하고, PoC 모델은 MiniMax M3로 간다

엔진의 모델 공급자를 [[decision-engine-api-key-auth]]가 확정했던 **Anthropic 단일 공급자**에서
**공급자 중립 설계**로 전환한다. PoC 실측 모델은 사용자가 보유한 **MiniMax M3**로 간다.
API 키 인증 결정([[decision-engine-api-key-auth]])의 등록 UI·401 감지→admin 이메일 골격은
그대로이고 **대상 키만 공급자별**로 바뀌므로, 이 역시 supersede가 아니라 구현체·공급자 차원의
갱신이다.

## 무엇을

- **공급자 중립 설계** — 공급자를 `base URL` · `키` · `모델명` 세 값의 교체로 갈아끼운다.
  엔진 오케스트레이션([[decision-engine-orchestration-langgraph]])의 LangGraph가 이를 자연
  수용한다(`init_chat_model`/`ChatAnthropic` 또는 base URL·키 교체).
- **PoC 모델 = MiniMax M3** — 1M 컨텍스트, 에이전틱 추론·tool use·코딩 지향. 사용자 보유.
  OpenAI-호환(`https://api.minimax.io/v1`)과 Anthropic-호환
  (`https://api.minimax.io/anthropic`) 엔드포인트를 **둘 다** 제공해 LangGraph에 base URL·키
  교체로 자연스럽게 붙고, LiteLLM 경로도 M3를 지원한다.
- **인증 = 공급자별 API 키 등록** — [[decision-engine-api-key-auth]]의 대시보드 등록 UI·
  러너 환경변수 주입·401 감지→admin 이메일([[decision-email-alerting]]의 인증 해지 케이스)
  골격을 계승하되, 저장·주입 대상 키만 공급자별로 둔다. 저장 보안은
  [[question-secret-storage-security]]의 운영 과제로 계속 이어진다.
- **프로덕션 공급자는 PoC 후 최종 확정** — PoC의 품질·비용 실측 결과로 확정한다. 중립
  설계이므로 나중에 Claude로 되돌리거나 여러 공급자를 병용할 수 있다.

## 근거

- **잠금 회피 + 옵션 가치** — 공급자를 세 값 교체로 다루면 특정 공급자에 코드가 묶이지 않아,
  품질·비용·가용성에 따라 공급자를 바꿀 여지가 유지된다.
- **PoC 즉시 착수** — 사용자가 M3를 보유하고 있어 별도 조달 없이 바로 실측에 들어갈 수 있다.
  M3의 양쪽(OpenAI·Anthropic) 호환 엔드포인트가 LangGraph·LiteLLM 어느 경로로도 붙는다.
- **1M 컨텍스트·에이전틱** — 코드베이스·긴 순회 관측을 다루는 두 파이프라인의 입력 특성에
  1M 컨텍스트와 tool use·에이전틱 추론이 맞는다.
- **비용 실측 수단 유지** — 호출 단위 usage 토큰 집계 축([[question-cost-estimation]])은
  공급자가 바뀌어도 종량제 키 기반으로 그대로 성립한다.
- 근거 실측: MiniMax API 문서(Anthropic SDK) · M3 API 셋업 가이드 · LiteLLM MiniMax provider.

## 기각 대안

- **Anthropic 단일 공급자 확정 유지** — [[decision-engine-api-key-auth]]가 택했던 안.
  단일 공급자는 잠금 위험이 있고, 사용자가 보유한 M3로 즉시 PoC할 유연성을 잃는다.
  중립 설계는 나중에 Anthropic으로 되돌리는 것도 포함하므로 이를 배제하지 않는다.
- **공급자 하드코딩(중립 계약 없음)** — 공급자 교체 시 엔진 코드를 뜯어야 한다. base URL·
  키·모델명 계약층을 두면 교체가 설정 변경으로 끝난다.

## 열린 항목

- 프로덕션 공급자 최종 확정 — PoC 품질·비용 실측 후. 향후 Anthropic 회귀 시 엔진 오케스트레이션도
  Claude Agent SDK를 재고할 여지가 있다([[decision-engine-orchestration-langgraph]] 기각 대안).

소스: [[2026-07-07-engine-framework-langgraph-minimax]] · 요약: [[summary-engine-framework-langgraph-minimax]]
관련: [[decision-engine-api-key-auth]] · [[decision-engine-orchestration-langgraph]] · [[decision-email-alerting]] · [[question-cost-estimation]] · [[question-secret-storage-security]]
