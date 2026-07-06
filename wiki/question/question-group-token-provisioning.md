---
type: question
title: 최소 권한 group access token 발급·프로비저닝
tags: [security, token, scm, least-privilege]
status: open
---

# ❓ 최소 권한 group access token을 어떻게 발급·프로비저닝하나

커넥터 auth 책임([[decision-scm-connector-abstraction]])과 보안 원칙([[entity-mirero-gitlab]])은
"소스 read + docs-hub write 최소 권한 group access token"을 전제한다. 실측
([[2026-07-06-wish-gitlab-api-survey]])이 그 발급 자체에 제약이 있음을 드러냈다.

## 실측 제약 (확정)

- `GET /groups/:id/access_tokens` → **401**: 그룹 토큰 발급·조회는 **Owner 권한**이 필요.
  조사 계정(일반 사용자)으로는 불가 → **누가 토큰을 발급하나**가 열려 있다.
- **권한이 소스별로 다름**: 같은 계정도 x-lab `registry` 403 vs ros-sw-rcs `registry` 200.
  registry에서 아티팩트를 당기려면 최소 Reporter+ 필요 → 토큰 권한을 소스별 실측으로 정해야.
- 이 인스턴스가 지원하는 scope 목록은 실측됨(entity 참조) — 최소 조합은 `read_api`+`read_repository`(소스)
  · `write_repository`(docs-hub) · `read_registry`+packages(아티팩트).

## 부분 답 (2026-07-06) — 소스 등록은 레포별 토큰으로 확정

소스 read 등록의 **토큰 발급 주체** 축은 [[decision-repo-dev-release-registration]]로 좁혀졌다:
그룹 access token(Owner 필요)이 아니라 **레포별 project access token**(`read_repository`+`api`)을
대시보드에 입력하는 방식으로 확정 — 위 "발급 주체" 검토 항목의 *프로젝트 access token으로 대체* 갈래가 채택됐다.
등록 시 compare API dry-run 200으로 **소스별 실제 접근 레벨을 실측·검증**하는 단계도 그 결정에 포함된다.

**그래도 이 질문은 open으로 유지**한다 — 아직 남은 축:
- **docs-hub write 토큰** 프로비저닝(등록되는 소스 토큰과 별개 자격).
- 소스별 **최소 권한 조합**(read_api+read_repository / write_repository / read_registry+packages)의 확정.
- 아티팩트 **registry read 권한**(소스마다 멤버십 상이 — x-lab 403 vs ros-sw-rcs 200)의 등록 시 흡수.

## 검토할 것 (open)

- ~~토큰 **발급 주체**~~ → 소스 read는 레포별 project access token으로 확정([[decision-repo-dev-release-registration]]).
  docs-hub write 토큰 발급 주체는 미확정.
- **최소 권한 조합**을 소스 역할별로 확정(소스=read, docs-hub=write, 아티팩트=read_registry).
- 소스별 멤버십 편차를 어떻게 흡수 — 소스 read는 등록 dry-run으로 검증되나, 아티팩트 read 권한 편차는 별도.

이 질문은 **토큰 발급·권한 프로비저닝**에 한정한다. 발급된 시크릿의 **저장 보안**(at-rest 암호화·접근 제어)은
별개 관심사 → [[question-secret-storage-security]].

관련: [[decision-repo-dev-release-registration]] · [[decision-scm-connector-abstraction]] · [[entity-mirero-gitlab]]
