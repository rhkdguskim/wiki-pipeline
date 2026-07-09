---
type: summary
title: 코드 인덱스 후속 확정 (MCP 서빙·clone·형상 관리) 요약
tags: [code-index, session]
status: active
---

# 요약: 코드 인덱스 후속 논의 (2026-07-05)

원문: [[2026-07-05-code-index-followup]]

직전 ingest([[summary-code-index-pipeline]])가 남긴 열린 질문 3건에 대한 사용자 답으로 결정 3건이 확정됐다:
질의 채널은 **MCP 서버**(개발자가 붙어 코드베이스를 빠르게 스캔), 소스 확보는 **러너 git clone**
(커넥터 4책임 확장 기각), 인덱스는 **버전 스냅샷 + 원자 교체**로 형상 관리(재인덱싱 중 직전 버전 서빙).

## 파생 페이지

- [[decision-code-index-mcp-serving]] — 질의 채널 = MCP 서버 (자체 UI·IDE 플러그인은 후순위)
- [[decision-runner-git-clone]] — checkout은 러너 직접, 커넥터는 3책임 유지 ([[question-scm-checkout]] answered)
- [[decision-code-index-versioning]] — sha 결부 버전 스냅샷·원자 교체·직전 버전 서빙
- 갱신: [[question-code-index-query-surface]](서빙 형태 확정, 연산 목록 open) · [[question-code-index-store]](버저닝 확정, 소유·보존 open)

## 계보

- 선행: [[summary-code-index-pipeline]] — 파이프라인 설계 논의 (도입·프로바이더 추상화·traversal)
- 후속: [[summary-code-index-finalization]] — 마지막 열린 질문 3건 확정 (어댑터·질의 범위·저장소 평면)
