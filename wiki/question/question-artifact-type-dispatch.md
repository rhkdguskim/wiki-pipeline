---
type: question
title: 아티팩트 타입 소스별 대응 (exe/msi/nuget/container)
tags: [artifact, package-registry, manual-pipeline]
status: answered
---

# ❓ 소스별 아티팩트 타입을 어떻게 획득·배포·기동하나

> ✅ **답(2026-07-07): exe/msi만 구동 대상 · 자산은 담당자가 대시보드에서 지정 · MCP가 설치 실행(silent install)까지** → [[decision-artifact-type-dispatch]].
> nuget은 UI 없어 자연 제외, container는 MVP 이후. container로만 배포되는 소스(MCP 이미지 등)는
> "MVP 매뉴얼 대상 밖"으로 자연히 빠지며, 이는 방치 소스 수동 큐레이션([[question-ci-less-source-policy]] · [[decision-source-manual-curation]])과 같은 결이다.

아티팩트 소비 경로가 **Generic Package Registry로 확정**됐다(실측
[[2026-07-06-wish-gitlab-api-survey]] · 사실은 [[decision-artifact-consumption]]에 반영). 그
경로 위에서 **소스마다 아티팩트 타입이 다르다**는 미해결 문제가 남는다.

## 실측 사실 (확정)

- ros-sw-rcs 릴리스 `MiRcsServer/3.2.2`의 자산 11개가 전부 `/projects/947/packages/generic/…`로 서빙
  (`…Setup(for WindowNT).exe`, `AutoInstaller.exe`, `.msi` 등). `packages`에 generic·nuget 병존.
- 컨테이너 아티팩트는 별도 `registry/repositories` 경로(MCP 이미지 실물).

## 검토했던 것 (→ 모두 [[decision-artifact-type-dispatch]]에서 답)

- 매뉴얼 파이프라인이 **타입별로 배포·기동**을 달리해야 함: exe/msi는 설치 실행, nuget은 라이브러리(구동 대상 아님?),
  container는 컨테이너 런타임 기동. 어떤 타입이 "구동 가능한 앱"인가. → **답 ①**: exe/msi만 구동 대상.
- 한 릴리스에 자산 11개 — **어느 자산을 문서화 대상으로 고르나**(설치본 1개? 다중?). 자산 선택 규칙. → **답 ②**: 담당자가 대시보드에서 지정.
- MCP 파일전송([[entity-remote-control-mcp]])이 타입별 배포를 어디까지 처리하나(설치 스크립트 실행 포함?). → **답 ③**: 전송 + 설치 실행(silent install)까지.
- nuget/라이브러리성 자산만 있는 소스는 매뉴얼 대상에서 빠지나 → [[question-ci-less-source-policy]]와 경계. → **답**: 빠짐(nuget 자연 제외 · container로만 배포되는 소스는 "MVP 매뉴얼 대상 밖").

관련: [[decision-artifact-consumption]] · [[decision-release-tag-trigger]] · [[entity-remote-control-mcp]]
