# wiki-pipeline backend

사내 GitLab·gitlab.com·github.com 레포의 변경을 감지해 AI로 문서를 재생성하고
docs-hub에 MR/PR로 제출하는 **Control Plane(관리 서버) + Data Plane(러너)** 백엔드.

> 설계 근거: 위키 `wiki/decision/` — control-data-plane-split, control-plane-fastapi,
> control-plane-postgresql, scm-multi-instance-github-mvp, db-source-of-truth,
> mr-review-gate, nightly-batch, email-alerting, engine-orchestration-langgraph.

## 아키텍처

```
┌─ Control Plane (controlplane/) ── FastAPI :8420 ─────────────────┐
│ 소스/인스턴스/타깃 등록(자동 조회+dry-run) · DB source of truth   │
│ 과제별 cron 스케줄(기본 평일 20:00) · 수동 트리거                 │
│ webhook 이벤트 적재(증분 커서) · 완료 보고(sha 전진) · 이메일 알림│
└──────── ① 트리거(러너 기동) ↓        ↑ ② 이벤트/완료 보고 ───────┘
┌─ Data Plane (runner/ + *_pipeline/) ─────────────────────────────┐
│ runner/job.py: 컨텍스트 조회 → init/diff 실행 → MR/PR 제출 → 보고 │
│ static_pipeline: 코드 diff → 기술문서 (LangGraph, 실측 L4)        │
│ manual_pipeline: 앱 관측 → 매뉴얼 (MCP, 실측 전)                  │
│         ↓ connectors/ ScmConnector (compare·read·submit·auth)    │
└── GitLabConnector(사내·gitlab.com) · GitHubConnector(github.com) ─┘
```

## 구조

```
backend/
├── connectors/          # SCM 커넥터 계층 (GitLab·GitHub 동등 1급, 포트/어댑터)
├── controlplane/        # 관리 서버 — FastAPI·SQLAlchemy·APScheduler·알림·시크릿 암호화
│   ├── app.py           #   앱 팩토리 + 서버 엔트리 (python -m backend.controlplane.app)
│   ├── api.py           #   HTTP API (프런트 계약 + 러너 webhook + 비용 집계)
│   ├── models.py        #   scm_instances·sources·source_branches·runs·run_events·doc_targets
│   ├── projection.py    #   이벤트 -> KPI 프로젝션 (DB/JSONL 공용)
│   └── services/        #   registration(등록·검증)·runs(수명주기)·scheduler·notifier
├── runner/              # Data Plane 러너 (python -m backend.runner.job)
├── common/              # 저수준 공유 런타임 (LLM 팩토리·이벤트·observer·재시도·MCP 브리지)
├── common_pipeline/     # 파이프라인 공통 (RunContext·write→critic 루프·병렬 분배)
├── static_pipeline/     # ① 코드 diff -> 기술문서
├── manual_pipeline/     # ② 앱 관측 -> 매뉴얼 (독자 2축)
└── tests/               # 커넥터 계약·Control Plane 통합·러너 테스트
```

계층 규칙: `common` ← `common_pipeline` ← 파이프라인, `connectors`는 어디서나 —
역방향 의존 금지. 파이프라인·제출·등록은 프로바이더(GitLab/GitHub)를 모른다.

## 설치·실행

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env    # LLM_API_KEY·토큰·CONTROL_* 채움

# Control Plane (등록·스케줄·대시보드 API)
python -m backend.controlplane.app     # http://127.0.0.1:8420

# 프런트엔드 (별도 Vite 서버 — /api는 8420으로 프록시)
cd frontend && npm install && npm run dev

# 러너 단독 실행 (Control Plane이 트리거하면 자동 — 수동 진단용)
python -m backend.runner.job --run-id <id>

# CLI 단독 실행 (Control Plane 없이 — 로컬 상태 파일 기반)
python -m backend.static_pipeline.main --source <id>
python -m backend.manual_pipeline.main --smoke

# 테스트
.venv/bin/python -m pytest backend/tests/ -q
```

## 운영 흐름

1. **등록**: `POST /api/sources` — kind(gitlab|github)·url·repo·토큰. 서버가 자동 조회
   (default_branch·namespace→doc_dir) + compare dry-run 검증, dev/release 브랜치 2역할 저장.
2. **배치**: 소스별 cron(기본 평일 20:00) → run 생성 → 러너 기동. 수동은 `POST /api/runs/trigger`.
3. **실행**: 러너가 `last_processed_sha` 없으면 전량 init, 있으면 증분 diff.
   이벤트는 webhook으로 실시간 push(+로컬 JSONL 감사 사본), run별 격리 디렉터리 사용.
4. **제출**: 활성 doc target에 MR/PR — 같은 브랜치에 열린 자동 MR이 있으면 갱신(중복 방지).
   머지는 사람 리뷰 게이트.
5. **보고**: MR 제출까지 성공한 run만 `last_processed_sha` 전진 (실패 run은 포인터 불변 →
   다음 배치가 같은 구간 재처리). compare 404는 소스 자동 비활성화 + admin 이메일,
   401은 admin 이메일, 실패는 담당자+admin 이메일.

## 보안·운영

- **인증**: 모든 API는 자체 토큰(`CONTROL_API_TOKENS`), 러너 webhook은 전용 토큰.
- **시크릿**: SCM 토큰은 DB에 Fernet 암호화 저장(`CONTROL_SECRET_KEY`), API 응답은
  `has_token`만 노출. 러너 전용 `/api/runner/context`만 복호화 토큰을 전달.
- **DB**: 운영 PostgreSQL(`CONTROL_DB_URL`), 개발 SQLite. runs 이력은 영구 보존,
  상세 이벤트는 `EVENT_RETENTION_DAYS`(기본 30일) 후 정리.
- **튜닝**: 재시도·동시성·컨텍스트 한도는 전부 .env 노브 (하드코딩 금지) — `.env.example` 참조.
- **비용**: usage 토큰이 run별 자동 적재 → `GET /api/costs` (과제별 집계).

## 자격증명

전부 `backend/.env`(gitignore 차단) + DB 암호화 저장. 코드·문서 어디에도 하드코딩하지 않는다.
