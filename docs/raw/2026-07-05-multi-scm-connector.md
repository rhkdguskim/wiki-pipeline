# 다중 SCM 커넥터 도입 지시 (GitLab + GitHub)

> 2026-07-05 설계 지시 기록 (불변). 형상관리 연동을 커넥터 인터페이스로 추상화한다.

## 지시 요지

- 지금까지 형상관리(SCM) 연동은 **GitLab 전용** — compare API로 변경 감지, MR로 제출, group access token 인증.
- **GitLab과 GitHub 둘 다 연동 가능하게 만든다.** 형상관리 연동을 **2개의 커넥터**(GitLab · GitHub)로 가져간다.
- 두 SCM은 **동등한 1급 연동 대상**이다. SCM 접근을 단일 인터페이스 뒤로 추상화하고 GitLab/GitHub 두 구현을 둔다. 소스 레포는 어느 SCM에 있든 동일 파이프라인으로 처리된다.

## 유지되는 골격

pull 모델 · 야간 배치 · MR/PR 리뷰 게이트 · sha 멱등 전진이라는 기존 설계 골격은 그대로 유지하되,
SCM 종속 지점(compare · submit · auth)만 커넥터로 교체 가능하게 분리한다.

## SCM별 대응 매핑

| 책임 | GitLab | GitHub |
|------|--------|--------|
| 변경 파일 집합 조회 | compare API (`/projects/:id/repository/compare`) | compare API (`/repos/{owner}/{repo}/compare/{base}...{head}`) |
| 문서 변경 제출 | Merge Request | Pull Request |
| 인증 | group access token | GitHub 토큰(PAT) |
| 열린 자동 MR/PR 갱신 | 동일 소스 MR 갱신 | 동일 소스 PR 갱신 |

소스 레포는 서버 DB에 `scm: gitlab | github` 타입과 함께 등록되어, 그 타입으로 커넥터가 선택된다.
