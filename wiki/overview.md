---
type: overview
title: wiki-pipeline 전체 그림
tags: [hub, architecture]
status: active
---
# wiki-pipeline 전체 그림

사내 GitLab 과제 레포들(X-LAB/ROC/Smart-ROS/SW-RCS)의 변경을 **야간 배치**로 감지해,
AI 생성 엔진이 공통 문서 레포(docs-hub)의 영향받은 문서만 재생성하고 **MR로 제출**하는 시스템.

## 구조 (Control/Data Plane)

```
                     ┌─────────────────────────────┐
  사용자 ─ 대시보드 ─▶│  관리 서버 (Control Plane)    │ 등록·스케줄·수동 트리거·이력 DB
                     └──────┬──────────────▲───────┘
              ① 트리거        ▼              │ ④ 완료 보고 + webhook
                     ┌───────────────────────────────┐
                     │  docs-hub CI 러너 (Data Plane)  │ 감지 → 생성 → MR
                     └───┬──────────┬────────────────┘
           ② compare API │          │ ③ 생성 엔진 headless
                         ▼          ▼
                 GitLab 소스 레포들   Docu-Automatic
```

분리 이유: 서버는 지휘만(가볍게), AI 생성이라는 무거운 작업은 격리된 러너가 담당.

## 실행 흐름

트리거(스케줄/수동) → 러너가 처리 대상 수신 → 소스별 compare API로 변경 파일 집합 →
frontmatter 매핑으로 영향 테마 산출 → 테마당 1회 엔진 호출 → MR 생성 → **성공 후에만** sha 전진.

## 페이지 안내

- **구성 요소**: [[entity-docs-hub]] · [[entity-docu-automatic]] · [[entity-mirero-gitlab]]
- **핵심 결정**: [[decision-pull-model]] · [[decision-nightly-batch]] · [[decision-db-source-of-truth]] · [[decision-mr-review-gate]]
- **핵심 패턴**: [[concept-idempotent-sha]]
- **소스 요약**: [[summary-design-session]] · [[summary-docu-automatic]]
- **미해결 질문** (블로킹 ⛔): [[question-runner-ai-network]] · [[question-headless-claude-auth]] · [[question-mr-vs-docs-auto]]
- **미해결 질문** (그 외): [[question-server-stack-db]] · [[question-server-deploy-auth]] · [[question-schedule-policy]] · [[question-existing-site-relation]] · [[question-theme-expansion]] · [[question-cost-estimation]]
