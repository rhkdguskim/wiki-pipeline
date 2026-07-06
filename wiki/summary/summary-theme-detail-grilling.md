---
type: summary
title: 신규 테마 상세 설계 grilling 요약
tags: [themes, engine, grilling]
status: active
---

# 신규 테마 상세 설계 grilling 요약

> 원본: [[2026-07-06-theme-detail-grilling]]

[[decision-theme-scope-expansion]]으로 추가된 dev-guide · api-protocol 테마의 상세 설계를
grilling 인터뷰(질문 6건)로 확정한 기록의 요약.

## 요지

- **활성화**: 소스별 테마 체크리스트 — 기본 5개 on · api-protocol opt-in → [[decision-theme-activation-checklist]]
- **dev-guide**: 1문서 · 코드 근거만(환경 구성·실행/테스트/디버그·프로젝트 구조), 조직 규칙 제외
  — ⚠️ 이 항목은 **당일 번복**됨: 근거 범위 = 코드 + 레포 내 문서, 코딩 규칙 포함 → [[decision-devguide-grounding-scope]]
- **api-protocol**: 외부 노출 API만(HTTP/gRPC) — 내부 프로토콜(Akka 메시지·장비)은 제외
- **라우팅**: 두 테마 모두 dev/ 전용, release/는 기존 4테마 유지
- **검증**: critic 확장 = 근거 대조(source_files 실존 근거 필수) + 시크릿 기재 금지
  → [[decision-critic-grounding-secrets]]

## 이 소스에서 파생된 페이지

생성: [[decision-theme-activation-checklist]] · [[decision-critic-grounding-secrets]]
갱신: [[decision-theme-scope-expansion]] · [[entity-docu-automatic]]
