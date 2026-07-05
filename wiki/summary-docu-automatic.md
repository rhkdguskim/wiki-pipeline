---
type: summary
title: Docu-Automatic 레포 분석 요약
tags: [docu-automatic, engine]
status: active
---

# Docu-Automatic 레포 분석 요약

> 원본: `../raw/2026-07-05-docu-automatic-notes.md` · 레포: https://github.com/jaeCheon8587/Docu-Automatic

기존에 구축 완료된 **문서 생성 엔진**의 분석 기록 요약. wiki-pipeline은 이 엔진의 자동 운영 계층이다.

## 요지

- Claude Code 기반, scout → docu-writer → critic 에이전트가 테마를 순차 순회하며 문서 생성 ([[entity-docu-automatic]])
- 산출물 6개(스킬 4 + 에이전트 2) 완료 상태
- 원 설계(v4)는 push 트리거 + docs-auto 브랜치 방식 — wiki-pipeline에서 pull 배치 + MR로 조정
  ([[decision-pull-model]], [[decision-mr-review-gate]])
- frontmatter의 `source_files`/`theme` 필드가 "코드 경로 ↔ 문서" 매핑의 기반
- 대화형 CLI 전제라 **headless 실행 검증 필요** → [[question-headless-claude-auth]]

## 이 소스에서 파생된 페이지

[[entity-docu-automatic]] · [[question-headless-claude-auth]] · [[question-mr-vs-docs-auto]] · [[question-theme-expansion]]

전체 그림 → [[overview]]
