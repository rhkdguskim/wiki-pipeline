---
type: summary
title: 실시간 이메일 알림 지시 요약
tags: [alerting, email, observability]
status: active
---

# 실시간 이메일 알림 지시 요약

> 원본: [[2026-07-06-failure-alerting-email]]

headless 로그인이 무인으로 지속되지 않는다는 확인에서 출발해, 알림 기능을 확정한 지시의 요약.

## 요지

- **확인된 사실**: headless 로그인은 무인으로 지속되지 않음 → [[question-headless-claude-auth]]
  초점이 만료 감지·재로그인 절차로 이동
- **이메일 발송 기능 신설** (관리 서버) — 인증 해지 시 admin 담당자에게, 파이프라인 실패 등
  운영 이벤트는 실시간 푸시
- **수신 = 역할 기반** (확인 문답): 인증 해지·인프라 → admin, 과제 실패 → 과제 담당자 + admin 참조
- → [[decision-email-alerting]]

## 이 소스에서 파생된 페이지

생성: [[decision-email-alerting]] · 갱신: [[question-headless-claude-auth]] ·
[[question-batch-observability]] · [[decision-engine-single-account-auth]] · [[overview]]
