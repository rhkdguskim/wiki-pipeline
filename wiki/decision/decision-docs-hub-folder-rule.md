---
type: decision
title: docs-hub 소스별 폴더 = doc_dir 자동 규칙 (full_namespace_path/branch)
tags: [docs-hub, doc-dir, registration, folder, branch]
status: active
---

# 결정: docs-hub 폴더는 레포 1폴더 + `dev/`·`release/` 하위폴더로 자동 생성한다

모든 과제 문서를 **하나의 docs-hub 레포**에서 관리하고, 등록 레포([[decision-repo-dev-release-registration]])마다
docs-hub 안에서 **한 폴더**로 모은 뒤 그 아래를 **역할별 하위폴더**로 가른다. 폴더 경로(`sources.doc_dir`)는
사람이 입력하지 않고 **규칙으로 자동 생성**한다 → **`full_namespace_path/` + `{dev|release}/`**.

## doc_dir 규칙

- `full_namespace_path` — GitLab 프로젝트의 전체 네임스페이스 경로(그룹/서브그룹/프로젝트).
  등록 토큰으로 `GET /projects/:id`에서 자동 조회.
- 그 아래 **역할 하위폴더** — 개발 브랜치 산출물은 `dev/`, 배포 브랜치 산출물은 `release/`.
  등록당 레포 1폴더에 브랜치가 하위로 모이므로(레포 = 사용자 멘탈 단위) 탐색이 자연스럽다.
- 폴더는 **역할 이름**(`dev`/`release`)으로 고정 — 브랜치명 자체를 경로에 넣지 않아 슬래시 치환·충돌 문제가 사라진다.

예: `mirero/ros/ros-sw-rcs` 레포 → `mirero-ros-ros-sw-rcs/dev/` · `mirero-ros-ros-sw-rcs/release/`
(네임스페이스 구분자 처리는 구현 세부, 핵심은 **레포 1폴더 + 역할 하위폴더**로 전역 유일).

## 채택 근거

- **단일 유지보수 지점** — 파이프라인 로직·문서 사이트가 docs-hub 한 곳에 모여, 과제가 늘어도
  운영 지점은 하나 → [[entity-docs-hub]].
- **사람 입력 제거** — 폴더 경로를 규칙으로 못 박아 등록 UI가 토큰+브랜치 2개로 최소화되고
  ([[decision-repo-dev-release-registration]]), 오타·충돌 여지가 사라진다.
- **레포 1폴더 + 역할 하위폴더** — 한 레포의 문서(개발·배포)가 한 곳에 모여 탐색이 자연스럽고,
  역할이 명시적으로 갈린다 → [[decision-repo-dev-release-registration]].

## 기각된 대안

| 대안 | 기각 이유 |
|------|----------|
| **사람이 폴더 경로 입력** | 오타·충돌·중복 관리 부담. 자동 규칙이면 등록이 결정적 |
| **등록마다 `full_namespace_path/branch` 평면 폴더**(옛 규칙) | 레포×브랜치 원자단위와 함께 폐기 — 한 레포 문서가 여러 최상위 폴더로 흩어짐 |
| **브랜치명을 경로에 직접**(예: `release-1.2`) | 슬래시 치환·충돌 관리 필요. 역할 이름(dev/release) 고정이 결정적 |

이 규칙은 서버 DB `sources.doc_dir` 컬럼의 값을 채운다 → [[decision-db-source-of-truth]].
근거: [[2026-07-06-repo-dev-release-branches]]. 관련: [[decision-repo-dev-release-registration]] · [[entity-docs-hub]] · [[overview]]
