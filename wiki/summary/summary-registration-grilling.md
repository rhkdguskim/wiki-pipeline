---
type: summary
title: 레포 등록·docs-hub grilling 요약
tags: [registration, docs-hub, branch, grilling, summary]
status: active
---

# 요약: 레포 등록·docs-hub 구조 grilling (2026-07-06)

등록 시나리오([[decision-repo-registration-flow]]) 확정 직후, "등록된 뒤 무엇을 하는가"의
남은 모호함을 `/grill-me`로 좁힌 기록. 원본: [[2026-07-06-registration-grilling]](불변).

> [!note] 후속 전환 (2026-07-06)
> 이 세션이 확정한 "레포×브랜치 다중 등록(정책 C)" 모델은 이후 **레포 1개 등록 + 개발/배포 브랜치 2개**로
> 대체됐다 → [[decision-repo-dev-release-registration]]. 아래 기록은 그 전환 이전의 상태다.
> 좀비 비활성화·protected 재활성화·baseline 질문은 새 모델에서도 유효하다.

## 확정 (decision으로 반영)

- **docs-hub 구조** — 소스 N개 → 레포 1개, 소스별 폴더 분리. 폴더 경로는 `full_namespace_path/branch`
  규칙으로 자동 생성(슬래시 브랜치명은 `-` 치환) → [[decision-docs-hub-folder-rule]].
- **브랜치 등록 정책 C** — 모든 브랜치 노출 + 비-기본 경고. 같은 레포를 다른 브랜치로 여러 번 등록
  허용(각 등록이 독립 원자 단위·독립 폴더) → [[decision-branch-loss-policy]].
- **좀비 등록 처리** — compare 404 시 자동 비활성화 + 알림(삭제 아님). 5xx/타임아웃은 재시도
  → [[decision-branch-loss-policy]].
- **브랜치 소실 재활성화** — protected/default는 자동 재활성화, 비-protected는 수동만(flapping 차단)
  → [[decision-branch-loss-policy]].

## 미확정 (question으로 남김)

- **첫 문서화 baseline** — 신규 등록 소스의 `last_processed_sha` 초기값(A 전체/B HEAD/C 지정).
  A 기본 + backfill 분리안이 제안됐으나 사용자 승인 전 → [[question-initial-backfill-baseline]].

## 갱신된 기존 페이지

[[entity-docs-hub]](소스별 폴더 규칙)·[[decision-db-source-of-truth]](doc_dir·enabled 의미론)·
[[decision-repo-registration-flow]](정책 C·다중 브랜치 등록 명확화)·[[decision-pull-model]](404 실패 경로)·
[[question-ci-less-source-policy]](소실 vs 방치 구분).

전체 그림: [[overview]]
