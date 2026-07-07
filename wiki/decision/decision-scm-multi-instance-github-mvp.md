---
type: decision
title: SCM 다중 인스턴스 + GitHub 커넥터를 MVP로 승격
tags: [scm, connector, github, gitlab-com, mvp, multi-instance]
status: active
---

# 결정: SCM 다중 인스턴스와 GitHub 커넥터를 MVP 범위로 앞당긴다

소스 등록 단위를 "레포"에서 **"SCM 인스턴스 × 레포"**로 바꾸고, 사내 GitLab(wish.mirero.co.kr)
외에 **gitlab.com·github.com(클라우드)** 레포도 MVP에서 소스로 등록할 수 있게 한다.
[[decision-scm-connector-abstraction]]가 설계한 커넥터 인터페이스(compare·submit·auth 3책임)의
**구현을 MVP로 앞당기는 것** — GitHub 커넥터를 MVP 이후로 미뤘던 [[decision-mvp-scope]]의
"GitLab 1 커넥터" 절단선을 **부분 번복**한다(두 파이프라인 포함 절단선 자체는 유효).

## 무엇이 바뀌나 — 등록 단위 = SCM 인스턴스 × 레포

- **`scm_instances` 테이블 신설** — `kind`(gitlab | github) · `base_url` · `token` · `token_header`.
  사내 GitLab·gitlab.com·github.com이 각각 하나의 인스턴스 행이 된다.
- **`sources`·`doc_targets`가 인스턴스를 참조** — 레포가 어느 인스턴스에 속하는지로 커넥터·엔드포인트·토큰이 결정된다.
  기존 `doc_targets.kind=gitlab` 하드코딩([[2026-07-07-ops-backend-plan]] 진단)을 대체한다 → [[decision-db-source-of-truth]]

## 커넥터 구현 — base_url 주입식 GitLab + 신규 GitHub

- **GitLabConnector는 base_url/token 주입식** — 사내 GitLab과 gitlab.com이 **동일 구현**으로 붙는다
  (인스턴스마다 base_url·token만 다름). [[2026-07-06-wish-gitlab-api-survey]]에서 실증된 사내 API 표면이 gitlab.com에도 그대로 적용된다.
- **GitHubConnector 신규** — compare = `GET /repos/{owner}/{repo}/compare/{base}...{head}`,
  파일 읽기 = contents/git-trees API, submit = Pull Request. GitLab의 3책임과 동일 계약을 GitHub 어법으로 구현.
- **동일 계약 테스트 스위트를 양쪽에 적용** — 커넥터가 계약을 지키는지 GitLab·GitHub 구현 모두 같은 테스트로 검증 → [[concept-port-adapter]]

## 근거

- **사용자 요구** — 소스 레포가 사내 GitLab에만 있지 않고 클라우드(gitlab.com·github.com)에도 존재하므로,
  이들을 MVP에서 못 붙이면 대상 과제 일부가 첫 출시에서 빠진다.
- **커넥터 추상화가 이미 GitHub를 1급으로 설계** — [[decision-scm-connector-abstraction]]가 GitLab·GitHub를 동등한 1급으로 두었으므로,
  MVP 승격은 새 설계가 아니라 **구현 착수 시점을 앞당기는 결정**이다. auth 표에 GitHub PAT도 이미 명시돼 있어 모순 없이 확장된다.
- **다중 인스턴스는 base_url 주입 하나로 흡수** — GitLabConnector를 base_url 주입식으로 두면 인스턴스 수와 무관하게 커넥터 코드는 1벌이다.

## 기각 대안

- **MVP를 GitLab 1 커넥터로 유지** ([[decision-mvp-scope]]의 원래 절단선) — 실측 완료 환경이 사내 GitLab뿐이라
  가장 안전한 절단선이었으나, **사용자가 클라우드 소스 등록을 MVP 요구로 명시**해 기각. 클라우드 SCM은
  아웃바운드 네트워크·토큰 발급이 미확인이라 실측이 선행돼야 한다 → [[question-cloud-scm-network]] · [[question-cloud-scm-token-policy]]

## 남는 열린 질문

- 관리 서버 VM·러너에서 github.com/gitlab.com로의 아웃바운드 HTTPS 경로 (AI API는 확인됨, 클라우드 SCM은 미확인) → [[question-cloud-scm-network]]
- 클라우드 토큰 발급 정책(GitHub PAT 종류·gitlab.com project access token 주체·순환) + GitHub rate limit 대응 → [[question-cloud-scm-token-policy]]

관련: [[decision-scm-connector-abstraction]](구현 승격의 모체) · [[decision-mvp-scope]](부분 번복 대상) · [[decision-db-source-of-truth]] · [[entity-mirero-gitlab]] · [[concept-port-adapter]] · [[overview]]
소스: [[2026-07-07-ops-backend-plan]] · 요약: [[summary-ops-backend-plan]]
