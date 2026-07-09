---
type: decision
title: requirements ↔ dev-guide 경계 = 통합 없이 독자 축으로 명시
tags: [themes, phase-1]
status: active
---

# 결정: requirements와 dev-guide는 통합하지 않고 독자 축으로 경계를 명시한다

소재(런타임·의존성)가 겹치는 두 테마를 **하나로 합치지 않고 독자 축으로 경계를 명시**해 분리 유지한다.
[[decision-manual-taxonomy-two-reader]]와 같은 원리 — 독자가 다르면 별개 문서다.

## 경계 (독자 축)

- **requirements** = 소스 빌드 **없이** 제품을 설치·실행하는 환경/조건. 독자: 설치자·운영자.
- **dev-guide** = 소스에서 빌드·테스트·디버그하며 **개발**하는 환경. 독자: 개발자.
- 겹치는 사실(필요 런타임·OS·의존성)은 **상세를 한쪽에 두고 다른 쪽이 참조**한다 — 두 문서에서 따로 갱신되어 서로 어긋나는 것을 막는다.

## 근거

- 독자가 다르면 묻는 질문이 다르다 — 설치자는 "무엇을 깔면 도나", 개발자는 "어떻게 빌드·디버그하나". 한 테마로 합치면 양쪽 다 검색 비용이 커진다.
- scout가 경계를 모르면 dev-guide에 설치·운영 내용이, requirements에 개발 도구 내용이 섞여 중복·드리프트가 난다([[entity-docu-automatic]]의 테마 체계는 관점×독자로 정의).
- 위키 잠정안(통합 아닌 경계 명시)과 **일치** — 사용자 최종 확정.

## 구현 세부는 열어둠

경계 문장을 **테마 정의(프롬프트)**에 명시할지, **critic 적합성 기준**([[decision-critic-grounding-secrets]])에 반영할지는
구현 세부로 남긴다 — 양쪽 다 가능하며 이 결정이 강제하지 않는다.

## 기각 대안

- **두 테마를 하나로 통합** — 소재가 겹친다는 이유로 합치면 설치자와 개발자가 같은 색인을 뒤져야 하고, 관점×독자로 정의된 테마 체계가 무너진다.
- **겹치는 사실을 양쪽에 중복 기재** — 상세를 양쪽에 두면 따로 갱신되어 드리프트. 한쪽 상세 + 다른쪽 참조로 회피.

이 결정이 [[question-requirements-devguide-boundary]]를 답한다. 관련: [[decision-theme-scope-expansion]] · [[decision-theme-activation-checklist]]. 근거: [[2026-07-07-open-questions-decisions]]. 요약: [[summary-open-questions-decisions]].
