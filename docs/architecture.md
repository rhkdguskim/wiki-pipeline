# 아키텍처

← [문서 인덱스](./README.md)

## 용어

| 용어 | 정의 |
|------|------|
| docs-hub | 공통 문서 레포. Docusaurus multi-instance + pipeline 스크립트 보유 |
| 소스(source) | 문서화 대상으로 등록된 과제 레포 |
| Control Plane | 관리 서버. 등록/스케줄/수동 트리거/이력/대시보드 담당 |
| Data Plane | docs-hub CI 러너. 변경 감지~MR 생성의 무거운 작업 실행 |
| 생성 엔진 | Docu-Automatic의 task-pipeline + scout/docu-writer/critic |
| run | 파이프라인 1회 실행 단위 (스케줄 또는 수동) |
| last_processed_sha | 소스별 "어디까지 문서에 반영했는지" 포인터 |
| 테마 | 페이지 단위 문서 정의 (1 테마 = 1 md). 1차 스코프 4개 |

## 시스템 구성

```
                        ┌───────────────────────────────┐
   사용자 ── 대시보드 ──▶│   관리 서버 (Control Plane)     │  ← 신규 개발
                        │  등록/해제 API · 스케줄러        │
                        │  수동 트리거 · 실행 이력 DB      │
                        └───────┬───────────────▲────────┘
                 ① 파이프라인 트리거              │ ④ 완료 보고 + pipeline webhook
                                ▼               │
                        ┌───────────────────────┴────────┐
                        │  docs-hub CI 러너 (Data Plane)  │  ← 신규 구성
                        │  변경 감지 → 생성 엔진 호출 →     │
                        │  MR 생성                        │
                        └───┬──────────┬─────────────────┘
                ② compare API│          │ ③ 생성 엔진 (headless Claude Code)
                             ▼          ▼
                    GitLab 소스 레포들   Docu-Automatic     ← 기존 자산 재사용
                    (X-LAB/ROC/…)      (scout→writer→critic)
```

| # | 컴포넌트 | 상태 | 책임 |
|---|----------|------|------|
| 1 | 관리 서버 | 신규 개발 | 소스 등록/해제, 야간 스케줄, 수동 트리거, 실행 이력([DB가 source of truth](./data-model.md)), 대시보드, webhook 수신 |
| 2 | docs-hub 레포 + CI | 신규 구성 | [변경 감지](./features/change-detection.md), [생성 엔진 호출](./features/generation.md), [MR 생성](./features/mr.md), Docusaurus 빌드/배포 |
| 3 | 생성 엔진 (Docu-Automatic) | 기존 자산 | 테마 순회, 판단(scout)→작성(docu-writer)→검증(critic), execution-log |
| 4 | Docusaurus 사이트 | 기존/확장 | multi-instance로 과제별 문서 분리, 사이트는 하나 |

## 실행 흐름 (야간 배치 / 수동 트리거 공통)

1. 스케줄러(또는 대시보드 버튼)가 GitLab pipeline trigger API 호출 — `TARGET_SOURCES` 변수로 대상 지정
2. 러너가 서버 API(`GET /runs/{id}/plan`)에서 처리 대상 소스 + `last_processed_sha` 수신
3. 소스별 compare API로 변경 파일 집합 조회 → [change-detection](./features/change-detection.md)
4. 변경 경로 ↔ 문서 frontmatter 매핑으로 영향 테마 산출
5. 테마당 1회 생성 엔진 호출 → [generation](./features/generation.md)
6. docs-hub에 브랜치 push + MR 생성 → [mr](./features/mr.md)
7. **MR 성공 후에만** 서버에 완료 보고 → `last_processed_sha` 전진 (멱등성)

## 핵심 구조 결정과 근거

### Control Plane / Data Plane 분리
서버는 "지휘"만 하고(등록 상태·실행 이력·스케줄), AI 생성이라는 무거운 작업은 격리된 CI 러너가 담당한다.
서버는 가볍게 유지되고, AI 부하로 서버가 죽는 일이 없다.

### pull 모델 (push 기각)
- 소스 레포 무수정 — 과제 담당자 협조 불필요, 온보딩 = 등록 1건
- 큐 인프라 불필요 — 커밋 히스토리 자체가 큐 역할
- compare API가 커밋 N개를 최종 변경 파일 집합 1개로 병합 (디바운스 공짜)
- 야간 배치이므로 실시간성 포기는 트레이드오프가 아님

검토했던 대안(push 즉시 실행, push+큐)과 기각 이유 → [설계 논의 기록](../raw/2026-07-05-design-session.md)

### DB가 source of truth (sources.yml 커밋 기각)
`last_processed_sha`가 매일 갱신되어 포인터 커밋이 매일 쌓이고, 사용자 등록 시점과 야간 배치의 갱신 시점이 겹치면
push 충돌이 난다. 구독 목록·SHA·이력은 서버 DB로 → [data-model.md](./data-model.md)

## docs-hub 레포 구조

```
docs-hub/
├── docs-xlab/            # Docusaurus multi-instance: 과제별 분리, 사이트는 하나
├── docs-roc/
├── docs-smart-ros/
├── docs-sw-rcs/
├── pipeline/
│   ├── fetch_changes.py   # compare API로 변경분 조회
│   ├── analyze_impact.py  # 경로 ↔ 문서 매핑 대조
│   ├── run_engine.py      # 생성 엔진 headless 호출
│   └── create_mr.py       # 브랜치 push + MR 생성
├── docusaurus.config.js
└── .gitlab-ci.yml
```
