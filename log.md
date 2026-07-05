# Wiki Log

> append-only 연산 기록. 형식: `## [YYYY-MM-DD] <op> | <제목>` — 최근 이력: `grep "^## \[" log.md | tail -5`

## [2026-07-05] init | 위키 초기화 (schema.md 제정)
- Karpathy LLM Wiki 3계층(raw/ · wiki/ · schema.md) 구조 채택, 경량 frontmatter(4필드)
- 이전 시도(.omc/wiki, 스키마 없음)를 폐기하고 본 구조로 마이그레이션

## [2026-07-05] ingest | 설계 논의 기록
- raw: raw/2026-07-05-design-session.md (docs/01-design-summary.md에서 이동)
- 생성: summary-design-session, overview, decision-pull-model, decision-nightly-batch,
  decision-db-source-of-truth, decision-mr-review-gate, concept-idempotent-sha,
  entity-docs-hub, entity-mirero-gitlab, question-* 9건

## [2026-07-05] ingest | Docu-Automatic 레포 분석 노트
- raw: raw/2026-07-05-docu-automatic-notes.md
- 생성: summary-docu-automatic, entity-docu-automatic / 갱신: overview

## [2026-07-05] lint | 초기 구축 검증
- wiki 20페이지 + raw 2건: 깨진 링크 0 / 고아 0 / index 누락 0 / frontmatter 누락 0 / 파일명↔type 불일치 0 / 상대경로 깨짐 0 (PASS)

## [2026-07-05] schema | wiki 유형별 하위 폴더 구조 도입
- flat → `wiki/{summary,entity,concept,decision,question}/` 5개 폴더 (overview.md만 루트 고정)
- 파일명 접두사 유지 → `[[링크]]` 무변경, 파일명 전역 유일 보장. 하위 폴더 페이지의 raw/docs 상대경로는 `../../`
- schema.md 개정: 라우팅 표 경로, 링크 깊이 규칙, lint에 type↔폴더 일치 검사 추가

## [2026-07-05] lint | 폴더 구조 마이그레이션 검증
- wiki 20페이지 + raw 2건: 깨진 링크 0 / 고아 0 / index 누락 0 / frontmatter 누락 0 / 접두사·폴더 불일치 0 / 상대경로 깨짐 0 (PASS)
