---
type: decision
title: 등록 baseline = A(null → 전체 코드베이스 initialize), backfill은 1급 작업
tags: [registration, baseline, backfill, source-registration]
status: active
---

# 결정: 신규 등록 소스는 last_processed_sha=null로 시작해 전체 코드베이스를 문서화한다

신규 소스를 등록하면 `source_branches.last_processed_sha`([[decision-db-source-of-truth]])의 초기값은 **null**이고,
첫 처리는 **전체 코드베이스를 확인해 문서를 initialize**한다 (선택지 A). 등록당 개발·배포 브랜치별로
하나씩([[decision-repo-dev-release-registration]]).

## 초기 전량 backfill = 정기 야간 배치와 분리된 1급 작업

방대한 역사가 야간 배치([[decision-nightly-batch]]) 한 밤에 터지지 않도록, **초기 전량 backfill**을 별도 1급
작업으로 분리한다:

- **초기 backfill** = 대시보드에서 트리거하는 명시적 작업, 진행률 표시. 등록 직후 전체 코드베이스를 initialize.
- **정기 야간 배치** = 증분(compare diff)만 처리. backfill이 세운 baseline sha 이후의 변경분만.

## 근거

- **"기존 코드 문서화"가 자동화의 핵심 가치** — 등록 시점 HEAD만 잡으면(선택지 B) 기존 코드는 영원히 미문서화로 남아 그 가치를 버린다.
- 그러나 A를 야간 배치에 그냥 태우면 x-lab 8년치 같은 방대한 역사가 한 밤에 폭발한다. backfill을 1급 개념으로 떼어내 진행률·재시도를 별도로 다룬다.
- 위키 잠정안(A 기본 + backfill을 정기 배치와 분리된 별도 개념으로)과 **일치** — 사용자 최종 승인으로 확정.

## 기각 대안

- **B. 등록 시점 HEAD (변경분만)** — 가볍지만 기존 코드가 영원히 미문서화. 자동화의 핵심 가치를 버려 기각.
- **C. 사람이 baseline 지정(태그/sha)** — 유연하나 등록이 무거워지고 사람 판단을 매 등록마다 요구. A + backfill 분리로 유연성 없이도 폭발 문제를 해결.
- **A를 야간 배치에 그대로 태움** — 초기 실행이 폭발적. backfill 분리로 회피.

이 결정이 [[question-initial-backfill-baseline]]을 답한다. 근거: [[2026-07-07-open-questions-decisions]]. 요약: [[summary-open-questions-decisions]].
