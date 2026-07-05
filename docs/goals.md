# 목표 / 비목표 / 범위

← [문서 인덱스](./README.md)

## 목표

- **G1.** 과제 레포 main 변경이 **다음 영업일 아침까지** 문서 MR로 제출된다 → [scheduling](./features/scheduling.md), [mr](./features/mr.md)
- **G2.** AI 호출 횟수가 커밋 수가 아니라 **영향받은 문서 수**에 비례한다 → [change-detection](./features/change-detection.md)
- **G3.** 신규 과제 온보딩 = **등록 1건** (소스 레포 무수정) → [sources](./features/sources.md)
- **G4.** 실행 상태·이력을 대시보드에서 확인하고, 수동 트리거할 수 있다 → [monitoring](./features/monitoring.md), [scheduling](./features/scheduling.md)
- **G5.** 모든 문서 변경은 **사람의 MR 리뷰**를 거친다 (AI 직접 머지 금지) → [mr](./features/mr.md)

측정 방법 → [kpi.md](./kpi.md)

## 비목표 (v1 제외)

- **N1.** 실시간 문서 갱신 — 야간 배치로 충분하며, 실시간성은 의도적으로 포기한다
- **N2.** AI의 리뷰 없는 자동 머지
- **N3.** 생성 엔진(에이전트/스킬) 자체의 재설계 — Docu-Automatic 산출물을 재사용하며, 엔진 개선은 별도 과제
- **N4.** 기존 수동 작성 문서의 자동 이관 (Docu-Automatic 미결 사항 #10, 범위 외 유지)
- **N5.** 다국어 문서 생성

## 범위 구분: 본 시스템 vs 생성 엔진

| | Docu-Automatic (기존, 완료) | wiki-pipeline (본 문서) |
|---|---|---|
| 책임 | 문서 **생성** — 테마 순회, 판단·작성·검증 | 생성 엔진의 **자동 운영** — 감지·스케줄·MR·관리·모니터링 |
| 산출물 | 에이전트 3 + 스킬 4 | docs-hub CI 파이프라인 + 관리 서버 + 대시보드 |
| 상세 | → [features/generation.md](./features/generation.md) | → [architecture.md](./architecture.md) |
