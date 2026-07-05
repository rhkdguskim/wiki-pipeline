# 모니터링 · 대시보드 (FR-11~15)

← [문서 인덱스](../README.md)

"지금 어느 과제가 돌고 있고, 어젯밤 뭐가 실패했나"를 보이게 만든다 ([vision P4](../vision.md), [G4](../goals.md)).

## 요구사항

| ID | P | 요구사항 |
|----|---|----------|
| FR-11 | P0 | **완료 보고 API**: 러너가 run 종료 시 결과(소스별 성공/실패, 생성 문서 수, MR URL, 새 sha) 보고 → [api](./api.md) |
| FR-12 | P1 | **GitLab webhook 수신**: pipeline 이벤트로 run 상태(시작/진행/종료)를 실시간 반영 |
| FR-13 | P1 | **대시보드**: 실행 중 상태, 실행 이력, MR 링크, 실패 사유, 소스 목록, 다음 스케줄, 수동 트리거 버튼 |
| FR-14 | P2 | **실패 알림**: run 실패 시 메일/메신저 알림 |
| FR-15 | P1 | **로그 보존**: 엔진 execution-log를 run 아티팩트로 보존, GitLab job 로그 링크 제공 |

## 모니터링 데이터 소스 (두 갈래)

1. **러너 완료 보고** (`POST /runs/{id}/report`) — 최종 결과: 성공/실패, 문서 수, MR 링크, 새 sha
2. **GitLab pipeline webhook** (`POST /hooks/pipeline`) — 실시간 이벤트: 파이프라인 시작/진행/종료

둘을 합쳐 대시보드를 실시간으로 그린다 (서버 push, SignalR 제안 → [tech-stack](../tech-stack.md)).

## 화면 요구사항

| 화면 | 내용 |
|------|------|
| 메인 | 현재 실행 중 run 카드(소스별 대기/실행/완료/실패), 최근 run 테이블(일시·유형·대상·결과·문서 수·MR 링크), 다음 스케줄 시각, 수동 트리거 버튼 |
| 소스 관리 | 등록 목록(마지막 처리 시각, `last_processed_sha`), 등록 폼, 비활성화, 소스별 즉시 실행 |
| 실행 상세 | run_item별 결과, execution-log 뷰어, GitLab 파이프라인/MR 링크, 실패 사유, 미매핑 변경(신규 문서 후보) 리포트 |
| 공통 | 실시간 갱신, 사내망 접근 (인증 방식 미확정 → [open-questions](../open-questions.md) #4) |
