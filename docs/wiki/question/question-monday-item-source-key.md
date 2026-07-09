---
type: question
title: Monday item ↔ wiki_pipeline source(repo)를 잇는 키
tags: [dwh, bridge-fact, item-source-mapping, dwh]
status: open
---

# Monday item ↔ wiki_pipeline source(repo)를 잇는 키

## 질문

Monday.com의 과제(item)와 wiki_pipeline의 문서화 대상 source(repo)를 서로 연결할 **안정적 키**는 무엇인가?

## 맥락

이 키가 **DWH의 핵심 가치**를 결정한다. [[entity-data-warehouse]]의 교차 팩트 `silver.fact_item_documentation`이 Monday item ↔ pipeline source/run/문서를 잇는데, 이 연결이 없으면 두 소스가 나란히 놓일 뿐 교차 분석이 불가능하다.

후보 키:
1. **Monday 커스텀 컬럼에 repo 경로/URL 저장** — Monday 보드에 "GitLab Repo"·"소스 경로" 같은 text/link 컬럼이 있고, 운영자가 과제 등록 시 채우는지. 있으면 가장 깔끔한 키.
2. **별도 매핑 테이블(`bridge_item_source`) 운영** — 운영자가 대시보드에서 수동으로 (Monday item_id, pipeline source_id) 쌍을 관리. 유연하나 운영 부담·누락 risk.
3. **이름/경로 휴리스틱 매칭** — Monday item 이름과 repo 이름·namespace의 유사도로 자동 추정. 부정확, 검증 필요.
4. **연결고리 없음** — 이 경우 두 소스는 독립 마트로만 서비스되고, 교차 분석은 포기.

Monday의 connect boards 컬럼이나 dependency 컬럼을 활용할 수도 있으나, 일반적으로 repo 추적은 text/link 컬럼 또는 매핑 테이블이 일반적.

## 답

<!-- answered로 전환 시: 선택된 키 + bridge_item_source 운영 방침 + 관련 decision 링크 -->
