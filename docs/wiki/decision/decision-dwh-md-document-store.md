---
type: decision
title: 문서 저장 = md 표준 포맷 + DocumentStore 포트/어댑터 (DB 교체 가능)
tags: [dwh, document-store, md, port-adapter, llm-wiki, postgresql, vector-db]
status: active
---

# 문서 저장 = md 표준 포맷 + DocumentStore 포트/어댑터 (DB 교체 가능)

## 결정

수집·정리된 내용을 **Markdown(md) 표준 포맷**으로 저장하고, 저장 백엔드는 **`DocumentStore` 포트 인터페이스 + 어댑터**로 추상화해 **언제든 교체 가능**하게 만든다.

```
interface DocumentStore:
    save(doc_md: str, meta: dict) -> id
    get(id) -> doc_md
    query(filter) -> [meta]

구현 어댑터:
    PostgresDocumentStore   # 지금 — control plane과 같은 PG 클러스터(별도 스키마)
    FileDocumentStore       # 로컬/테스트
    VectorDocumentStore     # 향후 — 팀 LLM WIKI (임베딩·유사도 검색)
```

- **md = 교환/산출 포맷** — 사람이 읽고, LLM WIKI가 1급 자원으로 소비. DB 스키마와 무관하게 안정적.
- **DocumentStore = 저장 포트** — 상위 로직(수집 에이전트·조회)은 포트에만 의존. DB 교체 = 어댑터 교체, 상위 코드 무변경.
- **초기 어댑터 = PostgreSQL** — 이미 쓰는 PG([[decision-control-plane-postgresql]] · [[decision-dwh-storage-postgres-single]]) 클러스터의 별도 스키마에 md 원문 + 메타를 저장.

## 근거

- **LLM WIKI 대비 교체 가능성이 핵심 요구** — 앞으로 팀 내부 LLM WIKI를 개발하므로, 관계형 저장(PG)에서 **벡터 검색 저장(VectorStore)** 으로 backing store를 갈아끼워야 한다. 이 교체를 처음부터 열어두는 게 사용자 명시 요구.
- **포트/어댑터의 교과서적 적용** — 교체 가능성을 열어두고 싶은 외부 저장 기술이 코어 흐름에 들어오는 상황 → [[concept-port-adapter]]의 정확한 사용 조건. SCM 커넥터([[decision-scm-connector-abstraction]])·생성 엔진([[decision-engine-orchestration-langgraph]])과 같은 패턴의 또 다른 실체화.
- **md를 SoT 포맷으로 고정하면 DB 중립** — 문서 원문이 md 텍스트이므로, 어떤 DB로 옮겨도 원문 손실이 없다. DB는 인덱싱·검색·메타 저장 수단일 뿐.
- **DWH와 역할 분리** — DWH gold 마트는 분석용 집계 저장소, DocumentStore는 md 문서 원문·조회용. 둘은 별개 관심사다. 다만 md 메타(생성 이력·소스·품질)는 DWH `fact_item_documentation` 브릿지 팩트와 조인 가능 → 교차 분석과 문서 조회를 각자 최적 저장소로.

## 기각 대안

- **PG 테이블에 직접 결합(추상화 없음)** — 지금은 단순하나, LLM WIKI로 VectorStore 전환 시 저장·조회 코드를 전면 재작성해야 함. 사용자의 "언제든 갈아끼울 수 있게" 요구를 정면 위배.
- **md 파일시스템만 저장** — DB 없이 파일로만. 메타 질의·동시 접근·트랜잭션이 약하고, control plane과의 조인이 어렵다. (단 `FileDocumentStore` 어댑터로 테스트/로컬 용도는 유지.)
- **처음부터 VectorStore로 시작** — LLM WIKI가 아직 착수 전이고 임베딩·청킹 정책 미정([[2026-07-10-dwh-monday-ingestion-refinements]] 열린 항목). 지금 도입은 조기 최적화 — 포트만 열어두고 어댑터는 PG로 시작.

## 관련

- [[concept-port-adapter]] — 이 결정이 실체화하는 패턴
- [[decision-dwh-storage-postgres-single]] — 초기 PostgresDocumentStore가 얹히는 PG 클러스터
- [[decision-control-plane-postgresql]] — 재사용하는 PG 근거
- [[decision-monday-collector-langgraph-scheduled]] — 수집 에이전트가 md를 이 스토어에 적재
- [[entity-data-warehouse]] — DWH gold 마트와의 역할 분리·조인 지점
- [[2026-07-10-dwh-monday-ingestion-refinements]] — 논의 원본
