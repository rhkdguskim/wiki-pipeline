---
type: decision
title: 스케줄 = 소스별 다중 스케줄, 파이프라인 선택, 대시보드 설정
tags: [schedule, phase-2, dashboard, pipeline]
status: active
---

# 결정: 스케줄은 소스별로 여러 개 등록하고, 각 스케줄이 실행할 파이프라인을 선택한다

평일 20:00 1회라는 단일 고정 스케줄([[decision-nightly-batch]]의 기본안)을 넘어,
**소스마다 여러 자동 실행 스케줄**을 대시보드에서 설정·변경할 수 있게 한다. 스케줄은 단순히 "몇 시"만
갖지 않고, 실행할 `pipeline_id`, `mode`, `branch_role`, 요일/시간, 활성 여부를 함께 가진다.

## 세 가지

- **소스별 다중 스케줄** — 한 저장소에 여러 스케줄을 둘 수 있다. 예: dev 브랜치 정적 문서 자동화는 평일 20:00, release 브랜치 점검은 토요일 06:45.
- **스케줄이 파이프라인을 선택** — 스케줄 row는 `pipeline_id`, `mode(auto|init|diff)`, `branch_role(dev|release)`를 가진다. 현재 Control Plane runner가 실제 실행 가능한 값은 `pipeline_id=static`이며, 매뉴얼 파이프라인이 Control Plane trigger에 연결되면 같은 구조에 `manual` 스케줄을 추가한다.
- **대시보드 설정** — 스케줄 편집 UI를 대시보드에 둔다. 과제 담당자/운영자가 코드 아닌 설정으로 바꾼다. UI는 raw cron 대신 요일/시간 토글을 기본으로 보여주고, 서버는 이를 cron으로 정규화한다.
- **기본값 유지** — 새 소스 등록 시 기본 스케줄은 평일 20:00 KST, `static/auto/dev`다. 기존 단일 `source.schedule_cron`은 레거시 호환값으로 남기되, 신규 실행 기준은 `source_schedules`다.
- **run당 상한** — 처리 시간·AI 호출 상한값도 과제/스케줄별 설정 후보. 초과 시 중단 알림 → [[question-batch-observability]].

## 근거

- 과제마다 릴리스 주기·팀 리듬이 다르다 — 단일 시각 강제는 운영 마찰. 소스별 다중 스케줄이 실 운영에 가깝다.
- 같은 저장소라도 dev 문서와 release 문서는 실행 대상 브랜치·모드가 다르다. 스케줄이 파이프라인/브랜치 역할을 품어야 잘못된 파이프라인 실행을 막을 수 있다.
- 대시보드 설정은 코드 배포 없이 스케줄 변경을 허용 → 운영 자율성↑, 엔지니어 개입↓.
- 평일 20:00 기본값을 유지해 [[decision-nightly-batch]]의 병합 효과(낮은 트래픽·하루치 누적)를 기본으로 누린다.

## 기각 대안

- **단일 고정 스케줄(평일 20:00 전 과제 동일)** — 단순하지만 과제별 리듬 차이를 무시. 운영 마찰.
- **소스당 단일 cron만 저장** — 어떤 파이프라인/브랜치 역할을 돌릴지 표현하지 못하고, 같은 저장소에 dev·release 등 복수 자동화를 둘 수 없다.
- **코드로 스케줄 관리(sources.yml 등)** — 변경마다 배포가 필요. 대시보드 설정이 운영 민첩성에서 우위.

이 결정이 [[question-schedule-policy]]를 답한다. 야간 배치라는 **기본 골격**은 [[decision-nightly-batch]]가 그대로 제공한다.
