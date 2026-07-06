---
type: decision
title: 형상관리 연동을 커넥터로 추상화 (GitLab + GitHub)
tags: [scm, connector, gitlab, github, compare-api, mr]
status: active
---

# 결정: 형상관리(SCM) 연동을 커넥터 인터페이스로 추상화하고 GitLab·GitHub 두 커넥터를 지원한다

소스 레포에 접근하는 모든 SCM 종속 동작을 단일 **커넥터 인터페이스** 뒤로 숨긴다.
파이프라인·서버는 커넥터를 통해서만 SCM과 대화하며, 대상이 어느 SCM인지 알 필요가 없다.
**GitLab과 GitHub는 동등한 1급 연동 대상**이다 — 소스 레포는 둘 중 어디에 있든 동일 파이프라인으로 처리된다.

## 커넥터 인터페이스 (3책임)

| 책임 | 역할 | GitLab 구현 | GitHub 구현 |
|------|------|-------------|-------------|
| **compare** | 두 sha 사이 변경 파일 집합 조회 | compare API | compare API |
| **submit** | 문서 변경을 브랜치+리뷰요청으로 제출·갱신 | Merge Request | Pull Request |
| **auth** | 소스 read + docs-hub write 최소 권한 토큰 | 소스 read = 레포별 project access token(확정) / docs-hub write = 미확정 | GitHub 토큰(PAT) |

- **auth 두 축**: 소스 read는 레포별 project access token으로 확정(그룹 토큰은 Owner 권한이라 기각) → [[decision-repo-dev-release-registration]]. docs-hub write 토큰의 발급 주체는 여전히 열림 → [[question-group-token-provisioning]].
- 소스 레포는 서버 DB에 `scm: gitlab | github` 타입과 함께 등록되고, 그 타입으로 커넥터가 선택된다 → [[decision-db-source-of-truth]]
- 커넥터는 SCM 세부(엔드포인트·리뷰요청 명칭·인증)만 바꾸고, 파이프라인 상위 로직은 공유한다.
- 코드 인덱스 파이프라인이 요구하는 소스 전체 확보(checkout)를 4번째 책임으로 넣을지는 미확정 → [[question-scm-checkout]]

## 변하지 않는 것 (커넥터 무관)

- **pull 모델** — 커넥터의 compare로 밤에 직접 조회. 소스 레포 무수정 → [[decision-pull-model]]
- **sha 포인터 멱등성** — sha 전진은 submit 성공 후에만. SCM 무관 → [[concept-idempotent-sha]]
- **사람 리뷰 게이트** — GitLab MR = GitHub PR, 둘 다 사람이 머지 (AI 자동 머지 금지) → [[decision-mr-review-gate]]

## 실측 확인 (2026-07-06) — GitLab 구현이 실물 API로 실증됨

[[2026-07-06-wish-gitlab-api-survey]]에서 GitLab 커넥터의 3책임이 일반 권한으로 전부 200 확인됐다:
**compare** = `GET /projects/:id/repository/compare`(두 sha → `diffs[].new_path`), **submit** = `GET/POST /merge_requests`,
**auth** = OAuth/PAT/프로젝트·그룹 access token. 단 **auth의 group access token 발급은 Owner 권한**이라 열린 설계점이 있고
([[question-group-token-provisioning]]), 이 인스턴스는 CE라 MR approval rule은 부재 → 게이트는 관례 기반 → [[decision-mr-review-gate]].

관련: [[entity-mirero-gitlab]] · [[concept-port-adapter]] · [[overview]] · 소스: [[2026-07-05-multi-scm-connector]] · [[2026-07-06-wish-gitlab-api-survey]]
