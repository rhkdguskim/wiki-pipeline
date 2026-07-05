---
type: decision
title: 사람 MR 리뷰 게이트 (AI 자동 머지 금지)
tags: [mr, review, quality-gate]
status: active
---

# 결정: 모든 문서 변경은 사람 MR 리뷰를 거친다

AI 산출물은 docs-hub에 브랜치 + MR로만 제출한다. AI가 main에 직접 쓰지 않는다.

## 기존 docs-auto 브랜치 방식을 대체

Docu-Automatic 원 설계(v4)는 각 레포의 docs-auto 브랜치에 push 후 중앙 배치가 pull하는 방식.
MR 방식이 권장되는 이유: 사람 리뷰 게이트 확보 + 원 레포의 미결 사항("인간 리뷰 프로세스",
"docs-auto 브랜치 관리")이 함께 해소. 단 **최종 확정 필요** → [[question-mr-vs-docs-auto]]

## MR 규격

- 기본 소스별 1 MR. 본문에 근거 커밋 구간·변경 파일·생성 문서·경고 목록 명시
- 동일 소스의 열린 자동 MR이 있으면 **갱신** (중복 방지) → [[concept-idempotent-sha]]
- critic 2회 초과 fail 문서는 `auto_generated_warning` 태그 + MR에 표시 → 리뷰어가 판단
- 품질 추적 지표: 자동 MR 머지율

관련: [[entity-docu-automatic]] · [[summary-design-session]] · 상세: `../docs/features/mr.md`
