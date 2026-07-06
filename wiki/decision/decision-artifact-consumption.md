---
type: decision
title: 소스 빌드 대신 릴리스 아티팩트 소비
tags: [artifact, build, release]
status: active
---

# 결정: 파이프라인은 빌드하지 않고 아티팩트를 소비한다

[[entity-manual-pipeline]]은 앱을 소스에서 빌드하지 않는다. 빌드는 기존 CI가 담당하고 릴리스가
아티팩트를 생성하므로, 파이프라인은 **그 버전의 아티팩트를 가져와** MCP 파일전송으로 배포한다
→ [[entity-remote-control-mcp]].

## 근거

- **빌드 책임 중복 제거** — 빌드 파이프라인은 이미 존재·검증됨. 다시 빌드하면 도구체인·환경을 이중 유지해야 함.
- **릴리스가 곧 소재** — 릴리스 아티팩트는 "문서화 대상 버전"의 정확한 산출물이다. 트리거와 짝 → [[decision-release-tag-trigger]].

## 기각 대안

- **파이프라인 내 재빌드** — 아티팩트 획득 실패에 독립적이라는 장점은 있으나, 빌드 환경·의존성·서명까지 복제해야 해 비용이 크고 "릴리스된 그 바이너리"와 어긋날 위험.

## 실측 확인 (2026-07-06) — 아티팩트 실체 = Generic Package Registry

[[2026-07-06-wish-gitlab-api-survey]]에서 "그 버전의 아티팩트"의 실체가 확정됐다: ros-sw-rcs 릴리스
`MiRcsServer/3.2.2`의 자산 11개가 전부 `/api/v4/projects/947/packages/generic/…`로 서빙됐다
(`…Setup(for WindowNT).exe`·`AutoInstaller.exe`·`.msi` 등). `packages`에 generic·nuget 병존, 컨테이너는 registry.
→ 소비 경로는 Job artifacts가 아니라 **Generic Package(+nuget/컨테이너)**가 정석. 이 사실은 결정을 실증한다.
소스별 타입(exe/msi/nuget/container) 획득·기동 분기는 미해결로 승격 → [[question-artifact-type-dispatch]].

관련: [[entity-manual-pipeline]] · [[entity-mirero-gitlab]] · 원본: [[2026-07-05-manual-extraction-pipeline]] · [[2026-07-06-wish-gitlab-api-survey]]
