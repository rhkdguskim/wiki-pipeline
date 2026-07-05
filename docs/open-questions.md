# 열린 질문 · 리스크

← [문서 인덱스](./README.md)

## 열린 질문 (확정 필요)

| # | 질문 | 블로킹 대상 |
|---|------|------------|
| 1 | **러너 → AI API 네트워크 경로**: 폐쇄망/프록시? 도메인 화이트리스트 또는 사내 LLM 게이트웨이? — 인프라팀 선행 확인 | Phase 1 ⛔ |
| 2 | headless Claude Code 실행의 인증/라이선스 방식 (API 키? 사내 게이트웨이?) | Phase 1 ⛔ |
| 3 | 서버 스택·DB 확정 (제안: ASP.NET Core Minimal API + BackgroundService + SignalR / SQLite 시작 → [tech-stack](./tech-stack.md)) | Phase 2 |
| 4 | 서버 배포 위치(사내 VM/컨테이너)와 API 인증(사내 SSO 연동?) | Phase 2 |
| 5 | MR 정책: 리뷰어 자동 지정 규칙, 소스별 MR vs 하루치 통합 MR, docs-auto 브랜치 방식 대비 최종 확정 → [mr](./features/mr.md), [generation](./features/generation.md) | Phase 1 ⛔ |
| 6 | 스케줄: 시각/요일, 과제별 개별 스케줄 필요 여부 → [scheduling](./features/scheduling.md) | Phase 2 |
| 7 | 기존 문서 사이트(110.110.10.70:8080)와 docs-hub의 관계: 기존 사이트 확장 vs 신규 구축 | Phase 1 |
| 8 | 테마 2차 확장(제품별 페이지 등 28+) 시점과 우선순위 | Phase 3 이후 |
| 9 | 비용 예측: 과제 4개 × 일일 영향 문서 수 × 토큰 단가 산정 | Phase 1 실측 후 |

⛔ = Phase 착수를 막는 블로킹 질문 → [roadmap](./roadmap.md)

## 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| AI 환각/품질 미달 | 잘못된 문서 배포 | critic 검증 + warning 태그 + MR 사람 리뷰([G5](./goals.md)). 머지율을 품질 지표로 추적 → [kpi](./kpi.md) |
| 러너에서 AI API 접근 불가 | 전체 불성립 | 질문 #1을 설계 확정 전 인프라팀에 선행 확인 |
| headless 실행 미검증 | 엔진 통합 실패 | Phase 1 첫 작업으로 검증. 실패 시 대안(에이전트 로직의 스크립트 포팅) 검토 |
| 문서 MR 리뷰 부담 증가 | 자동화가 리뷰 병목으로 전이 | 소스별 MR 분리, 문서별 변경 근거 명시로 리뷰 비용 최소화 → [mr](./features/mr.md) |
| force-push로 sha 무효화 | 변경 누락/오탐 | fallback + 경고 → [change-detection](./features/change-detection.md), 소스 레포 main protect 권장 |
| 토큰 만료/권한 변경 | 야간 배치 무단 실패 | 만료 전 알림(P2), 실패 사유를 대시보드에 명시 |
| 순차 실행 시간 증가 (소스 확대 시) | 야간 window 초과 | Phase 1에서 소스당 소요 실측 → 초과 시 소스 단위 병렬화 검토 (엔진 내부는 순차 유지) |
