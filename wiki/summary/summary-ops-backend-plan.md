---
type: summary
title: 2026-07-07 운영화 전환 백엔드 계획 요약
tags: [ops, backend, phase, scm, fastapi, postgresql]
status: active
---

# 요약: 2026-07-07 운영화 전환 — 백엔드 개선 계획

POC 검증을 끝내고 운영 단계로 전환하며, 위키 확정 설계와 POC 코드(poc/)를 전수 대조해 백엔드 개선
계획을 세우고 미확정 3건(SCM 범위·스택·DB)을 확정한 논의. 소스: [[2026-07-07-ops-backend-plan]].

## 진단 — 설계 대비 POC 격차

엔진(LangGraph 오케스트레이션·4계층 이벤트·sha 멱등성·병렬 테마)은 설계 수준 도달. 반면 **시스템 계층이 부재**:
Control Plane이 read-only 대시보드 수준(등록/스케줄/트리거/알림 없음), 상태가 파일 분산(SCM_SOURCES_JSON·_state.json,
DB SoT 미연결), SCM이 GitLab 하드코딩, 이벤트가 JSONL+offset 폴링(webhook 미구현), MR 제출 스텁·무인증·시크릿 평문·smoke 테스트.

## 확정 결정 3건

- **SCM 다중 인스턴스 + GitHub 커넥터 MVP 승격** → [[decision-scm-multi-instance-github-mvp]]
  — 등록 단위를 "레포"→"SCM 인스턴스 × 레포"로. `scm_instances` 테이블 신설, GitLabConnector는 base_url 주입식(사내·gitlab.com 동일 구현),
  GitHubConnector 신규, 동일 계약 테스트. [[decision-mvp-scope]]의 "GitLab 1 커넥터" 절단선을 **부분 번복**.
- **Control Plane 스택 = FastAPI(Python)** → [[decision-control-plane-fastapi]]
  — Data Plane(LangGraph=Python)과 언어 일치로 이벤트 스키마·DB 모델·커넥터 코드 공유. ASP.NET Core는 언어 이원화 비용으로 기각.
- **Control Plane DB = PostgreSQL** → [[decision-control-plane-postgresql]]
  — API·스케줄러·webhook 동시 쓰기·트랜잭션 요구. SQLite(동시성 한계)·SQL Server(FastAPI 선택으로 조합 이점 소멸) 기각.

## 단계별 계획 (Phase 1–4 + 병행)

- **Phase 1 — SCM 커넥터 계층**: ScmConnector 포트(read/write/auth), gitlab_client+docshub 흡수, GitHubConnector 신규, 계약 테스트. 완료 기준 = 클라우드 레포 diff→문서.
- **Phase 2 — Control Plane 승격**: serve.py→FastAPI, DB SoT 이관(SCM_SOURCES_JSON 폐기), 소스 등록 API, 자체 토큰 인증, cron+수동 트리거, 역할 기반 이메일 알림 → [[decision-server-vm-self-token]] · [[decision-email-alerting]] · [[decision-schedule-per-source]] · [[decision-branch-loss-policy]]
- **Phase 3 — Data Plane 러너화**: 파이프라인을 러너 잡으로, run별 격리 작업 디렉터리, 이벤트 webhook push+DB 적재, MR/PR 실구현(성공 후에만 sha 전진) → [[decision-observability-event-contract]] · [[concept-idempotent-sha]] · [[decision-mr-review-gate]]
- **Phase 4 — 신뢰성·보안·운영성**: 시크릿 암호화·토큰 순환, 구조화 로깅·이벤트 회전, 하드코딩 8곳 Settings 승격, usage 토큰 비용 집계, 테스트 피라미드·CI, daily digest → [[question-secret-storage-security]] · [[question-cost-estimation]] · [[question-batch-observability]]
- **병행 트랙 — 매뉴얼 파이프라인 실측**: MCP 실 연결, 스텁 3곳(수집·배포·제출) 구현, 릴리스 태그 트리거를 스케줄러에 통합 → [[entity-manual-pipeline]] · [[decision-release-tag-trigger]]

## 새로 열린 질문 2건

- 클라우드 SCM 아웃바운드 네트워크 경로(Phase 1 실측 차단) → [[question-cloud-scm-network]] (blocking)
- 클라우드 SCM 토큰 발급 정책·rate limit → [[question-cloud-scm-token-policy]]

관련: [[decision-control-data-plane-split]] · [[decision-db-source-of-truth]] · [[decision-engine-orchestration-langgraph]] · [[overview]]
