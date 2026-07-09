---
type: decision
title: pull 모델 채택 (push 기각)
tags: [trigger, compare-api]
status: active
---

# 결정: pull 모델 채택

docs-hub가 구독 목록을 보유하고, 밤에 각 소스 레포를 compare API로 직접 조회한다.
소스 레포는 아무것도 하지 않는다.

## 기각된 대안

| 대안 | 기각 이유 |
|------|----------|
| push 즉시 실행 (커밋마다 trigger job) | 커밋마다 AI 호출 → 비용·부하·리뷰 폭주 |
| push 수집 + 야간 배치 (큐) | 큐 인프라의 push 충돌·유실·완료표시 관리 부담. 소스 레포마다 CI 수정 = 과제 담당자 협조 필요 |

## 채택 근거

- **소스 레포 무수정** — 온보딩 = 서버에 등록 1건
- **큐 불필요** — 커밋 히스토리 자체가 큐. compare API가 커밋 N개를 변경 파일 집합 1개로 병합 → [[concept-idempotent-sha]]. compare는 SCM 커넥터가 제공(GitLab·GitHub 공통) → [[decision-scm-connector-abstraction]]
- 야간 배치라 실시간성 포기는 트레이드오프가 아님 → [[decision-nightly-batch]]
- **compare가 404를 만나면**(브랜치·레포 소실) 소스를 자동 비활성화하고 알린다(재활성화는 protected 분기) → [[decision-branch-loss-policy]]

## 적용 범위 (2026-07-05 한정)

push 기각 근거(커밋마다 AI 호출 → 비용·리뷰 폭주)는 **AI 문서 파이프라인 전제**다.
비-AI인 코드 인덱스 파이프라인이 같은 pull 메커니즘을 짧은 주기 폴링으로 재사용할 계획이었으나
([[decision-code-index-pipeline]]), 그 파이프라인 자체가 2026-07-06 범위에서 제외됐다
→ [[decision-code-index-out-of-pipeline]]. "주기는 파이프라인별 정책"이라는 원칙은 유효하다.

결정 과정: [[summary-design-session]] · 전체 그림: [[overview]]
