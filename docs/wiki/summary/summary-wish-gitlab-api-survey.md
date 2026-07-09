---
type: summary
title: wish GitLab API 실측 조사 요약
tags: [gitlab, api, survey, measured]
status: active
---

# 요약: wish GitLab API 실측 조사 (2026-07-06)

사내 GitLab(`http://wish.mirero.co.kr/`)에 실제 로그인해 인증된 상태로, 문서 자동화 파이프라인이
**사용해야 하고 접근 가능한 API 표면**을 실측한 기록. 일반 사용자 계정(`api` scope OAuth 토큰) 기준,
조사 후 토큰 revoke. 원본: [[2026-07-06-wish-gitlab-api-survey]] (불변).

## 확정 사실 (fact — entity/decision에 반영)

- **인스턴스**: GitLab **16.3.0 Community Edition**(`enterprise:false`), KAS 활성, OIDC issuer `http://…`(endpoint `https://`).
  일반 계정 접근 규모 **610 프로젝트**, 100+ 그룹 → [[entity-mirero-gitlab]].
- **파이프라인 책임별 API가 실증됨**: compare 200 / MR 200 → 커넥터 3책임(compare/submit)이 실물로 확인 → [[decision-scm-connector-abstraction]].
- **CE에는 `/approvals`가 없다(404)** → approval rule로 리뷰 게이트를 *강제*할 수 없다. 우리 MR 게이트는 관례 기반이라 모순 아님(근거 보강) → [[decision-mr-review-gate]].
- **아티팩트 실체 = Generic Package Registry**(`/packages/generic/…`). 릴리스 자산 11개가 전부 이 경로로 서빙됨 → [[decision-artifact-consumption]].
- **러너 = Windows**(PowerShell·msbuild·windows_build_base), **git LFS 사용** → [[decision-runner-git-clone]].
- **MCP 컨테이너가 이미 실물로 존재**(ros-sw-rcs registry에 `mivncmcpserver` 등) — 원격 제어 MCP가 가설이 아님 → [[entity-remote-control-mcp]].

## 파생된 미해결 질문 (question — status: open)

- 트리거를 태그가 아닌 **Release 객체**로 할지 (태그 규칙 4종·태그≫릴리스 폭주) → [[question-release-object-vs-tag-trigger]].
- **CI/릴리스 없는 방치 소스**(ros-codec류) 처리 정책 → [[question-ci-less-source-policy]].
- 기존 CI **`docs` stage**(ros-sw-rcs)와 우리 자동화의 공존/대체 → [[question-existing-ci-docs-stage]].
- GitLab 내장 **blob 검색 vs 코드 인덱스**(CodeScene/codegraph) 역할 중복 → [[question-blob-vs-code-index-overlap]].
- **아티팩트 타입 소스별 대응**(exe/msi/nuget/container) → [[question-artifact-type-dispatch]].
- **최소 권한 group access token** 설계 (발급이 Owner 권한·소스별 멤버십 상이) → [[question-group-token-provisioning]].

## 핵심 관찰

- default branch가 `master`/`main` 혼재 → 하드코딩 금지, API 조회 필수.
- 같은 계정도 **소스마다 접근 레벨이 다름**(x-lab registry 403 vs ros-sw-rcs registry 200) → 권한은 소스별 실측 필요.
- 웹훅·스케줄 0개 → 사내에 이벤트 구독/자동 스케줄 인프라 부재 → **pull 모델이 현실적** → [[decision-pull-model]].
- CE는 Advanced Search(Elasticsearch) 미탑재 → blob 검색은 기본 인덱스 수준, 코드 인덱스의 대체 아님(보완).
