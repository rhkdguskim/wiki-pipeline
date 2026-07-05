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
| **auth** | 소스 read + docs-hub write 최소 권한 토큰 | group access token | GitHub 토큰(PAT) |

- 소스 레포는 서버 DB에 `scm: gitlab | github` 타입과 함께 등록되고, 그 타입으로 커넥터가 선택된다 → [[decision-db-source-of-truth]]
- 커넥터는 SCM 세부(엔드포인트·리뷰요청 명칭·인증)만 바꾸고, 파이프라인 상위 로직은 공유한다.

## 변하지 않는 것 (커넥터 무관)

- **pull 모델** — 커넥터의 compare로 밤에 직접 조회. 소스 레포 무수정 → [[decision-pull-model]]
- **sha 포인터 멱등성** — sha 전진은 submit 성공 후에만. SCM 무관 → [[concept-idempotent-sha]]
- **사람 리뷰 게이트** — GitLab MR = GitHub PR, 둘 다 사람이 머지 (AI 자동 머지 금지) → [[decision-mr-review-gate]]

관련: [[entity-mirero-gitlab]] · [[overview]] · 소스: [[2026-07-05-multi-scm-connector]]
