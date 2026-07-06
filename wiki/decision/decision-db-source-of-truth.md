---
type: decision
title: 서버 DB가 source of truth (sources.yml 커밋 기각)
tags: [database, state]
status: active
---

# 결정: 서버 DB가 source of truth

구독 목록·`last_processed_sha`·실행 이력은 관리 서버의 DB에 저장한다.

## 기각된 대안: sources.yml을 레포에 커밋

- `last_processed_sha`가 매일 갱신 → 포인터 하나 바꾸는 커밋이 매일 쌓임
- 사용자 등록 시점과 야간 배치의 sha 갱신 시점이 겹치면 push 충돌

## 스키마 (3 테이블)

`sources`(project_id, doc_dir, enabled) — **레포 단위 1행** ·
`source_branches`(source_id, role[dev|release], branch, baseline_sha, last_processed_sha, enabled) — **등록당 2행(개발·배포)** ·
`runs`(type, status, target, pipeline_url) · `run_items`(run×브랜치 결과: from/to sha, 문서 수, mr_url, error)

- **등록 원자 = 레포 1개**([[decision-repo-dev-release-registration]]) → `sources`는 레포 단위, 브랜치는 `source_branches`에 개발/배포 2행으로 딸린다. sha 추적(baseline·last_processed)은 브랜치별.
- **`doc_dir`** — 사람이 입력하지 않고 `full_namespace_path/` + 역할 하위폴더(`dev`/`release`) 규칙으로 자동 생성 → [[decision-docs-hub-folder-rule]]
- **`enabled`** — compare 404(브랜치·레포 소실) 시 자동 `false` 전환(좀비 비활성화), 재활성화는 protected 여부로 분기. 브랜치 단위(`source_branches.enabled`)로 적용 → [[decision-branch-loss-policy]]
- 불변 규칙: sha는 MR 성공 보고 후에만 전진 → [[concept-idempotent-sha]]
- run_items는 삭제하지 않음 (비활성화 후에도 이력 보존)
- 필요 시 sources.yml은 읽기 전용 스냅샷 export만

관련: [[summary-design-session]] · [[overview]]
