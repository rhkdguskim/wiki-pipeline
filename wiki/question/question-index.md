# question 인덱스

> question 페이지 카탈로그. 허브: [[index]] · 규약: [[schema]]
> **기능(파이프라인) 축으로 그룹핑.** ✅=answered · ⛔=blocking(진행 차단) · 무표시=open. 파일은 모두 `wiki/question/` 평면에 있고, 그룹은 인덱스에서만 나눈다.

### 공통 · 인프라 (파이프라인 공유)

- [[question-runner-ai-network]] ✅ — 러너→AI API 네트워크 경로 (answered: 뚫려 있음)
- [[question-headless-claude-auth]] ✅ — headless 인증/동작 검증 (answered: 무인 지속 불가 → 자체 에이전트 전환으로 질문 해소 → [[decision-engine-api-agent]] · [[decision-engine-api-key-auth]])
- [[question-engine-runtime]] ✅ — 생성 엔진: Claude Code 재사용 vs 자체 에이전트 (answered: 하이브리드 → [[decision-engine-hybrid]]; 2026-07-06 B 전환 확정 → [[decision-engine-api-agent]])
- [[question-server-deploy-auth]] ✅ — 배포 위치·API 인증 (answered: 사내 VM + 자체 토큰 → [[decision-server-vm-self-token]])
- [[question-cost-estimation]] — 비용 예측 (Phase 1 PoC 실측 후; usage 토큰 자동 적재로 실측 수단 확보 → [[decision-agent-step-observability]])
- [[question-progress-event-contract]] ✅ — 진행 이벤트 형태·granularity (answered: 표준 스키마 + 가변 단위 + webhook push → [[decision-observability-event-contract]])
- [[question-batch-observability]] — 배치 알림/리포트 — 실패 알림=실시간 이메일·역할 기반 확정 → [[decision-email-alerting]]; daily digest 구체 남음
- [[question-mvp-scope]] ✅ — MVP 절단선 (answered: 정적 + 매뉴얼 둘 다 → [[decision-mvp-scope]]; 후보안〈정적만〉을 확대 · 매뉴얼 open 질문이 MVP 블로커로 승격)

### 정적 파이프라인 (Docu-Automatic)

- [[question-mr-vs-docs-auto]] ✅ — MR 방식 최종 확정 (answered: docs-hub 직접 MR → [[decision-mr-review-gate]])
- [[question-schedule-policy]] ✅ — 스케줄 시각/상한 정책 (answered: 과제별 대시보드 설정 → [[decision-schedule-per-source]])
- [[question-change-significance-filter]] ✅ — 사소한 변경 재생성 스킵 (answered: 규칙 기반 먼저 → [[decision-change-filter-rule-based]])
- [[question-requirements-devguide-boundary]] ✅ — requirements(설치/실행 환경) vs dev-guide(개발환경) 경계 (answered: 통합 없이 독자 축으로 명시 → [[decision-requirements-devguide-boundary]])

#### 소스 등록 · docs-hub 산출 (정적 파이프라인 하위)

- [[question-group-token-provisioning]] — 최소 권한 group access token 발급 (그룹 토큰=Owner 권한·소스별 멤버십 상이)
- [[question-initial-backfill-baseline]] ✅ — 신규 등록 소스의 첫 문서화 baseline (answered: A null → 전체 initialize, backfill을 1급 작업으로 분리 → [[decision-registration-baseline]])
- [[question-release-object-vs-tag-trigger]] — 트리거 = 태그 vs Release 객체 (태그 규칙 4종·태그≫릴리스 → [[decision-release-tag-trigger]])
- [[question-ci-less-source-policy]] ✅ — CI/릴리스 없는 방치 소스(ros-codec류) 처리 정책 (answered: 운영자 수동 큐레이션, 자동 판정 없음 → [[decision-source-manual-curation]])
- [[question-existing-ci-docs-stage]] — 기존 CI docs stage(ros-sw-rcs)와 우리 자동화의 공존/대체
- [[question-artifact-type-dispatch]] — 아티팩트 타입 소스별(exe/msi/nuget/container) 획득·기동 (→ [[decision-artifact-consumption]])

### 매뉴얼 추출 파이프라인 (2026-07-05)

- [[question-app-exec-environment]] ✅ — 앱 실행 환경 (답함: 별도 호스트·IP/port·시크릿 저장 → [[decision-app-host-connection]])
- [[question-mcp-auth-network]] ✅ — MCP·앱·AI 네트워크 (answered: MCP=IP/port, AI 뚫림)
- [[question-secret-storage-security]] — 등록 시크릿 저장 보안 (우선순위 낮음, 운영 단계로 연기)
- [[question-ui-coverage-completeness]] ✅ — "모든 기능" 완전 순회 보장·측정 (answered: 커버리지 지표 + 누락 표시 → [[decision-coverage-metric-gap]])
- [[question-manual-delete-safety]] ✅ — 매뉴얼 삭제 판정 안전성 (answered: deprecated 유예 후 삭제 → [[decision-manual-delete-grace]])
- [[question-scenario-set-ownership]] ✅ — 시나리오 세트 소유·유지 (answered: 과제 담당자 대시보드 정의 → [[decision-scenario-owner-dashboard]])
- [[question-manual-theme-taxonomy]] ✅ — 사용자/엔지니어 매뉴얼 분류 체계 (answered: 사용자/운영파트 2축 → [[decision-manual-taxonomy-two-reader]])

### 코드 인덱스 파이프라인 (2026-07-05 → 2026-07-06 범위 제외 — 답 결정들은 superseded)

- [[question-code-index-query-surface]] ✅ — 질의 표면·서빙 경계 (answered: MCP 서빙·단일 레포 — 답 결정군은 범위 제외로 superseded → [[decision-code-index-out-of-pipeline]])
- [[question-scm-checkout]] ✅ — SCM 커넥터 4번째 책임(checkout) 추가 여부 (answered: 러너 git clone — superseded, 커넥터 3책임 원칙은 유효)
- [[question-code-index-store]] ✅ — 인덱스 저장소 소유 (answered: 별도 질의 서비스 평면 — superseded)
- [[question-blob-vs-code-index-overlap]] ✅ — 내장 blob 검색·CodeScene vs 코드 인덱스 역할 중복 (answered: 파이프라인 제외로 질문 자체 해소 → [[decision-code-index-out-of-pipeline]])

### 향후 기능 후보 (Phase 3+)

- [[question-theme-expansion]] — 테마 2차 확장 시점 (dev-guide·api-protocol은 1차 승격 → [[decision-theme-scope-expansion]]; 남은 후보 실측 후)
- [[question-review-feedback-loop]] — 리뷰 피드백 되먹임 (Phase 3, 사람 큐레이션 후 반영 방침)
- [[question-doc-qa-rag]] — 생성 문서 위 Q&A/RAG (Phase 3+ 도입 방침)
