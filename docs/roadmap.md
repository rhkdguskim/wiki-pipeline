# 로드맵 (Phase 0~3)

← [문서 인덱스](./README.md)

| Phase | 범위 | 완료 기준 |
|-------|------|-----------|
| **0 (완료)** | 생성 엔진: [Docu-Automatic](https://github.com/jaeCheon8587/Docu-Automatic) 산출물 6개 (스킬 4 + 에이전트 2) | 완료됨 |
| **1 — PoC** | docs-hub 레포 구성(Docusaurus multi-instance), pipeline 스크립트 4종, 임시 sources.yml + GitLab pipeline schedule (**서버 없이**) | 과제 1개로 end-to-end 검증: 야간 배치가 변경을 감지해 문서 MR을 생성. **headless 엔진 실행과 러너→AI 네트워크 경로를 이 단계에서 검증** |
| **2 — 관리 서버** | DB, 소스/트리거/보고 API, 서버 내장 스케줄러로 이관(sources.yml 대체), 수동 트리거 | 등록·수동 트리거·완료 보고가 API로 동작, 소스 4개(전 과제) 온보딩 |
| **3 — 대시보드·운영** | 대시보드 UI, webhook 실시간 모니터링, 실패 알림, baseline 자동 생성 옵션 | 대시보드에서 상태 확인·수동 트리거·이력 조회 가능 |

## Phase 1 착수 전 선행 조건

[open-questions.md](./open-questions.md)의 블로킹 질문 3개가 풀려야 한다:
① 러너→AI API 네트워크 경로 (#1), ② headless 실행 인증 방식 (#2), ③ MR vs docs-auto 브랜치 확정 (#5)

## Phase별 문서 매핑

- Phase 1: [change-detection](./features/change-detection.md) · [generation](./features/generation.md) · [mr](./features/mr.md)
- Phase 2: [sources](./features/sources.md) · [scheduling](./features/scheduling.md) · [api](./features/api.md) · [data-model](./data-model.md)
- Phase 3: [monitoring](./features/monitoring.md)
