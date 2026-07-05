---
type: question
title: 서버 배포 위치·API 인증 방식?
tags: [phase-2, deploy, auth]
status: open
---

# ❓ 관리 서버는 어디에 배포하고 API 인증은 무엇으로 하는가?

사내 VM인가 컨테이너인가? 대시보드·API 접근 인증은 사내 SSO 연동인가 자체 토큰인가?
러너용 엔드포인트(plan/report)는 서비스 토큰으로 가닥은 잡혀 있다.

- 블로킹 대상: Phase 2
- 관련: [[entity-mirero-gitlab]] · 상세: `../../docs/features/api.md`
