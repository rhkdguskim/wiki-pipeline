---
type: decision
title: dev-guide 근거 범위 = 코드 + 레포 내 문서 (코딩 규칙 포함)
tags: [themes, engine, scope]
status: active
---

# dev-guide 근거 범위 = 코드 + 레포 내 문서

dev-guide 테마([[decision-theme-scope-expansion]])의 scout 탐색·근거 범위를 **코드 + 레포 내
문서**로 정한다. 원본 지시: [[2026-07-06-devguide-docs-grounding]]

## 결정

- scout의 탐색 대상 = 코드(빌드 스크립트·CI 설정·매니페스트·analyzer 설정) + **레포 내 문서**
  (README·CONTRIBUTING·docs/ 등 clone 범위 안의 문서)
- **코딩 컨벤션·개발 규칙도 포함** — 레포 안(코드 또는 문서)에서 발견되는 규칙을 찾아 정리한다
- 근거 대조 원칙([[decision-critic-grounding-secrets]])은 유지 — 문서 파일도 `source_files`에
  근거로 기재하며, 레포 안에 근거가 없는 항목은 여전히 기재 불가
- 레포 **밖** 규칙(구두 전승, 외부 사내 위키)은 엔진 접근 범위 밖이라 제외 — 필요해지면 별도 결정

## 근거

- 온보딩 문서로서 코딩 규칙이 빠지면 반쪽이다 (테마 추가의 근거가 온보딩 — [[decision-theme-scope-expansion]])
- 레포 문서에 이미 흩어져 있는 규칙을 모아 정리하는 것은 근거 기반 작업이라 환각 위험이 낮다 —
  "조직 규칙 제외"의 원래 이유(근거 부재)가 레포 내 문서까지 근거로 인정하면 해소된다

## 기각 대안 (같은 날 번복 이력 포함)

- **코드 근거만 (조직 규칙 제외)** — grilling([[2026-07-06-theme-detail-grilling]] Q2)에서 최초
  확정했고 직후 확인 문답에서도 유지를 택했으나, **당일 번복**됨. 컨벤션·개발 규칙이 빠져 온보딩
  문서로 불완전하다는 이유
- **담당자 입력 자료 등록** (컨벤션 문서를 대시보드에 등록) — 등록 부담. 레포 내 문서 탐색으로 대체

## 영향

- scout 프롬프트의 탐색 지시에 레포 문서 포함 필요 (Docu-Automatic 레포 측 작업)
- dev-guide 산출 문서에 "코딩 규칙·개발 규칙" 섹션 추가 (근거 있는 경우에만)
