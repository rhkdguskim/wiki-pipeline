# MiVnc MCP 서버 소스 실측 — 원격제어 MCP의 실체 (2026-07-06)

> `D:/project/ros-sw-rcs-windows` 소스와 실행 중인 세션 MCP를 직접 조사한 기록. 원본 불변 — 위키에서 증류.
> 위키 [[entity-remote-control-mcp]]가 "사내 제공 MCP"로만 서술하던 것의 **실물 근거**.

## 조사 계기

사용자 지시: "D:/project/ros-sw-rcs-windows의 MiVncManagerMcpServer를 사용해서 MCP 환경을 구성"
→ 이 세션에 이미 연결된 `mcp__mi-vnc__*` 도구의 실체를 소스에서 확인하고 위키에 설계 반영.

## 실측 사실 (소스 + 실행 인스턴스)

### 두 개의 MCP 서버 앱 (같은 도구 라이브러리 위)

| 앱 | 세션 | 포트 | 성격 |
|----|------|------|------|
| `Src/app/MiVncMcpServer` | **단일 세션** | 9100 (SSE) | VNC 세션 1개를 LLM 도구로 노출 |
| `Src/app/MiVncManagerMcpServer` | **다중 세션** | 9200 (SSE) | 세션 ID로 여러 VNC 호스트 동시 제어 (오케스트레이션) |

- 둘 다 `Src/engine/vnc-mcp-lib`의 **단일 도구 정의** 위에 wrapping — 도구를 양쪽에 중복 정의하지 않음.
  Manager는 공통 도구에 `withSessionId=true`를 붙인 형태.
- "sw-rcs-session-mcp"([[entity-remote-control-mcp]]·[[decision-app-host-connection]]에서 부르던 이름)의 실체가 이 서버 계열이다.

### MiVncManagerMcpServer 도구 세트 — 60 + 6 + 4

- **60 공통 도구** (`withSessionId=true`) — vnc-mcp-lib 정의. 스크린샷·클릭·키입력·UIA 트리·터미널·파일전송·프로세스·클립보드·OmniParser 등.
- **6 세션 관리 도구** — Add/Remove/Connect/Disconnect/List/… (VncSessionManager).
- **4 alias** — Add/AddSession, Remove/RemoveSession 등 가독성용 별칭(agent 입장 동작 동일 → 중복 호출 주의).

### 전송·모드

- **전송 2종**: SSE(HTTP, `mcp::server`) / stdio(`mcp::stdio_server`) — 도구 등록이 두 오버로드 별개, 추가 시 둘 다 등록.
- **연결 모드 2종**(MiVncMcpServer 기준, 단일세션):
  - **remote** (`--transport remote`, 기본) — 외부 `MiRcsServer`에 TCP 접속(`--host`/`--port`), auto-reconnect(exp backoff) 기본 ON.
  - **local** (`--transport local`) — in-process `LocalRfbEngine` + AnonymousPipe로 같은 프로세스에서 화면 캡처/입력. 네트워크 우회. Windows 서비스(`--service-mode`)는 **local 전용**.

### 외부 의존

- **OmniParser** (`--omniparser-url`) — VLM 기반 화면 분석 외부 서비스. 미설정 시 `vnc_omniparser_analyze` 같은 도구 즉시 실패.
- **cpp-mcp** (vendored, `3rdparty/cpp-mcp`) — MCP 프로토콜 구현. 업데이트 시 `register_tool` ABI 영향.

### 배포

- **Docker**(Linux, 멀티세션 운영): `docker compose -f Src/app/MiVncManagerMcpServer/docker-compose.yml up -d`.
  이미지 `mivncmanagermcp:latest`, 컨테이너 `vnc_manager_mcp`, 포트 매핑 **8081→9200**, `restart: unless-stopped`, env `SSE_PORT=9200`.
- **Windows**: msbuild ReleaseMT/x86 → exe. 서비스 설치(`-install`) 또는 foreground(`--sse-host 0.0.0.0 --sse-port 9200`).

### 실행 인스턴스 실증 (이 세션)

- 세션에 `mcp__mi-vnc__*` 도구(vnc_* 60여 개)가 이미 연결·작동. `vnc_screen_info` 응답:
  `connected:true, 1920×1080, capabilities: uia·terminal·file_transfer·hwnd·process_info 전부 true`.
- 즉 원격제어 MCP는 가설이 아니라 **지금 실제로 붙어 동작하는 실물**.

### 동시성 주의 (소스 ADR)

- `VncSessionManager` add/remove/connect/disconnect가 agent race로 동시 실행 → lock 가정 위배 시 데드락(ADR 0001).
- 도구는 idempotent·재시도 가능 설계 — agent 명령 순서 보장 안 함.

## 위키 반영 방향

- 이건 **실측 사실**이라 기존 [[entity-remote-control-mcp]]에 fact로 보강(신규 결정·번복 아님).
- registry 컨테이너 실재([[2026-07-06-wish-gitlab-api-survey]])는 "이미지가 있다"였고, 이번은 "소스·모드·도구·전송이 이렇다"로 한 단계 구체화.
