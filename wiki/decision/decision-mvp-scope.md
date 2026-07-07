---
type: decision
title: MVP 절단선 = 정적 + 매뉴얼 두 파이프라인 (GitLab 1 커넥터)
tags: [mvp, scope, phase-1, phase-2]
status: active
---

# 결정: 첫 출시(MVP)에 정적과 매뉴얼 추출 파이프라인을 둘 다 넣는다

MVP 첫 출시 범위를 **정적(Docu-Automatic) + 매뉴얼 추출** 두 파이프라인 모두로 확정한다.
코드 인덱스는 여전히 시스템 범위 자체에서 제외([[decision-code-index-out-of-pipeline]]).
SCM 커넥터는 인터페이스를 유지하되 구현은 **GitLab 1개**만, GitHub는 MVP 이후.

## 후보안(정적만)에서 갈라진 지점

[[question-mvp-scope]]가 2026-07-06 query에서 도출한 잠정 후보안은 **정적 파이프라인 1개 + 최소 Control Plane**
(매뉴얼은 절단면이 깨끗하다는 이유로 제외)이었다. 사용자는 이번(2026-07-07)에 **매뉴얼 포함**을 선택해
후보안과 갈라졌다. 즉 이 결정은 위키가 합성한 잠정안을 **번복이 아니라 상향(확대)**한 것이다 —
후보안이 결정으로 굳지 않았으므로 supersede 대상이 아니고, question이 answered로 전환될 뿐이다.

## 함의 — 매뉴얼 open 질문이 MVP 블로커로 승격

매뉴얼을 MVP에 넣으면 매뉴얼 파이프라인의 미해결 질문이 더는 Phase 3+로 미룰 수 없는 **MVP 블로커**가 된다:

- [[question-artifact-type-dispatch]] — 아티팩트 타입별(exe/msi/nuget/container) 획득·기동. 매뉴얼 순회의 전제라 MVP 블로커.
- [[question-ci-less-source-policy]] — CI/릴리스 없는 방치 소스 처리. 매뉴얼은 릴리스 트리거·아티팩트에 의존하므로 매뉴얼 대상 등록에 직접 걸림 (2026-07-07 수동 큐레이션으로 정책 확정 → [[decision-source-manual-curation]]).
- [[question-release-object-vs-tag-trigger]] — 태그 vs Release 객체 트리거 확정.

## 포함 (확정 결정 위)

- 정적 파이프라인 전량 — 등록·pull·야간 배치·엔진·MR 게이트·관측성·장애 안전장치 ([[decision-repo-dev-release-registration]] · [[decision-pull-model]] · [[decision-nightly-batch]] · [[decision-mr-review-gate]] · [[decision-pipeline-observability]] · [[decision-branch-loss-policy]])
- 매뉴얼 추출 파이프라인 — 릴리스 아티팩트 소비·앱 관측·라이프사이클 diff ([[decision-manual-pipeline-separate]] · [[decision-artifact-consumption]] · [[decision-release-tag-trigger]] · [[decision-hybrid-app-traversal]])
- 공유 뼈대 — Control/Data Plane 분리·이력 DB SoT·사내 VM 서버 ([[decision-control-data-plane-split]] · [[decision-db-source-of-truth]] · [[decision-server-vm-self-token]])
- SCM 커넥터 — 추상화 인터페이스는 유지, MVP 구현은 GitLab 1개(실측 완료 환경 [[entity-mirero-gitlab]]) → [[decision-scm-connector-abstraction]]

## 제외

- **GitHub 커넥터** — 인터페이스는 있으나 구현은 MVP 이후 (실측 환경이 GitLab뿐).
- **코드 인덱스** — MVP 차원이 아니라 시스템 범위 자체에서 제외 → [[decision-code-index-out-of-pipeline]]
- **Phase 3+ 후보** — 테마 2차 확장([[question-theme-expansion]]) · 리뷰 피드백 루프([[question-review-feedback-loop]]) · 문서 Q&A/RAG([[question-doc-qa-rag]])
- **시크릿 저장 보안 강화** — 운영 단계로 연기 → [[question-secret-storage-security]]

## 기각 대안

- **정적만 (위키 후보안)** — 절단면이 가장 깨끗하고 결정 성숙도가 높지만, 사용자가 매뉴얼도 첫 출시에 원했다. 매뉴얼을 미루면 두 모달리티 중 절반만 검증한 채 출시하게 된다.
- **세 파이프라인 전부(코드 인덱스 포함)** — 코드 인덱스는 이미 범위 밖이라 후보에서 배제.

이 결정이 [[question-mvp-scope]]를 답한다. 근거: [[2026-07-07-open-questions-decisions]]. 요약: [[summary-open-questions-decisions]].
