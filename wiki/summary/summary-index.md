# summary 인덱스

> summary 페이지 카탈로그. 허브: [[index]] · 규약: [[schema]]
> **기능(파이프라인) 축으로 그룹핑** — raw 소스 1건당 요약 1건. 파일은 모두 `wiki/summary/` 평면에 있고, 그룹은 인덱스에서만 나눈다.

### 정적 파이프라인 · 공통 설계

- [[summary-design-session]] — 설계 논의 기록 요약: 대안 3개 검토 → pull 모델 채택 과정
- [[summary-docu-automatic]] — Docu-Automatic 레포 분석 요약: 생성 엔진 구조와 조정점
- [[summary-registration-grilling]] — 레포 등록·docs-hub grilling 요약: 폴더 규칙 · 브랜치 정책 C · 좀비 비활성화
- [[summary-theme-scope-expansion]] — 테마 1차 스코프 확장 요약: dev-guide · api-protocol 즉시 추가 (4→6)
- [[summary-theme-detail-grilling]] — 테마 상세 설계 grilling 요약: 체크리스트 활성화 · dev 전용 · critic 근거 대조
- [[summary-devguide-docs-grounding]] — dev-guide 근거 범위 번복 요약: 코드+레포 문서 · 코딩 규칙 포함
- [[summary-engine-single-account]] — 엔진 단일 계정 인증 요약: 다중 회전 보류 · 단일 계정 · 아이디/패스워드 등록
- [[summary-engine-api-agent-architecture]] — 엔진 API 자체 에이전트 전환 요약: B 확정 · API 키 인증 · 에이전트 스텝 관측
- [[summary-engine-framework-langgraph-minimax]] — 엔진 프레임워크 LangGraph 전환 + MiniMax M3 PoC 요약: 자체 루프→LangGraph · 공급자 중립 · 3자 비교(OpenAI SDK 탈락·Claude Agent SDK 비채택)
- [[summary-failure-alerting-email]] — 실시간 이메일 알림 요약: 인증 해지·파이프라인 실패 · 역할 기반 수신
- [[summary-open-questions-decisions]] — 2026-07-07 열린 질문 결정 4건 요약: MVP 절단선(정적+매뉴얼) · 등록 baseline A · 방치 소스 수동 큐레이션 · 테마 경계

### 매뉴얼 추출 파이프라인

- [[summary-manual-extraction-pipeline]] — 매뉴얼 추출 파이프라인 요약: MCP 구동 · 아티팩트 소비 · 라이프사이클 diff
- [[summary-artifact-type-dispatch]] — 아티팩트 타입 dispatch 결정 요약: exe/msi만 · 담당자 자산 선택 · MCP 설치 실행까지

### 코드 인덱스 파이프라인 (2026-07-06 범위 제외)

- [[summary-code-index-pipeline]] — 코드 인덱싱 파이프라인 논의 요약: 폴링 · 프로바이더 추상화 · traversal
- [[summary-code-index-followup]] — 코드 인덱스 후속 확정 요약: MCP 서빙 · 러너 git clone · 형상 관리
- [[summary-code-index-finalization]] — 코드 인덱스 최종 확정 요약: 어댑터 cg-colby · 단일 레포 · 저장소 평면
- [[summary-code-index-out-of-pipeline]] — 코드 인덱스 범위 제외 요약: 개인 관리 이관 · 결정군 8건 supersede

### 사내 환경 실측

- [[summary-wish-gitlab-api-survey]] — wish GitLab API 실측 조사 요약: 16.3 CE · 파이프라인별 API 표면 · 파생 질문 6건
