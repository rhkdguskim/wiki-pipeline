---
type: decision
title: 사람 MR 리뷰 게이트 (AI 자동 머지 금지)
tags: [mr, review, quality-gate]
status: active
---

# 결정: 모든 문서 변경은 사람 MR 리뷰를 거친다

AI 산출물은 docs-hub에 브랜치 + MR로만 제출한다. AI가 main에 직접 쓰지 않는다.

## 기존 docs-auto 브랜치 방식을 대체 (확정)

Docu-Automatic 원 설계(v4)는 각 레포의 docs-auto 브랜치에 push 후 중앙 배치가 pull하는 방식.
**MR 방식으로 최종 확정** — 사람 리뷰 게이트 확보 + 원 레포의 미결 사항("인간 리뷰 프로세스",
"docs-auto 브랜치 관리")이 함께 해소 → [[question-mr-vs-docs-auto]] 답변(2026-07-05).

SCM 커넥터에 따라 제출 수단이 다르다: GitLab은 **MR**, GitHub은 **PR** — 사람 리뷰 게이트는 동일하다 → [[decision-scm-connector-abstraction]]

## MR 규격 (PR도 동일)

- 기본 소스별 1 MR. 본문에 근거 커밋 구간·변경 파일·생성 문서·경고 목록 명시
- 동일 소스의 열린 자동 MR이 있으면 **갱신** (중복 방지) → [[concept-idempotent-sha]]
- critic 2회 초과 fail 문서는 `auto_generated_warning` 태그 + MR에 표시 → 리뷰어가 판단
- 품질 추적 지표: 자동 MR 머지율

## 실측 근거 (2026-07-06) — CE라 approval rule 강제 불가 (모순 아님)

[[2026-07-06-wish-gitlab-api-survey]]에서 인스턴스가 **Community Edition**이라 `GET /projects/:id/approvals`가
**404**임이 확인됐다 — MR approval rule로 리뷰 게이트를 *기술적으로 강제*할 수 없다. 우리 게이트는 처음부터
"AI가 main에 직접 쓰지 않고 MR로만 제출, 사람이 머지"라는 **관례·프로세스 기반**이라 이 사실과 모순되지 않는다(오히려 근거 보강).
`POST /merge_requests`는 200으로 확인돼 MR 제출 경로 자체는 실증됐다 → [[decision-scm-connector-abstraction]].

관련: [[entity-docu-automatic]] · [[entity-mirero-gitlab]] · [[summary-design-session]] · 원본: [[2026-07-06-wish-gitlab-api-survey]]
