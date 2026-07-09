---
type: decision
title: 커밋 히스토리 + 관측으로 매뉴얼 add/update/delete
tags: [lifecycle, commit-history, diff]
status: active
---

# 결정: 매뉴얼 라이프사이클을 커밋 히스토리와 관측의 결합으로 판정한다

기존 완성 매뉴얼(docs-hub) 대비 무엇을 더하고 고치고 지울지를, **커밋 히스토리 신호**와
**UI 전수 순회 관측**을 결합해 판정한다 → [[concept-manual-lifecycle-diff]].

## 두 신호

- **커밋 히스토리** (`last_documented_version` ~ 태그) — 무엇이 추가/제거/변경됐나. 특히 **삭제 탐지에 필수**("UI에 안 보임"만으론 없어진 건지 못 찾은 건지 불확실).
- **UI 순회 관측** — 지금 앱의 현재 상태 ground truth.

| 판정 | 조건 |
|------|------|
| ADD | 히스토리 신규 + 관측 신규 + 기존 매뉴얼에 없음 |
| UPDATE | 히스토리 변경 + 관측이 기존 매뉴얼과 불일치 |
| DELETE | 히스토리 제거 + 관측 부재 (두 신호 모두 "없음") |

## 삭제는 파괴적 → 이중 게이트

DELETE는 자동 삭제가 아니라 **MR에 "삭제 제안"으로 올리고 사람이 최종 확인** → [[decision-mr-review-gate]].
오검출로 멀쩡한 매뉴얼이 사라지는 것 방지 → [[question-manual-delete-safety]].

## 기각 대안

- **매 실행 전체 재생성** — 단순하나 리뷰 부담이 크고, 안 바뀐 매뉴얼의 diff 노이즈로 삭제/변경 신호가 묻힌다.
- **관측만으로 판정** — 삭제를 안전하게 못 가린다(부재 ≠ 제거).

멱등성: 버전 포인터는 MR 성공 후에만 전진 → [[concept-idempotent-sha]]. 원본: [[2026-07-05-manual-extraction-pipeline]]
