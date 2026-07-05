---
type: summary
title: 코드 인덱스 파이프라인 최종 확정 요약 (어댑터·질의 범위·저장소 평면)
tags: [code-index, session]
status: active
---

# 요약: 코드 인덱스 파이프라인 최종 확정 (2026-07-05)

원문: [[2026-07-05-code-index-finalization]]

코드 인덱스 파이프라인의 마지막 열린 질문 3건이 사용자 결정으로 닫혔다. 어댑터는 **cg-colby(A)**,
질의 범위는 **단일 레포 우선**, 저장소 평면은 **별도 질의 서비스 평면**. 이로써 파이프라인의 쓰기/읽기/저장/형상
전 축이 결정으로 닫혔다.

## 파생 페이지

- [[decision-code-index-adapter-cg-colby]] — 첫 어댑터 = cg-colby 확정 (cgc 기각)
- [[decision-code-index-single-repo-scope]] — v1 질의 범위 = 단일 레포 (cross-repo 후순위)
- [[decision-code-index-store-plane]] — 인덱스 저장소 = 별도 질의 서비스 평면 (관리 서버와 분리)

## 열린 question 닫힘

- [[question-code-index-query-surface]] answered — MCP 서빙 확정에 이어 cross-repo=후순위, tool 표면은 어댑터 정책 따름
- [[question-code-index-store]] answered — 별도 서비스 평면 + 버전 스냅샷([[decision-code-index-versioning]])

## 선행 요약

- [[summary-code-index-pipeline]] → [[summary-code-index-followup]] → (이 요약) — 코드 인덱스 세션 3부작의 마지막.

## 계보 (코드 인덱스 결정 전목)

1. 도입·트리거 — [[decision-code-index-pipeline]]
2. 프로바이더 추상화 — [[decision-code-index-provider-abstraction]]
3. 형상 관리 — [[decision-code-index-versioning]]
4. 질의 채널 — [[decision-code-index-mcp-serving]]
5. 소스 확보 — [[decision-runner-git-clone]]
6. **어댑터** — [[decision-code-index-adapter-cg-colby]]
7. **질의 범위** — [[decision-code-index-single-repo-scope]]
8. **저장소 평면** — [[decision-code-index-store-plane]]
