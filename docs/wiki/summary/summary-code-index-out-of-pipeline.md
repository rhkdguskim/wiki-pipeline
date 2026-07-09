---
type: summary
title: 코드 인덱스 파이프라인 범위 제외 요약
tags: [code-index, scope, supersede]
status: active
---

# 요약: 코드 인덱스 — 파이프라인 범위 제외 (개인 관리 이관)

소스: [[2026-07-06-code-index-out-of-pipeline]] (2026-07-06 대화)

커밋 되돌리기(revert/reset) 시 중앙 인덱스와 레포 상태가 어긋나는 문제 질문에서 출발했다.
분석 결과 revert는 기존 폴링이 소화하고 force-push는 "HEAD 전체 재인덱싱 + 원자 교체"로 풀 수
있었지만, 논의는 더 근본적인 결론에 도달했다 — **소비 지점이 개발자 개인의 로컬 작업 트리라면,
중앙 인덱스가 안고 가는 원격 동기화 문제(신선도 랙 · 되돌리기 복구 · 미푸시 상태와의 괴리)는
개인 로컬 도구에서는 발생 자체를 하지 않는다.** 이에 코드 인덱스를 중앙 파이프라인 범위에서
제외하고 개발자 개인 관리로 이관했다. 시스템은 문서 자동화 2 파이프라인(정적·매뉴얼 추출)으로 좁아진다.

## 파생 페이지

- 생성: [[decision-code-index-out-of-pipeline]] — 범위 제외 결정 + 2026-07-05 코드 인덱스 결정군 8건 일괄 supersede
- 갱신(superseded 8건): [[decision-code-index-pipeline]] · [[decision-code-index-provider-abstraction]] ·
  [[decision-code-index-mcp-serving]] · [[decision-runner-git-clone]] · [[decision-code-index-versioning]] ·
  [[decision-code-index-adapter-cg-colby]] · [[decision-code-index-single-repo-scope]] · [[decision-code-index-store-plane]]
- 갱신(question): [[question-blob-vs-code-index-overlap]] answered(질문 자체 해소) ·
  [[question-code-index-query-surface]] · [[question-code-index-store]] · [[question-scm-checkout]]에 supersede 주석
- 갱신(기타): [[entity-codegraph]](개인 도구 참고 자료로 재규정) · [[overview]](파이프라인 3종→2종) ·
  [[question-mvp-scope]](절단선 단순화)
