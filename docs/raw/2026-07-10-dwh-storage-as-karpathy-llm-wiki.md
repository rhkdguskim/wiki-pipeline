# raw — DWH 저장을 Karpathy LLM Wiki 구조로 재설계

- 날짜: 2026-07-10
- 성격: grill 세션 중 사용자 지시 (방향 전환)
- 사용자 지시 원문: "데이터를 저장할때 안드레이카파시의 LLM WIKI 구조를 따라야해, 그러니까 원본데이터는 계속 쌓고, 변경점을 기록하고, 우리가 가지고 있어야할 핵심 데이터는 정리하고, 안드레이카파사의 LLM WIKI를 보고 데이터 저장 방법에 대해서 상세하게 다시 설계하세요."

## 사용자가 명시한 3원칙

1. 원본 데이터는 계속 쌓고 (불변 축적)
2. 변경점을 기록하고 (연산/변경 로그)
3. 우리가 가지고 있어야 할 핵심 데이터는 정리하고 (증류된 지식)

## Karpathy LLM Wiki 원형 (조사 확인 — 1차 출처)

- 출처: Karpathy Gist "llm-wiki.md" (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) + 원 트윗(X, 2026-04, https://x.com/karpathy/status/2040470801506541998). "idea file"로 정리됨.
- **원형의 3계층 = raw / wiki / schema** (raw/log/distilled가 아님). `log`는 wiki 안의 append-only 파일.
  - Raw sources — "immutable — the LLM reads from them but never modifies them"
  - The wiki — summaries/entities/concepts + index.md + **log.md(chronological, append-only record of ingests/queries/lint)**
  - The schema — CLAUDE.md/AGENTS.md, 구조·워크플로우 규약
- 복리(compounding): "the wiki is a persistent, compounding artifact" — 질의 결과도 다시 파일링돼 복리 축적.
- 워크플로우: ingest(raw 투입 → wiki 반영) / query(원본이 아니라 증류된 wiki에 질의, 좋은 답은 재파일링) / lint(모순·낡은 주장 점검).
- 인간 vs LLM: 인간은 소스 큐레이션·질문·의미 판단, LLM은 나머지(15개 파일 한 번에 갱신 등).
- 미검증 주의: "본인 위키 100문서/400,000단어" 수치는 2차 출처만, Gist 미확인 → 미검증 취급.

## 재해석 핵심 (Medallion ↔ Karpathy)

Medallion(bronze/silver/gold)과 Karpathy LLM Wiki는 같은 layering discipline을 다른 언어로 말한 것. concept-medallion-dwh-on-postgres도 "본질은 layering discipline이지 데이터 모델이 아니다"라고 이미 명시.

| 사용자 3원칙 | Karpathy | 기존 Medallion DWH | 우리 위키 저장소 |
|---|---|---|---|
| ① 원본 계속 쌓기 | raw (immutable) | bronze (append, sha256 skip — 오늘 확정) | docs/raw/ (수정금지·추가만) |
| ② 변경점 기록 | log.md (append-only) | (명시적 계층 없음) activity_log·SCD2가 부분 담당 | docs/wiki/log/ (날짜별 append-only) |
| ③ 핵심 정리 | wiki (summaries/entities/concepts) | silver/gold (정제 차원·팩트) | docs/wiki/<type>/ + index |

- 이미 오늘 확정한 "bronze=append(sha256 skip)"가 사실 Karpathy의 raw 불변 축적과 동일 → 우연이 아니라 원칙으로 명문화.
- 어제 decision-monday-ingest-hybrid의 "bronze upsert + 전용 테이블(monday_webhook_events_raw)"은 Karpathy raw 철학(불변·append)과 충돌 → 오늘 append+단일 테이블로 정정 방향.
- ② 변경점 기록이 기존 DWH 설계에서 가장 약한 고리 — bronze append가 곧 변경 로그가 되도록(스냅샷 히스토리) 설계하면 Karpathy log 원칙과 정합.
