---
type: question
title: CI/릴리스 없는 방치 소스 처리 정책
tags: [source-registration, ci, release, coverage]
status: open
---

# ❓ CI·릴리스가 없는 방치 소스는 어떻게 처리하나

실측([[2026-07-06-wish-gitlab-api-survey]])에서 **ros-codec(1157)** 은 CI 파이프라인이 없고
릴리스 2/커밋 2018년 잔존 상태로 방치돼 있었다. 이는 설계가 암묵적으로 깔던 가정을 깬다.

## 깨진 가정

- "모든 등록 소스에 CI·릴리스가 있다" — 정적 파이프라인은 compare로 돌아 CI 무관하지만,
  **매뉴얼 파이프라인은 릴리스 아티팩트를 트리거·소재로 삼는다**([[decision-release-tag-trigger]] · [[decision-artifact-consumption]]).
  릴리스가 없으면 트리거도 아티팩트도 없다.

## 검토할 것

- 방치/CI-less 소스를 **등록 대상에서 제외**할지, 아니면 정적 파이프라인만 적용(문서만, 매뉴얼 제외)할지.
- 릴리스가 없어도 태그/커밋으로 대체 트리거를 허용할지 → [[question-release-object-vs-tag-trigger]]와 연결.
- "이 소스는 어느 파이프라인 대상인가"를 등록 시 대시보드에서 명시하는 모델([[decision-db-source-of-truth]]).
- 활성/방치 판정 기준(마지막 커밋·릴리스 시점)을 자동 감지할지.

관련: [[entity-mirero-gitlab]] · [[decision-scm-connector-abstraction]]
