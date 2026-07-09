---
type: question
title: Monday.com plan tier와 activity log 보존기간
tags: [dwh, monday-com, plan-tier, activity-log, incremental]
status: open
---

# Monday.com plan tier와 activity log 보존기간

## 질문

사내 Monday.com 가입 plan tier는 무엇이며, 그 tier의 **activity log 보존기간**은 얼마인가?

## 맥락

Monday.com activity log는 [[decision-monday-ingest-hybrid]]의 야간 전수 폴링에서 증분(incremental) 동기화의 핵심 신호다 — 어떤 item이 변경됐는지 activity log 이벤트로 식별해 변경된 item만 재추출한다.

**Airbyte Monday 커넥터 문서가 명시적으로 경고**: *"If the time between syncs exceeds the activity log retention period for your Monday.com plan, some changes may not be captured during incremental syncs."*

즉, **보존기간 < 동기화 주기**면 증분이 안전하지 않다. 이 경우:
- full refresh(전수 폴맨스)를 매번 해야 → API 호출량·rate limit 비용 크게 증가
- 또는 동기화 주기를 보존기간 이내로 좁혀야(예: 보존 7일이면 주간 폴맨스는 위험, 일간 이하로)

Monday plan tier별 activity log 보존:
- **Basic/Standard**: 활동 로그 기능 제한적
- **Pro**: 보존기간 상대적 짧음
- **Enterprise**: 보존기간 길고 audit 기능 강화

정확한 수치는 현재 plan tier를 확인해야 알 수 있다.

## 답

<!-- answered로 전환 시: 답이 된 내용 + 관련 decision 링크. 보존기간에 따라 decision-monday-ingest-hybrid의 폴링 주기·full refresh 필요 여부가 확정됨 -->
