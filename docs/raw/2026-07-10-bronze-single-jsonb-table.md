# raw — bronze 저장 방식 결정 (단일 범용 JSONB 테이블)

- 날짜: 2026-07-10
- 성격: grill(설계 검증) 세션 중 사용자 결정
- 맥락: 데이터 수집 커넥터 아키텍처([[decision-ingestion-connector-architecture]])에서 `IngestionConnector.to_bronze(raw_record) -> bronze_row`가 선언돼 있으나, 정작 bronze_row를 저장할 테이블이 backend 코드에 없음(코드 확인 2026-07-10: models.py는 전부 run 중심, bronze/silver/gold 부재). 개발 착수 시 "bronze를 어디에 INSERT 하나"에서 막히는 지점.

## 제시한 갈래

- **A. 소스별 전용 테이블** (`monday_items_bronze`, `jira_issues_bronze` …): 쿼리 편하나 소스 추가마다 마이그레이션 → "상위 코드 무변경" 확장성 원칙과 충돌.
- **B. 단일 범용 bronze 테이블** (`raw_records(connector_kind, source_id, external_id, payload_jsonb, content_sha256, watermark, ingested_at)`): 소스 추가에 스키마 변경 0. medallion "bronze=원본 거울, 변환 금지" 철학과 일치. PostgreSQL JSONB.
- **C. bronze 없이 곧장 DocumentStore(md)**: 지금 제일 단순하나 오늘 확정한 4층 아키텍처를 스스로 뒤엎음.

## 사용자 결정

> "서랍 하나에 넣자."

= **B 채택.** 소스 구분 없는 단일 bronze 테이블에 `payload = 원본 JSON 통째` + 꼬리표(connector_kind·external_id·수집시각 등)만 붙여 쌓는다. 타입 정제·필드 추출은 다음 층(silver)에서.

## 코드 관례 재사용 (models.py 확인)

- `RunDocOutput.content_sha256`(String(64)) 패턴 → bronze도 `content_sha256`으로 "이미 받은 레코드면 skip"(증분 수집).
- `RunDocOutput.content_text`가 `deferred=True`인 관례 → bronze의 `payload_jsonb`도 리스트 조회 시 원본 통째를 안 읽도록 deferred 고려.
- `SystemSetting`처럼 커넥터 설정은 별도([[decision-connector-settings-system-settings]]).
