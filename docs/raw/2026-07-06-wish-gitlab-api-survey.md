# wish GitLab API 실측 조사 (2026-07-06)

사내 GitLab(`http://wish.mirero.co.kr/`)에 실제 로그인해 인증된 상태로, 문서 자동화
파이프라인이 **사용해야 하고 접근 가능한 API 표면**을 실측한 기록. 본인 계정(KwangHyeon.Kim,
일반 사용자, `api` scope OAuth 토큰) 기준. 조사 후 토큰은 revoke함.

> 이 문서는 raw 원본(불변)이다. 실측 시점의 사실 스냅샷이며, 이후 값은 변할 수 있다.

## 인스턴스 확정 사실

| 항목 | 값 | 근거 |
|------|-----|------|
| 버전 | **GitLab 16.3.0** (revision `85a896db163`) | `GET /api/v4/version` |
| 에디션 | **Community Edition** (`enterprise: false`) | `/version`, `/help` |
| KAS | Kubernetes Agent Server 활성 (`ws://wish.mirero.co.kr/-/kubernetes-agent/`) | `/version` |
| 프론트 | nginx, `X-Gitlab-Meta` 헤더 노출 | 응답 헤더 |
| OIDC issuer | `http://wish.mirero.co.kr`, endpoint는 `https://`로 발급 (HSTS 有) | `/.well-known/openid-configuration` |
| 내 계정 | id 212, admin 아님, 그룹/프로젝트 생성 불가(`projects_limit:0`) | `GET /api/v4/user` |
| 접근 규모 | **610개 프로젝트** 접근(`X-Total`), 100+ 그룹 멤버 | `/projects`, `/groups` |

### OIDC discovery가 노출한 지원 scope (이 인스턴스에서 토큰으로 얻을 수 있는 권한 전부)

```
api  read_api  read_user  read_repository  write_repository
create_runner  read_registry  write_registry
read_observability  write_observability
sudo  admin_mode  openid  profile  email
```

- grant_types: authorization_code, **password**, client_credentials, refresh_token
- OAuth password grant로 access token 발급됨 (`scope: api`, Bearer, 64자)

## 인증 방식 실측

- **익명(무인증)**: `GET /api/v4/projects?visibility=public` → 200 (공개 프로젝트 메타·git URL 노출).
  `/explore/projects`, 공개 프로젝트 페이지 200. 하지만 `/api/v4/version`·`/metadata`·GraphQL은 401/404.
- **OAuth password grant**: `POST /oauth/token {grant_type:password, username, password}` → `access_token`(`api` scope).
- **PAT**: `/-/user_settings/personal_access_tokens`에서 발급 가능 (read_api + read_repository 권장).
- **프로젝트 access token**: `GET /projects/:id/access_tokens` → 200 (내 권한으로 가능).
- **그룹 access token**: `GET /groups/:id/access_tokens` → **401** (Owner 권한 필요 — 내 계정 불가).

## 파이프라인 책임별 API 표면 (내 일반권한, ros-sw-rcs id=947 기준 실측)

전부 HTTP 200 확인:

| 파이프라인 책임 | API | 상태 | 비고 |
|---------------|-----|:---:|------|
| **compare** (변경 파일) | `GET /projects/:id/repository/compare?from=&to=` | ✅ | 두 sha → `diffs[].new_path`. x-lab에서 42개 파일 반환 실증 |
| **submit (MR)** | `GET/POST /projects/:id/merge_requests` | ✅ | 현재 열린 MR 0건 |
| **MR 승인 규칙** | `GET /projects/:id/approvals` | ❌ 404 | **CE에 없음** — approval rule로 리뷰 게이트 강제 불가 |
| **checkout** | `http_url_to_repo` (git clone) / `GET /projects/:id/repository/archive.zip` | ✅ | ros-sw-rcs는 git LFS 사용(`git lfs`) |
| **트리거(릴리스)** | `GET /projects/:id/releases` | ✅ | Release 객체(자산 링크 포함) |
| **트리거(태그)** | `GET /projects/:id/repository/tags` | ✅ | 태그 수 ≫ 릴리스 수 (폭주 위험) |
| **아티팩트: 패키지** | `GET /projects/:id/packages` | ✅ | generic·nuget. **릴리스 자산 실체** |
| **아티팩트: 컨테이너** | `GET /projects/:id/registry/repositories` | ✅ | ros-sw-rcs에 MCP 서버 이미지 존재 |
| **아티팩트: job** | `GET /projects/:id/jobs?scope=success` + artifacts | ✅ | `expire_in`으로 만료 |
| **이벤트 구독** | `GET/POST /projects/:id/hooks` | ✅ | 현재 0개 (사내 웹훅 인프라 부재) |
| **스케줄** | `GET /projects/:id/pipeline_schedules` (cron) | ✅ | 현재 0개 |
| **파이프라인** | `GET /projects/:id/pipelines`, `/pipelines/:pid/jobs` | ✅ | |
| **CI 트리거** | `GET /projects/:id/triggers` | ✅ | |
| **CI 변수(masked)** | `GET /projects/:id/variables` | ✅ | 토큰/키 masked var 확인 |
| **코드 검색(blob)** | `GET /projects/:id/search?scope=blobs&search=` | ✅ | 파일 경로+라인. 4개 프로젝트 전부 200 |
| **커밋 이력** | `GET /projects/:id/repository/commits?since=` | ✅ | since로 증분 조회 |
| **파일 트리** | `GET /projects/:id/repository/tree`, `/files/:path/raw` | ✅ | `.gitlab-ci.yml` raw 조회 실증 |
| **기여자·이벤트** | `/repository/contributors`, `/events` | ✅ | |
| **위키(내장)** | `GET /projects/:id/wikis` | ❌ 403 | ros-sw-rcs에서 비활성 |

### 그룹 레벨 (gid=504, mirero/project/ros/1.0 기준)

| API | 상태 |
|-----|:---:|
| `GET /groups/:id/projects` | ✅ 200 (하위 프로젝트 일괄 조회 — 소스 등록에 유용) |
| `GET /groups/:id/registry/repositories` | ✅ 200 |
| `GET /groups/:id/members` | ✅ 200 |
| `GET /groups/:id/variables` | ❌ 403 (Maintainer+ 필요) |
| `GET /groups/:id/access_tokens` | ❌ 401 (Owner 필요) |

### 전역 레벨

`GET /api/v4/version` · `/metadata` · `/events` · `/todos` · `/projects` · `/groups` · `/search?scope=projects` 모두 200.

## 권한이 소스별로 다름 (중요)

같은 내 계정인데 프로젝트마다 접근 레벨이 다르다:
- **x-lab (id 1124)**: `registry/repositories` → **403**, `runners` → 403
- **ros-sw-rcs (id 947)**: `registry` → **200**, `packages` → 200, `variables` → 200

→ group access token의 "최소 권한" 설계는 **소스별 실제 멤버십 레벨을 확인**해야 하고,
registry에서 아티팩트를 당기려면 최소 Reporter+ 필요. 그룹 토큰 발급 자체가 Owner 권한.

## 대상 과제 5개 실측 프로파일

| 프로젝트 | id | 주 언어 | default | 브랜치 | 태그/릴리스 | 태그 규칙 예 | CI | 성격 |
|---------|----|--------|---------|:---:|:---:|----------|:---:|------|
| ros-sw-rcs | 947 | C++49 / C29 / TSX·TS | master | 8 | 41 / 4 | `MiRcsServer/3.2.2` | ✅ **docs stage 有** | C++ 서버 + 웹 UI |
| pcc/ros-common | 1008 | C#88 / C++6 | master | 5 | 0 / 0 | (없음) | ✅ | C# 공통 라이브러리 |
| pcc30 | 1010 | HTML76 / C#23 | master | 11 | 125 / 1 | `version/ROC/Siltron_Ev/1.1.1` | ✅ | ROC 다변종(브랜치 폭발) |
| sdc-smart-ros | 918 | C61 / C#27 / C++12 | **main** | 7 | 33 / 0 | `version/SmartROS/SDCA6/1.2.10` | ✅ | 임베디드+클라 혼합 |
| ros-codec | 1157 | C63 / Asm13 / OpenCL | master | 1 | 2 / 0 | `version/2000` | ❌ CI 없음 | 저수준 코덱(2018 커밋 잔존, 방치) |
| x-lab (참고) | 1124 | C#83 / HTML9 / Py4 | master | 3 | 3 / 2 | `version/XLab/Common/0.0.2` | ✅ | C# 중심 |

관찰:
- default branch가 `master`/`main` 혼재 → 하드코딩 금지, API 조회 필수.
- 태그 규칙이 소스마다 다름(4종+): `Component/semver`, `version/제품/변종/semver`, `version/숫자`.
- **태그 ≫ 릴리스** (pcc30 125:1, smart-ros 33:0) → 태그 트리거는 폭주. Release 객체 트리거가 안전.
- ros-codec처럼 CI·릴리스 없는 방치 소스 존재 → "모든 소스에 CI/릴리스 있음" 가정 깨짐.
- ros-sw-rcs CI stages: `build → test → registry → merge → bundle → deploy → docs` (이미 docs stage 有).
- CI가 PowerShell(`.ps1`)·msbuild·windows_build_base → **러너가 Windows**. LFS 사용.

## 아티팩트 소비 = Generic Package Registry (실체 확인)

ros-sw-rcs 릴리스 `MiRcsServer/3.2.2`의 자산 11개가 전부
`/api/v4/projects/947/packages/generic/...`로 서빙됨 (`MiRcsServerSetup(for WindowNT).exe`,
`MiRcsServerAutoInstaller.exe`, `.msi` 등). `packages`에 generic·nuget 병존.
→ 아티팩트 소비는 Job artifacts가 아니라 **Generic Package(+nuget, 컨테이너)** 경로가 정석.
소스마다 아티팩트 타입이 다름(exe/msi/nuget/container).

## 사내에 이미 존재하는 관련 실물

- **MCP 서버 컨테이너**: ros-sw-rcs registry에 `mivncmcpserver`, `mivncmanagermcpserver`,
  `mivnc2rtspserver` 이미지 → "원격 제어 MCP"가 가설이 아니라 이미 빌드·배포되는 실물.
- **CodeScene 정적분석 파이프라인**: `mirero/Static-Code-Analysis` 그룹에 26개 프로젝트
  (`pwm-*-codescene`, `daq-*-codescene`, `oars_*`) → 코드 인덱스와 역할 중복 가능성.
- **AI 관련 프로젝트군**: `midews/26/claude-code-standardization-platform`, `team/dm/claude`,
  `ctc/pwm/ai-context`, `team/planning-group/ai-tool-monitoring`, `cdm/3.0/dams30-wiki`(README만).
- **웹훅·스케줄 0개** → 사내에 이벤트 구독/자동 스케줄 인프라 아직 없음 → pull 모델이 현실적.

## GitLab 16.3 CE 검색의 한계

`search?scope=blobs`는 동작하나 CE는 Advanced Search(Elasticsearch) 미탑재 → 정규식/기본 인덱스
수준. 의미 검색 아님. 코드 인덱스(codegraph/CodeScene)의 대체가 아니라 보완 정도.
