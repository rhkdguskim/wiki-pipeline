---
type: decision
title: 엔진 오케스트레이션 = LangGraph (자체 루프 → 프레임워크, 프레임워크 계층 명문화)
tags: [engine, orchestration, langgraph, framework, phase-1]
status: active
---

# 결정: 엔진 오케스트레이션을 LangGraph 프레임워크로 간다

두 파이프라인(정적·매뉴얼 추출)의 판단 루프를, [[decision-engine-api-agent]]가 함의했던
**직접 구현 Messages API 루프**에서 **LangGraph 오케스트레이션**으로 전환한다. 이로써 위키에
없던 **"엔진 오케스트레이션 프레임워크 계층"**(자체 루프 vs 프레임워크) 결정을 명문화한다 —
이 계층은 그동안 대응하는 결정도 open question도 없던 갭이었다(소스 결정 3).
[[decision-engine-hybrid]]의 **엔진 인터페이스 계약은 그대로 유효**하다 → 인터페이스 뒤
구현체 교체 패턴이므로 supersede가 아니라 구현체 갱신이다.

## 무엇을

- **판단 루프 = LangGraph 그래프** — 두 파이프라인의 에이전트 루프를 러너가 직접 손으로 짠
  Messages API while-루프가 아니라 LangGraph 그래프(노드·엣지·상태)로 구성한다. 러너가
  소유하던 "도구 실행→결과 회신 반복"을 프레임워크가 맡는다.
- **엔진 인터페이스 계약 불변** — 입력(요구사항서+diff+테마+코드)/출력(frontmatter 포함 .md +
  검증 결과) 계약은 [[decision-engine-hybrid]] 그대로. 그 인터페이스 뒤의 구현체만
  자체 루프 → LangGraph로 교체된다. 러너↔엔진 경계·Control/Data Plane 계약
  ([[decision-control-data-plane-split]])은 손대지 않는다.
- **관측 = get_stream_writer 커스텀 이벤트** — LangGraph 노드 안에서 `get_stream_writer()`로
  커스텀 key-value 이벤트를 방출하고 `stream_mode="custom"`으로 수신해,
  [[decision-observability-event-contract]]의 표준 스키마로 직접 매핑한다(어댑터가 얇다).
  사고 요약·도구 호출·토큰의 에이전트 스텝 계층([[decision-agent-step-observability]])을
  프레임워크 이벤트로 그대로 채운다.
- **durable execution·체크포인팅** — 매뉴얼 파이프라인의 긴 UI 전수 순회
  ([[decision-hybrid-app-traversal]])는 중단·재개가 잦다. LangGraph의 durable execution과
  체크포인팅이 순회 세션의 중단 지점 재개를 프레임워크 차원에서 받쳐준다.
- **공급자 중립을 프레임워크가 자연 수용** — LangGraph의 `init_chat_model(...)`/`ChatAnthropic`
  또는 base URL·키 교체로 임의 공급자를 붙일 수 있어, 모델 공급자 중립 설계
  ([[decision-model-provider-neutral-minimax]])와 정합한다.

## 근거

- **공급자 중립** — LangGraph는 공급자에 묶이지 않는다. `init_chat_model("claude-...")` /
  `ChatAnthropic` + `ANTHROPIC_API_KEY`, 또는 base URL·키만 갈아끼워 임의 공급자를 수용한다.
  자체 루프도 중립일 수 있으나 재시도·스트리밍·상태 관리를 전부 손으로 유지해야 한다.
- **커스텀 관측이 1급** — `get_stream_writer()` 커스텀 이벤트가 우리 이벤트 계약으로 곧장
  매핑돼, 자체 관측·단일 대시보드 요구([[decision-pipeline-observability]])를 얇은 어댑터로
  충족한다.
- **durable 체크포인팅** — 매뉴얼 긴 순회의 중단 재개가 프레임워크 기능으로 해결된다.
- **프로덕션 실적** — 2026 기준 스테이트풀 에이전트의 표준으로 자리 잡아, 러너가 루프를
  직접 유지하며 지는 부담을 덜어낸다.
- 근거 실측: LangChain OSS LangGraph 문서(quickstart · workflows-agents · streaming).

## 기각 대안

- **OpenAI Agents SDK** — 탈락. ① Claude·비-OpenAI 모델은 LiteLLM(`LitellmModel`) 우회가
  필수라 1급 경로가 아니다. ② 트레이싱 기본 익스포터 `BackendSpanExporter`가
  `https://api.openai.com/v1/traces/ingest`로 하드코딩돼 `OPENAI_API_KEY`를 요구한다 —
  비-OpenAI 모델을 트레이싱하려 해도 별도 OpenAI 키로 OpenAI 클라우드에 전송해야 하므로
  자체 관측·단일 키([[decision-engine-api-key-auth]]) 결정과 정면 충돌한다. 근거: OpenAI
  Agents Python 문서(tracing · litellm_model), `BackendSpanExporter` 클래스 정의.
- **Claude Agent SDK** — 비채택(단 정합적). 위키의 자체 루프 결정과 가장 잘 맞고 기존
  Claude Code 스킬 4 + 에이전트 2([[entity-docu-automatic]]) 자산 이식 마찰이 최소이며,
  트레이싱도 OpenTelemetry(OTLP) 기반으로 자체 collector 방출까지 된다(업계 표준). 그러나
  **Anthropic 모델 전제 하네스**라 PoC 공급자 MiniMax M3(비-Anthropic)와 근본적으로
  안 맞는다. M3를 Anthropic-호환 엔드포인트로 억지 연결하면 이 SDK를 쓰는 이유 자체가
  약해진다. **향후 Anthropic 모델로 회귀하면 재고할 여지**를 남긴다. 근거: Claude Code
  Observability(OpenTelemetry) 문서, `opentelemetry/openinference-instrumentation-claude-agent-sdk`.
- **자체 Messages API 루프 유지** — 공급자 중립·관측·재시도·durable 재개를 전부 손으로
  유지해야 한다. 프레임워크가 주는 것을 재발명하는 비용이 크다.

## 열린 항목

- 기존 스킬·에이전트 프롬프트를 LangGraph 노드/도구 세트로 이식·재튜닝하는 품질 검증
  (Phase 1 PoC). [[decision-engine-api-agent]]가 남긴 이식 항목을 계승한다.
- PoC 실측 비용은 [[question-cost-estimation]]에서 LangGraph + M3 조합으로 측정 예정.

소스: [[2026-07-07-engine-framework-langgraph-minimax]] · 요약: [[summary-engine-framework-langgraph-minimax]]
관련: [[decision-engine-api-agent]] · [[decision-engine-hybrid]] · [[decision-model-provider-neutral-minimax]] · [[decision-agent-step-observability]] · [[decision-observability-event-contract]]
