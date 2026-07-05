# wiki_pipeline

사내 GitLab 다중 과제 AI 문서 자동화 시스템의 설계 저장소.

- **지식 위키**: `raw/`(불변 원본) · `wiki/`(지식 페이지) · `schema.md`(운영 지침) — Karpathy LLM Wiki 3계층
- 제품 스펙(PRD·docs/)은 **아직 작성하지 않는다** — 2026-07-05 삭제(git 이력 보존), 추후 위키를 근거로 재작성 예정

## 위키 유지 규칙

위키 관련 작업(지식 추가/조회/점검)을 하기 전에 **반드시 `schema.md`를 읽고 그 워크플로우(ingest/query/lint)를 따른다.**
raw/는 불변이며, wiki/ 갱신 시 폴더 인덱스(`wiki/<type>/<type>-index.md`)·log.md를 함께 갱신한다(인덱스는 허브 `wiki/index.md` + 폴더별 2계층).

## 하네스: 지식 위키 유지

**목표:** raw/ 원본을 불변 보존하고 wiki/ 지식 페이지로 증류·조회·검증하여 위키를 복리로 축적한다 (Karpathy LLM Wiki).

**트리거:**
- 위키 작업이 **모호하거나 여러 작업을 엮어야** 할 때 → `wiki-ops` 스킬(라우터)이 분류해 전문 에이전트로 위임.
- **단일 작업이 명확**하면 → `ingest`(반영) · `query`(조회) · `lint`(점검) 스킬을 직접 사용.
- 전문 에이전트(`.claude/agents/`): `wiki-ingestor` · `wiki-librarian` · `wiki-linter` (서브 에이전트/전문가 풀 모드, model: opus).
- 위키 저장소 자체가 상태이고 `log.md`가 감사 추적이다 — `_workspace/` 같은 중간 폴더를 만들지 않는다.

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-07-05 | 초기 구성 — ingest/query/lint 스킬 + 3 에이전트 + wiki-ops 라우터 | 전체 | 위키 워크플로우를 호출 가능한 하네스로 승격 |
