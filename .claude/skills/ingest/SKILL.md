---
name: ingest
description: >-
  wiki_pipeline 지식 위키에 새 지식을 반영한다 (Karpathy LLM Wiki의 ingest 워크플로우).
  새 논의 기록·외부 자료·설계 결정을 raw/에 보존하고 wiki/ 지식 페이지로 증류할 때 반드시 사용.
  트리거 - "ingest", "위키에 반영", "이 내용 위키에 넣어", "raw 추가", "새 지식 정리".
  후속 - "방금 반영한 거 보완", "이 소스도 추가", "위키 다시 정리", "페이지 업데이트".
  raw/는 불변, wiki/는 워크플로우로만 갱신, schema.md가 단일 기준이다. wiki-ingestor 에이전트의 절차 가이드이기도 하다.
---

# Ingest — 새 지식을 위키로 증류

이 스킬은 Andrej Karpathy의 **LLM Wiki** 원형을 따른다. 위키는 LLM이 LLM(과 사람)을 위해
유지하는 지식 베이스이며, 세션을 넘어 **복리로 축적**된다. 원본을 통째로 쌓는 게 아니라,
읽고 이해해서 **증류한 지식 페이지**로 재구성하는 것이 핵심이다.

## 0. 먼저 schema.md를 읽는다 (필수 · 위반 금지)

작업 전 **반드시 저장소 루트의 `schema.md`를 Read** 하라. schema.md가 구조·규약·워크플로우의
**단일 기준(SSOT)**이다. 이 스킬은 그 워크플로우를 대체하지 않고 실행을 강제·안내할 뿐이다.
schema.md의 "Ingest — 새 지식 반영" 절과 실제 단계가 어긋나면 **schema.md를 따른다**.

## 왜 이렇게 하는가 (Karpathy 3계층)

| 계층 | 위치 | 규칙 |
|------|------|------|
| Raw sources | `raw/` | **불변** — 수정 금지, 추가만. `YYYY-MM-DD-<slug>.md` |
| The wiki | `wiki/` | LLM이 생성·유지 — ingest/query/lint로만 갱신 |
| The schema | `schema.md` | 헌법 — 규약 변경 시에만 수정 (log 기록) |

- **불변 raw**: 원본은 진실의 앵커다. 정정이 필요해도 raw를 고치지 않고 새 raw를 추가한 뒤 wiki에서 갱신한다.
- **멱등성**: 같은 소스를 다시 ingest해도 중복 페이지가 생기면 안 된다. 기존 페이지가 있으면 **갱신**, 없을 때만 생성.
- **1페이지 = 1관심사**: 문서 통째 붙여넣기 금지. 각 페이지는 자체 완결.

## 실행 단계 (schema.md의 Ingest 워크플로우)

1. **raw 보존** — 소스를 `raw/YYYY-MM-DD-<slug>.md`로 저장 (원문 그대로, 이후 불변). 이미 raw가 있으면 재사용.
2. **summary 작성** — `wiki/summary/summary-<slug>.md`에 요지 + 파생 페이지 링크.
3. **지식 페이지 증류** — 소스가 건드리는 entity / concept / decision / question 페이지를 생성 또는 **갱신**.
   유형 라우팅과 concept↔decision 판별은 schema.md 표를 따른다. 한 소스가 여러 페이지를 건드릴 수 있다.
4. **인덱스·overview 갱신** — 건드린 각 유형의 폴더 인덱스(`wiki/<type>/<type>-index.md`)를 **반드시** 갱신.
   시스템 구조가 바뀌었으면 `wiki/overview.md`도 갱신. 새 유형/폴더면 허브 `wiki/index.md`도 갱신.
5. **log 기록** — `log.md`에 append:
   ```
   ## [YYYY-MM-DD] ingest | <소스 제목>
   - raw: [[YYYY-MM-DD-<slug>]]
   - 생성: <페이지들>
   - 갱신: <페이지들>
   ```
   (오늘 날짜는 environment의 currentDate를 쓴다.)

## 링크 규약 (schema.md 링크 규약)

- 모든 참조는 `[[파일명]]` wikilink (확장자·경로 없이). raw 참조도 `[[YYYY-MM-DD-<slug>]]`.
- **상대경로 마크다운 링크(`](../…)`) 금지.**
- 새 페이지는 최소 1개의 inbound 링크를 가져야 한다 (고아 금지) — 폴더 인덱스 등재가 그 최소선.

## 완료 게이트 (끝내기 전 자가 점검)

- [ ] raw/ 원본을 수정하지 않았다 (추가만).
- [ ] 새/갱신 페이지가 올바른 `wiki/<type>/` 폴더에 있고 frontmatter 4필드(type·title·tags·status)를 갖췄다.
- [ ] 건드린 모든 유형의 폴더 인덱스를 갱신했다. 새 폴더면 허브 index도 갱신했다.
- [ ] 모든 링크가 `[[wikilink]]`이고 깨진 링크·고아 페이지가 없다.
- [ ] `log.md`에 ingest 항목을 남겼다.

마무리로 **`/lint`를 돌려 무결성을 확인**할 것을 권한다.
