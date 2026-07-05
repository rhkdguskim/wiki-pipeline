---
type: question
title: 매뉴얼 삭제 판정의 안전성은 충분한가?
tags: [phase-2, delete, safety]
status: answered
---

# ❓ 매뉴얼 삭제 판정의 안전성은 충분한가?

[[decision-commit-history-manual-diff]]의 DELETE는 파괴적이다. "커밋 히스토리 제거 + 관측 부재"
두 신호 + MR 사람 확인의 이중 게이트로 충분한가?

- 커밋 히스토리에서 "기능 제거"를 어떻게 신뢰성 있게 식별하나 (리팩터링과 구분)?
- 관측 부재가 순회 실패(도달 못 함) 때문일 때 오삭제를 어떻게 막나 → [[question-ui-coverage-completeness]]와 얽힘.
- 삭제 대신 `deprecated` 표시 후 유예하는 단계가 필요한가?

## ✅ 답 (안전 장치, 2026-07-05)

**deprecated 표시 + 유예 기간 후 삭제** → [[decision-manual-delete-grace]]. 즉시 DELETE/삭제 자체 비활성화는 기각. "기능 제거" 신뢰적 식별(리팩터링 구분)은 여전히 열림 — deprecated 게이트가 완충하므로 본 question의 안전 장치 질문은 답함.

관련: [[decision-mr-review-gate]]
