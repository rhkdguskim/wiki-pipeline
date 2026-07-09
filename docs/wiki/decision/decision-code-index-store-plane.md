---
type: decision
title: 코드 인덱스 저장소 = 별도 질의 서비스 평면 (관리 서버와 분리)
tags: [code-index, storage, plane, ownership, mcp]
status: superseded
---

> [!superseded] 이 결정은 대체됨 (2026-07-06)
> 코드 인덱스가 중앙 파이프라인 범위에서 제외되어 질의 서비스 평면도 만들지 않는다
> → [[decision-code-index-out-of-pipeline]]

# 결정: 인덱스 저장소는 별도 질의 서비스 평면이 소유한다

코드 인덱스(파생 데이터)를 **별도의 질의 서비스 평면**이 직접 소유·운영한다. 이 평면은 현재
**MCP 서버**([[decision-code-index-mcp-serving]])가 담당하며, 관리 서버(Control Plane)·이력 DB
([[decision-db-source-of-truth]])와 **상태를 분리**한다.

## 근거

- **성격 차이** — 인덱스는 언제든 재구축 가능한 **파생 데이터**라 이력 DB(SoT)와 다르다. SoT 평면에
  섞으면 수명·백업·정합성 정책이 충돌한다 → [[decision-db-source-of-truth]]와 분리가 자연스럽다.
- **상시 서빙** — MCP 서버가 온라인 상시 읽기를 서빙한다([[decision-code-index-mcp-serving]]). 질의 주체가
  인덱스를 직접 소유하면 읽기 경로가 짧고 가용성 제어([[decision-code-index-versioning]]의 직전 버전 서빙)가
  국소적이다.
- **관심사 분리** — Control Plane은 *무엇을 인덱싱할까*(등록·트리거·sha 포인터)만 지휘하고,
  질의 서비스 평면은 *인덱스를 어떻게 저장·서빙할까*를 담당한다. [[decision-control-data-plane-split]]의
  평면 분리 원칙과 일관된다.

## 경계

- **관리 서버가 안 보는 게 아니다** — 등록 메타데이터(어떤 레포·sha·버전이 활성인가)는 Control Plane이
  유지하고, 질의 서비스 평면은 그 메타를 받아 인덱스 산출물(파일)을 소유한다. 메타 vs 파생 데이터의 분리.
- **형상 관리는 그대로** — 질의 서비스 평면 안에서 인덱스의 버전·교체는 [[decision-code-index-versioning]]가 소유한다.
- **저장 엔진은 어댑터 정책 따름** — cg-colby([[decision-code-index-adapter-cg-colby]])를 쓰면 SQLite 파일이
  이 평면의 산출물이 된다. 평면 소유권과 엔진 선택은 직교.

## 기각 대안

- **Data Plane(Windows CI) 산출물** — 러너가 인덱스까지 만들어 저장하면 쓰기는 단순하나, 상시 읽기를
  Data Plane이 아닌 곳에서 서빙하려면 이동·동기화 비용이 생긴다. 쓰기(러너 clone+index)와 읽기(서비스 평면
  소유)를 분리하는 쪽이 가용성에 유리.
- **관리 서버(Control Plane) 통합** — 단일 운영 지점은 편하나, 파생 데이터의 빈번한 갱신이 SoT 평면을
  흔들고 가용성 결합이 생긴다.

[[question-code-index-store]]의 답. 관련: [[decision-code-index-mcp-serving]] · [[decision-control-data-plane-split]]
· 소스: [[2026-07-05-code-index-finalization]]
