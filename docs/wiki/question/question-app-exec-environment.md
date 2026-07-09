---
type: question
title: 앱 실행 환경은 무엇이고 어떤 전제가 필요한가?
tags: [phase-1, infra, environment]
status: answered
---

# ❓ 앱 실행 환경은 무엇이고 어떤 전제가 필요한가?

[[entity-remote-control-mcp]]가 파일전송·기동을 해주지만, 그 대상 "앱 실행 환경"의 구체가 미확정이었다.

- **위치** — 사내 Windows CI 러너 자체인가([[entity-manual-pipeline]]), 별도 앱 호스트인가?
- **GUI 세션** — UI 자동화는 인터랙티브 데스크톱 세션이 필요할 수 있다.
- **기동 전제** — 로그인·백엔드 연결·테스트 데이터가 있어야 앱이 순회 가능한 상태가 된다(feasibility gate).

## ✅ 답 (2026-07-05) → [[decision-app-host-connection]]

- **위치** — **별도 호스트**. UI 테스트를 돌릴 수 있는 전용 환경을 제공한다(Windows CI 러너와 분리). GUI 세션은 이 전용 호스트가 제공.
- **연결·기동 전제** — 파이프라인은 그 호스트를 **IP/port로 원격 제어**(세션 MCP)하고, 로그인 등 시크릿은 **app 등록 시 저장**해 순회 중 주입한다. 테스트 데이터 등 나머지 전제는 호스트 프로비저닝에 포함.

관련: [[decision-artifact-consumption]] · [[question-mcp-auth-network]] · [[question-secret-storage-security]]
