---
type: decision
title: 문서 정체성을 run에서 분리 — Document(오래 사는 엔티티) + run은 갱신 사건
tags: [dwh, document-store, run, data-model, llm-wiki, scd]
status: active
---

# 문서 정체성을 run에서 분리 — Document(오래 사는 엔티티) + run은 갱신 사건

## 결정

문서의 정체성을 **특정 run에서 분리**한다.

- **`Document` = 오래 사는 엔티티** — `id`·`source`·`path`·`content_md`·`content_sha256`·`meta`·`updated_at`. Monday 수집물·파이프라인 산출·향후 LLM WIKI 지식 페이지가 모두 여기 산다.
- **`run_id` = nullable FK** — "이 문서를 어떤 run이 갱신했는가"의 이력일 뿐, 문서 존재의 전제가 아니다. run 없이도 문서가 존재할 수 있다(수집물·사람이 쓴 위키 문서).
- **기존 `run_doc_outputs`는 Document의 "run별 생성 스냅샷(리비전)"** 으로 재해석. 파이프라인이 만든 문서는 여전히 run에 연결되지만, 그건 리비전 이력이지 정체성이 아니다.

## 근거

- **현재 모델의 강결합(코드 확인 2026-07-10)** — `RunDocOutput.run_id`는 `nullable=False`. 모든 문서가 "어떤 run의 산출물"이라는 전제가 박혀 있다. Monday 수집물·LLM WIKI 문서를 여기 담으면 억지 run을 만들어야 한다.
- **LLM WIKI 문서는 본질적으로 run 산출물이 아니다** — 사람이 계속 편집·축적하는 지식 페이지는 오래 사는 엔티티다. run에 묶으면 "편집할 때마다 run 생성" 같은 왜곡이 생긴다.
- **DocumentStore 흡수와 정합** — [[decision-dwh-md-document-store]]가 `RunDocOutput`을 흡수·일반화하기로 했으므로, 그 일반화의 핵심이 바로 run 분리다. 파이프라인 산출·수집물·위키 문서가 같은 `save(md, meta)` 계약을 공유하려면 run 강제를 풀어야 한다.
- **SCD와 정합** — 리비전 이력은 [[decision-dwh-scd-strategy]]의 SCD2(effective_from/to·is_current)와 자연스럽게 맞는다. Document는 현재 상태, run별 스냅샷은 시점 이력.

## 기각 대안

- **현 구조 유지(모든 문서 run 강제)** — Monday 수집·LLM WIKI 문서마다 가짜 run을 만들어야 함. 데이터 모델 왜곡, "run"의 의미 오염.
- **문서 종류별 별도 테이블** — pipeline_doc / monday_doc / wiki_doc 분리. 공통 조회·DocumentStore 단일 계약이 깨지고 조인 복잡. 흡수·일반화 방향과 반대.

## 관련

- [[decision-dwh-md-document-store]] — 이 분리가 실현하는 DocumentStore 일반화
- [[decision-ingestion-connector-architecture]] — 수집물이 run 없이 저장되는 근거
- [[decision-dwh-scd-strategy]] — 리비전 이력 = SCD2
- [[concept-port-adapter]] — DocumentStore 포트의 저장 대상
- [[2026-07-10-ingestion-connector-architecture]] — 논의 원본
