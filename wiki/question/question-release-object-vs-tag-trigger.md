---
type: question
title: 트리거를 태그가 아닌 Release 객체로 할지
tags: [trigger, release, tag, manual-pipeline]
status: open
---

# ❓ 매뉴얼 파이프라인 트리거 = 태그 vs Release 객체

[[decision-release-tag-trigger]]는 "릴리스/버전 태그"에 트리거한다고 정했다. 실측
([[2026-07-06-wish-gitlab-api-survey]])이 이 결정 안에서 **태그 vs Release 객체** 중 무엇을 신호로
삼을지를 날카롭게 만든다.

## 실측이 드러낸 문제

- **태그 규칙이 소스마다 제각각(4종+)**: `MiRcsServer/3.2.2`, `version/ROC/Siltron_Ev/1.1.1`,
  `version/SmartROS/SDCA6/1.2.10`, `version/2000` — 태그 이름 파싱으로 "릴리스"를 식별하는 규칙이 소스마다 필요.
- **태그 ≫ 릴리스**: pcc30 125:1, smart-ros 33:0. 태그를 트리거로 쓰면 폭주하거나, 릴리스 아닌 태그까지 잡음.
- `GET /projects/:id/releases`는 200이고 **Release 객체는 자산 링크(Generic Package)를 직접 물고 있다**
  → 아티팩트 소비([[decision-artifact-consumption]] · [[question-artifact-type-dispatch]])와 자연스럽게 짝.

## 검토할 것

- 트리거 신호를 **Release 객체 생성**(`/releases`)으로 좁히면 태그 폭주·규칙 파싱을 회피하나,
  릴리스를 안 만드는 소스(smart-ros 33/0, pcc/ros-common 0/0)는 트리거가 영영 안 걸림.
- 릴리스 없는 소스는 어떻게? — [[question-ci-less-source-policy]]와 겹치는 경계.
- 소스별로 트리거 방식을 대시보드에서 고르게 할지(태그 정규식 vs Release 이벤트) → [[decision-schedule-per-source]]의 과제별 설정 사상과 정합.

관련: [[decision-release-tag-trigger]] · [[question-schedule-policy]] · [[entity-mirero-gitlab]]
