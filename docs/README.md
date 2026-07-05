# wiki-pipeline — 문서 인덱스

> 사내 GitLab의 여러 과제 레포 변경을 **야간 배치**로 감지해, AI 생성 엔진([Docu-Automatic](https://github.com/jaeCheon8587/Docu-Automatic))이
> 공통 문서 레포(docs-hub, Docusaurus)의 영향받은 문서만 재생성하고 **MR로 제출**하는 자동 문서화 시스템.

이 문서 묶음은 단일 책임 원칙(SRP)에 따라 관심사별로 분리되어 있다. 각 문서는 하나의 주제만 다루고, 서로 cross-link로 연결된다.

- **문서 상태**: Draft v0.1
- **소유자**: kwanghyeon.kim@mirero.co.kr
- **대상 과제**: X-LAB · ROC · Smart-ROS · SW-RCS (+향후 신규 과제)

## 읽는 순서

### 1. 왜 / 무엇을
- [vision.md](./vision.md) — 배경·문제 정의·비전
- [goals.md](./goals.md) — 목표·비목표·범위
- [users.md](./users.md) — 사용자·핵심 유스케이스

### 2. 어떻게 (설계)
- [architecture.md](./architecture.md) — 용어, Control/Data Plane 구조, 실행 흐름
- [data-model.md](./data-model.md) — 관리 서버 DB 스키마 (source of truth)
- [tech-stack.md](./tech-stack.md) — 기술 선택 (제안, 미확정)

### 3. 기능 (각 1책임)
- [features/sources.md](./features/sources.md) — 소스 레포 등록/해제, baseline (FR-1~3)
- [features/change-detection.md](./features/change-detection.md) — compare API 변경 감지 + 영향 분석 (FR-5~6)
- [features/generation.md](./features/generation.md) — 생성 엔진(Docu-Automatic) 통합 (FR-7)
- [features/mr.md](./features/mr.md) — MR 생성 + 멱등성 (FR-8~9)
- [features/scheduling.md](./features/scheduling.md) — 야간 스케줄 + 수동 트리거 (FR-4, FR-10)
- [features/monitoring.md](./features/monitoring.md) — 완료 보고, webhook, 대시보드, 알림 (FR-11~15)
- [features/api.md](./features/api.md) — 관리 서버 REST API

### 4. 품질 / 운영
- [nfr.md](./nfr.md) — 비기능 요구사항 + 실패 시나리오
- [kpi.md](./kpi.md) — 성공 지표
- [roadmap.md](./roadmap.md) — Phase 0~3 단계별 계획
- [open-questions.md](./open-questions.md) — 열린 질문·리스크

### 부록
- [설계 논의 기록](../raw/2026-07-05-design-session.md) — 설계 결정 과정 (검토한 대안과 기각 이유, push→pull 진화 과정). 지식 위키: [../schema.md](../schema.md) · [../wiki/overview.md](../wiki/overview.md)

## 핵심 결정 (한눈에)

| 항목 | 결정 |
|------|------|
| 트리거 | **pull 모델 야간 배치** — docs-hub가 compare API로 수집 (push 즉시 실행 기각: 비용·부하·리뷰 폭주) |
| 변경 감지 | compare API `last_processed_sha`~HEAD — 커밋 N개가 최종 변경 파일 집합 1개로 자연 병합 |
| 상태 저장 | **관리 서버 DB가 source of truth** (sources.yml 커밋 방식 기각: 매일 포인터 커밋 + push 충돌) |
| 생성 엔진 | **Docu-Automatic 재사용** — scout → docu-writer → critic, 테마 순차 순회 |
| 산출물 | docs-hub에 직접 브랜치 + **MR** (기존 docs-auto 브랜치 방식 대체, 최종 확정 필요) |
| 리뷰 | 모든 문서 변경은 **사람의 MR 리뷰** 필수 — AI 자동 머지 금지 |
| 멱등성 | `last_processed_sha`는 **MR 생성 성공 후에만 전진** — 실패 시 유실 없이 재처리 |
| 스케줄러 | 관리 서버 내장 cron (Phase 1 임시로 GitLab pipeline schedule) |
| 문서 사이트 | Docusaurus **multi-instance** — 과제별 문서 분리, 사이트는 하나 |
| 스택 | ASP.NET Core + SignalR / SQLite (**제안, 미확정** → [open-questions #3](./open-questions.md)) |
