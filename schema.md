# LLM Wiki Schema — wiki_pipeline

> 이 문서는 이 저장소의 지식 위키를 유지하는 LLM의 **운영 지침**이다 (Karpathy LLM Wiki 원형).
> 위키 관련 작업(ingest / query / lint) 전에 반드시 이 문서를 읽고 그대로 따른다.

## 3계층 구조

| 계층 | 위치 | 역할 | 변경 규칙 |
|------|------|------|-----------|
| Raw sources | `raw/` | 불변 원본 소스 (논의 기록, 외부 자료 발췌) | **수정 금지, 추가만.** 파일명 `YYYY-MM-DD-<slug>.md` |
| The wiki | `wiki/` | LLM이 생성·유지하는 지식 페이지 | ingest/query/lint 워크플로우로만 갱신 |
| The schema | `schema.md` (이 문서) | 구조·규약·워크플로우의 단일 기준 | 규약 변경 시에만, log에 기록 |

보조 파일: `index.md`(전 페이지 카탈로그), `log.md`(append-only 연산 기록).
`PRD.md`·`docs/`는 위키가 아니라 **정제된 제품 스펙**이다 — 위키 페이지는 상세를 docs/ 링크로 위임한다.

## 페이지 유형 라우팅 — 어디에 무엇을 넣는가

| 유형 | 무엇을 넣나 | 파일명 |
|------|------------|--------|
| overview | 위키 진입 허브 — 시스템 전체 그림. 페이지 추가·삭제 시 **함께 갱신** | `wiki/overview.md` (고정) |
| summary | raw 소스 1건의 요약 — ingest의 1차 산출물 | `wiki/summary-<slug>.md` |
| entity | 시스템·제품·조직 등 실재하는 대상 | `wiki/entity-<slug>.md` |
| concept | 개념·패턴·원리 — 재사용 가능한 지식 | `wiki/concept-<slug>.md` |
| decision | 내려진 결정 + 근거 + 기각 대안 | `wiki/decision-<slug>.md` |
| question | 미해결 질문 — **1질문 1페이지** | `wiki/question-<slug>.md` |

새 유형이 필요하면 이 표에 먼저 추가한 뒤 사용한다 (schema 변경 → log 기록).

## frontmatter (경량 — 필수 4필드)

```yaml
---
type: decision            # 위 라우팅 표의 유형
title: pull 모델 채택
tags: [trigger, compare-api]   # 소문자 kebab-case. 블로킹 질문은 blocking 태그
status: active            # active | open | answered | superseded
---
```

- `status` 의미: `active`(유효) · `open`(미해결 질문) · `answered`(답을 얻은 질문) · `superseded`(번복된 결정)

## 링크 규약

- wiki 페이지 간: `[[파일명]]` (확장자 없이, 예: `[[decision-pull-model]]`)
- raw·docs 참조: 상대경로 마크다운 링크 (예: `../raw/2026-07-05-design-session.md`, `../docs/architecture.md`)
- 모든 wiki 페이지는 `index.md`에 등재되고, 최소 1개의 inbound `[[링크]]`를 가져야 한다 (고아 금지)

## 워크플로우

### Ingest — 새 지식 반영

1. 소스를 `raw/YYYY-MM-DD-<slug>.md`로 저장 (원문 보존, 이후 불변)
2. 소스를 읽고 `wiki/summary-<slug>.md` 작성 (요지 + 파생 페이지 링크)
3. 소스가 건드리는 entity/concept/decision/question 페이지를 생성 또는 갱신 (한 소스가 여러 페이지를 건드릴 수 있음)
4. `wiki/overview.md` 갱신 (필요 시), `index.md` 갱신 (필수)
5. `log.md`에 append: `## [YYYY-MM-DD] ingest | <소스 제목>` + 건드린 페이지 목록

### Query — 질문에 답하기

1. `index.md`를 먼저 읽어 관련 페이지를 찾는다
2. 해당 페이지들(+필요 시 raw·docs)을 읽고 답을 합성한다
3. 유용한 합성 결과(비교·분석)는 새 wiki 페이지로 파일링한다 (복리 축적) → index/log 갱신

### Lint — 건강 점검

검사 항목: 깨진 `[[링크]]` / 고아 페이지 / index 누락·불일치 / frontmatter 필수 필드 누락 / 파일명↔type 접두사 불일치 / overview 드리프트(새 페이지 미반영) / 모순·중복 페이지 / `answered` question에 답 링크 부재.
결과를 `log.md`에 `## [YYYY-MM-DD] lint | 결과 요약`으로 기록한다.

## 콘텐츠 규칙

- **1페이지 = 1관심사.** 문서 통째 붙여넣기 금지. 상세는 docs/(PRD) 링크로 위임
- **question 라이프사이클**: `status: open` → 답이 확정되면 decision 페이지 생성 + question 본문에 답 페이지 링크 + `status: answered` (question 삭제 금지)
- **결정 번복**: 기존 decision을 덮어쓰지 않는다. 새 decision 페이지 생성 + 옛 페이지 `status: superseded` + 상호 링크
- **raw 불변**: raw/ 파일은 절대 수정하지 않는다. 정정이 필요하면 새 raw 파일을 추가하고 wiki에서 갱신

## log.md 형식 (grep-파싱 가능)

```
## [2026-07-05] ingest | 설계 논의 기록
- raw: raw/2026-07-05-design-session.md
- 생성: summary-design-session, decision-pull-model, …
```

- 항목 헤더는 반드시 `## [YYYY-MM-DD] <op> | <제목>` — `grep "^## \[" log.md | tail -5`로 최근 이력 조회
- op ∈ {init, ingest, query, lint, schema}
