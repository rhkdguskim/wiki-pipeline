# wiki-pipeline PoC

두 파이프라인(docu-automation·manual-automation)이 **어느 수준까지 실제로 도는지** 실측하는 PoC.
LangGraph + MiniMax M3(공급자 중립) 위에서, 얇은 공통 런타임을 두 파이프라인이 공유한다.

> 설계 근거: 위키 `wiki/decision/decision-engine-orchestration-langgraph.md`,
> `decision-model-provider-neutral-minimax.md`, `decision-agent-step-observability.md`.

## 구조

```
poc/
├── common/              # 저수준 공유 런타임 (파이프라인·문서 개념을 모른다)
│   ├── config.py        #   .env -> 타입있는 Settings
│   ├── llm.py           #   공급자 중립 LLM 팩토리 (base_url·key·model)
│   ├── events.py        #   관측 이벤트 스키마 + emit (4단 계층)
│   ├── observer.py      #   custom 스트림 -> 콘솔 + JSONL (+ 러너용 emitter)
│   ├── agent_spec.py    #   그래프 파라미터 (프롬프트+도구) + 기본 AgentState(messages)
│   ├── graph.py         #   파라미터화된 tool-use 루프 + 수렴 가드
│   ├── textproc.py      #   <think>·서문 제거, 혼재 텍스트 JSON 회수
│   ├── retry.py         #   지수 백오프 재시도
│   ├── mcp_bridge.py    #   MCP SSE 동기 브리지 (async 도구 -> 동기 래핑, 기록은 콜백 주입)
│   ├── docshub.py       #   docs-hub/product-common MR 계획·제출 게이트
│   └── run.py           #   run_graph·final_text + `--smoke`
├── common_pipeline/     # 파이프라인 공통 계층 (재사용 에이전트·오케스트레이션 패턴)
│   ├── run_context.py   #   러너 스캐폴드 (run_id·observer·run 이벤트·자원 정리)
│   ├── writer.py        #   writer 에이전트 실행 (수정모드 프롬프트 합성 + 1회 실행)
│   ├── verify.py        #   write->형식검증->lint->critic 재시도 루프 (경고태그 정책)
│   ├── parallel.py      #   에이전트 병렬 분배 (완료 순서 스트리밍)
│   ├── theme.py         #   테마 계약 (ThemeSpec·brief) — 레지스트리 데이터는 파이프라인 소유
│   └── output.py        #   생성 문서 저장 (strip_reasoning + .md)
├── dashboard/           # Agent View 대시보드 (React/Vite + API-only backend)
│   ├── serve.py         #   JSON API: run/events/source/docs-hub/product-common MR plan
│   ├── store.py         #   control-plane SQLite: sources, branches, docs targets
│   ├── dev_api_reload.py#   Python hot reload wrapper
│   └── src/             #   AI agent형 KPI/trace/source/product-common UI
├── static_pipeline/     # ① 정적 (코드 diff -> 기술문서) — 구현 완료
└── manual_pipeline/     # ② 매뉴얼 (앱 관측 -> 매뉴얼) — 구현 완료(실측 전)
    ├── observation.py   #   관측 로그 (JSONL 영속, 근거 블록/커버리지 재료 — 브리지 기록 콜백의 목적지)
    ├── scenarios.py     #   시나리오 세트 (결정적 뼈대 — PoC는 로컬 JSON)
    ├── traversal.py     #   하이브리드 순회: 시나리오 + 자율 탐색 (SqliteSaver 체크포인트)
    ├── themes.py        #   매뉴얼 테마 레지스트리 (독자 2축: user/operator)
    ├── prompts.py       #   explorer / writer / critic (관측 grounding)
    ├── generate.py      #   write->critic 재시도 (common_pipeline 어댑터)
    ├── lifecycle.py     #   add/update 판정 + DELETE 후보 deprecated 유예 표시
    ├── graph.py / runner.py / main.py
    └── scenarios/sample.json
```

계층 규칙: `common` ← `common_pipeline` ← 각 파이프라인 (역방향 의존 금지).
두 파이프라인은 같은 이름 계약을 쓴다 — `themes.py`(THEMES·DEFAULT_THEMES·get_theme·
theme_brief), `graph.py`(AgentSpec 빌더), `generate.py`(generate_with_critic),
`runner.py`(RunContext 골격). 파이프라인 고유 지식(프롬프트·도구·테마 데이터·근거
소스)은 콜러블/데이터로 주입한다.

## 설치

```bash
cd poc
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt   # Windows
cp .env.example .env       # 값 채움 (LLM_API_KEY·GITLAB_TOKEN 등)
```

## 실행

```bash
# 저장소 루트에서 (PYTHONUTF8=1 권장 — Windows 콘솔 UTF-8)
# L0 공통 런타임 스모크 (M3 왕복 + 이벤트 방출)
python -m poc.common.run --smoke

# ① 정적 파이프라인 (compare -> 테마별 문서 생성)
python -m poc.static_pipeline.main            # .env의 sha 사용
python -m poc.static_pipeline.main --from <sha> --to <sha>
# 산출: poc/out/{theme}.md + poc/out/events-*.jsonl

# 관측 대시보드 API (정적 서빙 없음 — JSON API만)
python -m poc.dashboard.serve                 # http://127.0.0.1:8420/api

# 프런트엔드 (별도 React/Vite 서버, /api는 8420으로 프록시)
cd poc/dashboard
npm install
npm run dev                                   # Vite URL에서 확인

# Python API hot reload
python -m poc.dashboard.dev_api_reload

# ② 매뉴얼 파이프라인 (MCP 관측 -> 독자 2축 매뉴얼)
python -m poc.manual_pipeline.main --smoke    # L1/L2: MCP 연결 + 도구 로드 + 관측 1회
python -m poc.manual_pipeline.main            # 시나리오 + 자율 탐색 -> user/operator 매뉴얼
python -m poc.manual_pipeline.main --no-explore --themes user-manual
python -m poc.manual_pipeline.main --resume manual-xxxxxxxx   # 체크포인트 중단 재개 (L4)
# 산출: poc/out/manual/{theme}.md + observations-*.jsonl + coverage-*.json + shots/
```

## 성공 기준 (도달 계층)

| 계층 | 정적 | 매뉴얼 |
|------|------|--------|
| L0 런타임 | M3 실호출 + 이벤트 JSONL | (동일) |
| L1 연결 | GitLab compare가 new_path 반환 | MCP SSE 연결 + 도구 로드 |
| L2 판단 | 에이전트가 read_file 실호출 후 초안 | 세션 생성 + screenshot 관측 |
| L3 완주 | 전 테마 frontmatter .md 생성 | 관측 근거로 manual.md |
| L4 관측 | 4단 이벤트 + usage 토큰 실측 | + 체크포인트 중단 재개 |

## 실측 결과 (2026-07-07, ros-sw-rcs 947)

**정적 파이프라인 — L4까지 전부 통과.**
compare `899f3d9d..8e5eddb6`(TcpServer accept 예외처리 FIX, 13파일 → 소스 7개) →
테마 3개(intro·architecture-overview·component-diagram) 생성.
- M3가 read_file/list_dir로 실제 코드 탐색 후 수렴, 관측 사실만 근거로 서술("코드에서 확인되지 않음" 정직 표시).
- component-diagram은 실제 mermaid 다이어그램 생성. frontmatter·`<think>` 제거 정상.
- 4단 관측 이벤트 + 토큰 usage(테마당 in 수천~2만·out 수백~4천) JSONL 기록 → 비용 실측 데이터.
- 수렴 가드: 도구 호출 6회 초과 시 도구 없는 모델로 강제 마무리(무한 탐색 방지).

**매뉴얼 파이프라인 — 구현 완료, 실측 전.**
위키 설계를 그대로 구현: 하이브리드 순회(시나리오=결정적 뼈대 + 자율 탐색), 관측 grounding
(매뉴얼 주장은 관측 로그에만 매단다 — critic이 로그 대조 검증), 독자 2축(user/operator),
커버리지 측정+누락 표시, DELETE는 deprecated 유예 표시만(물리 삭제 없음), 탐색 체크포인트
중단 재개(`--resume`). 아티팩트 수집·버전 포인터 전진은 스텁이고,
product-common MR 제출은 대시보드 API에서 run별 계획 생성 후 명시 요청으로 수행한다.
`--smoke`로 L1/L2부터 실측한다 (MCP 서버 도구 이름 확인 → 시나리오 파일 보정).

## product-common 제출 흐름

- 대상 repo: `http://wish.mirero.co.kr/mirero/project/pcc/product-common`
- 설정/토큰: `poc/.env`의 `DOCSHUB_*`와 control-plane DB(`poc/out/control-plane.sqlite`)에 보관한다. API 응답에는 토큰 값을 반환하지 않고 `has_token`만 노출한다.
- MR 계획: `GET /api/docs-hub/mr-plan?run=<run_id>&target=product-common`
- MR 제출: `POST /api/docs-hub/submit-mr` with `{ "run": "<run_id>", "target": "product-common", "confirm": "product-common" }`
- 경로 규칙: `source_doc_dir/{dev|release}/{pipeline}/...`로 산출물을 매핑한다. 기본 source doc_dir가 없으면 source id를 사용한다.

## 자격증명

전부 `poc/.env`(gitignore 차단). 코드·문서 어디에도 하드코딩하지 않는다.
채팅으로 공유된 키는 검증 후 재발급 권장.
