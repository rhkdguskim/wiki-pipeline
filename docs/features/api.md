# 관리 서버 REST API (초안)

← [문서 인덱스](../README.md)

Control Plane의 외부 계약. 대시보드·러너·GitLab이 모두 이 API로 서버와 통신한다.

## 엔드포인트

| Method | Path                | 호출자      | 설명                                                                                         |
| ------ | ------------------- | -------- | ------------------------------------------------------------------------------------------ |
| POST   | `/sources`          | 운영자      | 소스 등록 `{project_id, project_path, doc_dir, baseline_sha?}` → [sources](./sources.md)       |
| GET    | `/sources`          | 대시보드     | 소스 목록                                                                                      |
| DELETE | `/sources/{id}`     | 운영자      | 소스 비활성화 (soft delete)                                                                      |
| POST   | `/runs`             | 운영자/스케줄러 | 수동 트리거 `{targets:[...], full:false}` → run 생성 + GitLab 트리거 → [scheduling](./scheduling.md) |
| GET    | `/runs`             | 대시보드     | 실행 이력 (페이징, 필터)                                                                            |
| GET    | `/runs/{id}`        | 대시보드     | run 상세 (run_items 포함)                                                                      |
| GET    | `/runs/{id}/plan`   | 러너       | 이번 run의 처리 대상 소스 + `last_processed_sha` 목록                                                 |
| POST   | `/runs/{id}/report` | 러너       | 완료 보고 (소스별 결과, MR URL, 새 sha) → [monitoring](./monitoring.md)                              |
| POST   | `/hooks/pipeline`   | GitLab   | pipeline 이벤트 webhook 수신                                                                    |

## 인증

- 러너용 엔드포인트(`plan`/`report`): 서비스 토큰
- 운영자/대시보드: 사내망 한정 + 인증 방식 미확정 → [open-questions](../open-questions.md) #4

응답 스키마의 기반 엔티티 → [data-model.md](../data-model.md)
