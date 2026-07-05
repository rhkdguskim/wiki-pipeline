---
type: entity
title: docs-hub (공통 문서 레포)
tags: [docusaurus, repo, data-plane]
status: active
---

# docs-hub — 공통 문서 레포 (Data Plane)

신규 구성 예정. Docusaurus **multi-instance**로 과제별 문서를 분리하되 사이트는 하나.
파이프라인 로직이 이 레포 한 곳에만 존재 → 과제가 늘어도 유지보수 지점은 하나.

## 구성

- **과제별 문서 instance** — 과제(X-LAB/ROC/Smart-ROS/SW-RCS…)마다 문서 묶음을 분리하되 사이트는 하나 (Docusaurus multi-instance).
- **파이프라인 (4단계)** — 이 레포 한 곳에서 실행:
  1. **변경 조회** — SCM 커넥터의 compare로 변경 파일 집합 수신 → [[decision-scm-connector-abstraction]]
  2. **영향 분석** — 변경 경로 ↔ frontmatter 매핑 대조로 영향받은 문서 산출
  3. **재생성** — 생성 엔진 headless 호출 → [[entity-docu-automatic]]
  4. **제출** — 브랜치 + MR/PR 생성 → [[decision-mr-review-gate]]

전체 그림: [[overview]]
