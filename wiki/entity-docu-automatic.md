---
type: entity
title: Docu-Automatic (문서 생성 엔진)
tags: [engine, claude-code, agents]
status: active
---

# Docu-Automatic — 문서 생성 엔진

기존 자산 (완료 상태). 레포: https://github.com/jaeCheon8587/Docu-Automatic
wiki-pipeline 실행 흐름의 "AI 문서 생성" 단계를 담당한다.

## 구조 (v4, 1단계 오케스트레이션)

```
Main CLI (Level 0): task-pipeline 스킬 — 테마 루프 + 재시도 + 저장
  ├── scout:       코드 탐색 + 문서화 필요 판단 + 요구사항서
  ├── docu-writer: 요구사항서 기반 .md 작성
  └── critic:      frontmatter + 테마 적합성 독립 검증
```

- 테마 순차 순회, 4단계 사이클(판단→작성→검증→저장)
- 재시도 최대 2회 → 초과 시 `auto_generated_warning` 태그 저장, 3연속 FAIL 시 중단
- Full Reset: 매 테마 에이전트 신규 생성 (컨텍스트 오염 방지, 비용 1.0x)
- 1차 테마 4개 (intro / requirements / architecture-overview / component-diagram) → 확장은 [[question-theme-expansion]]
- frontmatter `source_files`/`theme` 필드 = 코드 경로 ↔ 문서 매핑 기반

## wiki-pipeline에서의 조정점

| 항목 | 원 설계 (v4) | wiki-pipeline |
|------|-------------|---------------|
| 트리거 | push 즉시 | 야간 pull 배치 → [[decision-pull-model]] |
| 산출물 | docs-auto 브랜치 | docs-hub 직접 MR → [[decision-mr-review-gate]], [[question-mr-vs-docs-auto]] |
| diff 입력 | 직전 커밋 | 누적 구간(sha~HEAD) → [[concept-idempotent-sha]] |
| 실행 | CLI 대화형 | headless `claude -p` — 미검증 ⛔ → [[question-headless-claude-auth]] |

소스 요약: [[summary-docu-automatic]] · 전체 그림: [[overview]] · 상세: `../docs/features/generation.md`
