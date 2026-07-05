# 비기능 요구사항 · 실패 시나리오

← [문서 인덱스](./README.md)

## NFR

| 분류 | 요구사항 |
|------|----------|
| 보안 | 소스 레포 read + docs-hub write 권한의 group access token 사용(최소 권한). 토큰·AI API 키는 CI masked variable로만 주입, 서버 DB에 저장 금지. 서버 API는 사내망 한정 + 인증([open-questions](./open-questions.md) #4) |
| 신뢰성 | 배치 실패 시 변경분 유실 0 ([mr.md 멱등성 규칙](./features/mr.md)). 러너 job 자동 재시도 1회. 서버 장애가 진행 중인 러너 작업을 중단시키지 않으며, 복구 후 이력 재동기화 가능 |
| 성능·비용 | 문서당 AI 생성 1회/run ([G2](./goals.md)). scout 판단 단계는 경량 모델(Haiku) 옵션. run당 처리 시간·AI 호출 횟수 상한 설정 가능(폭주 방지) |
| 운영 | run 이력 보존 180일(설정 가능). 구조화된 로그. 스케줄·상한 등 정책은 코드 수정 없이 설정 변경 |
| 확장성 | 소스 20개까지 야간 1회 배치로 처리 가능해야 함 (순차 실행 기준 소요 시간은 Phase 1에서 실측 → [roadmap](./roadmap.md)) |

## 실패 시나리오 및 처리

| 시나리오 | 처리 |
|----------|------|
| AI API 타임아웃/오류 | 엔진 재시도 정책(2회) → 초과 시 해당 테마 warning 저장. run_item은 partial로 기록 |
| 러너 다운/배치 중단 | sha 미전진 → 다음 run이 같은 구간 재처리 (유실 없음) → [mr](./features/mr.md) |
| MR 생성 실패 | sha 미전진 + run_item failed 기록 + 알림(P2) |
| sha 무효 (force-push/rebase) | "최근 N일" fallback + 경고 → [change-detection](./features/change-detection.md). 예방: 소스 레포 main protect 권장 |
| critic 2회 초과 fail | `auto_generated_warning` 태그로 저장하고 MR 본문에 경고 목록 명시 → 리뷰어가 판단 |
| 서버 다운 중 완료 보고 실패 | 러너가 보고 재시도. 최종 실패 시 execution-log 아티팩트 기반 수동 재동기화 절차 제공 |
| 어떤 문서에도 매핑 안 되는 변경 | 버리지 않고 "신규 문서 후보" 리포트로 노출 (침묵 누락 금지) |
