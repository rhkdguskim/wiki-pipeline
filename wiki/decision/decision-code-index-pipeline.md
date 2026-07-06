---
type: decision
title: 코드 인덱싱 파이프라인 도입 (짧은 주기 폴링, 개발자 직접 조회)
tags: [code-index, pipeline, polling, freshness, developer-facing]
status: active
---

# 결정: 코드 인덱싱 파이프라인을 도입한다 — 비-AI·짧은 주기 폴링·개발자 직접 조회

등록된 소스 레포(GitLab·GitHub — 문서 파이프라인과 같은 등록 체계)의 코드를 인덱싱해,
**개발자가 직접 조회**(코드 검색·code traversal)할 수 있는 저장소로 유지하는 새 파이프라인.
인덱싱 기술은 프로바이더 인터페이스 뒤로 숨긴다 → [[decision-code-index-provider-abstraction]].

## 문서 파이프라인과의 대비 — 독립 파이프라인

| 축 | 문서 파이프라인 | 코드 인덱스 파이프라인 |
|----|----------------|----------------------|
| 작업 성격 | AI 생성 — 무겁고 비쌈 | 결정적 인덱싱 — **비-AI, 빠름** |
| 트리거 | 야간 배치 1회 → [[decision-nightly-batch]] | **짧은 주기 폴링** (commit 수준 신선도) |
| 산출물 | MR — 사람 리뷰 게이트 → [[decision-mr-review-gate]] | 인덱스 저장소 — 파생 데이터, 게이트 없음 |
| sha 포인터 | MR 성공 후 전진 | 인덱싱 성공 후 전진 (**독립 포인터**) |
| 실시간성 | 의도적 포기 | 요구사항 (개발자 직접 조회) |

## 실행 흐름 — 쓰기와 읽기가 갈린다

- **쓰기 경로** (짧은 주기): 폴링으로 새 커밋 감지(compare) → SCM 커넥터로 소스 확보 → 프로바이더
  `index(repo, sha)` → **성공 후에만** 인덱스 sha 전진([[concept-idempotent-sha]] 재사용) + 완료 보고(이력 DB)
- **읽기 경로** (온라인): 개발자 → 질의 API/UI → 프로바이더 `query`(traversal). 재인덱싱 중에도
  직전 인덱스로 질의 가능해야 → [[question-code-index-store]]
- 인덱싱은 Data Plane에서 실행(지휘·실행 분리 유지 → [[decision-control-data-plane-split]]),
  소스 접근은 [[decision-scm-connector-abstraction]] 경유 — 단 소스 전체 확보 필요 → [[question-scm-checkout]]

## 기각 대안

| 대안 | 기각 이유 |
|------|----------|
| 야간 배치로 함께 처리 | 최대 하루 지연 — 개발자 직접 조회 용도에 신선도 미달. 비-AI·저비용이라 밤으로 모을 이유도 없음 |
| webhook 자동 설치 | GitHub(외부 클라우드) → 사내 서버 인바운드 개방 필요 — [[question-runner-ai-network]]와 같은 망 이슈 재현 |
| 소스 레포 CI job | [[decision-pull-model]]의 기각 유지 — 소스 레포 무수정 원칙·온보딩 마찰 |

## 기존 결정과의 관계 (번복 아님)

[[decision-pull-model]]·[[decision-nightly-batch]]가 push를 기각한 근거는 **AI 워크로드 전제**
(호출 비용·MR 리뷰 폭주). 인덱싱은 비-AI·빠름·MR 없음이라 그 근거가 적용되지 않는다.
pull 메커니즘(compare + sha 포인터)은 그대로 쓰되 **주기가 파이프라인별 정책**으로 분리된다 —
야간 배치는 문서 파이프라인의 속성으로 한정.

## 실측 배경 (2026-07-06) — 기존 검색·분석 실물과의 경계

[[2026-07-06-wish-gitlab-api-survey]]에서 인덱스 파이프라인 주변의 기존 실물이 드러났다: GitLab 내장 blob 검색
(`search?scope=blobs` 200, 단 CE라 Elasticsearch 미탑재 = 텍스트 매치 수준), CodeScene 정적분석 그룹(26개 프로젝트).
이 둘과 codegraph traversal의 역할 중복/보완 정리는 미해결 → [[question-blob-vs-code-index-overlap]]. 또한 웹훅·스케줄
0개라 사내 이벤트 인프라가 없어 폴링(pull) 전제가 실측으로 뒷받침된다.

관련: [[decision-code-index-provider-abstraction]] · [[question-code-index-query-surface]] · [[entity-mirero-gitlab]] · 소스: [[2026-07-05-code-index-pipeline]] · [[2026-07-06-wish-gitlab-api-survey]]
