---
type: decision
title: 코드 인덱스 프로바이더 추상화 (codegraph 은닉·교체 가능)
tags: [code-index, provider, abstraction, codegraph, traversal]
status: superseded
---

> [!superseded] 이 결정은 대체됨 (2026-07-06)
> 코드 인덱스가 중앙 파이프라인 범위에서 제외되어 프로바이더 인터페이스를 만들지 않는다
> → [[decision-code-index-out-of-pipeline]]. port-adapter 패턴 자체([[concept-port-adapter]])는
> SCM 커넥터에서 계속 유효.

# 결정: 인덱싱 기술을 프로바이더 인터페이스로 추상화하고 codegraph를 첫 어댑터로 숨긴다

파이프라인·서버는 우리가 정의한 **코드 인덱스 프로바이더 인터페이스**를 통해서만 인덱싱 기능과 대화한다.
[[entity-codegraph]]는 첫 구현 어댑터 후보일 뿐이며, **codegraph의 타입·API·저장 형식이 인터페이스 밖으로
새어나오면 안 된다** — 다른 기술로 교체해도 상위 로직은 무변경. [[decision-scm-connector-abstraction]]과
같은 패턴([[concept-port-adapter]])의 두 번째 실체화다.

## 프로바이더 인터페이스 (3책임)

| 책임 | 역할 | codegraph 어댑터 |
|------|------|------------------|
| **index** | 레포@sha 기준 인덱스 생성·증분 갱신 | codegraph 인덱싱 실행 |
| **query** | **code traversal 1급 연산** — 정의↔참조·호출·의존 관계 순회 + 심볼 검색 | codegraph 질의로 변환 |
| **manage** | 인덱스 상태 조회·무효화·재구축 | codegraph 저장소 관리 |

- query 표면의 구체 연산 목록은 미확정 → [[question-code-index-query-surface]] (traversal은 확정된 최소 요구)
- 어댑터 계약을 확정하려면 codegraph의 실제 기능·입출력 조사가 필요 → [[entity-codegraph]]

## 기각 대안

- **codegraph 직접 통합** — 파이프라인·서버가 codegraph API를 직접 호출. 초기 개발은 빠르지만
  타입·질의 언어·저장 형식이 시스템 전역에 퍼져 교체 비용이 시스템 전체 수정이 된다.
  교체 가능성이 이번 결정의 목적이므로 기각.

관련: [[decision-code-index-pipeline]] · [[concept-port-adapter]] · 소스: [[2026-07-05-code-index-pipeline]]
