# 2026-07-07 엔진 프레임워크·모델 공급자 결정 세션 (LangGraph + MiniMax M3)

wiki-query로 "docu-automation·manual-automation 2개를 LangGraph vs OpenAI Agents SDK 중
무엇으로 개발할까"를 질의. 위키 엔진 결정을 근거로 확보하고 두 프레임워크를 최신 문서로 실측한 뒤,
사용자가 LangGraph 전환 + MiniMax M3 PoC를 선택. 3개 결정 확정.

## 배경 — 위키가 이미 확정했던 것 (전환 전)
- decision-engine-api-agent: 생성 엔진 = Anthropic Messages API + tool use 자체 루프 (러너가 루프 소유).
- decision-engine-api-key-auth: 엔진 인증 = Anthropic API 키 등록.
- decision-agent-step-observability: 사고·도구 호출·토큰을 4단 계층 진행 이벤트로 대시보드/이력 DB에 방출.
- decision-engine-hybrid: 엔진 인터페이스(입력=요구사항서+diff+테마+코드 / 출력=frontmatter .md+검증)를 계약으로 두고 구현체는 교체 가능.

## 실측 요약 (최신 문서, 2026-07)

### OpenAI Agents SDK — 탈락
- Claude/비-OpenAI 모델은 LiteLLM(LitellmModel) 우회가 필수 — 1급 경로 아님.
- 트레이싱 기본 익스포터 BackendSpanExporter가 https://api.openai.com/v1/traces/ingest 로 하드코딩, OPENAI_API_KEY 요구. 비-OpenAI 모델도 트레이싱하려면 별도 OpenAI 키로 OpenAI 클라우드에 전송. → 자체 관측·단일 키 결정과 정면 충돌.
- 근거: OpenAI Agents Python 문서(tracing, litellm_model), BackendSpanExporter 클래스 정의.

### LangGraph — 선택
- 공급자 중립. init_chat_model("claude-...") / ChatAnthropic + ANTHROPIC_API_KEY, 또는 base URL·키 교체로 임의 공급자.
- get_stream_writer()로 노드 안에서 커스텀 key-value 이벤트 방출, stream_mode="custom"으로 수신 → decision-observability-event-contract 스키마로 직접 매핑 가능(어댑터 얇음).
- durable execution·체크포인팅 → 매뉴얼 파이프라인 긴 UI 순회의 중단 재개에 유리.
- 프로덕션 실적 다수(2026 기준 스테이트풀 에이전트 표준).
- 근거: LangChain OSS LangGraph 문서(quickstart, workflows-agents, streaming).

### Claude Agent SDK — 제3 선택지 (이번엔 비채택)
- pip install claude-agent-sdk. Claude Code를 움직이는 도구·에이전트 루프·컨텍스트 관리를 프로그래밍. 스트리밍·tool use·extended thinking·MCP 클라이언트·비용 추적 내장.
- 위키 자체 루프 결정과 가장 정합했고, 기존 Claude Code 스킬4+에이전트2 자산 이식 마찰이 최소.
- tracing: OpenTelemetry(OTLP) 기반 — 모델 요청·도구 실행마다 span, 토큰·비용 metric, 프롬프트·도구결과 log를 OTLP 백엔드(자체 collector 포함)로 방출. Python 계측 패키지 존재(query()/ClaudeSDKClient 몽키패치, PreToolUse/PostToolUse 훅). 즉 tracing 됨 — 오히려 업계 표준.
- 비채택 이유: Anthropic 모델 전제 하네스라 MiniMax M3(비-Anthropic)와 근본적으로 안 맞음. M3 Anthropic-호환 엔드포인트로 억지 연결은 SDK를 쓰는 이유 자체를 약화.
- 근거: Claude Code Observability(OpenTelemetry) 문서, opentelemetry/openinference-instrumentation-claude-agent-sdk.

### MiniMax M3 — PoC 모델
- OpenAI-호환(https://api.minimax.io/v1) + Anthropic-호환(https://api.minimax.io/anthropic) 양쪽 엔드포인트 제공. 1M 컨텍스트, 에이전틱 추론·tool use·코딩 지향.
- LangGraph에 base URL·키 교체로 자연스럽게 연결. LiteLLM도 M3 지원.
- 근거: MiniMax API 문서(Anthropic SDK), M3 API 셋업 가이드, LiteLLM MiniMax provider.

## 확정 결정 3건

### 결정 1 — 엔진 오케스트레이션 = LangGraph (자체 루프 → 프레임워크)
decision-engine-api-agent가 함의한 "직접 구현 루프"를 LangGraph 오케스트레이션으로 전환.
- 두 파이프라인(정적·매뉴얼)의 판단 루프를 LangGraph 그래프로 구성.
- 관측은 get_stream_writer 커스텀 이벤트 → decision-observability-event-contract 스키마로 방출(어댑터).
- 매뉴얼 긴 순회는 LangGraph durable execution·체크포인팅 활용.
- decision-engine-hybrid의 엔진 인터페이스 계약(입력/출력)은 그대로 유지 — 인터페이스 뒤 구현체 교체 패턴 안. 따라서 supersede가 아니라 구현체 갱신.
- OpenAI Agents SDK는 트레이싱 OpenAI 백엔드 강제·모델 우회로 탈락. Claude Agent SDK는 정합적이나 M3와 안 맞아 비채택(향후 Anthropic 회귀 시 재고 여지).

### 결정 2 — 모델 공급자 = 중립 설계, PoC는 MiniMax M3 (Anthropic 확정 → 중립 전환)
decision-engine-api-key-auth의 "Anthropic API 키 확정"을 공급자 중립으로 전환.
- 공급자를 base URL·키·모델명으로 갈아끼우는 중립 설계. LangGraph가 이를 자연 수용.
- PoC 모델 = MiniMax M3(1M 컨텍스트·에이전틱·tool use). 사용자 보유.
- 인증 = 공급자별 API 키 등록(대시보드 등록 UI·401 감지→admin 이메일 골격은 유지, 대상 키만 공급자별로). decision-email-alerting의 인증 해지 케이스 계승.
- 나중에 Claude로 되돌리거나 병용 가능(중립이므로). 프로덕션 공급자 최종 확정은 PoC 품질·비용 실측 후.

### 결정 3 — 프레임워크 계층 결정을 위키에 명문화 (기존 갭 해소)
위키에 "엔진 오케스트레이션 프레임워크 계층"(자체 루프 vs 프레임워크) 결정이 없던 갭을, LangGraph 채택으로 명문화. 3자 비교(OpenAI SDK 탈락·LangGraph 채택·Claude Agent SDK 비채택) 근거를 남긴다.

## 반영 방침 (사용자 선택)
- PoC 전제 결정으로 반영. decision-engine-api-agent·decision-engine-api-key-auth는 완전 supersede가 아니라 "구현체=LangGraph·공급자 중립·PoC 단계"로 갱신(인터페이스 계약 유지).
- 모델 공급자는 M3로 전환하되 공급자 중립 설계.
