---
type: decision
title: 인덱싱 소스 확보 = 러너 git clone (커넥터 4책임 확장 기각)
tags: [code-index, scm, checkout, git]
status: superseded
---

> [!superseded] 이 결정은 대체됨 (2026-07-06)
> 코드 인덱스가 중앙 파이프라인 범위에서 제외되어 인덱싱용 소스 확보 자체가 불필요해졌다
> → [[decision-code-index-out-of-pipeline]]. **여전히 유효한 부분**: 커넥터 3책임(compare/submit/auth)
> 비대화 방지 원칙, 그리고 실측 사실(러너=Windows · ros-sw-rcs git LFS — [[entity-mirero-gitlab]] 보유).

# 결정: 인덱싱용 소스 전체 확보는 러너가 git clone으로 한다

코드 인덱싱에 필요한 소스 전체(레포@sha 작업 트리)는 SCM 커넥터를 거치지 않고
**러너가 git clone/fetch로 직접** 확보한다. 인증 토큰만 커넥터의 auth 책임에서 얻는다.

## 근거

- 커넥터는 "SCM마다 다른 것"(compare·MR/PR API·인증)을 숨기는 게 존재 이유 — **git 프로토콜은 SCM 중립**이라 숨길 차이가 없다
- 커넥터 인터페이스([[decision-scm-connector-abstraction]])는 3책임(compare/submit/auth) 그대로 유지 — 인터페이스 비대화 방지

## 기각 대안

- **커넥터 4번째 책임(checkout) 추가** — 모든 SCM 접근이 커넥터로 일원화되는 일관성은 있으나,
  SCM 간 차이가 없는 동작까지 추상화해 인터페이스만 무거워진다

## 실측 근거 (2026-07-06)

[[2026-07-06-wish-gitlab-api-survey]]에서 러너/체크아웃 환경이 확인됐다: `http_url_to_repo`(clone)·
`repository/archive.zip` 모두 200이고, ros-sw-rcs는 **git LFS를 사용**한다(clone 시 `git lfs` 필요). CI가
PowerShell(`.ps1`)·msbuild·windows_build_base를 쓰므로 **러너는 Windows**다 — 인덱싱용 clone/fetch도 Windows
러너에서 LFS 포함해 수행해야 한다.

[[question-scm-checkout]]의 답. 관련: [[decision-code-index-pipeline]] · [[entity-mirero-gitlab]] · 소스: [[2026-07-05-code-index-followup]] · [[2026-07-06-wish-gitlab-api-survey]]
