# wiki-pipeline 설계 정리

> 작성일: 2026-07-05 · 상태: 설계 논의 결과 정리 (PRD의 입력 자료)

## 1. 프로젝트 개요

사내 GitLab의 여러 과제 레포지토리(X-LAB, ROC, Smart-ROS, SW-RCS 및 향후 신규 과제)의 코드 변경을
**야간 배치**로 감지하여, AI가 공통 문서 레포(**docs-hub**, Docusaurus 기반)의 영향받은 문서만
재생성하고 **MR(Merge Request)로 제출**하는 자동 문서화 파이프라인.

- 문서 반영은 반드시 사람의 MR 리뷰/머지를 거친다 (AI가 직접 main에 쓰지 않음).
- 과제가 늘어나도 관리 지점은 docs-hub + 관리 서버 하나로 수렴한다.

## 2. 설계 진화 과정 (검토한 대안과 결정 이유)

| # | 방식 | 결론 | 이유 |
|---|------|------|------|
| 1안 | **Push 즉시 실행** — 각 과제 레포 CI에 trigger job을 심어 commit마다 docs-hub 파이프라인 실행 | ❌ 기각 | 커밋마다 AI 호출 → 비용·부하·리뷰 폭주. 요청이 큐에 무한정 쌓임 |
| 2안 | **Push 수집 + 야간 배치** — 낮에는 트리거가 큐에 작업 티켓만 적재(문서 단위 upsert 병합), 밤에 스케줄러가 큐를 비우며 AI 실행 | ❌ 대체됨 | 큐 인프라(파일/이슈/Redis)의 push 충돌·유실·완료표시 관리 부담. 소스 레포마다 CI 수정 필요(과제 담당자 협조 필요) |
| 3안 | **Pull 모델 + 야간 배치** — docs-hub가 구독 목록(`last_processed_sha`)을 보유, 밤에 GitLab compare API로 각 레포의 변경분을 직접 조회 | ✅ 채택 | 소스 레포 무수정. 큐 불필요(커밋 히스토리 자체가 큐). compare API가 커밋 N개를 최종 변경 파일 집합 하나로 병합해줌. 멱등성 확보 용이 |
| 추가 | **Control Plane 관리 서버** — 등록/해제 API, 수동 트리거, 모니터링 대시보드 | ✅ 채택 | 등록·스케줄·수동 실행·상태를 한 곳에서 통제. 무거운 AI 작업은 CI 러너(Data Plane)에 격리 |

핵심 원칙: **실시간성은 필요 없다.** 야간 배치이므로 pull 모델의 유일한 단점(비실시간)은 트레이드오프가 아니다.

## 3. 확정된 아키텍처

```
                        ┌───────────────────────────────┐
   사용자 ── 대시보드 ──▶│   관리 서버 (Control Plane)     │
                        │  · 소스 등록/해제 API           │
                        │  · 스케줄러 (야간 cron)          │
                        │  · 수동 트리거                   │
                        │  · 실행 이력 DB (source of truth)│
                        └───────┬───────────────▲────────┘
                 ① 파이프라인 트리거              │ ④ 완료 보고
                   (TARGET_SOURCES 변수)         │    + pipeline webhook
                                ▼               │
                        ┌───────────────────────┴────────┐
                        │   docs-hub CI 러너 (Data Plane)  │
                        │  변경 조회 → 영향 분석 → 재생성   │
                        │  → 제출 (브랜치 + MR/PR 생성)     │
                        └───┬──────────────────┬─────────┘
                ② compare API│                  │ ③ AI API 호출
                             ▼                  ▼
                    GitLab 소스 레포들        AI 모델
                   (X-LAB / ROC /          (제공자 미확정)
                    Smart-ROS / SW-RCS …)
```

- **Control Plane (관리 서버)**: 지휘만 담당. 등록 상태·실행 이력·스케줄 관리. 가볍게 유지.
- **Data Plane (docs-hub CI 러너)**: AI 생성이라는 무거운 작업을 격리 실행. 서버가 AI 부하로 죽지 않음.

### 실행 흐름 (야간 배치 / 수동 트리거 공통)

1. 스케줄러(또는 대시보드 버튼)가 GitLab pipeline trigger API 호출 — `TARGET_SOURCES` 변수로 대상 지정
2. 러너가 서버 API에서 처리 대상 소스 목록 + `last_processed_sha` 수신
3. 소스별로 compare API(`from=last_processed_sha&to=HEAD`)로 변경 파일 집합 조회 — 커밋 수와 무관하게 문서 단위 병합이 API 레벨에서 공짜로 됨
4. 변경 경로 ↔ 문서 매핑(frontmatter)으로 영향받은 문서 산출
5. 문서당 1회 AI 호출로 재생성
6. 하루치를 묶어 MR 생성
7. **MR 생성 성공 후에만** 서버에 완료 보고 → `last_processed_sha` 전진 (실패 시 다음 밤 같은 구간 재처리 = 멱등성)

### 상태 저장: 파일이 아닌 DB

`sources.yml`을 서버가 직접 커밋으로 수정하는 방식은 기각. 이유:
- `last_processed_sha`가 매일 갱신되어 포인터 변경 커밋이 매일 쌓임
- 사용자 등록 시점과 야간 배치의 sha 갱신 시점이 겹치면 push 충돌

→ 구독 목록·SHA·실행 이력은 **서버의 DB가 source of truth**.
`sources.yml`은 필요시 읽기 전용 스냅샷 export(git 이력·리뷰용)로만 사용.

### docs-hub 레포 구조

- **과제별 문서 instance** — docs-xlab / docs-roc / docs-smart-ros / docs-sw-rcs … 과제마다 문서 묶음을 분리하되 사이트는 하나 (Docusaurus multi-instance).
- **파이프라인** — 이 레포 한 곳에서 4단계 실행:
  1. 변경 조회 — SCM 커넥터의 compare로 변경 파일 집합 수신
  2. 영향 분석 — 변경 경로 ↔ 문서 매핑 대조
  3. 재생성 — 문서당 1회 AI 호출 (생성 엔진 headless)
  4. 제출 — 브랜치 + MR/PR 생성

## 4. 핵심 설계 결정 요약

| 결정 | 내용 | 근거 |
|------|------|------|
| 야간 배치 | 평일 퇴근 후(예: 20:00) 1회 실행 | AI 비용·부하·리뷰 폭주 방지. 하루치 변경을 문서 단위로 병합 |
| 병합(디바운스) | compare API가 커밋 N개 → 최종 변경 파일 집합 1개 | 같은 문서에 20커밋이 쌓여도 AI는 1회만 호출 |
| 멱등성 | sha는 MR 성공 후에만 전진 | 배치 실패 시 변경분 유실 없음, 재실행 안전 |
| 과제 온보딩 | 소스 레포 무수정, 서버에 등록 1건 | 신규 과제 추가 비용 최소화 |
| 초기 baseline | 등록 시점 HEAD를 baseline sha로 (또는 전체 스캔으로 초기 문서 생성 후 그 지점) | 첫 배치가 전체 히스토리를 처리하는 사고 방지 |
| force-push 방어 | sha가 현재 브랜치에서 유효한지 검증, 무효 시 "최근 N일" fallback | rebase/force-push로 조상 관계가 깨지는 경우 대비 (main protect 권장) |
| 스케줄러 위치 | GitLab pipeline schedule이 아닌 **서버 내장 cron** | 스케줄·수동 트리거·상태를 대시보드 한 화면에서 통제 |
| MR 리뷰 필수 | AI 결과물은 항상 MR로 제출 | 환각/오류에 대한 사람 게이트 |

## 5. API 표면 (초안)

```
POST   /sources          # 레포 등록 (project_id, doc_dir, baseline sha)
DELETE /sources/{id}     # 해제
POST   /runs             # 수동 트리거 { targets:[roc], full:false }
GET    /runs             # 실행 이력 (대시보드용)
GET    /runs/{id}        # 특정 실행 상태·로그 링크
POST   /runs/{id}/report # CI 러너가 완료 보고 (새 sha, 결과)
POST   /hooks/pipeline   # GitLab pipeline 이벤트 수신 (실시간 모니터링)
```

## 6. 모니터링 데이터 소스 (두 갈래)

1. **러너 완료 보고** (`POST /runs/{id}/report`): 성공/실패, 생성 문서 수, MR 링크, 새 sha
2. **GitLab pipeline webhook** (`POST /hooks/pipeline`): 파이프라인 시작/진행/종료 실시간 이벤트

→ 합쳐서 "지금 어느 과제가 돌고 있고, 어젯밤 뭐가 실패했나"를 대시보드에 실시간으로 표시.

## 7. 미확정 / 확인 필요 사항

1. **러너 → AI API 네트워크 경로**: 폐쇄망/프록시 여부, AI 도메인 화이트리스트 또는 사내 LLM 게이트웨이 존재 여부 → **인프라팀 확인이 선행 과제**
2. **AI 제공자/모델 및 예산**: Anthropic/OpenAI/사내 게이트웨이 중 무엇을, 월 호출량 상한은
3. **서버 배포 위치·인증**: 사내 VM/컨테이너, 사내 SSO 연동 여부
4. **경로 ↔ 문서 매핑 규약**: Docu-Automatic의 frontmatter `source_files`/`theme` 필드로 상당 부분 해결됨 (섹션 8 참조). glob 패턴 지원 여부만 추가 결정
5. **스케줄 정책**: 실행 시각/요일, 과제별 개별 스케줄 필요 여부
6. **MR 정책**: 리뷰어 자동 지정, 소스별 MR vs 하루치 통합 MR

## 8. 기존 자산: Docu-Automatic (Claude 문서 생성 에이전트)

> 레포: https://github.com/jaeCheon8587/Docu-Automatic

이미 구축 완료된 Claude Code 기반 **문서 생성 엔진**. 본 파이프라인 실행 흐름의 4~5단계
(영향 분석 + AI 문서 재생성)를 이 엔진이 담당한다. 산출물 6개(스킬 4 + 에이전트 2) 완료 상태.

### 엔진 구조 (v4, 1단계 오케스트레이션)

```
Main CLI (Level 0): skills/task-pipeline/SKILL.md 실행 — 테마 루프 + 재시도 + 저장
  ├── scout (Level 1):       코드 탐색 + 문서화 필요 판단 + 요구사항서 작성
  ├── docu-writer (Level 1): 요구사항서 기반 .md 작성
  └── critic (Level 1):      frontmatter 유효성 + 테마 적합성 독립 검증
```

- 테마 **순차 순회**, 테마별 4단계 사이클(판단 → 작성 → 검증 → 저장)
- 재시도 최대 2회 Hard Cap, 2회 초과 시 `auto_generated_warning` 태그 후 저장, 3연속 FAIL 시 파이프라인 중단
- **Full Reset**: 매 테마마다 에이전트 신규 생성 (컨텍스트 오염 방지, 비용 1.0x)
- **execution-log.md**: 파일 기반 상태 추적 (오토 컴팩트 대비 상태 복구)
- 1차 스코프 4개 테마: `getting-started/intro`, `getting-started/requirements`, `architecture/overview`, `architecture/component-diagram`
- YAML frontmatter 스키마 (필수 9 + 선택 2): `source_files`, `last_commit`, `theme` 등 → **경로↔문서 매핑의 기반이 이미 존재**
- 콜드 스타트 전략: Day 0 구조 뼈대 → push마다 점진 채움 (신규 소스 등록 시 baseline 생성과 연결)
- 비용 최적화: 판단 단계 Haiku, 코드 요약 캐싱, 불필요 테마 스킵

### 새 설계와의 조정 필요 지점

| 항목 | Docu-Automatic v4 설계 | 새 설계 (본 문서) | 조정 방향 |
|------|----------------------|------------------|----------|
| 트리거 | git push 시 각 제품 레포 CI에서 AI 생성 | 야간 pull 배치 (compare API로 수집) | **새 설계 채택** — 엔진 호출 시점만 바뀌고 엔진 자체는 그대로 재사용 |
| 산출물 저장 | 각 레포 `docs-auto` 브랜치 → 중앙 배치가 pull하여 빌드 | docs-hub에 직접 브랜치 + MR | **결정 필요** (MR 방식 권장: 사람 리뷰 게이트 확보, 기존 미결 사항 "인간 리뷰 프로세스"가 함께 해소됨) |
| 변경 감지 입력 | git diff (직전 커밋) | compare API 누적 구간 diff (`last_processed_sha`~HEAD) | scout 입력 계약에 누적 diff를 전달하도록 확장 |
| 실행 환경 | Claude Code CLI (대화형 전제) | CI 러너에서 headless 실행 (`claude -p`) | **headless 동작 검증 필요** (Phase 1 최우선 검증 항목) |

