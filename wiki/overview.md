---
type: overview
title: wiki-pipeline 전체 그림
tags: [hub, architecture]
status: active
---
# wiki-pipeline 전체 그림

사내 GitLab 과제 레포들(X-LAB/ROC/Smart-ROS/SW-RCS)의 변경을 **야간 배치**로 감지해,
AI 생성 엔진이 공통 문서 레포(docs-hub)의 영향받은 문서만 재생성하고 **MR/PR로 제출**하는 시스템.
형상관리 연동은 **SCM 커넥터**로 추상화되어 GitLab·GitHub 둘 다(동등한 1급 대상) 붙는다 → [[decision-scm-connector-abstraction]].

## 구조 (Control/Data Plane)

```mermaid
flowchart TB
    User(["👤 사용자"])

    subgraph CP["🎛️ Control Plane · 관리 서버"]
        direction LR
        Dash["대시보드 · API<br/>등록 · 스케줄 · 수동 트리거"]
        DB[("이력 DB<br/>source of truth")]
        Dash <--> DB
    end

    subgraph DP["⚙️ Data Plane · docs-hub CI 러너"]
        Runner["감지 → 생성 → MR/PR 제출"]
    end

    Engine["🤖 Docu-Automatic<br/>생성 엔진 · headless"]
    Src[("소스 레포<br/>GitLab · GitHub")]
    Hub[("docs-hub<br/>공통 문서 레포")]

    User -->|조작| Dash
    Dash ==>|"① 트리거 · 스케줄/수동"| Runner
    Runner -->|"② compare API"| Src
    Runner -->|"③ 엔진 headless 호출"| Engine
    Runner -->|"MR/PR 제출"| Hub
    Runner -. "④ 완료 보고 · webhook" .-> DB

    classDef control fill:#e3f2fd,stroke:#1565c0,stroke-width:1px,color:#0d47a1;
    classDef data fill:#ede7f6,stroke:#6a1b9a,stroke-width:1px,color:#4a148c;
    classDef ext fill:#fff3e0,stroke:#e65100,stroke-width:1px,color:#bf360c;
    class Dash,DB control
    class Runner data
    class Engine,Src,Hub ext
```

**Control Plane**(관리 서버)은 *무엇을 언제* 처리할지 지휘만 하고(가볍게), **Data Plane**(docs-hub CI 러너)은 AI 생성이라는 무거운 작업을 격리해 수행한다 → [[decision-control-data-plane-split]]. 이 분리는 추후 **LLM Wiki 통합·서비스화**를 위한 포석이기도 하다. 굵은 화살표(①)가 평면 간 트리거, 점선(④)이 완료 보고다.

## 실행 흐름

트리거(스케줄/수동) → 러너가 처리 대상 수신 → 소스별 compare API로 변경 파일 집합 →
frontmatter 매핑으로 영향 테마 산출 → 테마당 1회 엔진 호출 → MR 생성 → **성공 후에만** sha 전진.

## 더 보기

전체 페이지는 허브 인덱스에서 유형별로 드릴다운한다 → [[index]]. 최우선 확인 대상은 **Phase 1 블로킹 질문 3건**(⛔): [[question-runner-ai-network]] · [[question-headless-claude-auth]] · [[question-mr-vs-docs-auto]].
