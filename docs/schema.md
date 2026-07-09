# LLM Wiki Schema — wiki_pipeline

> 이 문서는 이 저장소의 지식 위키를 유지하는 LLM의 **운영 지침**이다 (Karpathy LLM Wiki 원형).
> 위키 관련 작업(ingest / query / lint) 전에 반드시 이 문서를 읽고 그대로 따른다.

## 3계층 구조

| 계층 | 위치 | 역할 | 변경 규칙 |
|------|------|------|-----------|
| Raw sources | `raw/` | 불변 원본 소스 (논의 기록, 외부 자료 발췌) | **수정 금지, 추가만.** 파일명 `YYYY-MM-DD-<slug>.md` |
| The wiki | `wiki/` | LLM이 생성·유지하는 지식 페이지 | ingest/query/lint 워크플로우로만 갱신 |
| The schema | `schema.md` (이 문서) | 구조·규약·워크플로우의 단일 기준 | 규약 변경 시에만, log에 기록 |

보조 파일: **lazy-loading 2계층 인덱스** — 허브 `wiki/index.md`(유형별 폴더 인덱스로 드릴다운) + 폴더별 `wiki/<type>/<type>-index.md`(그 폴더 페이지만 나열). `log.md`(append-only 연산 기록).

스키마 도구(`schema.md` 규약의 실행 보조물):
- `validate_frontmatter.py` — frontmatter 정합성 자동 검증기. lint 시 실행(`python docs/validate_frontmatter.py`, 종료코드 0=통과). 이 규약의 정적 검사 항목(필수 4필드·type 6종·status enum·type↔폴더·파일명 접두사·answered question의 blocking 잔존)을 코드화한 것. 규약을 바꾸면 이 스크립트의 규칙도 함께 고친다.
- `templates/<type>.md` — 유형별 노트 스타터 6종(overview·summary·entity·concept·decision·question). 새 페이지는 해당 템플릿을 복사해 시작한다.
제품 스펙(`PRD.md`·`docs/`)은 **아직 작성하지 않는다** (2026-07-05 삭제, 추후 재작성 예정 — git 이력에 보존). 현재는 raw/ + 위키가 유일한 지식 소스이며, PRD가 재작성되면 위키 페이지가 상세를 docs/ 링크로 위임한다.

## 페이지 유형 라우팅 — 어디에 무엇을 넣는가

wiki/는 **유형별 하위 폴더**로 나뉜다. 폴더명 = frontmatter `type`. 파일명 접두사는 폴더와 중복되지만 **유지한다** — 파일명이 전역 유일해야 `[[링크]]`가 모호해지지 않고, 본문 속 링크가 자기 유형을 설명한다.

| 유형 | 무엇을 넣나 | 경로 |
|------|------------|------|
| overview | 위키 진입 허브 — 시스템 전체 그림·다이어그램·실행 흐름 (**서사 중심**; 전체 페이지 카탈로그는 [[index]]에 위임). 시스템 구조가 바뀔 때 갱신 | `wiki/overview.md` (고정, 루트 유일 파일) |
| summary | raw 소스 1건의 요약 — ingest의 1차 산출물 | `wiki/summary/summary-<slug>.md` |
| entity | 시스템·제품·조직 등 실재하는 대상 | `wiki/entity/entity-<slug>.md` |
| concept | 개념·패턴·원리 — 재사용 가능한 지식 | `wiki/concept/concept-<slug>.md` |
| decision | 내려진 결정 + 근거 + 기각 대안 | `wiki/decision/decision-<slug>.md` |
| question | 미해결 질문 — **1질문 1페이지** | `wiki/question/question-<slug>.md` |

새 유형이 필요하면 이 표에 먼저 추가하고 폴더를 만든 뒤 사용한다 (schema 변경 → log 기록).

**카탈로그 파일** (네비게이션 전용, 지식 페이지 아님): 허브 `wiki/index.md` + 각 폴더 `<type>-index.md`. 파일명이 `index.md`/`*-index.md`인 것으로 식별하며, frontmatter·type↔폴더·고아 검사에서 제외된다. 새 유형 폴더를 만들면 그 폴더의 `<type>-index.md`도 함께 만들고 허브에 링크한다.

**폴더 인덱스 안의 기능 그룹핑**: 파일은 유형 폴더에 **평면으로** 둔다(폴더명=type 규약 유지, 하위 폴더 금지). 대신 페이지가 많아지는 폴더(현재 decision·question·summary)의 `<type>-index.md`는 **기능(파이프라인) 축의 `###` 소제목**으로 그룹핑한다 — 물리 이동 없이 인덱스에서만 드릴다운을 만든다. 표준 그룹 축:

| 그룹 | 담는 것 |
|------|--------|
| 공통 · cross-cutting | 파이프라인이 공유하는 결정/질문 (플레인 분리·관측성·커넥터·DB·서버·엔진) |
| 정적 파이프라인 (Docu-Automatic) | 코드→기술문서. 하위 `#### 소스 등록 · docs-hub 산출` 포함 |
| 매뉴얼 추출 파이프라인 | 실행 앱→사용자 매뉴얼 |
| 코드 인덱스 파이프라인 | 코드→질의 가능 인덱스 |
| 향후 기능 후보 / 실측 (question·summary) | Phase 3+ 미확정 · 사내 환경 실측 |

새 페이지는 등재 시 맞는 그룹에 넣는다. 그룹이 애매하면 "공통"에 두고, 한 그룹이 비대해지면 하위 `####`로 쪼갠다. 그룹 소제목은 지식이 아니라 네비게이션이므로 링크·고아 검사 대상이 아니다.

### concept vs decision — 헷갈릴 때

decision은 대개 concept을 **실체화(instantiate)** 한다 (예: [[decision-pull-model]]이 [[concept-idempotent-sha]]를 쓴다) → 겹쳐 보이지만 아래 3축으로 가른다.

| 축 | decision | concept |
|----|----------|---------|
| **번복** | 다르게 택하면 `superseded` 됨 | 번복이 아니라 "정정"의 대상 (대안으로 교체 불가) |
| **이식성** | 우리 맥락에서만 참 (예: 야간 20:00 배치) | 프로젝트 밖에서도 참 (예: 멱등성은 어디서나 멱등성) |
| **기각 대안** | 버린 대안이 있다 | 없다 — 선택이 아니라 설명이므로 |

- concept 페이지엔 **"우리가 택했다" 문장 금지** — 그건 decision으로 간다.
- decision 페이지는 메커니즘 설명을 **concept 링크로 위임**하고, 선택·근거·기각 대안에 집중한다.

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
- status 허용값은 유형별로 다르다: overview·summary·entity·concept = `active` / decision = `active`·`superseded` / question = `open`·`answered`. (검증기가 강제)
- 새 페이지는 `templates/<type>.md`를 복사해 시작한다.

## 링크 규약

- wiki 페이지 간: `[[파일명]]` (확장자·경로 없이, 예: `[[decision-pull-model]]`) — 하위 폴더와 무관하게 파일명만으로 참조
- raw 참조: wiki 페이지와 똑같이 `[[파일명]]` wikilink 사용 (예: `[[2026-07-05-design-session]]`). raw 파일명이 전역 유일하므로 폴더 깊이·상대경로를 신경 쓸 필요 없이 Obsidian이 해석하고 백링크를 잡는다. **상대경로 마크다운 링크(`](../…)`)는 금지**
- 모든 지식 페이지는 **자기 유형의 폴더 인덱스**(`<type>-index.md`)에 등재되고, 폴더 인덱스는 허브 [[index]]에 링크된다. 각 페이지는 최소 1개의 inbound `[[링크]]`를 가져야 한다 (고아 금지)

## 워크플로우

### Ingest — 새 지식 반영

1. 소스를 `raw/YYYY-MM-DD-<slug>.md`로 저장 (원문 보존, 이후 불변)
2. 소스를 읽고 `wiki/summary/summary-<slug>.md` 작성 (요지 + 파생 페이지 링크)
3. 소스가 건드리는 entity/concept/decision/question 페이지를 생성 또는 갱신 (한 소스가 여러 페이지를 건드릴 수 있음)
4. `wiki/overview.md` 갱신 (필요 시), **해당 폴더 인덱스**(`<type>-index.md`) 갱신 (필수). 새 유형/폴더면 허브 [[index]]도 갱신
5. `log.md`에 append: `## [YYYY-MM-DD] ingest | <소스 제목>` + 건드린 페이지 목록

### Query — 질문에 답하기

1. 허브 [[index]]에서 유형을 고르고 **해당 폴더 인덱스만** 열어 관련 페이지를 찾는다 (lazy-loading — 전체 카탈로그를 로드하지 않음)
2. 해당 페이지들(+필요 시 raw·docs)을 읽고 답을 합성한다
3. 유용한 합성 결과(비교·분석)는 새 wiki 페이지로 파일링한다 (복리 축적) → index/log 갱신

### Lint — 건강 점검

먼저 `python docs/validate_frontmatter.py`를 실행한다 — 정적 검사(frontmatter 필수 4필드 누락 / 알 수 없는 type / status enum 밖 / type↔폴더 불일치 / 파일명↔type 접두사 불일치 / answered question의 blocking 잔존)를 자동 판정한다(종료코드 0=통과).

이어서 스크립트가 못 잡는 항목을 수동 검사: 깨진 `[[링크]]` / 고아 페이지 / **폴더 인덱스 누락·불일치**(지식 페이지가 자기 `<type>-index.md`에 없음 / 폴더 인덱스가 허브 [[index]]에 없음) / 상대경로 마크다운 링크 잔존(`](../…)`·`](./…)` — raw·wiki 참조 모두 `[[wikilink]]`여야 함) / overview 드리프트(새 페이지 미반영) / 모순·중복 페이지 / `answered` question에 답 링크 부재. (카탈로그 파일 `index.md`/`*-index.md`은 frontmatter·접두사·고아 검사 제외)
결과를 `log.md`에 `## [YYYY-MM-DD] lint | 결과 요약`으로 기록한다.

## 콘텐츠 규칙

- **1페이지 = 1관심사.** 문서 통째 붙여넣기 금지. 페이지는 자체 완결로 유지 (PRD 재작성 후에는 상세를 docs/ 링크로 위임)
- **question 라이프사이클**: `status: open` → 답이 확정되면 decision 페이지 생성 + question 본문에 답 페이지 링크 + `status: answered` (question 삭제 금지). **answered로 전환할 때 `blocking` 태그가 있으면 제거한다** — `blocking`은 "지금 진행을 막는 미해결 질문"의 표식이므로, 해소된 질문에 남으면 활성 블로커 조회가 오염된다.
- **결정 번복**: 기존 decision을 덮어쓰지 않는다. 새 decision 페이지 생성 + 옛 페이지 `status: superseded` + 상호 링크
- **raw 불변**: raw/ 파일은 절대 수정하지 않는다. 정정이 필요하면 새 raw 파일을 추가하고 wiki에서 갱신

## log.md 형식 (grep-파싱 가능)

```
## [2026-07-05] ingest | 설계 논의 기록
- raw: [[2026-07-05-design-session]]
- 생성: summary-design-session, decision-pull-model, …
```

- 항목 헤더는 반드시 `## [YYYY-MM-DD] <op> | <제목>` — `grep "^## \[" log.md | tail -5`로 최근 이력 조회
- op ∈ {init, ingest, query, lint, schema}
