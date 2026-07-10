---
type: concept
title: Karpathy LLM Wiki — 저장 철학 (축적·기록·정리로 복리 축적)
tags: [karpathy-llm-wiki, knowledge-base, append-only, compounding, storage, distillation]
status: active
---

# Karpathy LLM Wiki — 저장 철학 (축적·기록·정리로 복리 축적)

## 정의

Andrej Karpathy가 2026-04 공개한 **LLM Wiki**(본인 표현 "idea file") 패턴. LLM을 써서 관심 주제의 지식 베이스를 **한 번 컴파일하고 이후 계속 최신 상태로 유지**하는(“compiled once and then kept current, not re-derived on every query”) 저장 방식이다. RAG처럼 매 질의마다 원본을 재검색·재합성하지 않고, **증류된 지식을 지속적·복리적 산출물(persistent, compounding artifact)로 축적**한다.

## 원형의 3계층 (raw / wiki / schema)

주의: 원형의 3계층은 `raw / log / distilled`가 아니라 **`raw / wiki / schema`**이며, `log`는 wiki 안의 파일이다.

| 계층 | 역할 | 규칙 |
|------|------|------|
| **raw** | 큐레이션된 원본 소스(문서·논문·데이터) | **불변** — LLM은 읽기만, 수정 안 함 |
| **wiki** | LLM이 생성·유지하는 지식 페이지 | `summaries/`(소스당 1) · `entities/` · `concepts/`(교차 종합) + `index.md`(카탈로그) + `log.md`(연산 이력) |
| **schema** | 구조·워크플로우 규약 | `CLAUDE.md`/`AGENTS.md` — 느리게·의도적으로만 변경 |

## 세 가지 동작으로 본 저장 (축적·기록·정리)

원형이 데이터를 다루는 방식은 세 동작으로 요약된다 — 이 프로젝트에서 저장 설계의 뼈대로 쓴다:

1. **원본을 계속 쌓는다(축적)** — raw에 소스를 append. 불변. 재생(replay)의 근거.
2. **변경점을 기록한다(기록)** — `log.md`는 chronological, **append-only**. ingest/query/lint가 언제 무엇을 했는지 남긴다. 감사 추적.
3. **핵심을 정리한다(정리·증류)** — raw를 읽어 summaries/entities/concepts로 합성. 질의는 원본이 아니라 이 증류된 지식을 향한다. 좋은 질의 결과도 다시 파일링돼 복리로 쌓인다.

## 워크플로우 (ingest / query / lint)

- **ingest** — raw에 소스 투입 → LLM이 wiki 페이지로 반영.
- **query** — 이미 증류된 wiki에 질의, 관련 페이지를 찾아 답 합성. 유용한 답은 재파일링(복리).
- **lint** — 주기적 무결성 점검(모순·낡은 주장·끊긴 교차참조).

**인간 vs LLM 역할**: 인간은 소스 큐레이션·분석 방향 지시·좋은 질문·의미 판단. LLM은 나머지 — "지루해하지 않고, 교차참조 갱신을 잊지 않고, 한 번에 15개 파일을 건드린다."

## 왜 중요한가

- **복리(compounding)** — 지식이 매번 재도출되지 않고 축적돼, 다음 질문이 더 적은 노력으로 풀린다.
- **재생 가능성** — raw 불변이므로 정리 로직을 바꿔도 원본에서 다시 만든다.
- **substrate 무관** — 이 discipline은 파일 위키든, PostgreSQL DWH든, 벡터 저장소든 그대로 적용된다([[concept-medallion-dwh-on-postgres]]의 "layering discipline이지 데이터 모델이 아니다"와 같은 통찰).

## 이 프로젝트에서의 실체화

- **위키 저장소 자체** — `docs/raw/`(축적) · `docs/wiki/log/`(기록) · `docs/wiki/<type>/`+`index`(정리). schema는 `docs/schema/`로 독립 계층 승격(원형의 호환 확장 — 원형은 schema를 CLAUDE.md 단일 파일로 둠).
- **DWH 저장** — 같은 3동작으로 재조직([[decision-dwh-as-karpathy-llm-wiki]]): raw_records(축적) · _meta 수집 로그(기록) · silver/gold(정리).

## 출처

- (1차) Karpathy Gist "llm-wiki.md": https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- (1차) 원 트윗 (X, 2026-04): https://x.com/karpathy/status/2040470801506541998
- 미검증 주의: "본인 위키 100문서/400,000단어" 수치는 2차 출처만, Gist 미확인.

## 관련

- [[decision-dwh-as-karpathy-llm-wiki]] — DWH 저장을 이 철학으로 재조직한 결정
- [[concept-medallion-dwh-on-postgres]] — 같은 layering discipline의 BI 언어 버전
- [[decision-bronze-single-jsonb-table]] — 축적(append) 실체
- [[decision-dwh-md-document-store]] — 팀 LLM WIKI 확장 대비 저장
- [[2026-07-10-dwh-storage-as-karpathy-llm-wiki]] — 논의 원본
