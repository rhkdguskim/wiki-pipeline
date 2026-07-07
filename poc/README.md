# wiki-pipeline PoC

두 파이프라인(docu-automation·manual-automation)이 **어느 수준까지 실제로 도는지** 실측하는 PoC.
LangGraph + MiniMax M3(공급자 중립) 위에서, 얇은 공통 런타임을 두 파이프라인이 공유한다.

> 설계 근거: 위키 `wiki/decision/decision-engine-orchestration-langgraph.md`,
> `decision-model-provider-neutral-minimax.md`, `decision-agent-step-observability.md`.

## 구조

```
poc/
├── common/            # 얇은 공통 런타임 (두 파이프라인 공유)
│   ├── config.py      #   .env -> 타입있는 Settings
│   ├── llm.py         #   공급자 중립 LLM 팩토리 (base_url·key·model)
│   ├── events.py      #   관측 이벤트 스키마 + emit (4단 계층)
│   ├── observer.py    #   custom 스트림 -> 콘솔 + JSONL
│   ├── agent_spec.py  #   그래프 파라미터 (프롬프트+도구+상태)
│   ├── graph.py       #   파라미터화된 tool-use 루프 + 수렴 가드
│   ├── retry.py       #   지수 백오프 재시도
│   └── run.py         #   실행 엔트리 + `--smoke`
├── static_pipeline/   # ① 정적 (코드 diff -> 기술문서) — 구현 완료
└── manual_pipeline/   # ② 매뉴얼 (앱 관측 -> 매뉴얼) — 예정
```

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

## 자격증명

전부 `poc/.env`(gitignore 차단). 코드·문서 어디에도 하드코딩하지 않는다.
채팅으로 공유된 키는 검증 후 재발급 권장.
