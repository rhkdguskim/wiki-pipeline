# 소스 관리 (FR-1~3)

← [문서 인덱스](../README.md)

문서화 대상 과제 레포의 등록/해제. 온보딩 = 등록 1건, 소스 레포는 무수정 ([G3](../goals.md)).

## 요구사항

| ID | P | 요구사항 |
|----|---|----------|
| FR-1 | P0 | **소스 등록**: `project_id`, `project_path`, `doc_dir`, `baseline_sha`(기본값: 등록 시점 HEAD)로 등록. 등록 즉시 다음 배치 대상에 포함 |
| FR-2 | P0 | **소스 해제/비활성화**: soft delete. 실행 이력은 보존 → [data-model](../data-model.md) |
| FR-3 | P2 | **baseline 문서 생성 옵션**: 등록 시 콜드 스타트 Day 0 뼈대 생성(구조·파일명 기반 목차 수준)을 선택 실행 |

## baseline_sha 규칙

새 소스 등록 시 `last_processed_sha`의 초기값. 비워두면 첫 배치가 레포 전체 히스토리를 처리하려 드는
사고가 나므로, 다음 중 하나로 설정한다:

1. **등록 시점 HEAD** (기본) — 그 시점 이후의 변경만 따라간다
2. 전체 스캔으로 baseline 문서를 먼저 생성(FR-3)한 뒤 **그 지점의 sha** — 콜드 스타트 전략은 생성 엔진의 "Day 0 뼈대 → 점진 채움"과 연결 → [generation](./generation.md)

## API

`POST /sources` · `GET /sources` · `DELETE /sources/{id}` → [api.md](./api.md)
