---
type: decision
title: 코드 인덱스 v1 질의 범위 = 단일 레포 (cross-repo 후순위)
tags: [code-index, query, scope, traversal]
status: active
---

# 결정: v1은 한 레포 단위 질의만 — cross-repo 질의는 후순위

코드 인덱스의 v1 질의 범위는 **단일 레포**로 한정한다. 한 레포 안의 심볼 검색·정의로 이동·참조 찾기·
호출 그래프·의존 순회(traversal, [[decision-code-index-provider-abstraction]]의 1급 연산)만 다룬다.
여러 레포를 횡단하는 질의(A 레포 함수가 B 레포를 호출·의존하는 관계 추적)는 **후순위**로 미룬다.

## 근거

- **단순성** — 단일 레포는 저장소·질의 계약이 단순하다. 인덱스·버전·sha 포인터가 레포 단위로 자연스럽게 매핑.
- **어댑터 정합** — cg-colby([[decision-code-index-adapter-cg-colby]])의 "레포별 독립 `.codegraph/`" 모델이
  단일 레포를 구조적으로 지원한다. 별도 합성 계층 없이 매핑.
- **실사용 우선순위 미확정** — cross-repo 질의가 실제로 얼마나 필요한지 개발자 사용 패턴 관찰이 선행해야 한다.

## 경계

- cross-repo가 후순위지 **기각은 아니다** — 프로바이더 인터페이스([[decision-code-index-provider-abstraction]])가
  확장 여지를 남기므로, 추후 레포 간 엣지 합성을 query 연산으로 추가해도 구조 변화가 없다.
- 단일 레포 한정이 **MCP tool 표면([[decision-code-index-mcp-serving]])을 제한하지는 않는다** — 한 레포 안에서의
  traversal 연산 종류는 cg-colby 정책(기본 단일 tool + 환경변수 다중 노출) 위에서 결정된다.

## 보류 대안 (기각 아님)

- **cross-repo 1급 지원** — 처음부터 여러 레포 관계를 묻는 연산 포함. 어댑터·저장소가 레포 간 엣지를
  합성해야 해서 v1 설계가 무거워진다. 사용 패턴 관찰 뒤 재검토.

관련: [[decision-code-index-pipeline]] · [[decision-code-index-adapter-cg-colby]] · 소스: [[2026-07-05-code-index-finalization]]
