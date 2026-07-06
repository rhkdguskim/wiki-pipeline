---
type: question
title: 기존 CI docs stage와 우리 자동화의 공존/대체
tags: [ci, docs, coexistence, docs-hub]
status: open
---

# ❓ 기존 CI `docs` stage와 우리 문서 자동화는 공존인가 대체인가

실측([[2026-07-06-wish-gitlab-api-survey]])에서 **ros-sw-rcs**의 CI stages가
`build → test → registry → merge → bundle → deploy → **docs**`로, 이미 **docs stage가 존재**한다.
우리 파이프라인이 문서를 생성해 docs-hub에 MR을 낸다면 기존 docs stage와 역할이 겹친다.

## 검토할 것

- 기존 docs stage가 **무엇을 산출**하나 — API 레퍼런스(Doxygen류)인가, 배포 문서인가, 사내 위키 push인가.
  (실측은 stage 존재만 확인, 내용은 미확인.)
- 우리 산출물([[entity-docs-hub]] 대상 기술문서/매뉴얼)과 **중복·보완·대체** 중 무엇인가.
- 대체라면 소스 CI 수정이 필요 → [[decision-pull-model]]의 "소스 레포 무수정" 원칙과 충돌 가능.
  보완이라면 산출물 경계(누가 무엇을 만드는지)를 문서화해야.
- 소스별로 기존 docs stage 유무가 다름 → 소스별 정책이 필요할 수 있음.

관련: [[entity-mirero-gitlab]] · [[entity-docs-hub]] · [[decision-mr-review-gate]]
