---
type: decision
title: 릴리스/버전 태그 트리거 (매뉴얼 파이프라인)
tags: [trigger, release, tag]
status: active
---

# 결정: 매뉴얼 파이프라인은 릴리스/버전 태그에 트리거된다

[[entity-manual-pipeline]]은 코드 커밋마다가 아니라 **릴리스/버전 태그**가 찍힐 때 실행된다.

## 근거

- **행위 기반 문서는 화면이 바뀔 때 의미** — 커밋 하나하나는 UI를 바꾸지 않는 경우가 많다. 릴리스 단위가 "사용자가 보는 앱이 실제로 바뀐" 자연 경계.
- **UI 자동화는 무겁다** — 앱 배포·기동·전수 순회는 정적 분석보다 비싸다. 매 커밋 실행은 과함.
- 아티팩트 소비와 짝 → [[decision-artifact-consumption]].

## 기각 대안

- **야간 배치 편입** (기존 [[decision-nightly-batch]]처럼 매일 밤) — 정적 파이프라인엔 맞지만 앱은 매일 바뀌지 않아 낭비. 매뉴얼 파이프라인은 다른 리듬으로 둔다.
- **커밋마다(push)** — [[decision-pull-model]]에서 정적 문서용으로 이미 기각된 이유(비용·폭주)가 여기선 UI 구동 비용까지 더해 더 크다.

## 실측 근거 (2026-07-06) — 태그보다 Release 객체가 안전

[[2026-07-06-wish-gitlab-api-survey]] 실측이 이 결정의 신호 선택을 날카롭게 했다:
- 태그 규칙이 소스마다 4종+ 제각각(`MiRcsServer/3.2.2`·`version/ROC/…`·`version/2000`) → 태그 이름 파싱 불안정.
- **태그 ≫ 릴리스**(pcc30 125:1, smart-ros 33:0) → 태그 트리거는 폭주 위험.
- `GET /projects/:id/releases`는 200이고 Release 객체가 아티팩트 링크를 직접 물음 → 소비([[decision-artifact-consumption]])와 짝.

→ 이 결정 안에서 **태그가 아닌 Release 객체를 트리거 신호로 좁힐지**는 미해결로 승격 → [[question-release-object-vs-tag-trigger]]. 릴리스가 아예 없는 방치 소스 처리와 경계를 나눈다 → [[question-ci-less-source-policy]].

수동 트리거는 대시보드에서 병행 가능. 원본: [[2026-07-05-manual-extraction-pipeline]] · [[2026-07-06-wish-gitlab-api-survey]]
