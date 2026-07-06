---
type: entity
title: 사내 GitLab 환경 (미레로)
tags: [gitlab, infra, environment]
status: active
---

# 사내 GitLab 환경

사내 자체 호스팅 GitLab로, 문서 자동화의 소스 레포들이 여기 있다.
GitLab은 지원하는 두 SCM 커넥터 중 하나이며, GitHub과 함께 **동등한 1급 연동 대상**이다 → [[decision-scm-connector-abstraction]].

## 인프라

- 사내 자체 호스팅 GitLab + CI 러너 (`http://wish.mirero.co.kr/`)
- **러너 → AI API 네트워크 경로 확보됨** ✅ (2026-07-05 확인, 폐쇄망 차단 아님) → [[question-runner-ai-network]]. 남은 것은 인증/실행 방식 → [[question-headless-claude-auth]]

### 실측 확정 사실 (2026-07-06 조사, 원본 [[2026-07-06-wish-gitlab-api-survey]])

일반 사용자 계정(`api` scope OAuth 토큰)으로 인증해 실측한 스냅샷. 값은 이후 변할 수 있다.

| 항목 | 값 | 근거 API |
|------|-----|---------|
| 버전 | **GitLab 16.3.0** (rev `85a896db163`) | `GET /api/v4/version` |
| 에디션 | **Community Edition** (`enterprise:false`) | `/version`, `/help` |
| KAS | Kubernetes Agent Server 활성 (`ws://…/-/kubernetes-agent/`) | `/version` |
| OIDC | issuer `http://…`, endpoint는 `https://` 발급(HSTS) | `/.well-known/openid-configuration` |
| 접근 규모 | **610 프로젝트** 접근, 100+ 그룹 멤버 | `/projects`, `/groups` (`X-Total`) |
| 계정 권한 | 일반 사용자, admin 아님, 그룹/프로젝트 생성 불가(`projects_limit:0`) | `GET /api/v4/user` |

**CE라는 사실의 파장**: Enterprise 전용 기능이 전부 부재 — `/projects/:id/approvals`가 **404**(MR approval rule로 리뷰 게이트를 강제할 수 없음 → [[decision-mr-review-gate]]), Advanced Search(Elasticsearch) 미탑재(blob 검색은 기본 인덱스 수준 → [[question-blob-vs-code-index-overlap]]).

### 이 인스턴스가 지원하는 OIDC scope (토큰으로 얻을 수 있는 권한 전부)

`api  read_api  read_user  read_repository  write_repository  create_runner  read_registry  write_registry  read_observability  write_observability  sudo  admin_mode  openid  profile  email`

- grant_types: authorization_code, **password**, client_credentials, refresh_token (OAuth password grant로 `api` scope 토큰 발급 실증).
- 파이프라인 실사용 조합: 소스 read(`read_api`+`read_repository`)·docs-hub write(`write_repository`)·아티팩트(`read_registry`, packages)가 핵심. 최소 권한 토큰 설계 → [[question-group-token-provisioning]].

### 인증 방식별 접근 (실측)

| 방식 | 결과 |
|------|------|
| 익명(무인증) | 공개 프로젝트 메타·git URL만 200. `/version`·`/metadata`·GraphQL은 401/404 |
| OAuth password grant | `POST /oauth/token` → `api` scope access token |
| PAT | `/-/user_settings/personal_access_tokens`에서 발급(read_api+read_repository 권장) |
| 프로젝트 access token | `GET /projects/:id/access_tokens` → 200 (일반 권한으로 가능) |
| 그룹 access token | `GET /groups/:id/access_tokens` → **401 (Owner 권한 필요)** → [[question-group-token-provisioning]] |

## 파이프라인 책임별 API 표면 (일반 권한, 전부 200 실증)

ros-sw-rcs(id 947) 기준. 커넥터 3책임([[decision-scm-connector-abstraction]])이 실물 API로 확인됐다.

| 파이프라인 책임 | API | 상태 | 비고 |
|---------------|-----|:---:|------|
| compare (변경 파일) | `GET /projects/:id/repository/compare?from=&to=` | ✅ | 두 sha → `diffs[].new_path` |
| submit (MR) | `GET/POST /projects/:id/merge_requests` | ✅ | 커넥터 submit 실증 |
| MR 승인 규칙 | `GET /projects/:id/approvals` | ❌ 404 | **CE에 없음** — approval rule 강제 불가 |
| checkout | `http_url_to_repo`(clone) / `repository/archive.zip` | ✅ | git LFS 사용 → [[decision-runner-git-clone]] |
| 트리거(릴리스) | `GET /projects/:id/releases` | ✅ | Release 객체(자산 링크) |
| 트리거(태그) | `GET /projects/:id/repository/tags` | ✅ | 태그 ≫ 릴리스 (폭주) → [[question-release-object-vs-tag-trigger]] |
| 아티팩트: 패키지 | `GET /projects/:id/packages` | ✅ | generic·nuget. **릴리스 자산 실체** → [[decision-artifact-consumption]] |
| 아티팩트: 컨테이너 | `GET /projects/:id/registry/repositories` | ✅ | MCP 서버 이미지 존재 → [[entity-remote-control-mcp]] |
| 아티팩트: job | `GET /projects/:id/jobs?scope=success` | ✅ | `expire_in` 만료 |
| 이벤트 구독(webhook) | `GET/POST /projects/:id/hooks` | ✅ | 현재 0개 (사내 웹훅 인프라 부재) |
| 스케줄(cron) | `GET /projects/:id/pipeline_schedules` | ✅ | 현재 0개 |
| 코드 검색(blob) | `GET /projects/:id/search?scope=blobs` | ✅ | 경로+라인, 의미검색 아님 → [[question-blob-vs-code-index-overlap]] |
| 커밋 이력 | `GET /projects/:id/repository/commits?since=` | ✅ | since로 증분 |
| 파일 트리 | `GET /projects/:id/repository/tree`, `/files/:path/raw` | ✅ | `.gitlab-ci.yml` raw 실증 |
| 위키(내장) | `GET /projects/:id/wikis` | ❌ 403 | ros-sw-rcs 비활성 |

그룹 레벨(gid 504 기준): `groups/:id/projects` 200(소스 일괄 등록에 유용)·`registry/repositories` 200·`members` 200 / `variables` 403(Maintainer+)·`access_tokens` 401(Owner). 전역 레벨 `version`·`metadata`·`projects`·`groups`·`search` 모두 200.

## 권한이 소스별로 다름 (설계 제약)

같은 계정인데 프로젝트마다 접근 레벨이 다르다 — x-lab(1124) `registry` **403**, ros-sw-rcs(947) `registry`·`packages`·`variables` **200**. registry에서 아티팩트를 당기려면 최소 Reporter+ 필요. → 최소 권한 토큰은 **소스별 실제 멤버십을 실측**해야 함 → [[question-group-token-provisioning]].

## 대상 과제 실측 프로파일 (5 + 참고 1)

| 프로젝트 | id | 주 언어 | default | 브랜치 | 태그/릴리스 | CI | 성격 |
|---------|----|--------|:---:|:---:|:---:|:---:|------|
| ros-sw-rcs | 947 | C++/C/TSX | master | 8 | 41/4 | ✅ **docs stage 有** | C++ 서버 + 웹 UI |
| pcc/ros-common | 1008 | C#/C++ | master | 5 | 0/0 | ✅ | C# 공통 라이브러리 |
| pcc30 | 1010 | HTML/C# | master | 11 | **125/1** | ✅ | ROC 다변종(브랜치 폭발) |
| sdc-smart-ros | 918 | C/C#/C++ | **main** | 7 | 33/0 | ✅ | 임베디드+클라 혼합 |
| ros-codec | 1157 | C/Asm/OpenCL | master | 1 | 2/0 | ❌ **CI 없음** | 저수준 코덱(2018 방치) |
| x-lab (참고) | 1124 | C#/HTML/Py | master | 3 | 3/2 | ✅ | C# 중심 |

관찰:
- default branch가 `master`/`main` 혼재 → 하드코딩 금지, API 조회 필수.
- 태그 규칙 4종+(`Component/semver`, `version/제품/변종/semver`, `version/숫자`) → 태그 파싱으로 릴리스 식별 불안정 → [[question-release-object-vs-tag-trigger]].
- ros-codec처럼 **CI·릴리스 없는 방치 소스** 존재 → "모든 소스에 CI/릴리스 있음" 가정 깨짐 → [[question-ci-less-source-policy]].
- ros-sw-rcs CI stages `build→test→registry→merge→bundle→deploy→docs` — 이미 docs stage 有 → [[question-existing-ci-docs-stage]].
- 웹훅·스케줄 0개 → pull 모델이 현실적 → [[decision-pull-model]].

## 사내에 이미 존재하는 관련 실물

- **MCP 서버 컨테이너**(ros-sw-rcs registry): `mivncmcpserver`·`mivncmanagermcpserver`·`mivnc2rtspserver` → [[entity-remote-control-mcp]].
- **CodeScene 정적분석**: `mirero/Static-Code-Analysis` 그룹 26개 프로젝트(`pwm-*-codescene` 등) → 코드 인덱스와 역할 중복 가능성 → [[question-blob-vs-code-index-overlap]].
- **AI 관련 프로젝트군**: `claude-code-standardization-platform`·`team/dm/claude`·`ctc/pwm/ai-context` 등.

## 대상 과제 (소스 4개 + 향후 확장)

X-LAB · ROC · Smart-ROS · SW-RCS — 개별 레포, C++/C#/JS/Python 혼재, Doxygen 주석 거의 없음.
경영진 방침: 문서 작성에 인적 리소스 투입 금지 (자동화의 근본 동기).

## 보안 원칙

group access token 최소 권한(소스 read + docs-hub write), 토큰·API 키는 CI masked variable로만,
서버 API는 사내망 한정 (인증 방식 → [[question-server-deploy-auth]]). 그룹 토큰 발급이 Owner 권한이라는
실측 제약과 소스별 멤버십 편차는 최소 권한 설계에 직접 영향 → [[question-group-token-provisioning]] · [[question-secret-storage-security]].

전체 그림: [[overview]]
