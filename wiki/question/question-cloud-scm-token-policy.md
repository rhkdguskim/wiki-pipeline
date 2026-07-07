---
type: question
title: 클라우드 SCM 토큰 발급 정책 (GitHub PAT·gitlab.com 토큰·rate limit)
tags: [scm, github, gitlab-com, auth, token, rate-limit]
status: open
---

# 질문: 클라우드 SCM 토큰을 어떻게 발급·순환하고 rate limit에 어떻게 대응하는가

[[decision-scm-multi-instance-github-mvp]]로 github.com·gitlab.com 레포를 소스로 등록하면,
각 인스턴스의 auth 토큰(`scm_instances.token`)을 **어떻게 발급하고 순환하는가**가 열린다. 사내 GitLab의
project access token 정책([[decision-repo-dev-release-registration]])이 클라우드에는 그대로 적용되지 않는다.

## 미확정 지점

- **GitHub 토큰 종류** — fine-grained PAT(레포·권한 세분) vs classic PAT. 소스 read + docs-hub write 최소 권한을
  어느 쪽으로 확보하는가.
- **gitlab.com 토큰 주체·순환** — gitlab.com project access token의 발급 주체(누가 만드나)와 순환 주기.
- **GitHub rate limit** — 인증 요청 5000 req/h 상한. 다수 레포×야간 배치 compare 호출이 이 상한에 걸리지 않도록
  하는 대응(호출 예산·백오프·캐싱)이 필요하다.

## 사내 GitLab과의 관계

사내 GitLab의 group access token 발급 주체 문제는 별도로 열려 있다 → [[question-group-token-provisioning]].
이 질문은 그 **클라우드 판**이며, 인스턴스별로 정책이 갈릴 수 있다(`scm_instances`가 인스턴스 단위로 토큰을 갖는 이유).

## 답이 나오면

토큰 발급·순환·rate limit 대응이 확정되면 decision으로 승격하고 이 질문을 `answered`.

관련: [[decision-scm-multi-instance-github-mvp]] · [[question-cloud-scm-network]] · [[question-group-token-provisioning]] · [[decision-repo-dev-release-registration]]
소스: [[2026-07-07-ops-backend-plan]]
