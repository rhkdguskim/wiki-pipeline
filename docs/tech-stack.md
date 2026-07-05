# 기술 스택 (제안, 미확정)

← [문서 인덱스](./README.md)

> ⚠️ 아직 **확정되지 않음** — 확정 조건은 [open-questions.md](./open-questions.md) #3.

| 구성요소 | 제안 | 근거 |
|----------|------|------|
| 관리 서버 | ASP.NET Core Minimal API + BackgroundService(cron) + SignalR | 팀 익숙 스택 (DDL Service 경험). API·스케줄러·실시간 대시보드가 한 프로세스에 |
| DB | SQLite 시작 → 규모 확대 시 Postgres | 초기 인프라 최소화. 스키마 → [data-model.md](./data-model.md) |
| 파이프라인 스크립트 | Python | GitLab API + 엔진 호출 스크립트 4종 → [architecture.md](./architecture.md) |
| 생성 엔진 실행 | Claude Code CLI (headless, `claude -p`) | 기존 Docu-Automatic 자산 재사용 → [generation](./features/generation.md). **headless 검증 필요** |
| 문서 사이트 | Docusaurus (multi-instance) | 과제별 문서 분리, 사이트는 하나. 기존 사이트(110.110.10.70:8080)와의 관계는 [open-questions](./open-questions.md) #7 |
| CI | GitLab CI (사내 자체 호스팅) | 기존 인프라 |
