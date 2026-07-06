---
type: question
title: requirements와 dev-guide 테마의 경계는?
tags: [themes, phase-1]
status: open
---

# ❓ requirements와 dev-guide 테마의 경계는?

`requirements` 테마의 원 정의는 "설치/실행 환경과 조건" (독자: 설치자·운영자 —
[[2026-07-05-docu-automatic-notes]]). 신규 `dev-guide` 테마의 ①절(환경 구성 — 사전 요구·의존·빌드,
[[decision-theme-scope-expansion]])과 **소재가 겹친다** — 필요 런타임·OS·의존성이 양쪽에 등장하고,
`source_files` 매핑도 겹쳐 같은 매니페스트·CI 파일 변경이 두 테마를 동시에 트리거한다.

## 왜 문제인가

- scout가 경계를 모르면 dev-guide에 설치·운영 내용이, requirements에 개발 도구 내용이 섞여
  **중복·드리프트** 발생 ([[entity-docu-automatic]]의 테마 체계는 관점×독자로 정의됨)
- 겹치는 사실이 두 문서에서 따로 갱신되면 서로 어긋난다

## 잠정 방향 (2026-07-06 query에서 제안)

**통합이 아니라 경계 명시** — 독자 축이 다르므로 분리 유지 ([[decision-manual-taxonomy-two-reader]]와
같은 원리):

- requirements = 소스 빌드 **없이** 제품을 설치·실행하는 환경/조건 (설치자·운영자)
- dev-guide = 소스에서 빌드·테스트·디버그하며 **개발**하는 환경 (개발자)
- 겹치는 사실은 상세를 한쪽에 두고 다른 쪽이 참조

테마 정의(프롬프트)에 위 경계 문장을 명시할지, critic 적합성 기준에 반영할지 확정 필요.
답이 확정되면 decision으로 승격하고 이 페이지를 `answered`로 전환한다.
