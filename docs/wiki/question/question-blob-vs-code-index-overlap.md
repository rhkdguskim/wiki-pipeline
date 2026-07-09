---
type: question
title: GitLab 내장 blob 검색 vs 코드 인덱스(CodeScene/codegraph) 역할 중복
tags: [code-index, search, codescene, overlap]
status: answered
---

# ❓ 내장 blob 검색·CodeScene과 코드 인덱스 파이프라인의 역할 중복

실측([[2026-07-06-wish-gitlab-api-survey]])이 코드 인덱스 파이프라인([[decision-code-index-pipeline]])
주변에 이미 존재하는 두 실물을 드러냈다.

## 실측 사실

- **GitLab 내장 blob 검색**: `GET /projects/:id/search?scope=blobs`는 200으로 동작(경로+라인 반환).
  단 CE라 **Advanced Search(Elasticsearch) 미탑재** → 정규식/기본 인덱스 수준, **의미 검색·traversal 아님**.
- **CodeScene 정적분석**: `mirero/Static-Code-Analysis` 그룹에 26개 프로젝트(`pwm-*-codescene` 등) 이미 운영 중.

## 검토할 것

- 코드 인덱스의 가치 제안(정의↔참조·호출 그래프 traversal → [[decision-code-index-provider-abstraction]])이
  **내장 blob 검색과 겹치지 않음**을 확인 — blob 검색은 텍스트 매치, 인덱스는 구조 순회. 보완 관계로 정리 가능한가.
- **CodeScene과의 관계**: CodeScene은 코드 건강도·기술부채 분석(정적 품질)이고 codegraph는 심볼/호출 순회(개발자 조회).
  대상 프로젝트군·목적이 다른가, 아니면 codegraph 도입 전 CodeScene 재활용 여지가 있는가.
- 개발자에게 "무엇을 언제 쓰라"는 경계(내장 검색 / CodeScene / codegraph MCP) → [[question-code-index-query-surface]] answered와 연결.

## 답 — 질문 자체가 해소 (2026-07-06)

코드 인덱스가 중앙 파이프라인 범위에서 **제외**되면서([[decision-code-index-out-of-pipeline]])
"중앙 코드 인덱스 vs 기존 실물" 중복 문제가 성립하지 않게 됐다. 내장 blob 검색·CodeScene은
기존대로 쓰고, 구조 질의(traversal)는 개발자 개인 로컬 도구의 영역이다. 이 중복 우려는
제외 결정의 근거 중 하나로 흡수됐다.

관련: [[decision-code-index-pipeline]] · [[entity-codegraph]] · [[entity-mirero-gitlab]]
