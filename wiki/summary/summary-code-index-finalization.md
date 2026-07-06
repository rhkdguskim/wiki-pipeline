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

## 계보

이 세션이 코드 인덱스 파이프라인의 마지막 세 축(어댑터·질의 범위·저장소 평면)을 닫으며,
쓰기/읽기/저장/형상 전 축의 결정이 완결됐다. 코드 인덱스 결정 8건의 전체 카탈로그는
[[decision-index]]의 "코드 인덱스 파이프라인" 섹션이 소유한다.
