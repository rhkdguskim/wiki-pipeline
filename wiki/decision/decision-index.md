# decision 인덱스

> decision 페이지 카탈로그. 허브: [[index]] · 규약: [[schema]]
> **기능(파이프라인) 축으로 그룹핑** — 페이지가 늘면 이 소제목으로 드릴다운한다. 파일은 모두 `wiki/decision/` 평면에 있고(폴더명=type 규약), 그룹은 인덱스에서만 나눈다.

### 공통 · cross-cutting (파이프라인 공유)

- [[decision-control-data-plane-split]] — Control/Data Plane 분리, 단일 프로세스 기각 (LLM Wiki 통합·서비스화 포석)
- [[decision-pipeline-observability]] — 모든 파이프라인 실시간 진행 모니터링(대시보드), 사후만·제각각 기각
- [[decision-observability-event-contract]] — 진행 이벤트 = 표준 스키마 + 가변 단위 + webhook push
- [[decision-scm-connector-abstraction]] — 형상관리 커넥터 추상화, GitLab·GitHub 2 커넥터(동등)
- [[decision-db-source-of-truth]] — 서버 DB가 SoT, sources.yml 커밋 기각
- [[decision-server-vm-self-token]] — 관리 서버 = 사내 VM + 자체 토큰 인증
- [[decision-engine-hybrid]] — 생성 엔진 = 하이브리드 (엔진 인터페이스 + 점진적 교체)

### 정적 파이프라인 (Docu-Automatic — 코드→기술문서)

- [[decision-pull-model]] — pull 모델 채택, push/큐 대안 기각
- [[decision-nightly-batch]] — 야간 배치 (평일 20:00), 서버 내장 cron
- [[decision-schedule-per-source]] — 스케줄 = 과제별 개별, 대시보드 설정
- [[decision-mr-review-gate]] — 사람 MR 리뷰 필수, docs-auto 브랜치 대체
- [[decision-change-filter-rule-based]] — 사소한 변경(주석·포맷) 재생성 스킵 = 규칙 기반 먼저 (LLM 판단 후순위)

#### 소스 등록 · docs-hub 산출 (정적 파이프라인 하위)

- [[decision-repo-dev-release-registration]] — 레포 1개 등록 + 개발/배포 브랜치 2개 (역할별 문서 산출). 레포×브랜치 원자단위·정책 C 대체
- [[decision-repo-registration-flow]] — ⛔ superseded — 레포별 토큰 + 브랜치 1개 스코프 (토큰=스코프 메커니즘은 위 결정이 계승)
- [[decision-docs-hub-folder-rule]] — docs-hub 폴더 = 레포 1폴더 + `dev/`·`release/` 하위폴더 자동 규칙 (평면 폴더·브랜치명 경로 기각)
- [[decision-branch-loss-policy]] — 등록 브랜치 선택(개발/배포) + compare 404 자동 비활성화 + protected 분기 재활성화

### 매뉴얼 추출 파이프라인 (2026-07-05 — 실행 앱→사용자 매뉴얼)

- [[decision-manual-pipeline-separate]] — 매뉴얼 추출은 Docu-Automatic과 별개 파이프라인
- [[decision-artifact-consumption]] — 소스 빌드 대신 릴리스 아티팩트 소비
- [[decision-release-tag-trigger]] — 릴리스/버전 태그 트리거 (매뉴얼 파이프라인)
- [[decision-hybrid-app-traversal]] — 하이브리드 순회 (시나리오 + 자율 탐색)
- [[decision-commit-history-manual-diff]] — 커밋 히스토리 + 관측으로 매뉴얼 add/update/delete
- [[decision-app-host-connection]] — 앱=별도 호스트, IP/port 세션 MCP 제어 + 시크릿 등록 저장
- [[decision-scenario-owner-dashboard]] — 시나리오 세트 = 과제 담당자가 대시보드에서 정의·유지
- [[decision-manual-taxonomy-two-reader]] — 매뉴얼 분류 = 사용자/운영파트(셋업자) 2축
- [[decision-manual-delete-grace]] — 매뉴얼 삭제 = deprecated 유예 후 삭제 (이중 게이트)
- [[decision-coverage-metric-gap]] — 순회 커버리지 = 지표 + 누락 표시 (시나리오 + 탐색 합산)

### 코드 인덱스 파이프라인 (2026-07-05 — 코드→질의 가능 인덱스)

- [[decision-code-index-pipeline]] — 코드 인덱싱 파이프라인 도입, 짧은 주기 폴링 (야간 배치·webhook·CI job 기각)
- [[decision-code-index-provider-abstraction]] — 프로바이더 추상화 (codegraph 은닉, traversal 1급 연산)
- [[decision-code-index-mcp-serving]] — 질의 채널 = MCP 서버 (개발자 붙어서 스캔; 자체 UI·IDE 플러그인은 후순위)
- [[decision-runner-git-clone]] — 인덱싱 소스 확보 = 러너 git clone (커넥터 4책임 확장 기각)
- [[decision-code-index-versioning]] — 인덱스 형상 관리 = 버전 스냅샷 + 원자 교체 (in-place 기각)
- [[decision-code-index-adapter-cg-colby]] — 첫 어댑터 = cg-colby 확정 (cgc 기각: 의존 heavy·Alpha)
- [[decision-code-index-single-repo-scope]] — v1 질의 범위 = 단일 레포 (cross-repo 후순위)
- [[decision-code-index-store-plane]] — 인덱스 저장소 = 별도 질의 서비스 평면 (관리 서버·이력 DB와 분리)
