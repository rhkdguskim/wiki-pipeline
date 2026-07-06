---
type: decision
title: 엔진 인증 = 단일 Claude Code 계정 로그인 (아이디/패스워드 등록)
tags: [engine, claude-code, auth, credential, mvp, phase-1]
status: superseded
---

# 결정: 엔진 인증은 단일 Claude Code 계정 로그인, 대시보드에 아이디/패스워드 등록

> ⛔ **superseded (2026-07-06)** — 엔진이 자체 에이전트(API 직접 호출)로 전환되면서
> ([[decision-engine-api-agent]]) 인증은 **API 키 등록**으로 대체됐다
> → [[decision-engine-api-key-auth]]. 등록 UI/백엔드·상태 표시·저장 보안 요구는
> 새 결정이 계승한다.

생성 엔진([[entity-docu-automatic]])이 `claude -p` headless로 돌 때의 인증을, MVP에서는
**단일 Claude Code 계정 로그인 방식**으로 간다. 대시보드(Control Plane)에 그 계정의
**아이디/패스워드를 등록·저장**하고, 파이프라인이 그 크리덴셜로 엔진을 구동한다.

## 무엇을

- **회전 단위 = 계정 1개.** 여러 계정을 두지 않고 단일 계정으로 시작한다 — 절단면이 깨끗하고 크리덴셜 관리가 단순하다.
- **등록 UI/백엔드에 계정 크리덴셜 항목.** 대시보드에 로그인 아이디·패스워드를 입력·저장하는 설정이 있어야 한다. 저장 보안(암호화·접근 제어)은 [[question-secret-storage-security]]의 운영 단계 과제로 이어진다.
- **상태 표시.** 등록된 계정의 로그인/토큰 상태를 대시보드에서 볼 수 있어야 한다 (만료·재로그인 필요 감지). 해지/만료 감지 시 admin 담당자에게 이메일 알림 → [[decision-email-alerting]].

## 근거

- 엔진 하이브리드 방침([[decision-engine-hybrid]])의 "당분간 A(`claude -p`)로 단순 시작"과 맞는 최소 구성이다. 인증 수단을 지금 하나로 고정해 [[question-headless-claude-auth]] 검증을 구체화한다.
- Control/Data Plane 분리([[decision-control-data-plane-split]])상 크리덴셜 배정은 Control Plane 소관이고, 이력 DB가 SoT([[decision-db-source-of-truth]])이므로 계정 크리덴셜도 DB 등록 항목으로 둔다.
- 단일 계정이라 등록·배정 로직이 단순해지고, MVP 범위([[question-mvp-scope]])의 엔진 인증 항목을 채운다.

## 기각 · 보류 대안

- **다중 계정 라운드 로빈 풀** (로그아웃/로그인 회전 + 토큰 만료 시 다른 계정 fallback) — MVP에서 제외. 단일 계정으로 충분·단순하며, 다중화는 이후 별도 판단으로 미룬다.

## 열린 항목

- headless 로그인은 **무인으로 지속되지 않음이 확인**됨(2026-07-06) — 만료 감지·재로그인 절차와 headless 동작 검증이 Phase 1 블로커로 남음 → [[question-headless-claude-auth]].
- 단일 계정의 사용량 한도가 파이프라인 처리량 상한이 되는 문제 → [[question-cost-estimation]] 실측.
