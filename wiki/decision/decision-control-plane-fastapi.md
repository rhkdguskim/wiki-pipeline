---
type: decision
title: Control Plane 서버 스택 = Python FastAPI
tags: [server, control-plane, stack, fastapi, python]
status: active
---

# 결정: 관리 서버(Control Plane)를 Python FastAPI로 구현한다

Control Plane(대시보드·API·스케줄러·webhook 수신)의 서버 스택을 **Python FastAPI**로 확정한다.
[[decision-server-vm-self-token]]이 배포 위치(사내 VM)와 인증(자체 토큰)을 정했다면, 이 결정은 그 위에서
**어떤 언어·프레임워크로 서버를 구현하는가**를 채운다.

## 근거 — Data Plane와 언어 일치로 코드 공유

- **Data Plane 엔진이 이미 Python 고정** — 생성 엔진이 LangGraph 오케스트레이션이라 Python으로 못박혀 있다
  ([[decision-engine-orchestration-langgraph]]). Control Plane도 Python으로 두면 **두 플레인이 코드를 공유**한다.
- **공유되는 것** — 진행 이벤트 스키마([[decision-observability-event-contract]]), DB 모델([[decision-db-source-of-truth]]),
  SCM 커넥터 코드([[decision-scm-connector-abstraction]] · [[decision-scm-multi-instance-github-mvp]]).
  언어를 이원화하면 이 셋을 두 벌로 유지해야 한다.
- **FastAPI** — 소스 등록 API·webhook 수신 등 JSON API 위주 서버에 적합하고, async가 스케줄러·webhook 동시성에 맞다.

## 기각 대안

- **ASP.NET Core** — 사용자 보유 전문성(미레로 ASP.NET Core/Akka.NET 경험)과 사내 Windows 인프라 정합은 있으나,
  Data Plane(Python)과 **언어가 이원화**되어 이벤트 스키마·DB 모델·커넥터를 두 벌로 유지하는 비용이 이점을 상쇄. 기각.

## 함의

- 이 선택이 [[decision-control-plane-postgresql]](DB = PostgreSQL)와 조합된다 — FastAPI를 택했으므로
  SQL Server를 골랐을 때의 (ASP.NET Core + SQL Server) 조합 이점은 성립하지 않는다.
- [[2026-07-07-ops-backend-plan]] Phase 2에서 기존 read-only `serve.py`(ThreadingHTTPServer)를 FastAPI로 재작성한다.

관련: [[decision-control-data-plane-split]] · [[decision-server-vm-self-token]] · [[decision-control-plane-postgresql]] · [[decision-engine-orchestration-langgraph]] · [[overview]]
소스: [[2026-07-07-ops-backend-plan]] · 요약: [[summary-ops-backend-plan]]
