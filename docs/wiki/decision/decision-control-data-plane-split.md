---
type: decision
title: Control/Data Plane 분리 (LLM Wiki 통합·서비스화 포석)
tags: [architecture, control-plane, data-plane, llm-wiki, service]
status: active
---

# 결정: 관리 서버(Control Plane)와 docs-hub CI 러너(Data Plane)를 분리한다

지휘(*무엇을·언제*)와 실행(무거운 AI 생성)을 **서로 다른 평면**으로 나눈다. 관리 서버는 등록·스케줄·수동 트리거·이력 DB만 담당하고, 실제 감지 → 생성 → MR/PR 제출은 격리된 docs-hub CI 러너가 수행한다. 구조 그림: [[overview]]

## 근거

- **부하 격리** — AI 생성은 무겁고 가변적이다. 지휘 계층이 그 부하에 흔들리면 안 되므로 러너를 별도 평면으로 둔다. 지휘는 항상 가볍게 응답.
- **독립 확장** — 러너는 과제·테마 수에 따라 수평 확장하고, 관리 서버는 상태·이력의 단일 기준점으로 유지한다 → [[decision-db-source-of-truth]]
- **서비스화 포석 (핵심 동기)** — 추후 **LLM Wiki**(사내 지식 위키 시스템)를 이 관리 계층에 통합해, 문서 자동화를 **서비스 형태**로 제공하려는 방향. 지휘/실행이 분리돼 있어야 관리 서버가 여러 소비자(문서 파이프라인 + LLM Wiki)를 오케스트레이션하는 허브로 성장할 수 있다.

## 기각 대안

- **단일 프로세스(모놀리식)** — 관리 로직과 AI 생성을 한 프로세스에 통합. 배포는 단순하지만 부하 격리·독립 확장이 불가하고, 나중에 서비스화할 때 관리 허브를 분리해내는 비용이 더 크다.

## 변하지 않는 것 (평면 간 계약)

- **① 트리거** (Control → Data) / **④ 완료 보고·webhook** (Data → Control) — 두 평면은 이 계약으로만 대화 → [[overview]]. ④는 완료뿐 아니라 **실시간 진행**도 실어 대시보드로 보낸다 → [[decision-pipeline-observability]]
- 러너는 pull 모델로 소스를 직접 조회한다 (소스 레포 무수정) → [[decision-pull-model]]

## 열린 부분

LLM Wiki와 **어떻게** 통합하고 서비스 경계를 어디에 둘지는 아직 미확정.
→ 활용 후보(생성 문서 위 Q&A/RAG)가 이 서비스 평면 위에 얹힐 수 있다 → [[question-doc-qa-rag]].

관련: [[overview]] · [[decision-db-source-of-truth]] · [[decision-pull-model]] · [[decision-nightly-batch]]
