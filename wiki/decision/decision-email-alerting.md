---
type: decision
title: 알림 = 실시간 이메일, 역할 기반 수신 (인증 해지·파이프라인 실패)
tags: [alerting, observability, email, dashboard]
status: active
---

# 알림 = 실시간 이메일 (역할 기반 수신)

관리 서버(Control Plane)에 **이메일 발송 기능을 신설**하고, 운영 이벤트를 발생 즉시 사람에게
푸시한다. 원본 지시: [[2026-07-06-failure-alerting-email]]

## 결정

- **채널 = 이메일.** 관리 서버가 이메일 발송 기능을 갖는다. 발송 인프라 구체(사내 SMTP 등)는
  기술 스택 단계에서 확정 — 여기서는 요구사항 수준만 고정한다
- **실시간 푸시.** 대시보드([[decision-pipeline-observability]])는 보고 있어야만 보인다 —
  실패·해지 같은 운영 이벤트는 발생 즉시 이메일로 도달해야 한다. 관측성 이벤트 계약
  ([[decision-observability-event-contract]])의 webhook push를 소비해 발송한다
- **수신 = 역할 기반**:

  | 이벤트 | 수신자 |
  |--------|--------|
  | 엔진 계정 인증 해지·만료 ([[decision-engine-single-account-auth]]) | admin 담당자 |
  | 인프라성 장애 (러너 다운 등) | admin 담당자 |
  | 과제 파이프라인 실패·중단 (3연속 FAIL 등) | 해당 과제 담당자 + admin 참조 |

- **담당자 이메일 = 등록 정보.** 과제(소스) 등록 정보에 담당자 이메일 필드를 추가하고,
  admin 이메일은 서버 설정으로 둔다
- 기존 결정들의 "알린다"는 이 채널을 쓴다 — 예: compare 404 자동 비활성화 알림
  ([[decision-branch-loss-policy]])

## 근거

- **headless 로그인은 무인으로 지속되지 않음이 확인**됐다 ([[question-headless-claude-auth]] 갱신) —
  엔진 계정 인증 해지는 정적 파이프라인 전체를 멈추는 단일 장애점이라, 사람(admin) 개입을
  즉시 호출해야 한다
- 실패가 사람에게 도달하는 경로가 대시보드뿐이면 "밤사이 조용한 실패"를 놓친다 —
  [[question-batch-observability]]가 지적한 공백 중 실패 알림 축을 이 결정이 채운다

## 기각 대안

- **대시보드만 (풀 방식)** — 실시간 인지 불가. 야간 배치 특성상 아침까지 실패를 모른다
- **admin 단일 수신** — 과제별 실패까지 admin이 중계해야 해 병목
- **사용자별 구독 설정** — 유연하지만 현 단계 과설계. Phase 3+ 후보로 보류
