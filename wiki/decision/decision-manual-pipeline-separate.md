---
type: decision
title: 매뉴얼 추출을 Docu-Automatic과 별개 파이프라인으로
tags: [manual, pipeline, architecture]
status: active
---

# 결정: 매뉴얼 추출은 신규 별개 파이프라인이다

사용자/엔지니어 매뉴얼 생성을 기존 [[entity-docu-automatic]] 엔진의 확장이 아니라
**별도 파이프라인**([[entity-manual-pipeline]])으로 둔다. 두 파이프라인은 관리 서버·[[entity-docs-hub]]·[[decision-mr-review-gate]]만 공유한다.

## 근거

- **근거 소스가 다르다** — Docu-Automatic은 코드 diff를 읽어 기술문서를 만들고, 매뉴얼 파이프라인은 실행 앱을 관측해 사용법을 만든다 → [[concept-observation-grounding]]. 입력·산출·독자가 전부 다르다.
- **구동 방식이 다르다** — 하나는 headless AI 호출, 하나는 MCP로 실제 앱을 띄워 UI를 순회 → [[entity-remote-control-mcp]].
- 억지로 한 엔진에 합치면 두 관심사가 서로를 오염시킨다.

## 기각 대안

- **Docu-Automatic 엔진 확장** (scout 입력을 diff→관측으로 교체) — 초기엔 재사용처럼 보이나, 트리거·구동·라이프사이클이 달라 결국 분기 투성이가 된다. 사용자가 "다른 기능"으로 명시.

관련: [[decision-control-data-plane-split]] · 원본: [[2026-07-05-manual-extraction-pipeline]]
