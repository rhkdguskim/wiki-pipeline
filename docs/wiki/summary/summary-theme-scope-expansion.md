---
type: summary
title: 테마 1차 스코프 확장 논의 요약 (4→6)
tags: [themes, engine, scope]
status: active
---

# 테마 1차 스코프 확장 논의 요약

> 원본: [[2026-07-06-theme-scope-expansion]]

query로 테마 확장 여부를 묻던 중 사용자가 확장을 지시해, 기존 "실측 후 확장" 방침의 예외로
테마 2개를 1차 스코프에 즉시 추가하기로 확정한 논의의 요약.

## 요지

- 1차 테마 4개 → **6개로 즉시 확장** → [[decision-theme-scope-expansion]]
- ⑤ `dev-guide`: 개발환경 구성 + 개발 가이드 — 근거: 신규 인력 온보딩 · 환경 재현성
- ⑥ `api-protocol`: API & 프로토콜 — **백엔드 성격 소스**에 적용
- 기존 방침(2차 확장은 Phase 1~2 실측 후 — [[question-theme-expansion]])은 이 2개에 한해 예외,
  남은 후보(제품별 서브페이지 · 라이브러리 · CI/CD)는 방침 유지 (question은 open 유지)

## 이 소스에서 파생된 페이지

생성: [[decision-theme-scope-expansion]] · 갱신: [[entity-docu-automatic]] · [[question-theme-expansion]]
