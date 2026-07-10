# decision 인덱스

> decision 페이지 카탈로그. 허브: [[index]] · 규약: [[schema]]
> **기능(파이프라인) 축으로 그룹핑** — 페이지가 늘면 이 소제목으로 드릴다운한다. 파일은 모두 `wiki/decision/` 평면에 있고(폴더명=type 규약), 그룹은 인덱스에서만 나눈다.

### 공통 · cross-cutting (파이프라인 공유)

- [[decision-mvp-scope]] — **MVP 절단선 = 정적 + 매뉴얼 두 파이프라인** (위키 후보안〈정적만〉을 확대 · 매뉴얼 open 질문이 MVP 블로커로 승격; 2026-07-07 "GitLab 1 커넥터" 절단선 부분 번복 → 아래 SCM 다중 인스턴스 결정)
- [[decision-scm-multi-instance-github-mvp]] — **SCM 다중 인스턴스 + GitHub 커넥터 MVP 승격** (등록 단위 = SCM 인스턴스 × 레포 · scm_instances 테이블 · GitLabConnector base_url 주입식〈사내·gitlab.com 동일〉 · GitHubConnector 신규 · 동일 계약 테스트; MVP GitLab 1커넥터 유지 기각)
- [[decision-control-plane-fastapi]] — **Control Plane 스택 = Python FastAPI** (Data Plane LangGraph와 언어 일치로 이벤트 스키마·DB 모델·커넥터 공유; ASP.NET Core 언어 이원화 비용으로 기각)
- [[decision-control-plane-postgresql]] — **Control Plane DB = PostgreSQL** (API·스케줄러·webhook 동시 쓰기·트랜잭션; SQLite 동시성 한계·SQL Server FastAPI 선택으로 조합 이점 소멸 기각)
- [[decision-registration-baseline]] — 등록 baseline = A(null → 전체 코드베이스 initialize); 초기 전량 backfill을 정기 야간 배치와 분리된 1급 작업으로, 야간 배치는 증분만
- [[decision-control-data-plane-split]] — Control/Data Plane 분리, 단일 프로세스 기각 (LLM Wiki 통합·서비스화 포석)
- [[decision-pipeline-observability]] — 모든 파이프라인 실시간 진행 모니터링(대시보드), 사후만·제각각 기각
- [[decision-observability-event-contract]] — 진행 이벤트 = 표준 스키마 + 가변 단위 + webhook push
- [[decision-scm-connector-abstraction]] — 형상관리 커넥터 추상화, GitLab·GitHub 2 커넥터(동등)
- [[decision-db-source-of-truth]] — 서버 DB가 SoT, sources.yml 커밋 기각
- [[decision-server-vm-self-token]] — 관리 서버 = 사내 VM + 자체 토큰 인증
- [[decision-engine-hybrid]] — 생성 엔진 = 하이브리드 (엔진 인터페이스 + 점진적 교체; 2026-07-06 driver 발동 → B 확정)
- [[decision-engine-api-agent]] — **생성 엔진 = API 자체 에이전트** (Messages API + tool use 루프 · Data Plane 내 실행 · 공통 런타임 + 파이프라인별 도구 세트; Managed Agents·claude -p 기각)
- [[decision-engine-api-key-auth]] — 엔진 인증 = API 키 등록 (계정 로그인 대체 · 러너 환경변수 주입 · 401 감지 → admin 이메일; 2026-07-07 공급자 중립으로 갱신)
- [[decision-engine-orchestration-langgraph]] — **엔진 오케스트레이션 = LangGraph** (자체 루프 → 프레임워크 · 프레임워크 계층 갭 명문화 · get_stream_writer 커스텀 관측 · durable 체크포인팅; OpenAI Agents SDK 탈락·Claude Agent SDK 비채택. 인터페이스 계약 불변 → 구현체 갱신)
- [[decision-model-provider-neutral-minimax]] — **모델 공급자 = 중립 설계, PoC = MiniMax M3** (Anthropic 확정 → base URL·키·모델명 교체 중립 · 공급자별 키 인증 · 프로덕션 공급자는 PoC 후 확정)
- [[decision-engine-single-account-auth]] — ⛔ superseded — 엔진 인증 = 단일 Claude Code 계정 로그인 (API 키 등록이 계승)
- [[decision-agent-step-observability]] — 에이전트 스텝 관측 = 사고 요약·도구 호출·토큰을 진행 이벤트 4단 계층으로 대시보드 출력 + 이력 DB 스텝 로그
- [[decision-email-alerting]] — 알림 = 실시간 이메일 · 역할 기반 수신 (인증 해지→admin, 과제 실패→담당자+admin); 대시보드 풀·admin 단일 기각

### 정적 파이프라인 (Docu-Automatic — 코드→기술문서)

- [[decision-pull-model]] — pull 모델 채택, push/큐 대안 기각
- [[decision-nightly-batch]] — 야간 배치 (평일 20:00), 서버 내장 cron
- [[decision-schedule-per-source]] — 스케줄 = 소스별 다중 스케줄, 파이프라인 선택, 대시보드 설정
- [[decision-mr-review-gate]] — 사람 MR 리뷰 필수, docs-auto 브랜치 대체
- [[decision-change-filter-rule-based]] — 사소한 변경(주석·포맷) 재생성 스킵 = 규칙 기반 먼저 (LLM 판단 후순위)
- [[decision-theme-scope-expansion]] — 1차 테마 4→6 즉시 확장 (dev-guide + api-protocol〈백엔드〉); 실측 대기 방침의 예외
- [[decision-critic-grounding-secrets]] — critic 확장 = 근거 대조 + 시크릿 기재 금지 (dev-guide·api-protocol 한정)
- [[decision-devguide-grounding-scope]] — dev-guide 근거 = 코드 + 레포 내 문서 (코딩 규칙 포함); "코드만" 당일 번복
- [[decision-requirements-devguide-boundary]] — requirements ↔ dev-guide 경계 = 통합 없이 독자 축으로 명시 (설치자·운영자 vs 개발자); 겹치는 사실은 한쪽 상세+다른쪽 참조

#### 소스 등록 · docs-hub 산출 (정적 파이프라인 하위)

- [[decision-repo-dev-release-registration]] — 레포 1개 등록 + 개발/배포 브랜치 2개 (역할별 문서 산출). 레포×브랜치 원자단위·정책 C 대체
- [[decision-source-manual-curation]] — 방치 소스 정책 = 운영자 수동 큐레이션 (쓸 것만 등록); 방치 자동 판정 기준 소거, compare 404 자동 비활성화는 별개 유지
- [[decision-repo-registration-flow]] — ⛔ superseded — 레포별 토큰 + 브랜치 1개 스코프 (토큰=스코프 메커니즘은 위 결정이 계승)
- [[decision-docs-hub-folder-rule]] — docs-hub 폴더 = 레포 1폴더 + `dev/`·`release/` 하위폴더 자동 규칙 (평면 폴더·브랜치명 경로 기각)
- [[decision-branch-loss-policy]] — 등록 브랜치 선택(개발/배포) + compare 404 자동 비활성화 + protected 분기 재활성화
- [[decision-theme-activation-checklist]] — 테마 활성화 = 소스별 체크리스트 (기본 5 on · api-protocol opt-in); 성격 분류·scout 판단 기각

### 매뉴얼 추출 파이프라인 (2026-07-05 — 실행 앱→사용자 매뉴얼)

- [[decision-manual-pipeline-separate]] — 매뉴얼 추출은 Docu-Automatic과 별개 파이프라인
- [[decision-artifact-consumption]] — 소스 빌드 대신 릴리스 아티팩트 소비
- [[decision-artifact-type-dispatch]] — 아티팩트 타입 dispatch = exe/msi만 구동 대상(nuget·container 제외) · 자산은 담당자가 대시보드 지정 · MCP가 전송+설치 실행(silent install)까지
- [[decision-release-tag-trigger]] — 릴리스/버전 태그 트리거 (매뉴얼 파이프라인)
- [[decision-hybrid-app-traversal]] — 하이브리드 순회 (시나리오 + 자율 탐색)
- [[decision-commit-history-manual-diff]] — 커밋 히스토리 + 관측으로 매뉴얼 add/update/delete
- [[decision-app-host-connection]] — 앱=별도 호스트, IP/port 세션 MCP 제어 + 시크릿 등록 저장
- [[decision-scenario-owner-dashboard]] — 시나리오 세트 = 과제 담당자가 대시보드에서 정의·유지
- [[decision-manual-taxonomy-two-reader]] — 매뉴얼 분류 = 사용자/운영파트(셋업자) 2축
- [[decision-manual-delete-grace]] — 매뉴얼 삭제 = deprecated 유예 후 삭제 (이중 게이트)
- [[decision-coverage-metric-gap]] — 순회 커버리지 = 지표 + 누락 표시 (시나리오 + 탐색 합산)

### 데이터 웨어하우스 · 분석 통합 (2026-07-09 — Monday.com + wiki_pipeline → PostgreSQL)

- [[decision-dwh-as-karpathy-llm-wiki]] — **DWH 저장 = Karpathy LLM Wiki 3동작(축적·기록·정리)으로 재조직** (저장의 1차 언어를 BI→LLM Wiki로; medallion은 그 아래 물리 계층으로 유지; hybrid 저장방식 부분 정정) ⭐ 저장 철학 상위 축
- [[decision-dwh-shape-kimball-medallion]] — **DWH 전체 형태 = Kimball 차원 모델링 + Medallion layering** (소스 2개·BI 지향; Inmon/Data Vault/Lakehouse 기각 — 오버스펙)
- [[decision-dwh-storage-postgres-single]] — **저장소 = PostgreSQL 단일 클러스터, 다른 스키마** (이미 쓰는 PG 재사용·별도 클러스터/클라우드 DW 기각; 읽기 복제본으로 점진 확장)
- [[decision-monday-ingest-polling-only]] — **Monday 적재 = 스케줄러 폴링 단일 레인** (webhook 삭제 — 지연 목표=일 배치 확정으로 실시간 근사 불필요; 근실시간 요구 시 webhook 옵션 복귀)
- [[decision-monday-ingest-hybrid]] — ⛔ superseded — Monday 적재 = webhook + 야간 전수 폴링 하이브리드 (지연 목표 일 배치 확정으로 webhook 레인 삭제, 위 polling-only가 계승)
- [[decision-dwh-column-value-hybrid]] — **반정형 = typed long table + JSONB 폴백 + GIN 인덱스** (pure JSONB/exploded/EAV 기각 — 드리프트/쿼리성능/안티패턴)
- [[decision-bronze-single-jsonb-table]] — **bronze 착륙 = 소스 구분 없는 단일 JSONB 테이블(raw_records) + 재수집 append(sha256 동일 시 skip)** (커넥터만 추가하면 소스 확장·스키마 변경 0; append 로그가 silver SCD2 입력; 소스별 전용 테이블/bronze 생략/upsert 기각. `bronze` 스키마에 위치)
- [[decision-dwh-scd-strategy]] — **SCD = entity별 0/1/2/append 혼합** (items/users/boards SCD2·statuses SCD1·run/step append-only fact; dbt snapshot + merge)
- [[decision-dwh-transform-dbt]] — **변환·오케스트레이션 = dbt-postgres + cron-first** (순수 SQL/데이터프레임/처음부터 Airflow 기각; Airflow는 10+ 태스크 시 이관)
- [[decision-monday-readonly-client-wrapper]] — **Monday 읽기 전용 = 앱 계층 래퍼(MondayReadOnlyClient)로 mutation 차단** (2026-07-10 정정 — 발급 토큰이 read/write라 코드적 강제; 토큰 신뢰/정적검사만/네트워크차단 기각)
- [[decision-monday-collector-langgraph-scheduled]] — **Monday 자동 수집 = 스케줄러 트리거 + LangGraph 에이전트 루프** (엔진 LangGraph 재사용·폴링 레인 실행체; 순수 스크립트/webhook만/Airbyte 단독 기각)
- [[decision-dwh-md-document-store]] — **문서 저장 = md 표준 포맷 + DocumentStore 포트/어댑터** (DB 교체 가능; PG 초기 → 향후 VectorStore(LLM WIKI); PG 직결·파일만·처음부터 벡터 기각)
- [[decision-ingestion-connector-architecture]] — **데이터 수집 아키텍처 = IngestionConnector → DWH → 파이프라인 AI 쿼리** (Monday=첫 구현체, SCM과 형제 포트; 스크립트/ScmConnector 욱여넣기/BI 전용 기각) ⭐ 상위 축
- [[decision-document-identity-run-separation]] — **문서 정체성을 run에서 분리** (Document=오래 사는 엔티티·run_id nullable; RunDocOutput 흡수; 모든 문서 run 강제/종류별 테이블 기각)
- [[decision-connector-settings-system-settings]] — **커넥터 설정 = 시스템 설정 페이지** (SystemSetting `connector.*` 네임스페이스·기존 llm.* 패턴 재사용; .env만/전용테이블/Source등록 기각. 토큰 암호화는 열린 항목)

### 코드 인덱스 파이프라인 (2026-07-05 도입 → 2026-07-06 범위 제외)

- [[decision-code-index-out-of-pipeline]] — **코드 인덱스 = 파이프라인 범위 제외, 개발자 개인 관리 이관** (아래 8건 일괄 supersede; 재검토 조건 = cross-repo 등 개인이 못 푸는 요구)
- [[decision-code-index-pipeline]] — ⛔ superseded — 코드 인덱싱 파이프라인 도입, 짧은 주기 폴링
- [[decision-code-index-provider-abstraction]] — ⛔ superseded — 프로바이더 추상화 (codegraph 은닉)
- [[decision-code-index-mcp-serving]] — ⛔ superseded — 질의 채널 = MCP 서버
- [[decision-runner-git-clone]] — ⛔ superseded — 인덱싱 소스 확보 = 러너 git clone (실측 사실은 [[entity-mirero-gitlab]] 보유)
- [[decision-code-index-versioning]] — ⛔ superseded — 인덱스 형상 관리 = 버전 스냅샷 + 원자 교체
- [[decision-code-index-adapter-cg-colby]] — ⛔ superseded — 첫 어댑터 = cg-colby (도구 실측은 [[entity-codegraph]]에 유효)
- [[decision-code-index-single-repo-scope]] — ⛔ superseded — v1 질의 범위 = 단일 레포 (cross-repo 축은 새 결정의 재검토 조건으로 계승)
- [[decision-code-index-store-plane]] — ⛔ superseded — 인덱스 저장소 = 별도 질의 서비스 평면
