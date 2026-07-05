---
type: concept
title: sha 포인터 멱등성 패턴
tags: [idempotency, compare-api, reliability]
status: active
---

# sha 포인터 멱등성 패턴

`last_processed_sha` = 소스별 "어디까지 문서에 반영했는지" 포인터.
이 하나의 규칙이 **유실 방지 · 재실행 안전 · 디바운스**를 모두 해결한다.

## 규칙

```
성공: compare → 생성 → MR 생성 성공 → 완료 보고 → sha 전진
실패: 어느 단계든 실패 → sha 그대로 → 다음 run이 같은 구간 재처리
```

- sha 전진은 소스 단위 — A 성공·B 실패면 B만 재처리
- 재처리 시 열린 자동 MR을 갱신 → 중복 MR 없음 ([[decision-mr-review-gate]])

## compare API 디바운스

`from=last_processed_sha&to=HEAD` 구간의 **최종 변경 파일 집합**만 받는다.
커밋 20개든 100개든 같은 문서에 대한 변경은 하나로 병합 — 큐/디바운스 코드가 필요 없다.
[[decision-pull-model]]이 성립하는 기술적 근거.

## 방어 로직

- **baseline**: 신규 소스 등록 시 초기값 = 등록 시점 HEAD (비우면 첫 배치가 전체 히스토리 처리 사고)
- **sha 무효화**(force-push/rebase): 조상 여부 검증 → 무효 시 "최근 N일" fallback + 경고. 예방: main protect

전체 그림: [[overview]] · 상세: `../../docs/features/mr.md`, `../../docs/features/change-detection.md`
