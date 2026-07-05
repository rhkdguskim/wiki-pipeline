---
type: question
title: 생성 문서 위에 Q&A(RAG)를 얹을까?
tags: [enhancement, rag, utilization, llm-wiki, phase-3]
status: open
---

# ❓ 자동 생성 문서를 "읽는" 것을 넘어 "묻는" 것으로?

파이프라인은 문서를 **생성·제출**까지 다루지만, 생성 이후의 활용은 비어 있다.
개발자가 "이 기능 어떻게 동작해?"를 문서 기반으로 질의응답할 수 있으면 자동 생성 문서의 ROI를 사람이 체감한다.

- 후보 기능: 생성 문서 코퍼스 위 **RAG 기반 Q&A** (사내 개발자 대상)
- 전략적 의미: 자동화의 가치를 경영진에게 증명하는 카드 + [[decision-control-data-plane-split]]의 **LLM Wiki 통합·서비스화** 방향과 정합
- 열린 부분: LLM Wiki와의 경계·통합 방식(그 자체가 [[decision-control-data-plane-split]]의 열린 부분)
- 블로킹 대상: 없음 (Phase 3+, 문서 코퍼스가 쌓인 뒤)

## 방침 (2026-07-05)

**Phase 3+ 도입**. 문서 코퍼스가 쌓이면 자동 생성 문서 위 RAG Q&A를 사내 개발자에게 제공. LLM Wiki 통합([[decision-control-data-plane-split]])과 정합. 경계·통합 방식은 그 때 설계.

전체 그림: [[overview]] · 근거 분석: 브레인스토밍 query 2026-07-05
