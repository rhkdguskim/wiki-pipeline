---
type: decision
title: 레포 1개 등록 + 개발/배포 브랜치 2개 (역할별 문서 산출)
tags: [scm, registration, branch, dashboard, dev-release]
status: active
---

# 결정: 등록 원자 단위는 레포 1개, 그 안에 개발·배포 브랜치를 지정한다

대시보드 등록의 원자 단위는 **레포 1개**다(레포당 등록 1건). 그 등록 안에서
**개발 브랜치 1 + 배포 브랜치 2 = 고정 2개**를 지정하고, 두 브랜치는 **역할이 다른 문서**를 낳는다.

이 결정은 앞선 "레포×브랜치 1개 = 등록 원자단위" 모델을 **대체한다** → [[decision-repo-registration-flow]] (superseded).

## 브랜치 역할 — 문서 산출을 가른다

| 브랜치 | 트리거 | 산출물 | docs-hub 위치 |
|--------|--------|--------|--------------|
| **개발(dev)** | compare 기반 야간 배치 → [[decision-pull-model]] | 최신 기술문서(자주 갱신) | `<레포폴더>/dev/` |
| **배포(release)** | 릴리스/버전 태그 → [[decision-release-tag-trigger]] | 안정 릴리스 문서·매뉴얼 | `<레포폴더>/release/` |

- 두 브랜치는 **독립 추적**되지만 **한 등록이 소유**한다 — 개발은 compare 야간, 배포는 릴리스 트리거.
- 브랜치 개수는 **역할별 정확히 1개(고정 2)** — UI가 명확하고 doc_dir이 결정적.

## 등록 흐름 (실측 API 기반)

1. **레포별 project access token 입력** — 그 프로젝트에서 생성한 project access token(`read_repository` + `api`).
   토큰이 곧 "어느 레포냐"를 스코프하므로 별도 프로젝트 선택 단계가 없다(실측: `GET /projects/:id/access_tokens` 200,
   그룹 토큰은 Owner 필요 401 → [[2026-07-06-wish-gitlab-api-survey]]).
2. **자동 조회로 채우는 값** — project id·`default_branch`·scm 타입·`http_url_to_repo`를 토큰으로 `GET /projects/:id`에서 얻는다.
3. **개발·배포 브랜치 각각 선택** — `GET /projects/:id/repository/branches` 목록에서 개발 1개·배포 1개를 고른다.
   `default_branch`(master/main 혼재라 하드코딩 금지 → [[entity-mirero-gitlab]])를 배포 브랜치 기본값으로 제안한다.
4. **소스 정책 입력** — 배포 브랜치의 트리거 기준(릴리스 객체/태그), 아티팩트 타입 등. 소스가 균질하지 않아 명시가 필요.
5. **연결 검증(dry-run)** — 등록 확정 전 두 브랜치 모두 compare API 200을 확인한 뒤에만 확정.

등록값은 서버 DB sources 테이블로 들어간다 → [[decision-db-source-of-truth]]. 토큰을 auth 자격으로 쓰는 주체는
SCM 커넥터의 auth 책임 → [[decision-scm-connector-abstraction]].

## docs-hub 폴더 — 레포 1폴더 + 역할 하위폴더

- 한 레포의 문서는 docs-hub에서 **한 폴더 아래에 모인다**: `full_namespace_path/` + `dev/`·`release/` 하위폴더
  → [[decision-docs-hub-folder-rule]]. 탐색이 자연스럽고, 개발/배포 문서가 명시적으로 갈린다.

## 채택 근거

- **레포 = 사용자 멘탈 모델의 단위** — 과제 담당자는 "이 레포를 문서화"로 생각하지 "이 브랜치를 등록"으로 생각하지 않는다.
- **개발/배포 역할이 실제 파이프라인을 가름** — 최신 기술문서(개발)와 안정 릴리스 문서·매뉴얼(배포)은 트리거·독자·주기가 달라
  한 등록 안에서 역할로 분리하는 편이 자연스럽다.
- **고정 2개로 단순** — 아무 브랜치나 N개(옛 정책 C)보다 UI·폴더·트리거 정책이 결정적.

## 기각된 대안

| 대안 | 기각 이유 |
|------|----------|
| **레포×브랜치 1개 = 원자단위**(옛 모델) | 같은 레포 문서화에 등록이 브랜치 수만큼 늘어 사용자 멘탈 모델과 어긋남 → [[decision-repo-registration-flow]] superseded |
| **아무 브랜치 N개 자유 등록**(옛 정책 C) | 역할 구분이 없어 트리거·폴더 정책이 브랜치마다 임의 → 개발/배포 2역할로 고정 |
| **개발/배포 라벨 없이 브랜치만** | 문서 산출이 안 갈림 — 역할이 트리거(compare vs 릴리스)·독자를 정하므로 라벨이 1급 |

## 열린 부분

- 개발/배포 중 **하나만 지정** 허용할지(필수 2 vs 선택) → 후속 grilling.
- 배포 변종이 여럿(pcc30류)일 때 배포 N개로 열지 — 이번엔 고정 2, 확장 후순위.

근거: [[2026-07-06-repo-dev-release-branches]] · 실측: [[2026-07-06-wish-gitlab-api-survey]].
관련: [[decision-repo-registration-flow]](superseded) · [[decision-branch-loss-policy]] · [[decision-docs-hub-folder-rule]] · [[decision-db-source-of-truth]] · [[decision-pull-model]] · [[decision-release-tag-trigger]] · [[overview]]
