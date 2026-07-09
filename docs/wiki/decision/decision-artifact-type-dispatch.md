---
type: decision
title: 아티팩트 타입 dispatch = exe/msi만 · 담당자 자산 선택 · MCP 설치 실행까지
tags: [artifact, manual-pipeline, dashboard, mcp, mvp]
status: active
---

# 결정: 매뉴얼 파이프라인의 아티팩트 타입 dispatch (3건 묶음)

아티팩트 소비 경로가 Generic Package Registry로 확정된([[decision-artifact-consumption]]) 위에서,
소스별 타입 분기·자산 선택·기동 범위가 열려 있었다([[question-artifact-type-dispatch]]).
MVP에 매뉴얼이 포함되면서([[decision-mvp-scope]]) 이 질문이 블로커로 승격돼, 3개 하위 답을 확정한다.
세 답은 서로 밀접해(모두 "담당자가 대시보드에서 명시 · Windows 설치본 집중") 한 결정으로 묶는다.

## 결정 ① 구동 대상 타입 = exe/msi(Windows 설치본)만

nuget·container를 제외하고 **exe/msi만** "구동 가능한 앱"(매뉴얼 대상)으로 삼는다.

- **근거**: nuget = 라이브러리성 자산이라 UI가 없어 구동·관측 불가 → 자연 제외. container = 별도 런타임 환경 부담이 커 MVP에서 미룬다.
- **함의**: container로만 배포되는 소스(예: MCP 서버 이미지 [[entity-remote-control-mcp]])는 MVP 매뉴얼 대상에서 자연히 빠진다. 이는 방치 소스를 담당자가 등록 안 하면 대상에서 빠지는 것과 **같은 결** — "MVP 매뉴얼 대상 밖" → [[question-ci-less-source-policy]] · [[decision-source-manual-curation]].
- **기각**: container 포함 — 컨테이너 런타임을 UI 테스트 호스트에 얹는 부담이 MVP 절단면을 흐린다. Phase 이후로.

## 결정 ② 자산 선택 = 담당자가 대시보드에서 지정

한 릴리스에 자산이 여럿일 때(실측: `MiRcsServer/3.2.2` 자산 11개), **과제 담당자가 app 등록 시
대시보드에서 구동할 설치 자산을 명시 선택**한다(파일명 패턴/명시 지정). 시스템은 규칙으로 자동 판별하지 않는다.

- **근거**: 릴리스마다 자산 명명이 달라(설치기·다중 exe·msi 혼재) 자동 규칙은 오판 위험이 크다. 그 앱을 아는 담당자가 가장 정확히 고른다.
- **정합**: [[decision-scenario-owner-dashboard]](시나리오 세트)·시크릿 등록과 **같은 축** — 시스템 자동 추론이 아니라 담당자 수동 큐레이션. app 등록 정보의 일부로 서버 DB(SoT)에 저장 → [[decision-db-source-of-truth]].
- **기각**: 규칙 기반 자동 판별(예: "가장 큰 msi" / 특정 접미사) — 명명 불규칙성 때문에 오판·유지비가 자동화 이득을 상쇄.

## 결정 ③ MCP 기동 범위 = 전송 + 설치 실행(silent install)까지

원격제어 MCP([[entity-remote-control-mcp]])가 **아티팩트 전송에 더해 설치 스크립트/설치기 실행(silent install)까지**
수행해 앱을 구동 상태로 만든다.

- **근거**: 파이프라인이 "실행 중인 앱"을 관측([[concept-observation-grounding]])하려면 설치까지 자동화돼야 한다. MCP는 파일전송 + UI 자동화 원자 동작(기존 정의) 위에 **설치 실행 오케스트레이션을 얹는다**.
- **정합**: 앱=별도 호스트를 IP/port로 제어하는 연결 모델([[decision-app-host-connection]]) 위에서 동작. 소비 경로(Generic Package Registry)에서 받은 exe/msi를 그 호스트에 전송·설치한다.
- **기각**: 전송까지만(설치는 사람 수동) — 무인 순회가 깨져 매뉴얼 자동 생성의 전제가 무너진다.

## 정합성 — 이번 세션의 일관된 방향

세 답이 한 방향으로 모인다: (1) 시스템이 자동 추론하지 않고 담당자가 대시보드에서 명시(자산 선택),
(2) MVP는 Windows 설치본(exe/msi)에 집중하고 container는 이후, (3) container 제외는
방치 소스 큐레이션과 같은 "MVP 매뉴얼 대상 밖" 처리다.

이 결정이 [[question-artifact-type-dispatch]]를 답한다. 근거: [[2026-07-07-artifact-type-dispatch-decision]]. 요약: [[summary-artifact-type-dispatch]].
관련: [[decision-artifact-consumption]] · [[decision-mvp-scope]] · [[entity-manual-pipeline]]
