---
type: question
title: MVP 절단선 — 첫 출시 범위를 무엇으로 확정하는가?
tags: [mvp, scope, phase-1, phase-2]
status: open
---

# ❓ MVP 절단선 — 첫 출시 범위를 무엇으로 확정하는가?

Phase 1·2 확정 결정들이 MVP를 **암묵적으로** 정의하지만, 공식 "MVP 범위" 결정 페이지는 아직 없다.
아래는 2026-07-06 query에서 위키 결정들로부터 도출한 **후보 절단선**이다 — 확정되면 decision 페이지로 승격하고 이 질문을 answered로 전환한다.

## 후보 절단선: 정적 파이프라인 1개 + 최소 Control Plane

두 파이프라인 중 **정적(Docu-Automatic)만** 첫 출시에 넣는다. 근거: 정적이 결정 성숙도가 가장 높고, 매뉴얼은 별개 파이프라인으로 분리 확정([[decision-manual-pipeline-separate]])되어 절단면이 깨끗하다. (코드 인덱스는 2026-07-06 시스템 범위 자체에서 제외 → [[decision-code-index-out-of-pipeline]] — 절단선이 더 단순해졌다. 한때 유일 블로커였던 headless 인증은 자체 에이전트 전환으로 해소 → [[decision-engine-api-agent]])

**포함 기능 (모두 확정 결정 위):**

1. **소스 레포 등록** — project access token으로 레포 1개 + 개발/배포 브랜치 2개, 자동 조회·compare dry-run 검증 → [[decision-repo-dev-release-registration]]
2. **변경 감지 (pull)** — compare API + sha 포인터(성공 후에만 전진), 야간 배치 평일 20:00 → [[decision-pull-model]] · [[decision-nightly-batch]] · [[concept-idempotent-sha]]
3. **스케줄·수동 트리거** — 과제별 대시보드 설정 → [[decision-schedule-per-source]]
4. **문서 생성 엔진** — 엔진 인터페이스([[decision-engine-hybrid]]) + **API 자체 에이전트**(Messages API + tool use 루프), 인증은 **API 키 등록** → [[decision-engine-api-agent]] · [[decision-engine-api-key-auth]]. 에이전트 스텝(사고·동작·진행) 대시보드 출력 포함 → [[decision-agent-step-observability]]
5. **MR 제출 + 사람 리뷰 게이트** — docs-hub 직접 MR → [[decision-mr-review-gate]] · 폴더 규칙 `레포/{dev|release}/` → [[decision-docs-hub-folder-rule]]
6. **최소 관리 서버** — 사내 VM + 자체 토큰, 이력 DB SoT, Control/Data Plane 분리 → [[decision-server-vm-self-token]] · [[decision-db-source-of-truth]] · [[decision-control-data-plane-split]]
7. **실시간 진행 모니터링** — 표준 이벤트 스키마 + webhook push. 관측성은 1급 제약이므로 MVP에서 뺄 수 없다 → [[decision-pipeline-observability]] · [[decision-observability-event-contract]]
8. **장애 안전장치** — compare 404 자동 비활성화 + protected 재활성화 → [[decision-branch-loss-policy]] · 사소 변경 스킵은 규칙 기반 → [[decision-change-filter-rule-based]]
9. **SCM 커넥터** — 인터페이스는 유지하되 구현은 **GitLab 1개**만 (실측 완료 환경 [[entity-mirero-gitlab]]) → [[decision-scm-connector-abstraction]]. GitHub 커넥터는 MVP 이후.

**제외 (위키 근거):**

- 매뉴얼 추출 파이프라인 — 별개 파이프라인 + open 질문 다수([[question-artifact-type-dispatch]] 등) → [[decision-manual-pipeline-separate]]
- 코드 인덱스 — MVP 제외 차원이 아니라 **시스템 범위 자체에서 제외**(개인 관리 이관) → [[decision-code-index-out-of-pipeline]]
- Phase 3+ 후보 — 테마 확장([[question-theme-expansion]]), 리뷰 피드백 루프([[question-review-feedback-loop]]), 문서 Q&A/RAG([[question-doc-qa-rag]])
- 시크릿 저장 보안 강화 — 운영 단계로 연기 명시 → [[question-secret-storage-security]]

## 확정 전 열린 항목

- ~~[[question-headless-claude-auth]]~~ ✅ 해소(2026-07-06) — 자체 에이전트 전환으로 블로킹 소멸 → [[decision-engine-api-agent]]
- [[question-initial-backfill-baseline]] — 신규 등록 소스의 첫 문서화 baseline. MVP 등록 흐름에 직접 걸림
- [[question-group-token-provisioning]] — 최소 권한 토큰 발급 절차
- 매뉴얼 추출 파이프라인을 MVP 직후 언제 올릴지 — 미정
