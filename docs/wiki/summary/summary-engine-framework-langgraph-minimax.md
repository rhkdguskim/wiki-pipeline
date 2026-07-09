---
type: summary
title: 엔진 프레임워크 LangGraph 전환 + MiniMax M3 PoC 요약
tags: [engine, orchestration, langgraph, model-provider, minimax, phase-1]
status: active
---

# 요약: 엔진 오케스트레이션 = LangGraph · 모델 공급자 = 중립(PoC MiniMax M3)

wiki-query로 "docu-automation·manual-automation 두 파이프라인을 LangGraph vs OpenAI Agents
SDK 중 무엇으로 개발할까"를 질의한 세션. 위키 엔진 결정을 근거로 확보하고 두 프레임워크(+
제3 선택지 Claude Agent SDK)를 최신 문서로 실측한 뒤, 사용자가 **LangGraph 전환 + MiniMax M3
PoC**를 선택했다. 소스: [[2026-07-07-engine-framework-langgraph-minimax]].

## 전환 전 위키가 확정했던 것

- [[decision-engine-api-agent]] — 생성 엔진 = Anthropic Messages API + tool use **자체 루프**(러너가 루프 소유).
- [[decision-engine-api-key-auth]] — 엔진 인증 = **Anthropic API 키** 등록.
- [[decision-agent-step-observability]] — 사고·도구 호출·토큰을 4단 계층 진행 이벤트로 방출.
- [[decision-engine-hybrid]] — 엔진 인터페이스(입력/출력)를 계약으로, 구현체는 교체 가능.

## 요지 — 무엇이 바뀌었나

- **구현체 교체(supersede 아님)** — [[decision-engine-hybrid]]의 엔진 인터페이스 계약이
  살아 있으므로, 자체 루프 → LangGraph, Anthropic 고정 → 공급자 중립은 **인터페이스 뒤
  구현체·공급자 차원의 이동**이다. [[decision-engine-api-agent]]·[[decision-engine-api-key-auth]]는
  status active를 유지하고 갱신 절만 달렸다.
- **프레임워크 계층 갭 해소** — 위키에 "엔진 오케스트레이션 프레임워크 계층"(자체 루프 vs
  프레임워크) 결정도, 대응하는 open question도 **없던 갭**이었다. LangGraph 채택
  ([[decision-engine-orchestration-langgraph]])이 이 갭을 새 질문을 만들지 않고 직접 메운다.

## 파생 결정

- [[decision-engine-orchestration-langgraph]] — 엔진 오케스트레이션 = LangGraph. 공급자
  중립·get_stream_writer 커스텀 관측·durable 체크포인팅이 근거. OpenAI SDK 탈락·Claude
  Agent SDK 비채택 3자 비교 포함.
- [[decision-model-provider-neutral-minimax]] — 모델 공급자 = 중립 설계, PoC = MiniMax M3.
  base URL·키·모델명 교체 · 공급자별 키 인증 · 프로덕션 공급자는 PoC 후 확정.

## 3자 프레임워크 비교 (실측, 2026-07)

| 프레임워크 | 공급자 중립 | 트레이싱/관측 | 판정 | 핵심 이유 |
|-----------|:---:|---|:---:|---|
| **LangGraph** | ✅ 1급 (`init_chat_model`/`ChatAnthropic`·base URL 교체) | `get_stream_writer()` 커스텀 이벤트 → `stream_mode="custom"` 수신, 이벤트 계약에 얇게 매핑. durable execution·체크포인팅 | **채택** | 공급자 중립 + 커스텀 관측 1급 + durable 재개 + 2026 스테이트풀 표준 |
| OpenAI Agents SDK | ⚠️ LiteLLM(`LitellmModel`) 우회 필수, 1급 아님 | 기본 익스포터 `BackendSpanExporter`가 `api.openai.com/v1/traces/ingest` 하드코딩·`OPENAI_API_KEY` 요구 → 비-OpenAI도 OpenAI 클라우드 전송 | 탈락 | 자체 관측·단일 키 결정과 정면 충돌 |
| Claude Agent SDK | ❌ Anthropic 모델 전제 하네스 | OpenTelemetry(OTLP) 기반 span·metric·log, 자체 collector 방출 가능(업계 표준) | 비채택 | 자체 루프 결정·기존 Claude Code 자산과 최정합이나 M3(비-Anthropic)와 불일치. **Anthropic 회귀 시 재고 여지** |

## PoC 모델 — MiniMax M3

- OpenAI-호환(`https://api.minimax.io/v1`) + Anthropic-호환(`https://api.minimax.io/anthropic`)
  **양쪽 엔드포인트** 제공. 1M 컨텍스트, 에이전틱 추론·tool use·코딩 지향. 사용자 보유.
- LangGraph에 base URL·키 교체로 자연 연결. LiteLLM도 M3 지원.

## 실측 출처

- LangGraph: LangChain OSS LangGraph 문서(quickstart · workflows-agents · streaming).
- OpenAI Agents SDK: OpenAI Agents Python 문서(tracing · litellm_model), `BackendSpanExporter` 클래스 정의.
- Claude Agent SDK: Claude Code Observability(OpenTelemetry) 문서, `opentelemetry/openinference-instrumentation-claude-agent-sdk`.
- MiniMax M3: MiniMax API 문서(Anthropic SDK) · M3 API 셋업 가이드 · LiteLLM MiniMax provider.

## 파급

- overview "지금 어디까지 왔나" Phase 1 엔진 항목이 LangGraph·공급자 중립·PoC M3로 갱신됨.
- [[question-cost-estimation]] PoC 실측 조합이 LangGraph + M3로 구체화됨.
- [[decision-observability-event-contract]]의 이벤트 계약은 불변 — LangGraph 커스텀 이벤트가 그 스키마를 채운다.
