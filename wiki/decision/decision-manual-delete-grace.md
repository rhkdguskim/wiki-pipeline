---
type: decision
title: 매뉴얼 삭제 = deprecated 유예 후 삭제 (이중 게이트)
tags: [manual, delete, safety, phase-2]
status: active
---

# 결정: 매뉴얼 DELETE는 즉시 삭제하지 않고 deprecated 표시 + 유예 기간 후 삭제한다

[[decision-commit-history-manual-diff]]의 DELETE 판정은 파괴적이다. 두 신호(커밋 히스토리 제거 + 관측 부재)가
DELETE를 가리켜도 **즉시 물리 삭제하지 않고**, deprecated 표시로 유예한 뒤 정해진 기간 후 삭제한다.

## 흐름

1. DELETE 판정(커밋 히스토리 + 관측 부재) → 매뉴얼을 `deprecated` 상태로 전환 (표시만, 본문 유지)
2. **유예 기간**(기본값 미정 — 운영 데이터로 산정) 동안 deprecated 표시 노출
3. 유예 만료 + 추가 신호 없음 → 그 때 삭제
4. 유예 중 관측이 다시 잡히거나 히스토리 정정 → `deprecated` 해제·복원

## 근거

- DELETE의 두 신호는 모두 위양(false positive) 가능 — "리팩터링 vs 기능 제거" 오분류, "순회 실패로 관측 못 함" 우려([[question-ui-coverage-completeness]])를 신호로 쓰면 오삭제.
- deprecated 유예는 되돌릴 수 없는 행위(물리 삭제)를 최후로 미룬다 — 유예 중 복원 비용은 표시 토글이면 충분.
- MR 사람 확인 게이트([[decision-mr-review-gate]])와 겹쳐 3중 안전망: 판정 → deprecated 표시 → 사람 확인 → 유예 만료 후 삭제.

## 기각 대안

- **즉시 DELETE + MR 강제** — 빠르지만 사람이 놓치면 오삭제가 곧장 물리 삭제. 되돌릴 수 없다.
- **Phase 1에 삭제 자체 비활성화(추가만)** — 가장 안전하지만 DELETE 필요 케이스가 Phase 2에 이미 보이므로, 유예 게이트로 다루는 쪽이 실용.

## 열린 부분

- 유예 기간 기본값(N일) — 운영 데이터·삭제 빈도로 산정 → 본 페이지 갱신
- "기능 제거" 신뢰적 식별(리팩터링 구분)은 여전히 열림 → [[question-manual-delete-safety]]의 본 질문이 해소될 때까지 deprecated 게이트가 완충

이 결정이 [[question-manual-delete-safety]]의 안전 장치 질문을 답한다.
