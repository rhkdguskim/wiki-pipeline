---
type: decision
title: 앱 실행 = 별도 호스트, IP/port 세션 MCP 제어 + 시크릿 등록 저장
tags: [manual, host, mcp, secret, registration]
status: active
---

# 결정: 앱은 별도 호스트에서 실행하고, IP/port로 세션 MCP를 제어하며, 시크릿은 등록 시 저장한다

[[entity-manual-pipeline]]의 앱 실행·연결·인증 모델.

## 세 가지

- **별도 호스트** — 앱은 Windows CI 러너가 아니라 **UI 테스트 전용 별도 호스트**에서 실행된다. 이 호스트가 UI 자동화 가능한 실행 환경(GUI 세션 포함)을 제공한다.
- **IP/port 제어** — 대시보드에서 app 등록 시 호스트의 **IP·port**를 입력하고, 파이프라인은 그 주소로 세션 MCP(`sw-rcs-session-mcp`)를 제어한다 → [[entity-remote-control-mcp]].
- **시크릿 등록 저장** — app 등록의 추가 입력칸에 UI 테스트에 필요한 시크릿(예: 로그인 정보)을 저장하고, 순회 중 인증 단계에 주입한다. 저장 위치는 서버 DB(SoT) → [[decision-db-source-of-truth]] (git·설정 파일 아님).

## 근거

- 앱 실행이 무겁고 상태 의존적이라 CI 러너와 분리된 전용 호스트가 격리·재현에 유리 → [[decision-control-data-plane-split]]의 부하 격리 정신과 일관.
- 로그인 등 기동 전제를 등록 시 1회 저장하면 릴리스마다 반복 주입이 자동화된다 → [[decision-release-tag-trigger]].

## 기각 대안

- **시크릿을 코드·설정 파일에 보관** — 보안 취약·과제별 분리 곤란. 서버 DB에 저장한다.
- **CI 러너에서 앱 직접 실행** — UI 세션·상태 격리가 어렵고 러너 부하와 얽힌다.

이 결정이 [[question-app-exec-environment]]를 답하고 [[question-mcp-auth-network]]의 MCP↔호스트 축을 확정한다.
시크릿 저장의 보안 세부 → [[question-secret-storage-security]]. 원본: [[2026-07-05-manual-extraction-pipeline]]
