---
type: decision
title: 1차 테마 스코프 확장 (4→6) — 개발환경·개발가이드 + API & 프로토콜
tags: [themes, engine, scope]
status: active
---

# 1차 테마 스코프 확장 (4→6)

생성 엔진([[entity-docu-automatic]])의 1차 테마 4개(intro / requirements / architecture-overview /
component-diagram)에 테마 2개를 **즉시** 추가한다. 원본 논의: [[2026-07-06-theme-scope-expansion]]

## 결정

| # | 테마 (잠정 식별자) | 담는 것 | 적용 범위 |
|---|------------------|--------|----------|
| ⑤ | `dev-guide` | 개발환경 구성 + 개발 가이드 | 모든 소스 (기본 on) |
| ⑥ | `api-protocol` | API & 프로토콜 문서 (외부 노출 API만) | 백엔드 성격 소스 — 담당자 opt-in → [[decision-theme-activation-checklist]] |

## 근거

- **신규 인력 온보딩** — 과제 투입 시 개발환경 구성에 드는 시간을 줄일 문서가 필요
- **환경 재현성** — 빌드/실행 환경이 문서화되어 있지 않으면 환경 재현이 어려움
- **백엔드 API·프로토콜 정리** — 백엔드 과제는 API & 프로토콜 문서가 기술문서의 핵심 산출물

## 기각 대안

- **실측 후 일괄 확장 (기존 방침)** — [[question-theme-expansion]]의 "Phase 1~2 실측 후 우선순위
  결정"을 이 2개 테마에 한해 예외 처리한다. 온보딩·재현성은 실측을 기다릴 수 없는 현재의 필요이기
  때문. 남은 후보(제품별 서브페이지 · 라이브러리 · CI/CD)는 기존 방침을 유지한다.
- **2차 확장 1순위로만 확정 (지금 생성 안 함)** — 확인 문답에서 기각, 즉시 추가를 선택.

## 상세 설계 (2026-07-06 grilling — [[2026-07-06-theme-detail-grilling]])

- **dev-guide = 1문서 · 레포 근거(코드+문서)**: ①환경 구성(사전 요구·의존·빌드) ②실행·테스트·디버그
  ③프로젝트 구조 ④코딩 규칙·개발 규칙. 근거는 빌드 스크립트·CI 설정·매니페스트·analyzer 설정과
  **레포 내 문서**(README·CONTRIBUTING·docs/). 당초 "코드 근거만(조직 규칙 제외)"이었으나 당일
  번복 — 상세·번복 이력은 [[decision-devguide-grounding-scope]]
- **api-protocol = 외부 노출 API만**: HTTP/gRPC 등 외부에서 호출하는 인터페이스만. 내부 프로토콜
  (Akka 메시지·소켓/장비)은 제외 — 필요해지면 별도 테마 후보
- **브랜치 라우팅**: 두 테마 모두 **dev/ 전용** — release/ 산출은 기존 4테마 유지
  ([[decision-repo-dev-release-registration]]의 역할 분리와 일관: 릴리스 문서에 개발자용 내용 배제)
- **검증**: critic 근거 대조 + 시크릿 기재 금지 → [[decision-critic-grounding-secrets]]

## 영향

- 테마당 1회 엔진 호출 구조라 소스당 호출량 최대 1.5배 — 비용 실측([[question-cost-estimation]])은
  6테마 기준으로 해야 한다
- frontmatter `source_files`/`theme` 매핑에 새 테마 2종 추가 필요 (Docu-Automatic 레포 측 작업)
- 기존 requirements 테마(설치/실행 환경과 조건)와 dev-guide의 환경 구성 절이 소재가 겹침 —
  경계 정의 필요 → [[question-requirements-devguide-boundary]]
