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

- **레포별 폴더 + 역할 하위폴더** — 등록 레포마다 docs-hub 안에서 한 폴더로 모으고, 그 아래를
  개발/배포 역할 하위폴더(`dev/`·`release/`)로 가른다. 경로는 `full_namespace_path/{dev|release}/`
  규칙으로 자동 생성된다(사람 입력 없음) → [[decision-docs-hub-folder-rule]] · [[decision-repo-dev-release-registration]].
  과제(X-LAB/ROC/Smart-ROS/SW-RCS…) 단위는 이 폴더들을 묶는 Docusaurus multi-instance로 표현되, 사이트는 하나다.
- **파이프라인 (4단계)** — 이 레포 한 곳에서 실행:
  1. **변경 조회** — SCM 커넥터의 compare로 변경 파일 집합 수신 → [[decision-scm-connector-abstraction]]
  2. **영향 분석** — 변경 경로 ↔ frontmatter 매핑 대조로 영향받은 문서 산출
  3. **재생성** — 생성 엔진 호출(API 에이전트 루프 → [[decision-engine-api-agent]]) → [[entity-docu-automatic]]
  4. **제출** — 브랜치 + MR/PR 생성 → [[decision-mr-review-gate]]

전체 그림: [[overview]]
