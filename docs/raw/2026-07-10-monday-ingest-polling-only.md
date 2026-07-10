# Monday 적재 = 폴링 단일 레인으로 단순화 (webhook 삭제)

> 2026-07-10 논의. [[2026-07-10-dwh-monday-ingestion-refinements]]에서 확정한 "webhook + 야간 폴링 하이브리드"를 재검토하여 webhook 레인을 삭제하고 스케줄러 폴링 단일 레인으로 단순화한 논의 기록.

## 발단 — Monday 커넥터 연결 설계 정리 중 두 지적

위키 query로 "Monday 커넥터를 어떻게 연결할 건지" 종합 답변을 제시한 뒤, 사용자가 두 지점을 지적:

1. **"4. 적재 전략 (webhook + 야간 폴링 하이브리드) — 이건 필요 없는데, 파이프라인 있잖아"**
2. **"6. 착륙지점 — 이건 안드레이 카파시가 말한 저장 아키텍처를 반영해야 할 거 같은데"**

## 지적 1 — webhook 하이브리드 삭제

### 문제 인식
- 이미 [[decision-monday-collector-langgraph-scheduled]]가 **스케줄러 + LangGraph 수집 에이전트**(= "파이프라인")를 확정했고, 이게 야간 전수 폴링 레인의 실행체다.
- webhook 레인의 유일한 존재 이유는 [[decision-monday-ingest-hybrid]]의 "실시간 근사(지연 단축)"뿐이다.
- webhook은 Monday가 30분(1분×30회) 재시도만 보장 → 유실 위험이 있어 **정확성은 어차피 폴링이 진실 소스**다. webhook은 correctness에 기여하지 않고 오직 latency만 줄인다.
- webhook 필요성 자체가 [[question-dwh-latency-target]](지연 목표 미확정)에 매달려 있었다.

### 사용자 결정
- **지연 목표 = 일 배치 수용**: "오늘 데이터를 내일 문서에 반영" 수용. 문서 자동화 파이프라인이 야간 배치라 실시간성이 불필요.
- 따라서 webhook 레인은 순수 과잉 → **삭제**. **스케줄러 폴링 단일 레인**으로 단순화.
  - 수집 = 스케줄러(cron) → LangGraph 폴링 에이전트 (야간 전수 + 증분 순회)
  - webhook 레인 없음 — 정확성은 폴링이 전담.

### 반영
- [[decision-monday-ingest-hybrid]] → `superseded`.
- 새 decision: [[decision-monday-ingest-polling-only]] (폴링 단일 레인).
- [[concept-readonly-saas-cdc]] → 하이브리드 정석에서 "폴링 단일이 기본, webhook은 지연 목표가 근실시간일 때만 더하는 옵션 레인"으로 정정.
- [[question-dwh-latency-target]] → `answered` (일 배치 확정 → webhook 불필요).

## 지적 2 — 카파시 저장 아키텍처

### 판정 — 이미 반영됨
- [[decision-dwh-as-karpathy-llm-wiki]]가 이미 bronze `raw_records` append를 Karpathy 3동작으로 승격:
  - ① 원본 축적 = `raw_records` append(sha256 skip) ≡ Karpathy `raw/` 불변
  - ② 변경 기록 = append 자체 + `_meta.ingest_log` append-only 로그
  - ③ 정리·증류 = silver/gold (SCD2)
- 즉 "6. 착륙지점"은 새 결정이 아니라, query 종합 답변이 이 상위 프레이밍을 누락한 것.

### 반영
- 위키 수정 불필요. query 답변만 "① 원본 축적(Karpathy raw ≡ bronze append)" 언어로 정정.
- webhook 삭제로 [[decision-dwh-as-karpathy-llm-wiki]]의 "2레인 중 webhook은 event_id skip으로 ①에 흡수" 서술은 "폴링 단일 레인" 기준으로 정정(정정 노트 대상은 이제 hybrid가 아니라 polling-only).

## 결론

- webhook 레인 삭제, 스케줄러 폴링 단일 레인 확정.
- 지연 목표 = 일 배치 확정.
- 카파시 저장 철학은 이미 반영됨 — 답변 프레이밍만 정정.
