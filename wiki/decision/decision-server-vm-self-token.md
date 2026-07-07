---
type: decision
title: 관리 서버 = 사내 VM + 자체 토큰 인증
tags: [phase-2, deploy, auth, server]
status: active
---

# 결정: 관리 서버는 사내 VM에 배포하고, API 인증은 자체 토큰으로 한다

관리 서버(Control Plane)의 배포·인증 모델.

## 세 가지

- **배포: 사내 VM** — 컨테이너가 아닌 사내 VM 위에서 실행. 사내 인프라를 재사용해 운영 부담을 줄인다.
- **대시보드/API 인증: 자체 토큰** — 사내 SSO 연동 없이 서버가 발급·검증하는 자체 토큰. SSO 연동 작업을 피하면서 인증을 확보한다.
- **러너용 엔드포인트(plan/report): 서비스 토큰** — 기존 가닥대로 러너 전용 서비스 토큰.

## 근거

- 사내 VM은 사내 표준 운영 체계(네트워크·백업·모니터링)를 그대로 탄다 → [[entity-mirero-gitlab]] 사내 환경과 정합.
- 자체 토큰은 SSO 연동 의존성(연동 정책·승인·가용성) 없이 인증을 갖는다 — Phase 2에서 가장 빠른 확보 경로.
- 서비스 토큰(러너)과 사용자 토큰(대시보드)을 분리하면 권한 범위를 기기/사람으로 나눌 수 있다.

## 기각 대안

- **사내 SSO 연동** — 보안·감사 우위지만 연동 승인·가용성이 일정을 잡을 수 없어 Phase 2에서 리스크. 추후 필요 시 토큰 교체 가능.
- **컨테이너 배포** — 이식성 좋지만 사내에 컨테이너 오케스트레이션 운영 체계가 없으면 VM 대비 이점이 사라진다.

## 구체화 (2026-07-07)

배포 위치(사내 VM)와 인증(자체 토큰)을 정한 이 결정 위에, 서버의 **구현 스택**이 채워졌다:
Control Plane 서버 = **Python FastAPI** → [[decision-control-plane-fastapi]], DB = **PostgreSQL** → [[decision-control-plane-postgresql]].
자체 토큰 인증은 그 FastAPI 서버가 발급·검증한다.

이 결정이 [[question-server-deploy-auth]]를 답한다.
