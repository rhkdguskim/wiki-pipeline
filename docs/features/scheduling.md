# 스케줄 · 수동 트리거 (FR-4, FR-10)

← [문서 인덱스](../README.md)

커밋마다 AI를 실행하지 않고 **야간 배치**로 모으는 것이 비용·부하·리뷰 폭주를 막는 핵심 결정이다
([vision P2](../vision.md)). 실시간성은 의도적으로 포기한다 ([goals N1](../goals.md)).

## 요구사항

| ID | P | 요구사항 |
|----|---|----------|
| FR-4 | P0 | **야간 스케줄 실행**: 서버 내장 스케줄러(cron 식 설정 가능, 기본 평일 20:00)가 활성 소스 전체를 대상으로 run 생성 후 GitLab 파이프라인 트리거 |
| FR-10 | P1 | **수동 트리거**: 대시보드/API에서 특정 소스(복수) 또는 전체 대상 즉시 실행. `full`(전체 재생성) 옵션 지원. 동일 소스가 실행 중이면 중복 트리거 거부(락) |

## 스케줄러 위치: 서버 내장 cron

GitLab pipeline schedule이 아닌 **관리 서버의 BackgroundService**에 둔다.
스케줄·수동 트리거·상태가 대시보드 한 화면에서 통제되기 때문 ("다음 실행 언제"를 GitLab UI에서 따로 볼 필요 없음).

- 예외: **Phase 1 (PoC)** 은 서버가 없으므로 GitLab pipeline schedule로 임시 운영 → [roadmap](../roadmap.md)

## 트리거 경로

```
스케줄러 or 대시보드 버튼
  → POST /runs (run 생성)
  → GitLab pipeline trigger API 호출 (TARGET_SOURCES, FULL_REGEN 변수 전달)
  → 러너가 GET /runs/{id}/plan 으로 처리 대상 수신
```

→ [api.md](./api.md), [architecture 실행 흐름](../architecture.md)

## 정책

- run당 처리 시간·AI 호출 횟수 상한 설정 가능 (폭주 방지) → [nfr](../nfr.md)
- 스케줄 시각/요일, 과제별 개별 스케줄 필요 여부는 미확정 → [open-questions](../open-questions.md) #6
