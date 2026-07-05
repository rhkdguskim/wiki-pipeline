# wiki_pipeline

사내 GitLab 다중 과제 AI 문서 자동화 시스템의 설계 저장소.

- **지식 위키**: `raw/`(불변 원본) · `wiki/`(지식 페이지) · `schema.md`(운영 지침) — Karpathy LLM Wiki 3계층
- 제품 스펙(PRD·docs/)은 **아직 작성하지 않는다** — 2026-07-05 삭제(git 이력 보존), 추후 위키를 근거로 재작성 예정

## 위키 유지 규칙

위키 관련 작업(지식 추가/조회/점검)을 하기 전에 **반드시 `schema.md`를 읽고 그 워크플로우(ingest/query/lint)를 따른다.**
raw/는 불변이며, wiki/ 갱신 시 index.md·log.md를 함께 갱신한다.
