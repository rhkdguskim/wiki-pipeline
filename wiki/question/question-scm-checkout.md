---
type: question
title: SCM 커넥터에 소스 checkout 책임 추가?
tags: [scm, connector, checkout, code-index, phase-2]
status: answered
---

# ❓ 인덱싱용 소스 전체 확보 — SCM 커넥터의 4번째 책임인가

[[decision-scm-connector-abstraction]]의 커넥터는 compare/submit/auth 3책임 — **변경 파일 목록**까지만 준다.
그러나 코드 인덱싱은 **소스 전체**(작업 트리)가 필요하다 → [[decision-code-index-pipeline]].

- 커넥터에 `checkout`(레포@sha 소스 확보)을 4번째 책임으로 추가할까, 러너의 git clone으로 충분한가?
- git 프로토콜 자체는 SCM 중립이라 커넥터 추상화가 불필요하다는 반론 가능 — 단 인증(토큰)은 커넥터 소관
- 증분 인덱싱을 택하면 fetch/diff 전략도 함께 정해진다

## 답 — 러너가 직접 git clone (커넥터 4책임 확장 기각)

→ [[decision-runner-git-clone]]. git 프로토콜은 SCM 중립이라 숨길 차이가 없고, 커넥터는 3책임(compare/submit/auth)을
유지하되 **인증 토큰만 auth에서 얻는다**. 커넥터 인터페이스 비대화 방지.

> (2026-07-06) 답이던 [[decision-runner-git-clone]]은 코드 인덱스의 파이프라인 범위 제외로 superseded
> → [[decision-code-index-out-of-pipeline]] (인덱싱용 소스 확보 자체가 불필요). 커넥터 3책임 유지
> 원칙과 실측 사실(Windows 러너·LFS)은 유효하다.

소스: [[2026-07-05-code-index-pipeline]] · [[2026-07-05-code-index-followup]]
