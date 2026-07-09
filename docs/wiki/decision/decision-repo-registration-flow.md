---
type: decision
title: 레포 등록 = 레포별 access token + 브랜치 1개 스코프
tags: [scm, connector, gitlab, token, registration, dashboard]
status: superseded
---

> [!superseded] 이 결정은 대체됨 (2026-07-06)
> "등록 1건 = 레포×브랜치 1개" 원자 단위는 **레포 1개 등록 + 개발/배포 브랜치 2개** 모델로 대체됐다
> → [[decision-repo-dev-release-registration]]. **여전히 유효한 부분**: 토큰 = 스코프(레포별 project
> access token, 사용자 PAT·그룹 토큰·별도 프로젝트 선택 단계 기각), 자동 조회, compare dry-run 검증 —
> 이 등록 메커니즘은 새 결정이 그대로 계승한다. **뒤집힌 부분**: 등록 원자 단위(브랜치 1개 → 레포 1개),
> 다중 등록(→ 등록 안에 dev/release 2브랜치).

# 결정: 대시보드 레포 등록은 "레포별 access token + 브랜치 1개"로 스코프한다

대시보드에서 소스 레포를 등록할 때, 사용자는 **그 레포(프로젝트)에서 발급한 project access token**
(`read_repository` + `api`)을 입력하고 **문서화 대상 브랜치 하나**를 고른다. 프로젝트가 무엇인지는
토큰이 결정하고, 나머지 메타데이터(project id·default_branch·scm 타입·git URL)는 그 토큰으로 자동 조회한다.
**등록 1건 = 브랜치 1개 = 문서화 대상 1개**가 등록의 원자 단위다.

## 등록 흐름 (실측 API 기반)

1. **레포별 project access token 입력** — 사용자 PAT/그룹 토큰이 아니라, 그 프로젝트에서 생성한
   project access token(`read_repository` + `api`). 실측: `GET /projects/:id/access_tokens` → **200**
   (레포 Maintainer면 발급 가능), 그룹 토큰은 **Owner 필요(401)** → [[2026-07-06-wish-gitlab-api-survey]].
   → **토큰이 곧 "어느 레포냐"를 스코프**하므로 별도 프로젝트 선택 단계가 없다.
2. **자동 조회로 채우는 값** — project id·`default_branch`·scm 타입(gitlab)·`http_url_to_repo`를
   전부 토큰으로 `GET /projects/:id`에서 얻는다 (사람이 입력하지 않는다).
3. **브랜치를 사람이 선택 (등록당 1개)** — `GET /projects/:id/repository/branches`의 **모든 브랜치를
   노출**하되 비-기본 브랜치를 고르면 경고한다(정책 C → [[decision-branch-loss-policy]]).
   `default_branch`를 기본값으로 자동 채운다(master/main 혼재라 하드코딩 금지 → [[entity-mirero-gitlab]]).
   pcc30처럼 제품 변종 브랜치가 여럿이면 **각 변종을 별도 등록**으로 취급한다 — 같은 레포를 다른 브랜치로
   여러 번 등록할 수 있고, 각 등록은 `full_namespace_path/branch` 폴더로 갈린다 → [[decision-docs-hub-folder-rule]].
4. **소스별 정책 입력** — 트리거 기준(릴리스 객체/태그/브랜치), 아티팩트 타입 등. 소스가 균질하지 않아
   등록 시 명시가 필요하다(실측 근거: 태그 규칙 4종·아티팩트 타입 상이).
5. **연결 검증(dry-run)** — 등록 확정 전 compare API(`GET /projects/:id/repository/compare`) 200을 확인해
   토큰·브랜치 조합이 실제로 조회 가능한지 검증한 뒤에만 등록을 확정한다.

등록된 값은 서버 DB의 sources 테이블로 들어간다 → [[decision-db-source-of-truth]]. 토큰을 auth 자격으로
쓰는 주체는 SCM 커넥터의 auth 책임이다 → [[decision-scm-connector-abstraction]].

## 기각된 대안

| 대안 | 기각 이유 |
|------|----------|
| **사용자 PAT로 등록** | 토큰이 사람 계정에 묶임 — 그 사람의 권한·재직에 등록이 종속. 레포 스코프도 넓음(계정 전체) |
| **그룹 access token으로 등록** | 발급에 **Owner 권한** 필요(실측 `groups/:id/access_tokens` 401) — 등록자가 갖기 어려움 |
| **별도 프로젝트 선택 단계** | 토큰이 이미 프로젝트를 스코프하므로 불필요 — 선택 UI는 토큰과 어긋날 여지만 만든다 |
| **한 등록에 여러 브랜치 묶기** | **"등록 1건 = 브랜치 1개"로 기각** — compare 라인 추적·트리거 관찰을 단순화. 단 같은 레포를 다른 브랜치로 **여러 번 등록**하는 것은 허용(정책 C, 각 등록이 독립 원자 단위) → [[decision-branch-loss-policy]] |

## 채택 근거

- **토큰 = 스코프**: project access token이 "어느 레포·무슨 권한"을 동시에 정의 → 등록 UI가 토큰 1개 + 브랜치 1개로 최소화.
- **사람에 안 묶임**: 프로젝트 소유의 토큰이라 등록이 특정 계정의 재직·권한 변동과 독립적.
- **레포 Maintainer 선에서 완결**: Owner 권한이 필요한 그룹 토큰과 달리 레포 Maintainer가 자기 레포 토큰을 발급 → 등록이 과제팀 안에서 자족적.

## 파생 효과 (브랜치 1개 스코프)

- **compare 단순화**: compare가 단일 브랜치 라인 추적으로 축소 → 밤 compare의 기준이 그 브랜치다 → [[decision-pull-model]].
- **트리거 축소**: 트리거도 그 브랜치의 릴리스/태그만 관찰 → 폭주 위험이 줄고, 트리거 정책 논의의 범위가 브랜치 1개로 좁혀진다 → [[question-release-object-vs-tag-trigger]].

## 열린 부분

이 결정은 **소스 read 등록**의 스코프·주체를 정한다. docs-hub **write** 토큰과 소스별 최소 권한 조합·아티팩트
read 권한의 프로비저닝은 여전히 열려 있다(그룹 토큰 대신 레포 토큰을 택함으로써 "발급 주체" 축은 좁혀짐) →
[[question-group-token-provisioning]].

관련: [[decision-scm-connector-abstraction]] · [[decision-db-source-of-truth]] · [[decision-pull-model]] · [[entity-mirero-gitlab]] · 근거: [[2026-07-06-wish-gitlab-api-survey]]
