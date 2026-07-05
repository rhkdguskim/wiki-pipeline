# 데이터 모델 (관리 서버 DB)

← [문서 인덱스](./README.md)

DB가 구독 목록·sha·실행 이력의 **source of truth**다. `sources.yml` 파일 커밋 방식은 채택하지 않는다
(매일 포인터 커밋 누적 + push 충돌 → 근거: [architecture.md](./architecture.md)). 필요 시 읽기 전용 스냅샷 export만 제공.

## 스키마

```
sources                        -- 문서화 대상 과제 레포
  id, project_id, project_path, doc_dir,
  baseline_sha,                -- 등록 시점 기준점 (기본: 등록 시점 HEAD)
  last_processed_sha,          -- 어디까지 문서에 반영했는지 포인터
  enabled, created_at, updated_at

runs                           -- 파이프라인 실행 단위
  id, type(scheduled|manual), status(queued|running|succeeded|failed|partial),
  triggered_by, target_source_ids, full_regen(bool),
  gitlab_pipeline_id, gitlab_pipeline_url,
  started_at, finished_at

run_items                      -- run × source 단위 결과
  id, run_id, source_id,
  from_sha, to_sha,
  changed_files_count, affected_docs_count, generated_docs_count, warning_docs_count,
  mr_url, status(pending|running|succeeded|failed|skipped), error_message
```

## 불변 규칙

- `sources.last_processed_sha`는 해당 소스의 **MR 생성 성공 보고 후에만** 전진한다 → [mr.md 멱등성](./features/mr.md)
- `run_items`는 삭제하지 않는다 — 소스 비활성화 후에도 이력 보존 → [sources](./features/sources.md)
- 보존 기간·DB 선택(SQLite→Postgres) → [nfr.md](./nfr.md), [tech-stack.md](./tech-stack.md)
