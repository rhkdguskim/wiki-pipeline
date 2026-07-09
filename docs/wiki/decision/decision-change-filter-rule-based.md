---
type: decision
title: 변경 중요도 필터 = 규칙 기반 먼저 (사소한 변경 재생성 스킵)
tags: [cost, impact-analysis, phase-2, filter]
status: active
---

# 결정: 사소한 변경(주석·포맷팅·공백)은 규칙 기반으로 재생성을 스킵한다

영향 분석이 변경 경로 ↔ frontmatter 매핑으로 영향 문서를 산출하지만, 그 변경이 의미 있는지는
구분하지 않는다 → [[question-change-significance-filter]]. **규칙 기반 필터**를 먼저 두어
사소한 diff의 재생성을 건너뛴다.

## 세 가지

- **규칙 기반 먼저** — 정적 규칙(예: 주석만 변경·공백/포맷팅만 변경·import 정렬만)으로 사소한 변경을 판정해 스킵.
- **LLM 판단은 후순위** — 규칙이 잡지 못하는 애매한 변경은 일단 재생성. 오탐(중요 변경 스킵) 위험이 큰 LLM 판단은 실측 후 필요성 보면 추가.
- **2차 최적화 위치** — compare가 이미 커밋 N개를 파일 집합 1개로 병합([[concept-idempotent-sha]])한 **위에** 얹는 추가 절감.

## 근거

- 규칙 기반은 구현 단순·호출 비용 0. 오탐(사소한데 재생성)은 비용 손실이지만 역오탐(중요한데 스킵)보다 안전.
- LLM 판단은 정확도가 높아도 호출 비용이 발생 — 비용 최적화 목적이 LLM 호출로 비용을 낸다면 본말 전도.
- [[decision-nightly-batch]](병합)·[[decision-pull-model]](호출 최소화)에 이은 다음 비용 절감 계단 → [[question-cost-estimation]].

## 기각 대안

- **처음부터 LLM 판단** — 정확하지만 호출 비용 발생. 비용 실측([[question-cost-estimation]]) 전엔 근거 부족.
- **필터 없이 모두 재생성** — 단순하지만 사소한 변경까지 AI 호출 → 비용 낭비.

## 열린 부분

- 규칙 목록 구체화(언어별 주석/포맷팅 패턴) — 구현 시 확정
- 스킵 통계(얼마나 절감했나)를 배치 리포트에 포함 → [[question-batch-observability]]

이 결정이 [[question-change-significance-filter]]를 답한다.
