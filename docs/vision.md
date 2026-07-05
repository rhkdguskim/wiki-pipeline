# 배경 · 문제 정의 · 비전

← [문서 인덱스](./README.md)

## 비전 (한 줄)

**코드가 바뀌면 문서가 따라온다 — 사람의 작성 노동 없이, 사람의 리뷰만 거쳐서.**

## 배경

- 팀 내 여러 과제(X-LAB, ROC, Smart-ROS, SW-RCS 및 향후 신규 과제)가 개별 GitLab 레포로 관리된다 (C++, C#, JavaScript, Python).
- 경영진 방침: **문서 작성에 인적 리소스를 투입하지 말 것.**
- 기존 코드베이스는 Doxygen 주석이 거의 없어, 파싱이 아닌 **AI의 코드 직접 분석**으로 문서를 생성해야 한다.
- 문서 생성 엔진(**Docu-Automatic**)은 이미 구축 완료 → [features/generation.md](./features/generation.md)
- 본 시스템은 그 엔진을 사내 GitLab 인프라 위에서 **자동으로, 지속적으로, 관리 가능하게 운영**하는 계층이다. (Docu-Automatic PRD가 "범위 외"로 남긴 CI/CD·인프라·중앙 처리 영역)

## 문제 정의

| # | 문제 | 설명 |
|---|------|------|
| P1 | **문서 부패** | 코드가 바뀌어도 문서는 갱신되지 않는다. 갱신을 사람에게 의존할 수 없다 |
| P2 | **비용·부하** | 커밋마다 AI를 실행하면 호출 비용, 러너 부하, 문서 MR 리뷰 폭주가 발생한다 → [scheduling](./features/scheduling.md) |
| P3 | **관리 분산** | 과제마다 파이프라인을 두면 과제 수만큼 유지보수 지점이 늘어난다 → [architecture](./architecture.md) |
| P4 | **관측 불가** | 자동화가 지금 무엇을 하고 있는지, 어젯밤 무엇이 실패했는지 볼 방법이 없다 → [monitoring](./features/monitoring.md) |

## 해결 방향 (요약)

야간 pull 배치(P1·P2) + 관리 지점의 docs-hub/관리 서버 수렴(P3) + 대시보드·이력(P4).
상세 설계 → [architecture.md](./architecture.md), 결정 과정 → [설계 논의 기록](../raw/2026-07-05-design-session.md)
