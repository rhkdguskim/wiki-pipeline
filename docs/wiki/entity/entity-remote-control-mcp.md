---
type: entity
title: 원격제어 MCP (사내 제공)
tags: [mcp, ui-automation, remote-control]
status: active
---

# 원격제어 MCP

사내에서 제공하는 MCP. [[entity-manual-pipeline]]의 앱 구동·관측·조작 채널이다.

## 제공 기능

- **파일전송** — 아티팩트를 앱 실행 환경으로 전송·배치 (배포 단계를 담당) → [[decision-artifact-consumption]]
- **UI 자동화 인식(기본)** — 창·컨트롤 트리와 라벨을 접근성 기반으로 읽고, 요소 단위로 클릭·입력, 스크린샷 캡처. 화면·컨트롤의 "의미"를 알 수 있어 매뉴얼 근거가 풍부
- **좌표 기반 데스크톱 제어(fallback)** — 요소 인식이 안 되는 화면에서 마우스/키보드/캡처로 대체 (비결정적)

## 왜 이 방식인가

실행 중인 앱을 실제로 조작·관측하므로, 코드만 읽는 정적 분석이 놓치거나 환각하는 UI 흐름을
**관측된 사실**로 확보한다 → [[concept-observation-grounding]].

## 연결 모델

앱 실행 호스트의 **IP/port**로 세션 MCP(`sw-rcs-session-mcp`)를 제어한다 — 대시보드 app 등록 시 IP·port를
입력한다 → [[decision-app-host-connection]]. 로그인 등 시크릿도 등록 시 저장돼 순회 중 주입된다.

## 미결

- AI 호출 네트워크 경로(폐쇄망/프록시) → [[question-mcp-auth-network]] (MCP↔호스트 축은 IP/port로 확정)
- 시크릿 전송·저장 보안 → [[question-secret-storage-security]]

## 실측 확인 (2026-07-06) — 이미 실물로 존재

[[2026-07-06-wish-gitlab-api-survey]]에서 ros-sw-rcs registry에 MCP 서버 컨테이너 이미지가 실재함이 확인됐다:
`mivncmcpserver`·`mivncmanagermcpserver`·`mivnc2rtspserver`. "원격 제어 MCP"는 가설이 아니라 사내에서 이미
빌드·배포되는 실물이다. 컨테이너 아티팩트는 `GET /projects/:id/registry/repositories`로 접근한다(단 소스별 권한 상이 → [[entity-mirero-gitlab]]).

## 소스 실측 (2026-07-06) — 서버 구조·모드·도구

소스(`D:/project/ros-sw-rcs-windows`)와 이 세션에 붙은 실행 인스턴스를 직접 조사 → [[2026-07-06-mivnc-mcp-server-survey]].

- **두 서버 앱, 한 도구 라이브러리**: `MiVncMcpServer`(단일 세션, :9100) · `MiVncManagerMcpServer`(다중 세션, :9200)가
  둘 다 `vnc-mcp-lib` 단일 도구 정의 위에 wrapping. "sw-rcs-session-mcp"의 실체가 이 계열이다.
- **Manager 도구 세트**: 60 공통(`withSessionId=true`) + 6 세션관리(Add/Remove/Connect/Disconnect/List) + 4 alias.
  다중 세션은 **세션 ID로 여러 VNC 호스트를 동시 제어**한다.
- **전송 2종**: SSE(HTTP) / stdio.
- **연결 모드 2종**: **remote**(외부 `MiRcsServer`에 TCP, auto-reconnect) / **local**(in-process, 네트워크 우회, Windows 서비스는 local 전용) → [[decision-app-host-connection]]의 IP/port 연결은 remote 모드에 해당.
- **외부 의존 OmniParser**(`--omniparser-url`, VLM 화면 분석) — 미설정 시 관련 도구 실패.
- **배포**: Docker compose(`mivncmanagermcp:latest`, 8081→9200) 또는 Windows 서비스.
- **동시성**: `VncSessionManager` lifecycle이 agent race로 동시 실행 — 도구는 idempotent·재시도 가능 설계(ADR 0001).
- **실행 실증**: 이 세션의 `mcp__mi-vnc__*` 도구가 원격 화면(1920×1080, uia·terminal·file_transfer·hwnd)에 연결·작동 확인.

원본: [[2026-07-05-manual-extraction-pipeline]] · [[2026-07-06-wish-gitlab-api-survey]] · [[2026-07-06-mivnc-mcp-server-survey]] · 전체 그림: [[overview]]
