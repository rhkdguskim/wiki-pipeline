---
type: summary
title: 아티팩트 타입 dispatch 결정 세션 요약
tags: [artifact, manual-pipeline, mvp]
status: active
---

# 요약: 2026-07-07 아티팩트 타입 dispatch 결정 세션

원본: [[2026-07-07-artifact-type-dispatch-decision]]

MVP에 매뉴얼 파이프라인이 포함되면서([[decision-mvp-scope]]) 블로커로 승격된
[[question-artifact-type-dispatch]]를 grilling해 3개 하위 답을 확정했다. 아티팩트 소비 경로는
이미 Generic Package Registry로 확정된 상태([[decision-artifact-consumption]], 실측
[[2026-07-06-wish-gitlab-api-survey]])였고, 그 위의 타입 분기가 열려 있었다.

## 요지 (파생 결정 → [[decision-artifact-type-dispatch]])

- **① 구동 대상 타입 = exe/msi만** — nuget은 UI 없어 자연 제외, container는 MVP 이후. container로만 배포되는 소스(MCP 이미지 등)는 MVP 매뉴얼 대상에서 자연히 빠짐 → [[question-ci-less-source-policy]]와 같은 결.
- **② 자산 선택 = 담당자가 대시보드에서 지정** — 릴리스 자산 다수 중 구동할 설치 자산을 담당자가 명시 선택. 자동 규칙 판별 안 함. [[decision-scenario-owner-dashboard]]와 같은 수동 큐레이션 축.
- **③ MCP 기동 범위 = 전송 + 설치 실행(silent install)까지** — 앱을 구동 상태로 만들어 관측 가능하게. [[entity-remote-control-mcp]]가 설치 실행 오케스트레이션을 얹음.

세 답이 "시스템 자동 추론 대신 담당자 대시보드 명시 · Windows 설치본 집중"이라는 일관 방향을 따라
단일 decision 페이지로 묶였다.
