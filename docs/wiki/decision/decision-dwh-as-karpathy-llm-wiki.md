---
type: decision
title: DWH 저장을 Karpathy LLM Wiki 구조로 재조직 (축적·기록·정리 3동작)
tags: [dwh, karpathy-llm-wiki, medallion, storage, append-only, compounding, architecture]
status: active
---

# DWH 저장을 Karpathy LLM Wiki 구조로 재조직 (축적·기록·정리 3동작)

## 결정

수집한 데이터를 DWH에 저장하는 방식을 **Karpathy LLM Wiki의 저장 철학**으로 재조직한다. BI/Kimball 언어(fact/dimension)를 1차 조직 원리로 두지 않고, 사용자가 명시한 **3동작**을 계층의 뼈대로 삼는다:

| # | 동작 | 이 저장소 DWH에서의 실체 | Karpathy 원형 | Medallion 대응 |
|---|------|--------------------------|---------------|----------------|
| ① | **원본을 계속 쌓는다** (불변 축적) | `raw_records` — 소스 구분 없는 단일 JSONB 테이블, **append**(sha256 동일 시 skip). 수정·삭제 없음 | `raw/` (immutable) | bronze |
| ② | **변경점을 기록한다** (append-only 로그) | ①의 append 자체가 곧 변경 로그 + `_meta` 스키마의 수집 이력(`ingest_log`: 배치·watermark·건수·해시) | wiki의 `log.md` (chronological) | (기존엔 약했던 고리) |
| ③ | **핵심을 정리한다** (증류) | 정제·통합·SCD2 이력을 담는 지식 계층(기존 silver/gold) — 질의가 향하는 대상 | `wiki/` (summaries·entities·concepts + index) | silver/gold |

즉 **저장의 1차 조직 원리 = "원본(불변) · 로그(변경) · 정리(증류)"** 이고, medallion의 bronze/silver/gold는 이 3동작을 PostgreSQL에 실체화하는 **물리 계층 이름**으로 그 아래에 산다. 둘은 대체 관계가 아니라 같은 layering discipline의 다른 언어다([[concept-medallion-dwh-on-postgres]]가 "본질은 layering discipline이지 데이터 모델이 아니다"라고 이미 명시).

## 근거

- **사용자 명시 지시** — "안드레이 카파시의 LLM WIKI 구조를 따라야 한다. 원본은 계속 쌓고, 변경점을 기록하고, 핵심 데이터는 정리하라." 저장 설계의 상위 원리를 BI가 아니라 LLM Wiki로 못박음.
- **우리는 이미 이 구조를 운영 중** — 이 저장소 자체가 `docs/raw/`(불변 축적) · `docs/wiki/log/`(변경 기록) · `docs/wiki/<type>/`(증류 정리)로 Karpathy 원형을 구현한다([[concept-karpathy-llm-wiki-storage]]). DWH를 같은 철학으로 두면 팀이 하나의 멘탈 모델로 저장소와 DWH를 동시에 이해한다. **향후 팀 LLM WIKI로 확장**할 때 저장 철학이 이미 정합([[decision-dwh-md-document-store]]).
- **오늘 확정한 bronze append가 사실 ①과 동일** — [[decision-bronze-single-jsonb-table]]의 "append(sha256 skip)"는 Karpathy raw 불변 축적과 같은 것이었다. 우연을 원칙으로 승격.
- **②가 기존 DWH 설계의 가장 약한 고리** — medallion엔 "변경 로그" 계층이 명시적으로 없었다. bronze append를 "스냅샷 히스토리 = 변경 로그"로 재해석하고 `_meta.ingest_log`로 수집 연산을 append-only 기록하면, Karpathy log 원칙과 정합하며 "무엇이 언제 어떻게 바뀌었나"의 감사 추적이 생긴다.
- **재생(replay) 가능성 공유** — raw 불변 → 정리 로직을 바꿔도 raw에서 재생. Karpathy("compiled once, kept current")·medallion·우리 위키가 모두 공유하는 성질.

## 기존 결정과의 정합 (supersede 아님 — 재해석·정정)

- **[[decision-dwh-shape-kimball-medallion]] · [[concept-medallion-dwh-on-postgres]]** — 유지. bronze/silver/gold는 3동작의 물리 실체화로 그대로 산다. 다만 조직의 1차 언어를 medallion → Karpathy 3동작으로 올린다.
- **[[decision-bronze-single-jsonb-table]]** — 유지·강화. 이 결정이 ①의 실체. append 정책이 Karpathy raw 원칙과 정합함을 명문화.
- **[[decision-monday-ingest-polling-only]]** ([[decision-monday-ingest-hybrid]]를 supersede) — 정합. 어제 서술한 "bronze upsert + 소스별 전용 테이블(`monday_webhook_events_raw`)"은 ①(append·단일 테이블)과 충돌해 append+`raw_records`로 정정됐고, 이후 지연 목표=일 배치 확정으로 webhook 레인 자체가 삭제되어 **스케줄러 폴링 단일 레인**만 남았다. 폴링 결과의 bronze 착륙이 곧 ①(append, sha256 skip)이다.
- **[[decision-dwh-scd-strategy]]** — 유지. silver의 SCD2는 ③(정리)의 이력 메커니즘. bronze append(①)가 그 입력을 제공.

## 열린 항목 (구현 시 확정)

- ② `_meta.ingest_log`의 정확한 스키마(배치 id·소스·watermark·수집 건수·skip 건수·해시)와 audit_logs([[decision-...]] 기존 감사 테이블)와의 역할 분담.
- ③ "핵심 정리" 계층을 silver/gold 2단으로 유지할지, Karpathy식 summaries/entities/concepts 유형으로 재명명할지 — 명칭이 팀 이해를 돕는지 vs BI 도구(dbt) 관례와의 마찰.
- Monday 외 소스로 확장 시 ①의 단일 테이블 + ②의 로그가 소스별로 어떻게 파티셔닝되는지.

## 관련

- [[concept-karpathy-llm-wiki-storage]] — 이 결정이 채택한 저장 철학의 개념 정의
- [[decision-bronze-single-jsonb-table]] — ① 원본 축적의 실체(append)
- [[decision-monday-ingest-polling-only]] — ① 원본 축적을 채우는 폴링 단일 레인(hybrid supersede)
- [[decision-dwh-scd-strategy]] — ③ 정리의 이력 메커니즘(SCD2)
- [[concept-medallion-dwh-on-postgres]] — 물리 실체화(bronze/silver/gold)
- [[decision-ingestion-connector-architecture]] — 이 저장이 놓인 4층 흐름의 [2]
- [[decision-dwh-md-document-store]] — 팀 LLM WIKI 확장과의 정합
- [[2026-07-10-dwh-storage-as-karpathy-llm-wiki]] — 논의 원본
