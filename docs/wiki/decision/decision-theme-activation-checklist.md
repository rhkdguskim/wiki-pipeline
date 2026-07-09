---
type: decision
title: 테마 활성화 = 소스별 테마 체크리스트 (기본 5 on · api-protocol opt-in)
tags: [themes, dashboard, registration]
status: active
---

# 테마 활성화 = 소스별 테마 체크리스트

테마가 소스마다 다르게 적용되는 문제(예: api-protocol은 백엔드 소스만)를 **소스 등록/설정 화면의
테마 체크리스트**로 푼다. 원본 논의: [[2026-07-06-theme-detail-grilling]]

## 결정

- 소스 등록/설정 화면에 **테마 체크리스트**를 둔다 — 테마×소스 활성화 매트릭스
- 기본값: 기존 4테마 + dev-guide는 **자동 on**, api-protocol은 담당자가 **opt-in**
- 향후 테마가 추가돼도 이 체크리스트에 항목만 늘어나는 **일반 메커니즘**
- 활성화 상태는 서버 DB(SoT)에 저장 → [[decision-db-source-of-truth]]

## 근거

- 과제별 설정을 대시보드에 두는 기존 패턴([[decision-schedule-per-source]])과 일관
- 결정적이고 비용이 없다 — 판정을 위한 엔진 호출·규칙 유지가 불필요
- "백엔드인가"라는 성격 판단을 시스템이 아니라 가장 잘 아는 사람(과제 담당자)에게 맡긴다

## 기각 대안

- **소스 성격 분류 필드** (백엔드/프론트/라이브러리 → 테마 세트 자동 결정) — 간접 구조. 테마마다
  성격 매핑 규칙을 별도로 유지해야 하고, 성격 하나로 테마 조합을 표현 못 하는 경우가 생긴다
- **scout 자동 판단** — 비결정적이고, 판정을 위한 불필요한 엔진 호출(비용)과 누락 위험이 있다

관련: 테마 목록 자체는 [[decision-theme-scope-expansion]] · 엔진 구조는 [[entity-docu-automatic]]
