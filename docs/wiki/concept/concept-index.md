# concept 인덱스

> concept 페이지 카탈로그. 허브: [[index]] · 규약: [[schema]]

- [[concept-idempotent-sha]] — sha 포인터 멱등성: 유실 방지·재실행 안전·디바운스
- [[concept-observation-grounding]] — 관측 기반 문서 근거: 실행 관측을 문서 근거로
- [[concept-manual-lifecycle-diff]] — 문서 라이프사이클 diff: add/update/delete, 안전한 삭제
- [[concept-port-adapter]] — 포트/어댑터: 구현 은닉 인터페이스, 기술 교체 = 어댑터 교체
- [[concept-observability-contract]] — 파이프라인 관측성 계약: 이기종 워커 공통 진행 보고·중앙 집계
- [[concept-medallion-dwh-on-postgres]] — Medallion DWH on PostgreSQL: Bronze/Silver/Gold layering을 PG 스키마로 실체화 (layering discipline, substrate 무관)
- [[concept-monday-column-value-modeling]] — Monday column value 정규화: 타입별 상이한 JSON의 typed long table + JSONB 폴백 하이브리드
- [[concept-readonly-saas-cdc]] — Read-only SaaS CDC: webhook(근사) + 야간 전수 폴링(보정) 하이브리드 (SaaS webhook 유실 한계 대응)
