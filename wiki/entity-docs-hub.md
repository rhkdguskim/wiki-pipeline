---
type: entity
title: docs-hub (공통 문서 레포)
tags: [docusaurus, repo, data-plane]
status: active
---

# docs-hub — 공통 문서 레포 (Data Plane)

신규 구성 예정. Docusaurus **multi-instance**로 과제별 문서를 분리하되 사이트는 하나.
파이프라인 로직이 이 레포 한 곳에만 존재 → 과제가 늘어도 유지보수 지점은 하나.

```
docs-hub/
├── docs-xlab/ · docs-roc/ · docs-smart-ros/ · docs-sw-rcs/   # 과제별 instance
├── pipeline/
│   ├── fetch_changes.py    # compare API로 변경분 조회
│   ├── analyze_impact.py   # 경로 ↔ frontmatter 매핑 대조
│   ├── run_engine.py       # 생성 엔진 headless 호출 → [[entity-docu-automatic]]
│   └── create_mr.py        # 브랜치 push + MR 생성
├── docusaurus.config.js
└── .gitlab-ci.yml          # $CI_PIPELINE_SOURCE(trigger/schedule) 조건 실행
```

- 산출물은 이 레포에 MR로 제출 → [[decision-mr-review-gate]]
- 기존 문서 사이트(110.110.10.70:8080)와의 관계는 미확정 → [[question-existing-site-relation]]

전체 그림: [[overview]] · 상세: `../docs/architecture.md`
