# Wiki Index — wiki_pipeline

> 전체 페이지 카탈로그. 매 ingest마다 갱신 (규약: [schema.md](./schema.md)). 진입점: [wiki/overview.md](./wiki/overview.md)

## overview

- [[overview]] — 시스템 전체 그림 (Control/Data Plane, 실행 흐름, 페이지 안내 허브)

## summary (raw 소스 요약)

- [[summary-design-session]] — 설계 논의 기록 요약: 대안 3개 검토 → pull 모델 채택 과정
- [[summary-docu-automatic]] — Docu-Automatic 레포 분석 요약: 생성 엔진 구조와 조정점

## entity

- [[entity-docu-automatic]] — 문서 생성 엔진 (scout→docu-writer→critic, 기존 자산)
- [[entity-docs-hub]] — 공통 문서 레포 (Docusaurus multi-instance + pipeline 스크립트)
- [[entity-mirero-gitlab]] — 사내 GitLab 환경 (과제 4개, 스택 제안, 보안 원칙)

## concept

- [[concept-idempotent-sha]] — sha 포인터 멱등성: 유실 방지·재실행 안전·디바운스

## decision

- [[decision-pull-model]] — pull 모델 채택, push/큐 대안 기각
- [[decision-nightly-batch]] — 야간 배치 (평일 20:00), 서버 내장 cron
- [[decision-db-source-of-truth]] — 서버 DB가 SoT, sources.yml 커밋 기각
- [[decision-mr-review-gate]] — 사람 MR 리뷰 필수, docs-auto 브랜치 대체

## question

- [[question-runner-ai-network]] ⛔ — 러너→AI API 네트워크 경로 (Phase 1 블로킹)
- [[question-headless-claude-auth]] ⛔ — headless Claude Code 인증/동작 검증 (Phase 1 블로킹)
- [[question-mr-vs-docs-auto]] ⛔ — MR 방식 최종 확정 (Phase 1 블로킹)
- [[question-server-stack-db]] — 서버 스택·DB 확정 (Phase 2)
- [[question-server-deploy-auth]] — 배포 위치·API 인증 (Phase 2)
- [[question-schedule-policy]] — 스케줄 시각/상한 정책 (Phase 2)
- [[question-existing-site-relation]] — 기존 문서 사이트 확장 vs 신규 (Phase 1)
- [[question-theme-expansion]] — 테마 2차 확장 시점 (Phase 3+)
- [[question-cost-estimation]] — 비용 예측 (Phase 1 실측 후)

---
페이지 20 · raw 소스 2 · 최종 갱신 2026-07-05 · PRD: [PRD.md](./PRD.md) → [docs/README.md](./docs/README.md)
