---
type: concept
title: 포트/어댑터 — 구현 은닉 인터페이스
tags: [architecture, abstraction, port-adapter, replaceability]
status: active
---

# 포트/어댑터 패턴 — 외부 기술을 인터페이스 뒤로 숨긴다

**한 줄 요약: 시스템이 필요로 하는 기능을 우리 언어로 정의한 인터페이스(포트)로 선언하고,
외부 기술은 그 인터페이스를 구현하는 어댑터로만 연결한다 — 기술 교체가 어댑터 교체로 끝난다.**

## 규칙

- 포트는 **소비자의 요구**로 정의한다 — 특정 기술이 제공하는 기능을 나열하는 게 아니라, 시스템에 필요한 연산만 담는다
- 외부 기술의 타입·API·오류·저장 형식이 포트 밖으로 **새어나오면 안 된다** (누수 방지, anti-corruption)
- 상위 로직은 포트에만 의존한다 → 구현 교체 시 상위 로직 무변경, 어댑터만 교체

## 언제 쓰나 / 언제 안 쓰나

- 교체 가능성을 열어두고 싶은 외부 의존(도구·라이브러리·엔진·SaaS)이 시스템 코어 흐름에 들어올 때
- 반대로 교체할 일 없는 안정된 의존이라면 추상화 비용(간접층·인터페이스 유지)만 남는다

## 이 위키에서의 실체화

- [[decision-scm-connector-abstraction]] — SCM 커넥터: GitLab·GitHub를 compare/submit/auth 뒤로
- [[decision-code-index-provider-abstraction]] — 코드 인덱스 프로바이더: codegraph를 index/query/manage 뒤로
- [[question-engine-runtime]] — 생성 엔진 인터페이스: 같은 패턴의 세 번째 후보 (검토 중)

전체 그림: [[overview]]
