---
type: question
title: DWH 다부서 확장 가능성과 RLS 도입 시기
tags: [dwh, multi-tenancy, rls, security, dwh]
status: open
---

# DWH 다부서 확장 가능성과 RLS 도입 시기

## 질문

DataWarehouse는 **단일 조직(해당 팀)만 소비**하는가, 아니면 **타부서·외부 그룹**이 향후 찌를 가능성이 있는가?

## 맥락

[[decision-dwh-storage-postgres-single]]의 접근 제어 전략이 결정된다.

- **단일 조직** — 역할 분리(`etl_writer`/`analytics_reader`)만으로 충분. 모든 분석가가 모든 gold 마트를 다 볼 수 있음. 초기 구현 단순.
- **다부서/외부 확장 예상** — PostgreSQL **Row Level Security(RLS)** 도입 필요. `_meta.tenant` 컬럼 + `CREATE POLICY ... USING (tenant_id = current_setting('app.tenant_id'))`. 부서별 데이터 격리. 연결 역할에 `BYPASSRLS`가 없도록 주의.
- **부서 경계가模糊한 경우** — Monday workspace·board 단위 격리가 이미 있으므로, DWH에서 RLS를 하면 이중 격리. 워크스페이스별로 분석 권한을 다르게 하려면 도입 가치.

RLS는 한번 도입하면 모든 쿼리에 정책 평가 오버헤드·복잡도가 붙으므로, **실제 다부서 수요가 생기기 전에는 미리 두지 않는다**는 것이 일반적 가이드.

가정(설계 계획): 초기는 단일 조직, 다부서 수요 생기면 RLS 도입. 단, 이 질문의 답이 "처음부터 다부서"면 Phase 0에 RLS 설계를 포함해야 한다.

## 답

<!-- answered로 전환 시: 단일 조직 vs 다부서 + RLS 도입 시기(Phase 0 vs 대기) + 관련 decision 링크 -->
