---
type: decision
title: 코드 인덱스 = 파이프라인 범위 제외 (개발자 개인 관리 이관)
tags: [code-index, scope, personal-tooling]
status: active
---

# 결정: 코드 인덱스는 중앙 파이프라인에서 뺀다 — 개발자 개인이 관리한다

코드 인덱싱을 시스템(중앙 파이프라인) 범위에서 **제외**한다. 코드 검색·traversal이 필요한 개발자는
**개인 로컬 도구**(예: [[entity-codegraph]]에서 조사한 cg-colby류)를 자기 작업 환경에서 직접 운영한다.
시스템 범위는 **문서 자동화 2 파이프라인**(정적 · 매뉴얼 추출)으로 좁아진다.

## 근거

- **소비 지점이 개인이다** — 코드 인덱스의 소비자는 개발자(와 그의 AI 코딩 도구) 개인이고, 조회 대상은
  대개 그 개발자의 **로컬 작업 트리**다. 로컬 도구가 작업 트리를 직접 감시하면, 중앙 인덱스가 안고 가야
  할 원격 동기화 문제 — 폴링 신선도 랙, 커밋 되돌리기(revert/reset)·force-push 복구, push 안 된 로컬
  상태와의 괴리 — 가 **발생 자체를 하지 않는다**. 되돌리기 불일치 논의가 이 결정의 직접 발단이다
  → [[2026-07-06-code-index-out-of-pipeline]]
- **중앙화의 근거가 없다** — 인덱싱은 비-AI·결정적·저비용이라, 이 시스템이 작업을 중앙에 모으는 이유
  (AI 호출 비용 통제·사람 MR 리뷰 게이트)가 애초에 적용되지 않는다. 반면 중앙 운영 비용(짧은 주기 폴링 ·
  버전 스냅샷 · 별도 서빙 평면 · 러너 clone)은 실재했다
- **가치 중복 우려가 있었다** — GitLab 내장 blob 검색·CodeScene 정적분석이 이미 존재
  → [[question-blob-vs-code-index-overlap]] (이 결정으로 질문 자체가 해소)
- **MVP 절단선 단순화** — 파이프라인 3종→2종으로 [[question-mvp-scope]]의 절단면이 더 깨끗해진다

## 효력 — 2026-07-05 코드 인덱스 결정군 일괄 supersede

| superseded 결정 | 담았던 내용 |
|---|---|
| [[decision-code-index-pipeline]] | 파이프라인 도입 · 짧은 주기 폴링 |
| [[decision-code-index-provider-abstraction]] | 프로바이더 추상화 (index/query/manage) |
| [[decision-code-index-mcp-serving]] | 질의 채널 = MCP 서버 |
| [[decision-runner-git-clone]] | 인덱싱 소스 확보 = 러너 git clone |
| [[decision-code-index-versioning]] | 버전 스냅샷 + 원자 교체 |
| [[decision-code-index-adapter-cg-colby]] | 첫 어댑터 = cg-colby |
| [[decision-code-index-single-repo-scope]] | v1 질의 범위 = 단일 레포 |
| [[decision-code-index-store-plane]] | 저장소 = 별도 질의 서비스 평면 |

- [[entity-codegraph]]의 도구 실측(cg-colby·cgc 조사)은 **개인 도구 선택 참고 자료**로 유효하다 —
  특히 cg-colby는 레포 내부 저장·와처 증분·content-hash sync라 개인 로컬 관리에 그대로 맞는다
- [[decision-runner-git-clone]]에 실렸던 실측 사실(러너=Windows · git LFS)은 [[entity-mirero-gitlab]]이 계속 보유

## 기각 대안

- **중앙 코드 인덱스 파이프라인 유지** (2026-07-05 결정군) — 개발자 개인 조회라는 소비 형태에 비해
  중앙 운영 비용이 크고, 원격 동기화 문제가 구조적으로 따라온다. 기존 실물(blob 검색·CodeScene)과의
  경계 정리 부담도 남아 있었다.

## 재검토 조건 (기각 아님 — 재도입 여지)

- **개인이 로컬에서 만들 수 없는 요구**가 실증되면 중앙화를 재검토한다 — 예: cross-repo 질의
  ([[decision-code-index-single-repo-scope]]가 후순위로 남겼던 축), 과제 횡단 심볼 검색.
  그때는 superseded 결정군이 설계 출발점이 된다.

소스: [[2026-07-06-code-index-out-of-pipeline]] · 요약: [[summary-code-index-out-of-pipeline]]
