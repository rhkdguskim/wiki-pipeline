---
type: meta
title: "Lint Report 2026-07-06"
created: 2026-07-06
updated: 2026-07-06
tags: [meta, lint]
status: developing
---

# Lint Report: 2026-07-06

> 기준: [[schema]]의 Lint 검사 항목. DragonScale(address/tiling)·Dataview·canvas는 이 저장소가 채택하지 않아 검사 대상에서 제외(`.vault-meta/`·`scripts/` 부재).

## Summary
- Pages scanned: 71 (overview 1 · summary 6 · entity 6 · concept 5 · decision 30 · question 23)
- 카탈로그 파일: 6 (index + 5 폴더 인덱스, frontmatter·접두사·고아 검사 제외)
- Issues found: 3 (HIGH 1 · MEDIUM 1 · LOW 1)
- **Auto-fixed: 3 (H1·M1·L1 모두 수정 완료 2026-07-06)**
- Needs review: 0

> **수정 반영(2026-07-06)**: 아래 세 항목을 사용자 승인으로 자동 수정하고 재검증 통과(깨진 링크 0 · H1 고아 해소 · L1 계보 연결). 각 항목 끝에 ✔ 수정 내용 기재.

### 통과한 검사 (이상 없음)
- **깨진 링크**: 0 — 모든 `[[wikilink]]` 대상이 실재 (wiki + raw + schema/index).
- **frontmatter 필수 4필드**(type/title/tags/status): 71/71 페이지 전부 충족.
- **type ↔ 폴더 일치**: 전부 일치. **파일명 접두사 ↔ type**: 전부 일치.
- **폴더 인덱스 등재 정합성**: 모든 지식 페이지가 자기 `<type>-index.md`에 등재됨. stale 인덱스 항목 0.
- **상대경로 마크다운 링크**(`](../…)`·`](./…)`): 0 — 전부 wikilink.
- **count 정합성**: 허브 index.md 표기(71 페이지 · question 16 answered) = 실측(active 48 · answered 16 · open 7 = 71, ✅ 마크 16개) 일치.
- **빈 섹션**: 없음.
- **superseded 결정**: 없음(번복 이력 없음 — 정상).

---

## HIGH

### H1 — answered question이 자기를 답한 decision을 본문에 역링크하지 않음
- [[question-progress-event-contract]] (status: `answered`): 본문이 [[decision-pipeline-observability]]·[[decision-control-data-plane-split]]는 링크하지만, **정작 이 질문을 답한** [[decision-observability-event-contract]]는 링크하지 않는다.
- 근거: `decision-observability-event-contract` 본문 마지막 줄 — "이 결정이 [[question-progress-event-contract]]을 답하고…". 답한 decision은 존재하는데 question 쪽 역링크만 빠짐.
- schema 위반: 콘텐츠 규칙 "question 라이프사이클 — 답이 확정되면 … question 본문에 답 페이지 링크".
- 부수효과: 이 단절 때문에 [[decision-observability-event-contract]]가 **카탈로그(index) 외 인바운드 0**인 약한 고아 상태가 된다. 역링크를 채우면 고아도 함께 해소됨.
- 제안: `question-progress-event-contract` 본문 "✅ 답" 블록에 `→ [[decision-observability-event-contract]]` 추가. (question-index.md에는 이미 이 링크가 있어 색인은 정상.)
- ✔ **수정됨**: `question-progress-event-contract`에 "✅ 답 (2026-07-05)" 블록 신설 + [[decision-observability-event-contract]] 역링크. → 해당 decision 카탈로그 외 인바운드 2개 확보, 고아 해소.

---

## MEDIUM

### M1 — overview 드리프트: 공통 모니터링 서사에 이벤트 계약 결정 누락
- [[overview]] "공통 — 실시간 모니터링" 절이 [[decision-pipeline-observability]]·[[concept-observability-contract]]는 링크하지만, 그 계약의 **구체형 결정**인 [[decision-observability-event-contract]](표준 스키마 + 가변 단위 + webhook)는 언급하지 않는다.
- 성격: schema상 overview는 "서사 중심, 전체 카탈로그는 index 위임"이라 모든 decision 나열 의무는 없다. 그러나 이벤트 계약은 관측성 서사의 핵심 구체라 링크할 값어치가 있다(이것이 H1의 고아를 서사 층위에서도 이어줌).
- 참고: overview 미링크 decision 9건 중 나머지 8건(`nightly-batch`·`pull-model`·`db-source-of-truth`·`change-filter-rule-based`·`scenario-owner-dashboard`·`manual-taxonomy-two-reader`·`manual-delete-grace`·`coverage-metric-gap`)은 세부 결정이라 index 위임이 정당 — 드리프트 아님.
- 제안: overview 모니터링 절 문장 끝에 `… → [[decision-pipeline-observability]] · [[concept-observability-contract]] · 이벤트 구체형 [[decision-observability-event-contract]]` 형태로 한 링크 추가.
- ✔ **수정됨**: overview "공통 — 실시간 모니터링" 절에 "진행 이벤트의 구체형은 … → [[decision-observability-event-contract]]" 문장 추가.

---

## LOW

### L1 — summary 계보 단절 (약한 고아, 설계상 허용 범위)
- [[summary-code-index-finalization]]·[[summary-code-index-followup]]: 자기 [[summary-index]] 외 인바운드가 없다.
- 성격: summary는 ingest 1차 산출물이라 다른 유형이 역참조하지 않는 게 **정상**(schema상 고아 금지 대상이지만 폴더 인덱스 등재로 최소 인바운드 1은 충족). 다만 세 코드인덱스 summary가 시간순 후속([[summary-code-index-pipeline]] → followup → finalization)인데 앞 summary가 뒤를 잇지 않아 계보 추적이 인덱스에만 의존한다.
- 제안(선택): 각 summary "파생 페이지" 아래 `## 후속` 한 줄로 다음 세션 summary를 링크해 읽기 동선을 잇는다. 무결성 오류는 아님 — 개선 제안.
- ✔ **수정됨**: 세 summary를 시간순 계보로 연결 — `summary-code-index-pipeline`에 `## 후속`, `summary-code-index-followup`에 `## 계보`(선행·후속), `summary-code-index-finalization`에 `## 선행 요약` 추가.

---

## 참고: 오탐이 아닌 정상 케이스
- [[question-runner-ai-network]] (answered): 본문에 decision 링크가 없으나, 이 질문의 답은 "네트워크가 뚫려 있다"는 **인프라 사실**이라 [[entity-mirero-gitlab]]로 귀결되는 게 옳다. decision을 만들 사안이 아니므로 H1과 달리 위반 아님.
- open question 7건([[question-doc-qa-rag]]·[[question-review-feedback-loop]] 등): 카탈로그 외 인바운드가 없어도 미해결 브레인스토밍 항목이라 정상. status가 open이면 답 decision 링크 부재가 기대되는 상태.
