---
type: question
title: Monday 사용자와 wiki_pipeline 사용자의 SSO 일치 여부
tags: [dwh, dim-user, conformed-dimension, sso, identity]
status: open
---

# Monday 사용자와 wiki_pipeline 사용자의 SSO 일치 여부

## 질문

Monday.com의 user 집합과 wiki_pipeline의 사용자(과제 담당자·운영자)가 **같은 사내 SSO로 연결된 동일 인물**인가, 아니면 **별도 집단(이름만 공유)**인가?

## 맥락

[[entity-data-warehouse]]의 conformed dimension 중 **`dim_user`** 가 가장 중요한 교차 차원이다 — Monday item의 담당자와 wiki_pipeline run의 담당자를 같은 차원으로 묶어 "A 담당자의 과제 처리량 ↔ 문서화 자동화 성공률"을 한 쿼리로 분석하려면 필수.

- **같은 SSO** → `email`을 안정적 키로 단일 `dim_user` 통합 가능. [[decision-dwh-scd-strategy]]의 SCD2(사실상 SCD6) 적용 대상.
- **별도 집단** → 두 시스템의 사용자를 매핑하는 별도 브릿지 테이블(`bridge_user`) 운영 필요. 운영자가 수동으로 매핑하거나, 이름 유사도·부서 정보로 휴리스틱 매칭 후 검증. 매핑 누락·중복 risk.

Monday user 모델: `id`·`email`·`name`·`kind`(admin/member/guest/view_only)·`teams[]`. wiki_pipeline 사용자: control plane에 명시적 user 테이블은 없으나 `sources.owner_email`·`audit_logs.actor`·`system_settings.updated_by` 등에 사내 이메일이 산재.

사내 SSO(예: Office 365·Google Workspace)를 Monday와 사내 시스템이 같이 쓰는지가 핵심.

## 답

<!-- answered로 전환 시: 같은 SSO인지 여부 + dim_user 통합 전략(단일 vs bridge) + 관련 decision 링크 -->
