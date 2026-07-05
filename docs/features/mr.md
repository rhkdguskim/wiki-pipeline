# MR 생성 · 멱등성 (FR-8~9)

← [문서 인덱스](../README.md)

AI 산출물이 사람 리뷰를 거쳐 반영되는 게이트 ([G5](../goals.md))이자, 배치 실패 시 유실을 막는 장치.

## 요구사항

| ID | P | 요구사항 |
|----|---|----------|
| FR-8 | P0 | **MR 생성**: docs-hub에 브랜치 push + MR 생성(기본: 소스별 1 MR). MR 본문에 근거 커밋 구간, 변경 파일, 생성/갱신 문서, 경고 목록 명시. 동일 소스의 열린 자동 MR이 있으면 새 MR 대신 **갱신** (중복 방지) |
| FR-9 | P0 | **멱등성**: `last_processed_sha`는 MR 생성 성공 보고 후에만 전진. 실패 시 다음 run이 같은 구간을 재처리하며, 이때 중복 MR을 만들지 않는다 |

## MR 본문 규격

리뷰 비용을 최소화하기 위해 근거를 명시한다:

- 근거 커밋 구간 (`from_sha`…`to_sha`, 소스 레포 링크)
- 변경 파일 목록 → 영향받은 문서(테마) 매핑
- 생성/갱신된 문서 목록
- `auto_generated_warning` 경고 목록 (critic 2회 초과 fail 문서 — 리뷰어가 중점 확인)
- 미매핑 변경(신규 문서 후보) 리포트 → [change-detection](./change-detection.md)

## 멱등성 규칙 (유실 방지의 핵심)

```
성공 경로: compare → 생성 → MR 생성 성공 → 완료 보고 → sha 전진
실패 경로: 어느 단계든 실패 → sha 그대로 → 다음 run이 같은 구간 재처리
```

- sha 전진은 소스(run_item) 단위 — 소스 A 성공, 소스 B 실패 시 B만 재처리 ([data-model](../data-model.md))
- 재처리 시 동일 소스의 열린 자동 MR을 갱신하므로 중복 MR이 생기지 않는다

## 미확정

리뷰어 자동 지정 규칙, 소스별 MR vs 하루치 통합 MR → [open-questions](../open-questions.md) #5
