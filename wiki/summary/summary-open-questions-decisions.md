---
type: summary
title: 2026-07-07 열린 질문 결정 세션 요약
tags: [mvp, registration, curation, themes]
status: active
---

# 2026-07-07 열린 질문 결정 세션 요약

wiki-query로 open 질문 13건을 추리고(테마 2차 확장·리뷰 피드백 루프·문서 Q&A/RAG·시크릿 보안은 제외),
영향이 크고 지금 답 가능한 4건을 사용자에게 질의해 확정했다. 원본: [[2026-07-07-open-questions-decisions]].

## 확정 4건 → 파생 decision

1. **MVP 절단선 = 정적 + 매뉴얼 둘 다** → [[decision-mvp-scope]]
   위키 후보안(정적만)과 갈라진 지점. 매뉴얼 포함으로 [[question-artifact-type-dispatch]] 등 매뉴얼 open 질문이 MVP 블로커로 승격. SCM 커넥터는 MVP에서 GitLab 1개만, GitHub는 이후.
2. **등록 baseline = A(null → 전체 initialize)** → [[decision-registration-baseline]]
   초기 전량 backfill을 정기 야간 배치와 분리된 1급 작업(대시보드 트리거·진행률)으로, 야간 배치는 증분만.
3. **방치 소스 = 운영자 수동 큐레이션** → [[decision-source-manual-curation]]
   시스템이 방치를 자동 판정·배제하지 않음. 방치/활성 자동 판정 기준이 소거됨. compare 404 자동 비활성화는 등록 후 소실 처리라 별개로 유지.
4. **테마 경계 = 통합 없이 독자 축으로 명시** → [[decision-requirements-devguide-boundary]]
   requirements=설치자·운영자, dev-guide=개발자. 겹치는 사실은 한쪽 상세+다른쪽 참조. 경계 문장 위치는 구현 세부로 열어둠.

## answered 전환된 question

- [[question-mvp-scope]] · [[question-initial-backfill-baseline]] · [[question-ci-less-source-policy]] · [[question-requirements-devguide-boundary]] — 모두 위 decision으로 answered.
