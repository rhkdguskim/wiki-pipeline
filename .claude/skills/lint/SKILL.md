---
name: lint
description: >-
  wiki_pipeline 지식 위키의 무결성을 점검한다 (Karpathy LLM Wiki의 lint 워크플로우).
  깨진 링크·고아 페이지·인덱스 불일치·frontmatter 누락·type↔폴더 불일치·overview 드리프트·
  모순/중복을 찾아 보고하고 고칠 때 반드시 사용. ingest·query 직후 검증 단계로도 사용.
  트리거 - "lint", "위키 점검", "위키 건강 검사", "링크 깨진 데 없나", "위키 정합성 확인".
  후속 - "다시 점검", "재검사", "고친 뒤 다시 확인".
  카탈로그 파일(index.md/*-index.md)은 일부 검사에서 제외, schema.md가 단일 기준이다. wiki-linter 에이전트의 절차 가이드이기도 하다.
---

# Lint — 위키 무결성 점검

이 스킬은 Andrej Karpathy의 **LLM Wiki** 원형을 따른다. 위키가 복리로 커질수록 링크·인덱스·
분류가 어긋나기 쉽다. lint는 위키를 **자체 정합적(self-consistent)** 으로 유지하는 정기 점검이며,
ingest/query가 남긴 흔적이 규약대로인지 검증한다.

## 0. 먼저 schema.md를 읽는다 (필수 · 위반 금지)

작업 전 **반드시 저장소 루트의 `schema.md`를 Read** 하라. 검사 항목의 **정본은 schema.md의
"Lint — 건강 점검" 절**이다. 아래 목록은 그 실행 체크리스트이며, 어긋나면 schema.md를 따른다.

## 검사 항목 (schema.md Lint 절)

각 항목을 실제로 확인하라 (grep·Glob·Read 활용). 카탈로그 파일 `index.md`/`*-index.md`는
frontmatter·접두사·고아 검사에서 **제외**된다.

1. **깨진 `[[링크]]`** — 링크 대상 파일이 실제로 존재하는가.
2. **고아 페이지** — 지식 페이지가 최소 1개의 inbound `[[링크]]`를 갖는가 (폴더 인덱스 등재 포함).
3. **폴더 인덱스 누락·불일치** — 지식 페이지가 자기 `<type>-index.md`에 등재됐는가 /
   폴더 인덱스가 허브 `wiki/index.md`에 링크됐는가 / 허브의 페이지 수 카운트가 맞는가.
4. **frontmatter 필수 4필드** — type · title · tags · status 누락 여부.
5. **파일명↔type 접두사 불일치** — 예: `type: decision`인데 파일명이 `decision-*`가 아님.
6. **type↔폴더 불일치** — 페이지가 자기 type 폴더 밖에 있음.
7. **상대경로 마크다운 링크 잔존** — `](../…)` · `](./…)` 검색. raw·wiki 참조 모두 `[[wikilink]]`여야 함.
8. **overview 드리프트** — 새 페이지·구조 변화가 `wiki/overview.md`에 반영됐는가.
9. **모순·중복 페이지** — 같은 관심사가 쪼개졌거나 서로 상충하는 내용.
10. **`answered` question에 답 링크 부재** — status가 answered인데 답 decision 링크가 없음.

## 참고 grep

- 상대경로 링크: `grep -rn "](\.\.\?/" wiki/`
- frontmatter 시작 확인: 각 지식 페이지 첫 줄이 `---`인지.
- 최근 이력: `grep "^## \[" log.md | tail -5`

## 보고와 수정

1. **보고** — 발견 항목을 심각도와 함께 나열한다 (깨진 링크/고아처럼 명백한 결함 우선).
2. **수정** — 명백한 결함(깨진 링크, 인덱스 누락, 접두사 불일치 등)은 고친다.
   판단이 필요한 항목(모순·중복 병합, 유형 재분류)은 **수정 전 사용자에게 확인**한다.
   raw/는 절대 수정하지 않는다.
3. **log 기록** — `log.md`에 append:
   ```
   ## [YYYY-MM-DD] lint | <결과 요약>
   ```
   (오늘 날짜는 environment의 currentDate를 쓴다.)

## 완료 게이트

- [ ] 10개 검사 항목을 모두 점검했다 (해당 없음도 명시).
- [ ] 명백한 결함은 수정했고, 판단 필요 항목은 사용자에게 올렸다.
- [ ] `log.md`에 lint 결과를 기록했다.
- [ ] "clean" 여부를 한 줄로 결론 냈다 (남은 이슈가 있으면 개수와 함께).
