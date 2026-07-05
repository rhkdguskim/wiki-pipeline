---
type: decision
title: 서버 DB가 source of truth (sources.yml 커밋 기각)
tags: [database, state]
status: active
---

# 결정: 서버 DB가 source of truth

구독 목록·`last_processed_sha`·실행 이력은 관리 서버의 DB에 저장한다 (SQLite 시작 → 필요시 Postgres, [[question-server-stack-db]]).

## 기각된 대안: sources.yml을 레포에 커밋

- `last_processed_sha`가 매일 갱신 → 포인터 하나 바꾸는 커밋이 매일 쌓임
- 사용자 등록 시점과 야간 배치의 sha 갱신 시점이 겹치면 push 충돌

## 스키마 (3 테이블)

`sources`(project_id, doc_dir, baseline_sha, last_processed_sha, enabled) ·
`runs`(type, status, target, pipeline_url) · `run_items`(run×source 결과: from/to sha, 문서 수, mr_url, error)

- 불변 규칙: sha는 MR 성공 보고 후에만 전진 → [[concept-idempotent-sha]]
- run_items는 삭제하지 않음 (비활성화 후에도 이력 보존)
- 필요 시 sources.yml은 읽기 전용 스냅샷 export만

관련: [[summary-design-session]] · [[overview]]
