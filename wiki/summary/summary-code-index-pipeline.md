---
type: summary
title: 코드 인덱싱 파이프라인 설계 논의 요약
tags: [code-index, session]
status: active
---

# 요약: 코드 인덱싱 파이프라인 설계 논의 (2026-07-05)

원문: [[2026-07-05-code-index-pipeline]]

새 파이프라인 — 등록된 소스 레포(GitLab·GitHub)의 코드를 인덱싱해 **개발자가 직접 조회**하는 저장소로 유지한다.
비-AI·빠름·결정적이라 야간 배치가 아닌 **짧은 주기 폴링**으로 commit 수준 신선도를 확보하고,
인덱싱 기술(codegraph)은 **프로바이더 인터페이스**(index/query/manage, code traversal 1급 연산) 뒤로 숨겨
교체 가능하게 한다. 기존 pull 메커니즘(compare + sha 포인터)은 주기만 바꿔 재사용 — 야간 배치·pull 결정의
push 기각 근거는 AI 워크로드 전제라 번복이 아니라 적용 범위 한정이다.

## 파생 페이지

- [[decision-code-index-pipeline]] — 파이프라인 도입·실행 흐름·짧은 주기 폴링 (야간 배치/webhook/CI job 기각)
- [[decision-code-index-provider-abstraction]] — 프로바이더 추상화, codegraph 은닉, traversal 1급 연산
- [[concept-port-adapter]] — SCM 커넥터와 공유하는 패턴의 개념 승격
- [[entity-codegraph]] — 첫 어댑터 후보 (계약 조사 필요)
- [[question-code-index-query-surface]] · [[question-scm-checkout]] · [[question-code-index-store]]
