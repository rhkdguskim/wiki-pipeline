---
type: question
title: 신규 등록 소스의 첫 문서화 baseline
tags: [registration, baseline, backfill, source-registration]
status: answered
---

# ❓ 신규 등록 소스의 첫 문서화는 어디부터 시작하나

> ✅ **답(2026-07-07): A(null → 전체 코드베이스 initialize)** → [[decision-registration-baseline]].
> 초기 전량 backfill은 정기 야간 배치와 분리된 1급 작업(대시보드 트리거·진행률), 야간 배치는 증분만.
> 위키 잠정안(A 기본 + backfill 분리)과 일치.

`source_branches.last_processed_sha`([[decision-db-source-of-truth]])는 "여기까지 문서화했다"는 포인터다
(등록당 개발·배포 브랜치별로 하나씩 → [[decision-repo-dev-release-registration]]).
**등록 직후 이 값의 초기값**이 첫 배치가 무엇을 문서화할지를 결정한다.

## 선택지

| 초기값 | 첫 배치 동작 | 트레이드오프 |
|--------|-------------|-------------|
| **A. null**(레포 최초 커밋) | 브랜치 전체 역사 문서화 | 완전하나 첫 실행이 폭발적(x-lab 8년치) |
| **B. 등록 시점 HEAD** | 등록 후 변경분만 | 가볍지만 기존 코드는 영원히 미문서화 |
| **C. 사람이 baseline 지정**(태그/sha) | 최근 릴리스부터 등 | 유연하나 등록이 무거워짐 |

## 검토 방향 (미확정)

- **A 기본 + "초기 전량 backfill"을 정기 배치와 분리된 별도 개념으로**. 등록 시
  `last_processed_sha = null`, 첫 처리는 대시보드 트리거 명시적 backfill 작업(진행률 표시),
  정기 야간 배치([[decision-nightly-batch]])는 증분만.
- 이유: "기존 코드 문서화"는 자동화의 핵심 가치라 B는 그걸 버린다. 하지만 A를 야간 배치에 그냥
  태우면 방대한 역사가 한 밤에 터지니 backfill을 1급 개념으로 분리.
- **사용자 최종 승인 전** — grilling 계속 대상.

블로킹 대상: 없음(Phase 1 등록 흐름 완성에는 필요하나 baseline은 운영 시작 시 결정 가능).

근거: [[2026-07-06-registration-grilling]]. 관련: [[decision-repo-dev-release-registration]] · [[decision-nightly-batch]]
