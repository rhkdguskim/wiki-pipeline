# 2026-07-07 운영화 전환 — 백엔드 개선 계획 확정 논의

## 배경

POC 검증이 끝나 운영 단계로 전환하기로 결정. 위키 확정 설계(51 결정)와 POC 코드(poc/)를 전수 대조해 백엔드 개선 계획을 수립하고, 미확정이던 스택·DB·SCM 범위 3건을 확정했다.

## 진단 — 위키 설계 대비 POC 격차

엔진(LangGraph 오케스트레이션·4계층 이벤트·sha 멱등성·병렬 테마)은 설계 수준 도달. 그러나 시스템 계층이 부재:

- Control Plane이 read-only 대시보드(serve.py, ThreadingHTTPServer) 수준 — 등록/스케줄/트리거/알림 없음
- 상태가 파일에 분산(.env SCM_SOURCES_JSON, _state.json) — DB source of truth 미구현 (store.py 스키마는 있으나 파이프라인 미연결)
- SCM이 GitLab 하드코딩(static_pipeline/gitlab_client.py, common/docshub.py, doc_targets.kind=gitlab 고정)
- 이벤트가 JSONL 파일+offset 폴링 (webhook push 미구현)
- MR 제출 스텁(DOCSHUB_MR_ENABLED=false), 알림 없음, 서버 무인증, 시크릿 SQLite 평문, 테스트 smoke만

## 신규 요구사항

소스 프로바이더 확장: 사내 GitLab(wish.mirero.co.kr) 외에 **gitlab.com·github.com(클라우드)** 레포도 소스로 등록 가능해야 한다. 기존 decision-scm-connector-abstraction(compare·submit·auth 3책임)의 구현을 MVP로 앞당기는 것 — decision-mvp-scope의 "GitLab 1 커넥터" 절단선을 부분 번복.

## 확정 결정 (2026-07-07)

1. **SCM 다중 인스턴스 + GitHub 커넥터를 MVP로 승격** — 소스 등록 단위를 "레포"에서 "SCM 인스턴스 × 레포"로 변경. scm_instances 테이블(kind·base_url·token·token_header) 신설, sources·doc_targets가 인스턴스 참조. GitLabConnector는 base_url/token 주입식이라 사내·gitlab.com 동일 구현, GitHubConnector 신규(compare=GET /repos/{o}/{r}/compare/{base}...{head}, contents/git-trees, PR). 동일 계약 테스트 스위트를 양쪽에 적용. 기각 대안: MVP를 GitLab 1 커넥터로 유지(사용자 요구로 기각).

2. **Control Plane 서버 스택 = Python FastAPI** — Data Plane 엔진이 LangGraph로 Python 고정이므로 단일 언어 유지, 이벤트 스키마·DB 모델·커넥터 코드를 두 플레인이 공유. 기각 대안: ASP.NET Core(보유 전문성·사내 Windows 인프라 정합은 있으나 언어 이원화 비용).

3. **Control Plane DB = PostgreSQL** — API 서버·스케줄러·webhook 수신의 동시 쓰기와 트랜잭션 요구. SQLite에서 이관. 기각 대안: SQLite 유지(동시성 한계), SQL Server(FastAPI 선택으로 조합 이점 소멸).

## 단계별 계획

- **Phase 1 — SCM 커넥터 계층**: ScmConnector 포트(read: resolve_ref·compare·read_file·list_tree·project_info / write: ensure_branch·commit_files·create_or_update_change_request / auth: verify_access). gitlab_client.py+docshub.py 흡수, GitHubConnector 신규, 계약 테스트. 완료 기준: github.com 레포와 gitlab.com 레포를 소스로 diff→문서 생성.

- **Phase 2 — Control Plane 승격**: serve.py→FastAPI 재작성, DB source of truth(_state.json의 last_processed_sha를 source_branches로 이관, SCM_SOURCES_JSON 폐기), 소스 등록 API(자동 조회+compare dry-run), 자체 토큰 인증, 과제별 cron 스케줄러+수동 트리거, 역할 기반 이메일 알림(401→admin, 실패→담당자+admin, compare 404→소스 자동 비활성화).

- **Phase 3 — Data Plane 러너화**: 파이프라인을 러너 잡으로(트리거→실행→보고→sha 전진), run별 격리 작업 디렉터리, 이벤트 webhook push+DB 적재(JSONL은 러너 로컬 감사 사본), MR/PR 제출 실구현(열린 자동 MR 갱신, MR 성공 후에만 sha 전진).

- **Phase 4 — 신뢰성·보안·운영성**: 시크릿 at-rest 암호화·토큰 순환, 구조화 로깅·이벤트 보존/회전, 하드코딩 8곳 Settings 승격·재시도 정책 통일, usage 토큰 비용 집계(과제·테마별), 테스트 피라미드(단위+계약+E2E)·CI, daily digest 설계.

- **병행 트랙 — 매뉴얼 파이프라인 실측**: MCP 실 연결 실측, 스텁 3곳(아티팩트 수집·배포·제출) 구현, 릴리스 태그 트리거를 스케줄러에 통합.

## 새로 열린 질문

- 관리 서버 VM·러너에서 github.com/gitlab.com 아웃바운드 HTTPS 경로가 열려 있는가 (AI API 경로는 확인됨, 클라우드 SCM은 미확인) — Phase 1 실측 전 확인 필요.
- 클라우드 토큰 발급 정책: GitHub fine-grained PAT vs classic, gitlab.com project access token 발급 주체·순환 주기. GitHub rate limit(인증 5000 req/h) 대응.
